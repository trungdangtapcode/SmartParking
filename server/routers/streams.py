"""
ESP32 streaming endpoints (raw streams, detection streams)
Uses broadcast model - all clients see the same frame at the same time
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
from services.stream_broadcaster import broadcast_manager

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
    🎥 BROADCAST MODE: All clients see the same frame at the same time
    
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
    client_id = str(uuid.uuid4())[:8]
    
    # Get or create broadcaster for this ESP32
    broadcaster = await broadcast_manager.get_broadcaster(stream_url)
    
    # Subscribe to broadcaster
    queue = await broadcaster.subscribe_raw()
    
    async def generate_broadcast_stream():
        """Generate stream from broadcaster queue"""
        try:
            print(f"🎥 [Client {client_id}] Connected to broadcast: {stream_url}")
            frames_sent = 0
            
            while True:
                # Check disconnect
                if await request.is_disconnected():
                    print(f"🔌 [Client {client_id}] Disconnected (is_disconnected)")
                    break
                
                try:
                    # Wait for next frame from broadcaster
                    frame = await asyncio.wait_for(queue.get(), timeout=5.0)
                    
                    if frame is None:
                        # Broadcaster ended
                        print(f"� [Client {client_id}] Broadcast ended")
                        break
                    
                    # Send frame
                    try:
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n\r\n" +
                            frame.jpeg_data + b"\r\n"
                        )
                        frames_sent += 1
                        
                        if frames_sent % 100 == 0:
                            print(f"📺 [Client {client_id}] Sent {frames_sent} frames (current: Frame {frame.frame_id})")
                    
                    except Exception as e:
                        print(f"🔌 [Client {client_id}] Write failed: {type(e).__name__}")
                        break
                
                except asyncio.TimeoutError:
                    # No frame received in 5 seconds - broadcaster might be stuck
                    print(f"⏱️  [Client {client_id}] Frame timeout")
                    continue
        
        except Exception as e:
            print(f"❌ [Client {client_id}] Stream error: {e}")
        finally:
            # Unsubscribe
            broadcaster.unsubscribe(queue)
            print(f"🧹 [Client {client_id}] Cleanup complete ({frames_sent} frames sent)")
            
            # Cleanup inactive broadcasters
            await broadcast_manager.cleanup_inactive()
    
    return StreamingResponse(
        generate_broadcast_stream(),
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
    camera_url: Optional[str] = Query(None, description="Direct camera URL (e.g., http://192.168.1.100)"),
    conf: float = Query(0.25, description="Confidence threshold"),
    show_labels: bool = Query(True, description="Show detection labels"),
    fps: int = Query(10, description="Target FPS", ge=1, le=30),
    skip_frames: int = Query(2, description="Process every Nth frame", ge=1, le=10),
    user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Stream ESP32 with real-time object detection
    🎥 BROADCAST MODE: Uses same frame feed as raw stream (synced frame IDs)
    
    Query parameters:
    - camera_url: Direct camera URL (priority over user_id and default)
    - conf: Confidence threshold (default 0.25)
    - show_labels: Show detection labels (default true)
    - fps: Target FPS (default 10, range 1-30)
    - skip_frames: Process every Nth frame (default 2)
    
    Usage:
    - http://localhost:8069/stream/detect?camera_url=http://192.168.1.100
    - http://localhost:8069/stream/detect?camera_url=http://localhost:8083&fps=15&conf=0.5
    """
    # Determine which ESP32 URL to use (priority: camera_url > user config > default)
    stream_source_url = ESP32_URL
    
    if camera_url:
        # Direct camera URL parameter takes priority
        stream_source_url = camera_url
        print(f"📹 Using provided camera URL: {stream_source_url}")
    elif user_id and firebase_service:
        try:
            config = await firebase_service.get_user_esp32_config(user_id)
            if config and config.get("esp32_url"):
                stream_source_url = config["esp32_url"]
                print(f"📹 Using user's ESP32 for detection: {stream_source_url}")
        except Exception as e:
            print(f"⚠️  Could not get user ESP32 config: {e}, using default")
    
    if not stream_source_url:
        raise HTTPException(
            status_code=400,
            detail="No camera URL provided. Use camera_url parameter or provide X-User-ID header with configured camera."
        )
    
    stream_url = f"{stream_source_url}/stream"
    client_id = str(uuid.uuid4())[:8]
    
    # Get or create broadcaster for this ESP32
    broadcaster = await broadcast_manager.get_broadcaster(stream_url)
    
    # Subscribe to broadcaster (same feed as raw stream!)
    queue = await broadcaster.subscribe_raw()
    
    async def generate_detected_stream():
        """Generate detection stream from broadcaster queue"""
        try:
            print(f"🔍 [Detect {client_id}] Connected to broadcast: {stream_url} | FPS:{fps} | Skip:{skip_frames}")
            
            frames_received = 0
            frames_processed = 0
            frames_sent = 0
            last_send_time = asyncio.get_event_loop().time()
            min_frame_interval = 1.0 / fps if fps > 0 else 0
            
            while True:
                # Check disconnect
                if await request.is_disconnected():
                    print(f"🔌 [Detect {client_id}] Disconnected")
                    break
                
                try:
                    # Wait for next frame from broadcaster
                    frame = await asyncio.wait_for(queue.get(), timeout=5.0)
                    
                    if frame is None:
                        print(f"🔴 [Detect {client_id}] Broadcast ended")
                        break
                    
                    frames_received += 1
                    
                    # Apply skip_frames filter
                    if (frames_received % skip_frames) != 0:
                        continue
                    
                    # Check if it's time to send (FPS throttle)
                    current_time = asyncio.get_event_loop().time()
                    time_since_last_send = current_time - last_send_time
                    
                    if time_since_last_send >= min_frame_interval:
                        # Process this frame with YOLO
                        process_start = current_time
                        
                        # Decode frame
                        nparr = np.frombuffer(frame.jpeg_data, np.uint8)
                        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        if img is not None:
                            # Run YOLO detection
                            results = ai_service.yolo_model(
                                img, conf=conf, device=ai_service.device,
                                verbose=False, half=True
                            )[0]
                            
                            # Annotate frame
                            annotated_frame = img.copy()
                            
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
                            
                            # Encode to JPEG
                            _, jpeg_encoded = cv2.imencode('.jpg', annotated_frame,
                                                            [cv2.IMWRITE_JPEG_QUALITY, 75])
                            
                            # Measure processing time
                            process_end = asyncio.get_event_loop().time()
                            process_time = process_end - process_start
                            
                            # Send frame
                            try:
                                yield (
                                    b"--frame\r\n"
                                    b"Content-Type: image/jpeg\r\n\r\n" +
                                    jpeg_encoded.tobytes() + b"\r\n"
                                )
                                
                                frames_processed += 1
                                frames_sent += 1
                                last_send_time = current_time
                                
                                if frames_sent == 1:
                                    print(f"✅ [Detect {client_id}] Started (Frame {frame.frame_id})")
                                elif frames_sent % 50 == 0:
                                    actual_fps = 1.0 / time_since_last_send if time_since_last_send > 0 else 0
                                    print(f"🔍 [Detect {client_id}] Sent {frames_sent} | Current: Frame {frame.frame_id} | FPS: {actual_fps:.1f} | Process: {process_time*1000:.1f}ms")
                            
                            except Exception as e:
                                print(f"🔌 [Detect {client_id}] Write failed: {type(e).__name__}")
                                break
                
                except asyncio.TimeoutError:
                    print(f"⏱️  [Detect {client_id}] Frame timeout")
                    continue
        
        except Exception as e:
            print(f"❌ [Detect {client_id}] Error: {e}")
        finally:
            # Unsubscribe
            broadcaster.unsubscribe(queue)
            print(f"🧹 [Detect {client_id}] Cleanup complete ({frames_sent} sent)")
            
            # Cleanup inactive broadcasters
            await broadcast_manager.cleanup_inactive()
    
    return StreamingResponse(
        generate_detected_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )
