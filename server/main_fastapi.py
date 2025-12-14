"""
FastAPI Backend cho SmartParking với ESP32-CAM
Thay thế Node.js signaling.js
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import aiohttp
import asyncio
import cv2
import os
from pathlib import Path
from contextlib import asynccontextmanager

# Import services
from services.ai_service import AIService
from services.firebase_service import FirebaseService
from services.video_buffer import VideoBufferManager
from services.tracking_manager import TrackingManager
from services.plate_track_assigner import PlateTrackAssigner

# Global instances
ai_service = None
firebase_service = None
video_buffer_manager = VideoBufferManager()
tracking_manager = None  # Will be initialized after YOLO model loads
plate_assigner = None  # Plate-to-track assignment service

# ========== CONFIGURATION ==========
ESP32_STREAM_URL = "http://192.168.33.122:81/stream"  # ESP32-CAM IP
MOCK_STREAM_URL = "http://localhost:8081/stream"      # FFmpeg mock stream
TEST_VIDEO_PATH = Path(__file__).parent / "test_video.mp4"  # Video file for testing

# Stream mode: "esp32" or "video_file" or "mock"
STREAM_MODE = os.getenv("STREAM_MODE", "esp32")  # Default: ESP32

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager - load models khi start server"""
    global ai_service, firebase_service, tracking_manager, plate_assigner
    
    print("🚀 Starting FastAPI SmartParking Server...")
    
    # Load AI models 1 LẦN duy nhất
    print("📦 Loading AI models...")
    ai_service = AIService()
    await ai_service.load_models()
    print("✅ AI models loaded successfully")
    
    # Initialize Firebase
    print("🔥 Initializing Firebase Admin SDK...")
    firebase_service = FirebaseService()
    print("✅ Firebase initialized")
    
    # Initialize Plate Assignment Service
    print("🏷️  Initializing Plate Track Assigner...")
    plate_assigner = PlateTrackAssigner()
    print("✅ Plate Track Assigner initialized")
    
    # Initialize Tracking Manager với YOLO model và PlateAssigner
    print("🎯 Initializing Tracking Manager...")
    tracking_manager = TrackingManager(
        yolo_model=ai_service.yolo_model,
        plate_assigner=plate_assigner
    )
    print("✅ Tracking Manager initialized")
    
    yield  # Server chạy ở đây
    
    # Cleanup khi shutdown
    print("🛑 Shutting down server...")
    if tracking_manager:
        tracking_manager.cleanup()
    if plate_assigner:
        plate_assigner.clear_all()
    if ai_service:
        ai_service.cleanup()

app = FastAPI(
    title="SmartParking API",
    description="FastAPI backend với ESP32-CAM streaming & AI detection",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Frontend React
        "http://192.168.1.*",     # LAN devices
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== HEALTH CHECK ==========
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "fastapi+esp32+ai+firebase",
        "models_loaded": ai_service is not None,
        "firebase_connected": firebase_service is not None,
    }

# ========== STREAM PROXY (ESP32 / VIDEO FILE / MOCK) ==========
@app.get("/stream")
async def stream_video(
    mode: str = Query(default=None, description="Stream mode: esp32, video_file, mock"),
    file: str = Query(default=None, description="Video filename (for mode=video_file)"),
    tracking: bool = Query(default=False, description="Enable real-time tracking (only for video_file mode)"),
    camera_id: str = Query(default=None, description="Camera ID for tracking"),
    owner_id: str = Query(default=None, description="Owner ID for loading barrier zones")
):
    """
    Stream video từ nhiều nguồn:
    - ESP32-CAM (default)
    - Video file (for testing) - supports multiple files from stream/ folder
    - Mock FFmpeg stream (for testing)
    
    NEW: Real-time tracking support for video files
    
    Usage:
    - <img src="http://localhost:8000/stream" />  (ESP32)
    - <img src="http://localhost:8000/stream?mode=video_file&file=parking_a.mp4" />  (Video file)
    - <img src="http://localhost:8000/stream?mode=video_file&file=parking_a.mp4&tracking=true&camera_id=cam1" />  (With tracking)
    - <img src="http://localhost:8000/stream?mode=mock" />  (FFmpeg mock)
    """
    # Determine stream mode
    stream_mode = mode or STREAM_MODE
    
    # NEW: Check if tracking is enabled (only for video_file mode)
    if stream_mode == "video_file" and tracking:
        if not camera_id:
            raise HTTPException(status_code=400, detail="camera_id is required when tracking=true")
        return await stream_with_tracking(video_filename=file, camera_id=camera_id, owner_id=owner_id)
    elif stream_mode == "video_file":
        return await stream_from_video_file(video_filename=file)
    elif stream_mode == "mock":
        return await stream_from_mock()
    else:  # Default: esp32
        return await stream_from_esp32()

async def stream_from_esp32():
    """
    Proxy MJPEG stream từ ESP32-CAM
    """
    async def generate_stream():
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_read=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(ESP32_STREAM_URL) as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=502,
                            detail=f"ESP32 stream unavailable (status: {response.status})"
                        )
                    
                    # Stream từng chunk từ ESP32 đến client
                    async for chunk in response.content.iter_chunked(1024):
                        yield chunk
                        
        except aiohttp.ClientError as e:
            print(f"❌ Error connecting to ESP32: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Cannot connect to ESP32 at {ESP32_STREAM_URL}"
            )
        except Exception as e:
            print(f"❌ Stream error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return StreamingResponse(
        generate_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )

async def stream_from_video_file(video_filename: str = None):
    """
    Stream MJPEG từ video file (for testing)
    Đọc video file và stream như ESP32-CAM
    
    Args:
        video_filename: Tên file video (optional). Nếu không có, dùng test_video.mp4
                       Sẽ tìm trong thư mục stream/ trước, nếu không có thì tìm ở root
    """
    # Determine video path
    if video_filename:
        # Tìm trong thư mục stream/ trước
        stream_folder = Path(__file__).parent / "stream"
        video_path = stream_folder / video_filename
        
        # Nếu không có trong stream/, thử tìm ở root
        if not video_path.exists():
            video_path = Path(__file__).parent / video_filename
        
        if not video_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Video file not found: {video_filename}. Please add to server/stream/ folder."
            )
    else:
        # Default: test_video.mp4 ở root
        video_path = TEST_VIDEO_PATH
        if not video_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Video file not found: {TEST_VIDEO_PATH}. Please add test_video.mp4 to server folder."
            )
    
    async def generate_video_stream():
        try:
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                raise HTTPException(status_code=500, detail=f"Cannot open video file: {video_path.name}")
            
            # Get FPS để stream đúng tốc độ
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            delay = 1.0 / fps
            
            print(f"📹 Streaming from video file: {video_path.name} ({fps} FPS)")
            
            while True:
                ret, frame = cap.read()
                
                # Loop video
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                # Cập nhật buffer với frame gốc (trước resize)
                try:
                    video_buffer_manager.update_frame(video_path.name, frame)
                except Exception as buffer_err:
                    print(f"⚠️ Buffer update error: {buffer_err}")
                
                # Resize để giống ESP32-CAM (640x480)
                frame = cv2.resize(frame, (640, 480))

                # Overlay timestamp
                try:
                    from datetime import datetime
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(
                        frame,
                        ts,
                        (10, frame.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2,
                        cv2.LINE_AA,
                    )
                except Exception as overlay_err:
                    print(f"⚠️ Timestamp overlay error: {overlay_err}")
                
                # Encode frame as JPEG
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not ret:
                    continue
                
                # MJPEG format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                
                # Delay để stream đúng FPS
                await asyncio.sleep(delay)
                
        except Exception as e:
            print(f"❌ Video stream error: {e}")
            raise
        finally:
            if 'cap' in locals():
                cap.release()
    
    return StreamingResponse(
        generate_video_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )

async def stream_from_mock():
    """
    Proxy stream từ FFmpeg mock server (localhost:8081)
    Giống stream_from_esp32 nhưng từ mock server
    """
    async def generate_stream():
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_read=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(MOCK_STREAM_URL) as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=502,
                            detail=f"Mock stream unavailable (status: {response.status}). Start mock: server/stream_video_mock.bat"
                        )
                    
                    print(f"📹 Streaming from mock FFmpeg server: {MOCK_STREAM_URL}")
                    
                    # Stream từng chunk từ mock đến client
                    async for chunk in response.content.iter_chunked(1024):
                        yield chunk
                        
        except aiohttp.ClientError as e:
            print(f"❌ Error connecting to mock stream: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Cannot connect to mock stream at {MOCK_STREAM_URL}. Start mock: server/stream_video_mock.bat"
            )
        except Exception as e:
            print(f"❌ Mock stream error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return StreamingResponse(
        generate_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )

async def stream_with_tracking(video_filename: str = None, camera_id: str = None, owner_id: str = None):
    """
    Stream MJPEG with real-time tracking annotations (YOLO + ByteTrack).
    Uses TrackingManager with multi-threaded tracking processor.
    
    Args:
        video_filename: Video filename in stream/ folder
        camera_id: Unique camera identifier
        owner_id: Owner ID to load barrier zones from Firestore (optional)
    """
    global tracking_manager
    
    if not video_filename:
        raise HTTPException(status_code=400, detail="video_filename is required for tracking mode")
    
    if not camera_id:
        raise HTTPException(status_code=400, detail="camera_id is required for tracking mode")
    
    # Determine video path
    stream_folder = Path(__file__).parent / "stream"
    video_path = stream_folder / video_filename
    
    if not video_path.exists():
        video_path = Path(__file__).parent / video_filename
    
    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found: {video_filename}. Please add to server/stream/ folder."
        )
    
    # Start tracking if not already started
    if not tracking_manager.is_tracking(camera_id):
        success = tracking_manager.start_tracking(
            camera_id=camera_id,
            video_path=str(video_path),
            conf_threshold=0.25,
            iou_threshold=0.45,
            frame_skip=1,  # Process all frames for smooth tracking
            resize_width=None,  # No resize for better quality (can adjust for performance)
            max_fps=30,
            owner_id=owner_id  # Pass owner_id to load barrier zones
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start tracking for camera: {camera_id}"
            )
        
        print(f"🎯 Started tracking for {camera_id} with video: {video_filename}")
    else:
        print(f"ℹ️  Tracking already active for {camera_id}, reusing processor")
    
    async def generate_tracked_stream():
        """Generator for MJPEG stream with tracking annotations."""
        try:
            # Wait a bit for first frame to be processed
            await asyncio.sleep(0.5)
            
            frame_count = 0
            while True:
                # Get annotated frame from tracking processor
                frame = tracking_manager.get_annotated_frame(camera_id)
                
                if frame is not None:
                    # Encode as JPEG
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        # MJPEG format
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + 
                               buffer.tobytes() + b'\r\n')
                        frame_count += 1
                    
                    # Log every 100 frames
                    if frame_count % 100 == 0:
                        stats = tracking_manager.get_stats(camera_id)
                        if stats:
                            print(f"📊 {camera_id}: FPS={stats['fps']:.1f}, Objects={stats['objects_tracked']}, Unique={stats['unique_tracks_count']}")
                else:
                    # No frame yet, wait a bit
                    await asyncio.sleep(0.01)
                
                # Control stream FPS (~30 FPS)
                await asyncio.sleep(0.033)
                
        except asyncio.CancelledError:
            print(f"⚠️  Stream cancelled for {camera_id}")
            # Don't stop tracking here - might have multiple clients
            raise
        except Exception as e:
            print(f"❌ Tracking stream error for {camera_id}: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    return StreamingResponse(
        generate_tracked_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )

# ========== AI DETECTION APIs ==========
@app.post("/api/plate-detect")
async def detect_license_plate(request: dict):
    """
    Detect license plate từ image
    Input: { "imageData": "data:image/jpeg;base64,..." }
    """
    try:
        image_data = request.get("imageData")
        if not image_data:
            raise HTTPException(status_code=400, detail="imageData is required")
        
        print(f"📥 Received plate detection request")
        
        # Gọi AI service trực tiếp (KHÔNG spawn subprocess)
        result = await ai_service.detect_plate(image_data)
        
        # Lưu vào Firebase
        if result.get("plates"):
            await firebase_service.save_plate_detection(result)
        
        print(f"✅ Detected {len(result.get('plates', []))} plates")
        return {"success": True, **result}
        
    except Exception as e:
        print(f"❌ Plate detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== AI DETECTION FROM VIDEO FILE ==========
@app.post("/api/plate-detect/video-file")
async def detect_license_plate_from_video(request: dict):
    """
    Detect license plate từ video file (lấy 1 frame tại time_ms hoặc frame_index)
    Input: { "file": "parking_a.mp4", "timeMs": 63000, "frameIndex": 1234 (optional) }
    """
    try:
        file = request.get("file")
        time_ms = request.get("timeMs")
        frame_index = request.get("frameIndex")

        if not file:
            raise HTTPException(status_code=400, detail="file is required")

        # Find video file
        stream_folder = Path(__file__).parent / "stream"
        video_path = stream_folder / file
        if not video_path.exists():
            video_path = Path(__file__).parent / file
        if not video_path.exists():
            raise HTTPException(status_code=404, detail=f"Video file not found: {file}")

        print(f"📥 Detecting plate from video file: {video_path.name} (time_ms={time_ms}, frame_index={frame_index})")

        # Ưu tiên lấy frame mới nhất từ buffer (nếu đang stream)
        buffered_frame = video_buffer_manager.get_frame(video_path.name)
        if buffered_frame is not None:
            print("🔄 Using buffered frame (last_frame) for ALPR (buffer takes precedence)")
            result = await ai_service.alpr_service.detect_plate_from_frame(buffered_frame)
            # Lưu lại ảnh buffer đang dùng để debug
            try:
                debug_path = Path(__file__).parent / "last_buffer_frame.png"
                cv2.imwrite(str(debug_path), buffered_frame)
                result["debugImagePath"] = str(debug_path)
            except Exception as debug_err:
                print(f"⚠️ Cannot save debug buffer frame: {debug_err}")
            result["usedBuffer"] = True
        else:
            result = await ai_service.detect_plate_from_video_file(
                video_path=video_path,
                time_ms=time_ms,
                frame_index=frame_index,
            )
            result["usedBuffer"] = False

        # Lưu vào Firebase
        if result.get("plates"):
            await firebase_service.save_plate_detection(result)

        print(f"✅ Detected {len(result.get('plates', []))} plates from video file")
        return {"success": True, **result}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Plate detection from video error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/object-tracking")
async def track_objects(request: dict):
    """
    Track objects trong video
    Input: { "videoData": "data:video/mp4;base64,..." }
    """
    try:
        video_data = request.get("videoData")
        if not video_data:
            raise HTTPException(status_code=400, detail="videoData is required")
        
        # Optional parameters
        frame_skip = request.get("frameSkip", 1)
        conf_threshold = request.get("confThreshold", 0.25)
        iou_threshold = request.get("iouThreshold", 0.45)
        
        print(f"📥 Received tracking request")
        
        # Gọi AI service trực tiếp
        result = await ai_service.track_objects(
            video_data,
            frame_skip=frame_skip,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold
        )
        
        # Lưu vào Firebase
        if result.get("success"):
            await firebase_service.save_tracking_result(result)
        
        print(f"✅ Tracking completed: {result.get('unique_tracks', 0)} unique tracks")
        return result
        
    except Exception as e:
        print(f"❌ Tracking error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== ESP32 SNAPSHOT ==========
@app.get("/api/esp32/snapshot")
async def get_esp32_snapshot():
    """
    Lấy 1 frame từ ESP32 stream để detect
    """
    try:
        snapshot_url = "http://192.168.1.158:81/capture"  # ESP32 capture endpoint
        
        async with aiohttp.ClientSession() as session:
            async with session.get(snapshot_url) as response:
                if response.status != 200:
                    raise HTTPException(status_code=502, detail="ESP32 snapshot failed")
                
                image_bytes = await response.read()
                
                # Convert to base64
                import base64
                image_b64 = base64.b64encode(image_bytes).decode('utf-8')
                
                return {
                    "success": True,
                    "imageData": f"data:image/jpeg;base64,{image_b64}"
                }
                
    except Exception as e:
        print(f"❌ Snapshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== STREAM SNAPSHOT ==========
@app.get("/api/stream/snapshot")
async def get_stream_snapshot(
    mode: str = Query(default="video_file", description="Stream mode: video_file"),
    file: str = Query(default=None, description="Video filename"),
    quality: str = Query(default="high", description="Quality: 'high' (original, PNG) or 'low' (640x480, JPEG)")
):
    """
    Lấy 1 frame snapshot từ video file stream để OCR/processing
    
    Args:
        quality: 
            - 'high': Lấy frame gốc từ video (không resize, PNG format) - TỐT NHẤT cho OCR
            - 'low': Resize 640x480, JPEG quality 85 - Cho stream preview
    """
    try:
        import base64
        
        if mode != "video_file" or not file:
            raise HTTPException(status_code=400, detail="Only video_file mode with file parameter is supported")
        
        # Find video file
        stream_folder = Path(__file__).parent / "stream"
        video_path = stream_folder / file
        
        if not video_path.exists():
            video_path = Path(__file__).parent / file
        
        if not video_path.exists():
            raise HTTPException(status_code=404, detail=f"Video file not found: {file}")
        
        # Read frame from video
        # Note: This opens a NEW VideoCapture, so it returns frame at current position
        # For best results, capture from <img> element in frontend (canvas)
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise HTTPException(status_code=500, detail=f"Cannot open video: {file}")
        
        # Try to get a frame from middle of video (not first frame)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames > 100:
            # Set position to middle of video
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
        
        ret, frame = cap.read()
        
        # If failed, try reading from beginning
        if not ret or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
        
        cap.release()
        
        if not ret or frame is None:
            raise HTTPException(status_code=500, detail="Failed to read frame from video")
        
        # Quality mode: 'high' = original frame (PNG), 'low' = resized (JPEG)
        if quality == "high":
            # Lấy frame gốc - KHÔNG resize, KHÔNG nén JPEG
            # Encode as PNG (lossless)
            ret, buffer = cv2.imencode('.png', frame)
            if not ret:
                raise HTTPException(status_code=500, detail="Failed to encode frame as PNG")
            
            image_b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            print(f"✅ High-quality snapshot: {frame.shape[1]}x{frame.shape[0]} (PNG, original size)")
            
            return {
                "success": True,
                "imageData": f"data:image/png;base64,{image_b64}",
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0])
            }
        else:
            # Low quality: Resize và JPEG (cho backward compatibility)
            frame = cv2.resize(frame, (640, 480))
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                raise HTTPException(status_code=500, detail="Failed to encode frame")
            
            image_b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
            print(f"⚠️ Low-quality snapshot: 640x480 (JPEG quality 85)")
            
            return {
                "success": True,
                "imageData": f"data:image/jpeg;base64,{image_b64}"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Stream snapshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== FIREBASE APIs ==========
@app.get("/api/firebase/detections")
async def get_detections(limit: int = 50):
    """Lấy detection history từ Firebase"""
    try:
        detections = await firebase_service.get_detections(limit=limit)
        return {"success": True, "detections": detections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/firebase/plates")
async def get_plate_history(limit: int = 50):
    """Lấy plate detection history"""
    try:
        plates = await firebase_service.get_plate_history(limit=limit)
        return {"success": True, "plates": plates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== PLATE-TO-TRACK ASSIGNMENT ENDPOINTS ==========
@app.post("/api/plate-tracking/assign")
async def assign_plate_to_track(request: dict):
    """
    Assign license plate to vehicle at barrier.
    Called after check-in OCR completes.
    
    Input: {
        "plate": "51A-12345",
        "cameraId": "CAM_B"  # Tracking camera ID (not check-in camera)
    }
    """
    try:
        plate = request.get("plate")
        camera_id = request.get("cameraId")
        
        if not plate or not camera_id:
            raise HTTPException(status_code=400, detail="plate and cameraId are required")
        
        # Get vehicles in barrier zone for this camera
        vehicles_in_barrier = tracking_manager.get_vehicles_in_barrier(camera_id)
        
        if vehicles_in_barrier is None:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found or not tracking")
        
        if not vehicles_in_barrier:
            return {
                "success": False,
                "error": "No vehicles detected in barrier zone",
                "message": "Please wait for vehicle to enter barrier zone"
            }
        
        # Assign to first vehicle in barrier (or could use heuristics like closest to center)
        vehicle = vehicles_in_barrier[0]
        track_id = vehicle['track_id']
        bbox = vehicle['bbox']
        
        # Assign plate to track
        success = plate_assigner.assign_plate_to_track(
            plate=plate,
            track_id=track_id,
            camera_id=camera_id,
            bbox=bbox
        )
        
        if success:
            return {
                "success": True,
                "message": f"Assigned plate '{plate}' to Track ID {track_id}",
                "track_id": track_id,
                "vehicle": vehicle
            }
        else:
            return {
                "success": False,
                "error": f"Track ID {track_id} already has a plate assigned"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Plate assignment error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/plate-tracking/mappings")
async def get_plate_mappings(camera_id: str = Query(None, description="Filter by camera (optional)")):
    """
    Get all plate-to-track mappings.
    
    Query params:
    - camera_id: Filter by camera (optional)
    
    Returns all active mappings.
    """
    try:
        all_assignments = plate_assigner.get_all_assignments()
        
        # Filter by camera if specified
        if camera_id:
            filtered = {
                plate: metadata
                for plate, metadata in all_assignments.items()
                if metadata.get('camera_id') == camera_id
            }
            return {
                "success": True,
                "camera_id": camera_id,
                "count": len(filtered),
                "assignments": filtered
            }
        else:
            return {
                "success": True,
                "count": len(all_assignments),
                "assignments": all_assignments
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/plate-tracking/vehicles-in-barrier")
async def get_vehicles_in_barrier(camera_id: str = Query(..., description="Camera ID")):
    """
    Get vehicles currently in barrier zone for a camera.
    Used for debugging and manual assignment.
    """
    try:
        vehicles = tracking_manager.get_vehicles_in_barrier(camera_id)
        
        if vehicles is None:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        
        return {
            "success": True,
            "camera_id": camera_id,
            "count": len(vehicles),
            "vehicles": vehicles
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/plate-tracking/remove")
async def remove_plate_assignment(plate: str = Query(..., description="License plate to remove")):
    """Remove a plate assignment."""
    try:
        success = plate_assigner.remove_assignment(plate)
        
        if success:
            return {"success": True, "message": f"Removed assignment for plate '{plate}'"}
        else:
            return {"success": False, "error": f"Plate '{plate}' not found"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== TRACKING CONTROL ENDPOINTS ==========
@app.post("/api/tracking/start")
async def start_tracking(request: dict):
    """
    Start tracking for a camera.
    Input: { 
      "camera_id": "cam1", 
      "video_file": "parking_a.mp4",
      "owner_id": "user123" (optional - để load barrier zones)
    }
    """
    try:
        camera_id = request.get("camera_id")
        video_file = request.get("video_file")
        owner_id = request.get("owner_id")  # Optional
        
        if not camera_id or not video_file:
            raise HTTPException(status_code=400, detail="camera_id and video_file are required")
        
        # Get video path
        stream_folder = Path(__file__).parent / "stream"
        video_path = stream_folder / video_file
        
        if not video_path.exists():
            raise HTTPException(status_code=404, detail=f"Video file not found: {video_file}")
        
        # Start tracking (with owner_id to load barrier zones)
        success = tracking_manager.start_tracking(
            camera_id=camera_id,
            video_path=str(video_path),
            conf_threshold=0.25,
            iou_threshold=0.45,
            frame_skip=1,
            max_fps=30,
            owner_id=owner_id
        )
        
        if success:
            return {"success": True, "message": f"Tracking started for {camera_id}"}
        else:
            return {"success": False, "error": "Failed to start tracking"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tracking/stop")
async def stop_tracking(request: dict):
    """
    Stop tracking for a camera.
    Input: { "camera_id": "cam1" }
    """
    try:
        camera_id = request.get("camera_id")
        
        if not camera_id:
            raise HTTPException(status_code=400, detail="camera_id is required")
        
        success = tracking_manager.stop_tracking(camera_id)
        
        if success:
            return {"success": True, "message": f"Tracking stopped for {camera_id}"}
        else:
            return {"success": False, "error": "Camera not being tracked"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tracking/stats")
async def get_tracking_stats(camera_id: str = Query(None, description="Camera ID (optional, returns all if not specified)")):
    """
    Get tracking statistics.
    
    Query params:
    - camera_id: Get stats for specific camera (optional)
    
    Returns stats for specific camera or all active cameras.
    """
    try:
        if camera_id:
            # Get stats for specific camera
            stats = tracking_manager.get_stats(camera_id)
            if stats is None:
                return {"success": False, "error": f"Camera {camera_id} not found or not tracking"}
            return {"success": True, "camera_id": camera_id, "stats": stats}
        else:
            # Get stats for all cameras
            all_stats = tracking_manager.get_all_stats()
            active_cameras = tracking_manager.get_active_cameras()
            return {
                "success": True,
                "active_cameras": active_cameras,
                "stats": all_stats
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== TESTING ENDPOINTS ==========
@app.get("/test/esp32")
async def test_esp32_connection():
    """Test kết nối với ESP32-CAM"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ESP32_STREAM_URL, timeout=aiohttp.ClientTimeout(total=5)) as response:
                status = response.status
                return {
                    "esp32_url": ESP32_STREAM_URL,
                    "status_code": status,
                    "connected": status == 200,
                    "message": "ESP32 OK" if status == 200 else "ESP32 unavailable"
                }
    except Exception as e:
        return {
            "esp32_url": ESP32_STREAM_URL,
            "connected": False,
            "error": str(e),
            "message": "Cannot connect to ESP32. Check IP address and network."
        }

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 SmartParking FastAPI Server")
    print("=" * 60)
    print(f"📹 ESP32-CAM: {ESP32_STREAM_URL}")
    print(f"🌐 Server will start at: http://localhost:8000")
    print(f"📖 API Docs: http://localhost:8000/docs")
    print("=" * 60)
    
    uvicorn.run(
        "main_fastapi:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload khi code thay đổi
        log_level="info"
    )

