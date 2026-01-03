"""
ESP32 streaming endpoints (raw streams, detection streams)
"""
from fastapi import APIRouter, HTTPException, Query, Header, Request
from fastapi.responses import StreamingResponse
from typing import Optional
import aiohttp
import cv2
import numpy as np
import asyncio
import uuid

from middleware.disconnect_watcher import cancel_on_disconnect
from models.stream_tracking import StreamConnection

router = APIRouter(prefix="/stream", tags=["Streaming"])

# Will be set by main app
ai_service = None
firebase_service = None
ESP32_URL = None

def init_router(ai_svc, firebase_svc, esp32_url):
    """Initialize router with service instances"""
    global ai_service, firebase_service, ESP32_URL
    ai_service = ai_svc
    firebase_service = firebase_svc
    ESP32_URL = esp32_url

@router.get("")
async def proxy_esp32_stream(
    request: Request,
    user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Proxy ESP32-CAM raw stream (user-specific or default)
    
    Headers (optional):
        X-User-ID: Firebase user ID (to use user's configured ESP32)
    """
    # Determine which ESP32 URL to use
    stream_source_url = ESP32_URL  # Default
    
    # If user_id provided, try to get user's configured ESP32
    if user_id and firebase_service:
        try:
            config = await firebase_service.get_user_esp32_config(user_id)
            if config and config.get("esp32_url"):
                stream_source_url = config["esp32_url"]
                print(f"📹 Using user's ESP32: {stream_source_url}")
        except Exception as e:
            print(f"⚠️  Could not get user ESP32 config: {e}, using default")
    
    stream_url = f"{stream_source_url}/stream"
    
    async def generate_proxy_stream():
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_read=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(stream_url) as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=502,
                            detail=f"ESP32 stream unavailable (status: {response.status})"
                        )
                    
                    print(f"📹 Proxying stream from: {stream_url}")
                    
                    chunk_count = 0
                    async for chunk in response.content.iter_chunked(1024):
                        if await request.is_disconnected():
                            print("🔌 Client disconnected from raw stream")
                            break
                        
                        try:
                            yield chunk
                            chunk_count += 1
                        except Exception:
                            print(f"🔌 Client disconnected during yield (raw stream after {chunk_count} chunks)")
                            break
                        
        except aiohttp.ClientError as e:
            print(f"❌ Error connecting to ESP32: {e}")
            raise HTTPException(status_code=502, detail=f"Cannot connect to ESP32 at {stream_url}")
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

@router.get("/proxy")
async def proxy_custom_esp32_stream(
    request: Request,
    esp32_url: str = Query(..., description="Custom ESP32-CAM URL")
):
    """
    Proxy custom ESP32-CAM stream from any IP address
    
    Usage:
    - <img src="http://localhost:8069/stream/proxy?esp32_url=http://192.168.1.100:81" />
    """
    # Remove trailing slash from URL to avoid double slashes
    esp32_url = esp32_url.rstrip('/')
    
    # Ensure URL ends with /stream
    if not esp32_url.endswith('/stream'):
        stream_url = f"{esp32_url}/stream"
    else:
        stream_url = esp32_url
    
    async def generate_proxy_stream():
        chunks_sent = 0
        MAX_CHUNKS_BEFORE_CHECK = 100
        
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_read=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(stream_url) as response:
                    if response.status != 200:
                        raise HTTPException(status_code=502, detail=f"ESP32 stream unavailable (status: {response.status})")
                    
                    print(f"📹 Proxying custom stream from: {stream_url}")
                    
                    async for chunk in response.content.iter_chunked(1024):
                        if chunks_sent >= MAX_CHUNKS_BEFORE_CHECK:
                            if await request.is_disconnected():
                                print(f"🔌 Raw stream client disconnected (periodic check)")
                                return
                            chunks_sent = 0
                        
                        try:
                            yield chunk
                            chunks_sent += 1
                        except (Exception, GeneratorExit, StopAsyncIteration) as e:
                            print(f"🔌 Raw stream client disconnected: {type(e).__name__}")
                            return
                        
        except aiohttp.ClientError as e:
            print(f"❌ Error connecting to ESP32: {e}")
            raise HTTPException(status_code=502, detail=f"Cannot connect to ESP32 at {stream_url}")
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

@router.get("/detect")
async def stream_with_detection(
    request: Request,
    conf: float = Query(0.25, description="Confidence threshold"),
    show_labels: bool = Query(True, description="Show detection labels"),
    fps: int = Query(10, description="Target FPS", ge=1, le=30),
    skip_frames: int = Query(2, description="Process every Nth frame", ge=1, le=10),
    user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Stream ESP32 with real-time object detection
    
    Performance parameters:
    - fps: Target FPS (default 10, range 1-30)
    - skip_frames: Process every Nth frame (default 2)
    """
    # Determine which ESP32 URL to use
    stream_source_url = ESP32_URL
    
    if user_id and firebase_service:
        try:
            config = await firebase_service.get_user_esp32_config(user_id)
            if config and config.get("esp32_url"):
                stream_source_url = config["esp32_url"]
                print(f"📹 Using user's ESP32 for detection: {stream_source_url}")
        except Exception as e:
            print(f"⚠️  Could not get user ESP32 config: {e}, using default")
    
    stream_url = f"{stream_source_url}/stream"
    stream_id = str(uuid.uuid4())[:8]
    
    return StreamingResponse(
        generate_detected_stream(request, stream_url, conf, show_labels, fps, skip_frames, stream_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )



async def generate_detected_stream(request: Request, stream_url: str, conf: float,
                                   show_labels: bool, fps: int, skip_frames: int, stream_id: str):
    last_annotated_frame = None
    frames_sent = 0
 
    frame_delay = 1.0 / fps if fps > 0 else 0
    
    try:
        async with cancel_on_disconnect(request):
            timeout = aiohttp.ClientTimeout(total=None, sock_read=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(stream_url) as response:
                    if response.status != 200:
                        raise HTTPException(status_code=502, detail=f"ESP32 stream unavailable (status: {response.status})")
                    
                    print(f"📹 [{stream_id}] Detection stream started: {stream_url} | FPS:{fps} | Skip:{skip_frames}")
                    
                    buffer = b""
                    frame_count = 0
                    processed_count = 0
                    
                    async for chunk in response.content.iter_chunked(1024):
                        buffer += chunk
                        
                        while True:
                            if await request.is_disconnected():
                                print(f"🔴 Client disconnected: {stream_id}")
                                return
                            start = buffer.find(b'\xff\xd8')
                            end = buffer.find(b'\xff\xd9')
                            
                            if start != -1 and end != -1 and end > start:
                                jpeg_data = buffer[start:end+2]
                                buffer = buffer[end+2:]
                                frame_count += 1
                                
                                should_process = (frame_count % skip_frames) == 0
                                
                                if should_process:
                                    nparr = np.frombuffer(jpeg_data, np.uint8)
                                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                                    
                                    if frame is not None:
                                        results = ai_service.yolo_model(
                                            frame, conf=conf, device=ai_service.device,
                                            verbose=False, half=True
                                        )[0]
                                        
                                        annotated_frame = frame.copy()
                                        
                                        for box in results.boxes:
                                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                                            confidence = float(box.conf[0])
                                            class_id = int(box.cls[0])
                                            class_name = results.names[class_id]
                                            
                                            color = (0, 255, 0)
                                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                                            
                                            if show_labels:
                                                label = f"{class_name} {confidence:.2f}"
                                                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                                                cv2.rectangle(annotated_frame, (x1, y1-th-8), (x1+tw+6, y1), color, -1)
                                                cv2.putText(annotated_frame, label, (x1+3, y1-5),
                                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                                        
                                        _, jpeg_encoded = cv2.imencode('.jpg', annotated_frame,
                                                                        [cv2.IMWRITE_JPEG_QUALITY, 75])
                                        last_annotated_frame = jpeg_encoded.tobytes()
                                        processed_count += 1
                                        
                                        if processed_count == 1:
                                            print(f"✅ [{stream_id}] Detection started (processing every {skip_frames} frames)")
                                        elif processed_count % 50 == 0:
                                            print(f"📹 [{stream_id}] Processed {processed_count} frames (skipped {frame_count - processed_count})")
                                
                                output = last_annotated_frame or jpeg_data
                                
                                yield (
                                    b"--frame\r\n"
                                    b"Content-Type: image/jpeg\r\n\r\n" +
                                    output + b"\r\n"
                                )
                                
                                frames_sent += 1
                                
                                if frame_delay > 0:
                                    await asyncio.sleep(frame_delay)
                            else:
                                break
                    
                    print(f"✅ [{stream_id}] Stream completed: {processed_count} processed, {frame_count} total frames")
                    
    except asyncio.CancelledError:
        print(f"🔌 [{stream_id}] Client disconnected after {frames_sent} frames")
        raise
    except aiohttp.ClientError as e:
        print(f"❌ [{stream_id}] Error connecting to ESP32: {e}")
        raise HTTPException(status_code=502, detail=f"Cannot connect to ESP32 at {stream_url}")
    except Exception as e:
        print(f"❌ [{stream_id}] Stream error: {e}")
        raise
    finally:
        print(f"🧹 [{stream_id}] Stream cleanup complete")