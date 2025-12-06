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

# Global instances
ai_service = None
firebase_service = None

# ========== CONFIGURATION ==========
ESP32_STREAM_URL = "http://192.168.33.122:81/stream"  # ESP32-CAM IP
MOCK_STREAM_URL = "http://localhost:8081/stream"      # FFmpeg mock stream
TEST_VIDEO_PATH = Path(__file__).parent / "test_video.mp4"  # Video file for testing

# Stream mode: "esp32" or "video_file" or "mock"
STREAM_MODE = os.getenv("STREAM_MODE", "esp32")  # Default: ESP32

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager - load models khi start server"""
    global ai_service, firebase_service
    
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
    
    yield  # Server chạy ở đây
    
    # Cleanup khi shutdown
    print("🛑 Shutting down server...")
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
    file: str = Query(default=None, description="Video filename (for mode=video_file)")
):
    """
    Stream video từ nhiều nguồn:
    - ESP32-CAM (default)
    - Video file (for testing) - supports multiple files from stream/ folder
    - Mock FFmpeg stream (for testing)
    
    Usage:
    - <img src="http://localhost:8000/stream" />  (ESP32)
    - <img src="http://localhost:8000/stream?mode=video_file&file=parking_a.mp4" />  (Video file)
    - <img src="http://localhost:8000/stream?mode=mock" />  (FFmpeg mock)
    """
    # Determine stream mode
    stream_mode = mode or STREAM_MODE
    
    if stream_mode == "video_file":
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
                
                # Resize để giống ESP32-CAM (640x480)
                frame = cv2.resize(frame, (640, 480))
                
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
    file: str = Query(default=None, description="Video filename")
):
    """
    Lấy 1 frame snapshot từ video file stream để OCR/processing
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
        
        # Resize if needed
        frame = cv2.resize(frame, (640, 480))
        
        # Encode as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            raise HTTPException(status_code=500, detail="Failed to encode frame")
        
        # Convert to base64
        image_b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
        
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

