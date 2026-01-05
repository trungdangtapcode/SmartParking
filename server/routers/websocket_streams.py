"""
WebSocket-based streaming endpoints (replaces HTTP MJPEG)
✅ Proper disconnect detection
✅ No zombie streams
✅ Clean resource management
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Header
from typing import Optional
import aiohttp
import cv2
import numpy as np
import asyncio
import uuid
import json
import base64

router = APIRouter(prefix="/ws", tags=["WebSocket Streaming"])

# Service instances (set by main app)
ai_service = None
firebase_service = None
ESP32_URL = None

def init_router(ai_svc, firebase_svc, esp32_url):
    """Initialize router with service instances"""
    global ai_service, firebase_service, ESP32_URL
    ai_service = ai_svc
    firebase_service = firebase_svc
    ESP32_URL = esp32_url


@router.websocket("/ws/stream/raw")
async def ws_raw_stream(
    websocket: WebSocket, 
    user_id: Optional[str] = None,
    fps: int = 30
):
    """
    WebSocket endpoint for raw ESP32-CAM stream
    
    Query params:
        user_id: Optional Firebase user ID for custom ESP32 URL
        fps: Target FPS for frame sending (default 30, max real-time)
    
    Usage (frontend):
        const ws = new WebSocket('ws://localhost:8069/ws/stream/raw?user_id=...&fps=15');
        ws.onmessage = (event) => {
            const img = new Image();
            img.src = 'data:image/jpeg;base64,' + event.data;
            canvas.getContext('2d').drawImage(img, 0, 0);
        };
    """
    await websocket.accept()
    stream_id = str(uuid.uuid4())[:8]
    
    # Determine ESP32 URL
    stream_source_url = ESP32_URL
    if user_id and firebase_service:
        try:
            config = await firebase_service.get_user_esp32_config(user_id)
            if config and config.get("esp32_url"):
                stream_source_url = config["esp32_url"]
                print(f"📹 [{stream_id}] Using user's ESP32: {stream_source_url}")
        except Exception as e:
            print(f"⚠️  [{stream_id}] Could not get user ESP32 config: {e}")
    
    stream_url = f"{stream_source_url}/stream"
    print(f"🔌 [{stream_id}] WebSocket raw stream connected: {stream_url} | Max FPS:{fps}")
    
    session = None
    response = None
    
    try:
        timeout = aiohttp.ClientTimeout(total=None, sock_read=30)
        session = aiohttp.ClientSession(timeout=timeout)
        response = await session.get(stream_url)
        
        if response.status != 200:
            await websocket.send_json({
                "type": "error",
                "message": f"ESP32 stream unavailable (status: {response.status})"
            })
            return
        
        buffer = b""
        frame_count = 0
        last_send_time = asyncio.get_event_loop().time()
        min_frame_interval = 1.0 / fps if fps > 0 else 0
        
        # 🔥 REAL-TIME: Read frames as fast as ESP32 sends, throttle sending by FPS
        async for chunk in response.content.iter_chunked(1024):
            buffer += chunk
            
            # Find JPEG boundaries
            while True:
                start = buffer.find(b'\xff\xd8')
                end = buffer.find(b'\xff\xd9')
                
                if start != -1 and end != -1 and end > start:
                    jpeg_data = buffer[start:end+2]
                    buffer = buffer[end+2:]
                    frame_count += 1
                    
                    # Check FPS throttle
                    current_time = asyncio.get_event_loop().time()
                    time_since_last_send = current_time - last_send_time
                    
                    if time_since_last_send < min_frame_interval:
                        # Skip this frame to maintain FPS limit (real-time, no queuing)
                        continue
                    
                    # Send frame as base64
                    frame_base64 = base64.b64encode(jpeg_data).decode('utf-8')
                    await websocket.send_text(frame_base64)
                    last_send_time = current_time
                    
                    if frame_count == 1:
                        print(f"✅ [{stream_id}] Raw stream started (max {fps} FPS)")
                    elif frame_count % 100 == 0:
                        actual_fps = 1.0 / time_since_last_send if time_since_last_send > 0 else 0
                        print(f"📹 [{stream_id}] Sent {frame_count} frames (actual {actual_fps:.1f} FPS)")
                else:
                    break
        
        print(f"✅ [{stream_id}] Stream completed: {frame_count} frames sent")
        
    except WebSocketDisconnect:
        print(f"🔴 [{stream_id}] Client disconnected (WebSocket closed)")
    except asyncio.CancelledError:
        print(f"🔴 [{stream_id}] Stream cancelled")
    except Exception as e:
        print(f"❌ [{stream_id}] Stream error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        # ✅ Clean shutdown (no zombies possible!)
        if response:
            try:
                response.close()
            except:
                pass
        if session:
            try:
                await session.close()
            except:
                pass
        print(f"🧹 [{stream_id}] WebSocket stream cleanup complete")


@router.websocket("/stream/detect")
async def ws_detection_stream(
    websocket: WebSocket,
    user_id: Optional[str] = None,
    camera_url: Optional[str] = None,
    conf: float = 0.25,
    show_labels: bool = True,
    fps: int = 10,
    skip_frames: int = 2
):
    """
    WebSocket endpoint for ESP32 stream with real-time object detection
    
    Query params:
        user_id: Optional Firebase user ID
        camera_url: Optional direct camera URL (e.g., http://192.168.1.100)
        conf: Confidence threshold (default 0.25)
        show_labels: Show detection labels (default true)
        fps: Target FPS (1-30, default 10)
        skip_frames: Process every Nth frame (1-10, default 2)
    
    Messages sent to client:
        {"type": "frame", "data": "<base64_jpeg>"}
        {"type": "stats", "processed": 100, "skipped": 50, "fps": 9.8}
        {"type": "error", "message": "..."}
    
    Usage (frontend):
        const ws = new WebSocket('ws://localhost:8069/ws/stream/detect?conf=0.3&fps=15&camera_url=http://192.168.1.100');
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === 'frame') {
                const img = new Image();
                img.src = 'data:image/jpeg;base64,' + msg.data;
                canvas.getContext('2d').drawImage(img, 0, 0);
            }
        };
    """
    await websocket.accept()
    stream_id = str(uuid.uuid4())[:8]
    
    # Determine ESP32 URL (priority: camera_url param > user config > default)
    stream_source_url = ESP32_URL
    
    if camera_url:
        # Direct camera URL parameter takes priority
        stream_source_url = camera_url
        print(f"📹 [{stream_id}] Using provided camera URL: {stream_source_url}")
    elif user_id and firebase_service:
        try:
            config = await firebase_service.get_user_esp32_config(user_id)
            if config and config.get("esp32_url"):
                stream_source_url = config["esp32_url"]
                print(f"📹 [{stream_id}] Using user's ESP32 for detection: {stream_source_url}")
        except Exception as e:
            print(f"⚠️  [{stream_id}] Could not get user ESP32 config: {e}")
    
    if not stream_source_url:
        await websocket.send_json({
            "type": "error",
            "message": "No camera URL provided. Use camera_url parameter or provide user_id with configured camera."
        })
        await websocket.close()
        return
    
    stream_url = f"{stream_source_url}/stream"
    print(f"🔌 [{stream_id}] WebSocket detection stream connected: {stream_url} | FPS:{fps} | Skip:{skip_frames}")
    
    session = None
    response = None
    last_annotated_frame = None
    
    try:
        timeout = aiohttp.ClientTimeout(total=None, sock_read=30)
        session = aiohttp.ClientSession(timeout=timeout)
        response = await session.get(stream_url)
        
        if response.status != 200:
            await websocket.send_json({
                "type": "error",
                "message": f"ESP32 stream unavailable (status: {response.status})"
            })
            return
        
        buffer = b""
        frame_count = 0
        processed_count = 0
        sent_count = 0
        last_send_time = asyncio.get_event_loop().time()
        min_frame_interval = 1.0 / fps if fps > 0 else 0
        
        # 🔥 CRITICAL FIX: Always keep the LATEST frame only
        # Don't process old frames - only process when ready to send
        latest_frame_data = None
        
        # Read MJPEG stream - ALWAYS drain at full ESP32 speed
        async for chunk in response.content.iter_chunked(1024):
            buffer += chunk
            
            # 🔥 Extract ALL frames from buffer (don't let buffer grow)
            while True:
                start = buffer.find(b'\xff\xd8')
                end = buffer.find(b'\xff\xd9')
                
                if start != -1 and end != -1 and end > start:
                    jpeg_data = buffer[start:end+2]
                    buffer = buffer[end+2:]
                    frame_count += 1
                    
                    # 🔥 CRITICAL: Just store the latest frame, don't process yet
                    # Only apply skip_frames filter
                    if (frame_count % skip_frames) == 0:
                        latest_frame_data = jpeg_data
                    
                    # 🔥 Check if it's time to SEND (FPS throttle)
                    current_time = asyncio.get_event_loop().time()
                    time_since_last_send = current_time - last_send_time
                    
                    if time_since_last_send >= min_frame_interval and latest_frame_data is not None:
                        # NOW process the LATEST frame and send immediately
                        process_start = current_time
                        
                        # Decode frame
                        nparr = np.frombuffer(latest_frame_data, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            # Run YOLO detection
                            results = ai_service.yolo_model(
                                frame, conf=conf, device=ai_service.device,
                                verbose=False, half=True
                            )[0]
                            
                            # Annotate frame
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
                            
                            # Encode to JPEG
                            _, jpeg_encoded = cv2.imencode('.jpg', annotated_frame,
                                                            [cv2.IMWRITE_JPEG_QUALITY, 75])
                            frame_base64 = base64.b64encode(jpeg_encoded.tobytes()).decode('utf-8')
                            
                            # Measure processing time
                            process_end = asyncio.get_event_loop().time()
                            process_time = process_end - process_start
                            
                            # 🔥 Send immediately (we only process when ready to send)
                            await websocket.send_json({
                                "type": "frame",
                                "data": frame_base64
                            })
                            
                            processed_count += 1
                            sent_count += 1
                            last_send_time = current_time
                            
                            # Clear latest_frame_data to avoid reprocessing
                            latest_frame_data = None
                            
                            if sent_count == 1:
                                print(f"✅ [{stream_id}] Detection started (reading all frames, processing/sending every {skip_frames} frames at {fps} FPS)")
                            elif sent_count % 50 == 0:
                                actual_fps = 1.0 / time_since_last_send if time_since_last_send > 0 else 0
                                print(f"📹 [{stream_id}] Sent {sent_count} | Read {frame_count} | FPS: {actual_fps:.1f} | Process: {process_time*1000:.1f}ms | Buffer: {len(buffer)}B")
                            
                            # Send stats periodically
                            if sent_count % 50 == 0:
                                await websocket.send_json({
                                    "type": "stats",
                                    "processed": processed_count,
                                    "sent": sent_count,
                                    "read": frame_count,
                                    "fps": actual_fps,
                                    "process_time_ms": process_time * 1000,
                                    "buffer_size": len(buffer)
                                })
                    
                    # 🔥 ALWAYS break inner loop to continue reading (drain buffer fast)
                else:
                    # No more complete frames in buffer
                    break
        
        print(f"✅ [{stream_id}] Stream completed: {processed_count} processed, {frame_count} total frames")
        
    except WebSocketDisconnect:
        print(f"🔴 [{stream_id}] Client disconnected (WebSocket closed)")
    except asyncio.CancelledError:
        print(f"🔴 [{stream_id}] Stream cancelled")
    except Exception as e:
        print(f"❌ [{stream_id}] Stream error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        # ✅ Clean shutdown (WebSocket guarantees disconnect event!)
        if response:
            try:
                response.close()
            except:
                pass
        if session:
            try:
                await session.close()
            except:
                pass
        print(f"🧹 [{stream_id}] WebSocket detection stream cleanup complete")
