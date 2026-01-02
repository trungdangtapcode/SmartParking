"""
FastAPI Backend cho SmartParking
Main API server for AI detection and Firebase integration
Streaming is handled by separate ESP32 folder
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import aiohttp
import os
import sys
import cv2
import numpy as np
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add ESP32 folder to path
ESP32_PATH = Path(__file__).parent.parent / "ESP32"
sys.path.insert(0, str(ESP32_PATH))

# Import services
from services.ai_service import AIService
from services.firebase_service import FirebaseService
from esp32_client import ESP32Client

# Global instances
ai_service = None
firebase_service = None
esp32_client = None

# ========== CONFIGURATION ==========
# ESP32-CAM Configuration
# Development: http://localhost:5069 (video file streaming for development)
# Production: http://192.168.33.122:81 (ESP32-CAM hardware)
ESP32_URL = os.getenv("ESP32_URL", "http://localhost:5069")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager - load models khi start server"""
    global ai_service, firebase_service, esp32_client
    
    print("🚀 Starting FastAPI SmartParking Server...")
    
    # Load AI models 1 LẦN duy nhất
    print("📦 Loading AI models...")
    ai_service = AIService()
    await ai_service.load_models()
    print("✅ AI models loaded successfully")
    
    # Initialize Firebase
    print("🔥 Initializing Firebase Admin SDK...")
    try:
        firebase_service = FirebaseService()
        print("✅ Firebase initialized")
    except Exception as e:
        print(f"⚠️  Firebase initialization failed: {e}")
        print("⚠️  Continuing without Firebase (some features will be disabled)")
        firebase_service = None
    
    # Initialize ESP32 client
    print(f"📹 Connecting to ESP32: {ESP32_URL}")
    esp32_client = ESP32Client(ESP32_URL)
    
    # Test connection
    async with ESP32Client(ESP32_URL) as test_client:
        result = await test_client.test_connection()
        if result['connected']:
            print(f"✅ ESP32 connected: {ESP32_URL}")
        else:
            print(f"⚠️  ESP32 not connected: {result.get('error', 'Unknown error')}")
            print(f"   💡 Start ESP32 server: cd ESP32 && python start_mock.py --port 5069")
    
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
        "http://localhost:5169",  # Frontend React (custom port)
        "http://localhost:5173",  # Frontend React (default)
        "http://127.0.0.1:5169",
        "http://127.0.0.1:5173",
        "*"  # Allow all for development
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
        "service": "smartparking-api",
        "models_loaded": ai_service is not None,
        "firebase_connected": firebase_service is not None,
        "esp32_url": ESP32_URL
    }

# ========== ESP32 STREAM PROXY ==========
@app.get("/stream")
async def proxy_esp32_stream():
    """
    Proxy ESP32-CAM stream (delegates to mock_esp32_server.py or real ESP32)
    
    Usage:
    - <img src="http://localhost:8069/stream" />
    """
    stream_url = f"{ESP32_URL}/stream"
    
    async def generate_proxy_stream():
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_read=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(stream_url) as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=502,
                            detail=f"ESP32 stream unavailable (status: {response.status}). "
                                   f"Ensure ESP32 server is running and accessible."
                        )
                    
                    print(f"📹 Proxying stream from: {stream_url}")
                    
                    # Proxy stream chunks
                    async for chunk in response.content.iter_chunked(1024):
                        yield chunk
                        
        except aiohttp.ClientError as e:
            print(f"❌ Error connecting to ESP32: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Cannot connect to ESP32 at {stream_url}. "
                       f"Ensure ESP32 server is running."
            )
        except Exception as e:
            print(f"❌ Stream proxy error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return StreamingResponse(
        generate_proxy_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )

# ========== STREAM WITH OBJECT DETECTION ==========
@app.get("/stream/detect")
async def stream_with_detection(
    conf: float = Query(0.25, description="Confidence threshold"),
    show_labels: bool = Query(True, description="Show detection labels")
):
    """
    Stream ESP32 với real-time object detection
    
    Usage:
    - <img src="http://localhost:8069/stream/detect" />
    - <img src="http://localhost:8069/stream/detect?conf=0.5&show_labels=true" />
    """
    stream_url = f"{ESP32_URL}/stream"
    
    async def generate_detected_stream():
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_read=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(stream_url) as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=502,
                            detail=f"ESP32 stream unavailable (status: {response.status})"
                        )
                    
                    print(f"📹 Streaming with detection from: {stream_url} (conf={conf})")
                    
                    buffer = b""
                    frame_count = 0
                    
                    # Read MJPEG stream
                    async for chunk in response.content.iter_chunked(1024):
                        buffer += chunk
                        
                        # Find JPEG boundaries
                        while True:
                            start = buffer.find(b'\xff\xd8')  # JPEG start
                            end = buffer.find(b'\xff\xd9')    # JPEG end
                            
                            if start != -1 and end != -1 and end > start:
                                # Extract frame
                                jpeg_data = buffer[start:end+2]
                                buffer = buffer[end+2:]
                                
                                # Decode frame
                                nparr = np.frombuffer(jpeg_data, np.uint8)
                                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                                
                                if frame is not None:
                                    # Run YOLO detection on GPU
                                    results = ai_service.yolo_model(
                                        frame,
                                        conf=conf,
                                        device=ai_service.device,  # Use detected device (cuda/mps/cpu)
                                        verbose=False
                                    )[0]
                                    
                                    # Draw detections
                                    annotated_frame = frame.copy()
                                    
                                    for box in results.boxes:
                                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                                        confidence = float(box.conf[0])
                                        class_id = int(box.cls[0])
                                        class_name = results.names[class_id]
                                        
                                        # Draw box
                                        color = (0, 255, 0)  # Green
                                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                                        
                                        # Draw label
                                        if show_labels:
                                            label = f"{class_name} {confidence:.2f}"
                                            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                                            cv2.rectangle(annotated_frame, (x1, y1-th-8), (x1+tw+6, y1), color, -1)
                                            cv2.putText(
                                                annotated_frame, label, (x1+3, y1-5),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
                                            )
                                    
                                    # Encode back to JPEG
                                    _, jpeg_encoded = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                                    
                                    # Yield as MJPEG frame
                                    yield (b'--frame\r\n'
                                           b'Content-Type: image/jpeg\r\n\r\n' +
                                           jpeg_encoded.tobytes() + b'\r\n')
                                    
                                    frame_count += 1
                                    if frame_count % 30 == 0:
                                        print(f"📹 Processed {frame_count} frames with detection")
                            else:
                                break
                        
        except aiohttp.ClientError as e:
            print(f"❌ Error connecting to ESP32: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Cannot connect to ESP32 at {stream_url}"
            )
        except Exception as e:
            print(f"❌ Detection stream error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return StreamingResponse(
        generate_detected_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )

# ========== ESP32 SNAPSHOT ==========
@app.get("/api/esp32/snapshot")
async def get_esp32_snapshot():
    """
    Capture single frame from ESP32-CAM
    """
    try:
        async with esp32_client as client:
            frame_bytes = await client.capture_frame()
            
            # Convert to base64
            import base64
            image_b64 = base64.b64encode(frame_bytes).decode('utf-8')
            
            return {
                "success": True,
                "imageData": f"data:image/jpeg;base64,{image_b64}"
            }
            
    except Exception as e:
        print(f"❌ Snapshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/esp32/status")
async def get_esp32_status():
    """Get ESP32-CAM status"""
    try:
        async with esp32_client as client:
            status = await client.get_status()
            return {"success": True, **status}
    except Exception as e:
        return {"success": False, "error": str(e)}

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
        async with esp32_client as client:
            result = await client.test_connection()
            return result
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "message": "Cannot connect to ESP32. Check configuration and network."
        }

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 SmartParking FastAPI Server")
    print("=" * 60)
    print(f"📹 ESP32-CAM: {ESP32_URL}")
    print(f"🌐 Backend Server: http://localhost:8069")
    print(f"📖 API Docs: http://localhost:8069/docs")
    print(f"💡 Start ESP32 server: cd ESP32 && python start_mock.py --port 5069")
    print("=" * 60)
    
    uvicorn.run(
        "main_fastapi:app",
        host="0.0.0.0",
        port=8069,
        reload=True,  # Auto-reload khi code thay đổi
        log_level="info"
    )

