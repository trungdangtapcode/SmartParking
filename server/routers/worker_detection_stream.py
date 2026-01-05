"""
Worker Detection Stream Endpoint
Efficiently streams detection results from active workers using MJPEG
Similar optimization to /stream but shows annotated detection results
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import asyncio
import logging
from typing import Optional

from services.detection_broadcaster import broadcaster

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stream/worker-detection")
async def stream_worker_detection(
    camera_id: str = Query(..., description="Camera ID to watch"),
    fps: int = Query(10, ge=1, le=30, description="Target FPS")
):
    """
    Stream worker detection results as MJPEG stream (efficient, low-latency)
    
    This endpoint provides the same detection stream that workers are generating,
    but delivered as an efficient MJPEG stream instead of WebSocket.
    
    Query params:
        camera_id: Required - Camera ID to watch
        fps: Target FPS (1-30, default 10)
    
    Usage:
        <img src="http://localhost:8069/stream/worker-detection?camera_id=cam123&fps=15" />
    """
    
    async def generate_mjpeg():
        """Generate MJPEG stream from worker detection frames"""
        stream_id = f"worker-{camera_id}"
        logger.info(f"📺 Starting worker detection stream: {camera_id}")
        
        frame_interval = 1.0 / fps
        last_frame = None
        last_frame_time = 0
        
        try:
            # Check if worker is active for this camera
            viewer_count = broadcaster.get_viewer_count(camera_id)
            logger.info(f"📺 Camera {camera_id} has {viewer_count} active viewers")
            
            # Send MJPEG header
            yield b'--frame\r\n'
            
            while True:
                current_time = asyncio.get_event_loop().time()
                
                # Rate limiting
                if current_time - last_frame_time < frame_interval:
                    await asyncio.sleep(frame_interval - (current_time - last_frame_time))
                    continue
                
                # Get latest frame from broadcaster
                if camera_id in broadcaster._latest_frames:
                    frame_base64 = broadcaster._latest_frames[camera_id]
                    
                    # Decode base64 to bytes
                    import base64
                    frame_bytes = base64.b64decode(frame_base64)
                    
                    # Send frame as MJPEG
                    yield b'Content-Type: image/jpeg\r\n'
                    yield b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n\r\n'
                    yield frame_bytes
                    yield b'\r\n--frame\r\n'
                    
                    last_frame_time = current_time
                    last_frame = frame_bytes
                else:
                    # No frame available yet - wait or send error message
                    if last_frame is None:
                        # Send a placeholder message
                        logger.warning(f"⚠️ No frames available for camera {camera_id}")
                        await asyncio.sleep(1)
                        continue
                    else:
                        # Resend last frame to keep stream alive
                        yield b'Content-Type: image/jpeg\r\n'
                        yield b'Content-Length: ' + str(len(last_frame)).encode() + b'\r\n\r\n'
                        yield last_frame
                        yield b'\r\n--frame\r\n'
                        await asyncio.sleep(frame_interval)
                
        except asyncio.CancelledError:
            logger.info(f"📺 Worker detection stream cancelled: {camera_id}")
        except Exception as e:
            logger.error(f"❌ Error in worker detection stream: {e}")
        finally:
            logger.info(f"📺 Worker detection stream closed: {camera_id}")
    
    return StreamingResponse(
        generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
