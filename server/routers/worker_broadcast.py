"""
Worker Broadcast Router
Receives detection frames from worker process and broadcasts to viewers
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from services.detection_broadcaster import broadcaster

logger = logging.getLogger(__name__)

router = APIRouter()

# Import tracking debug broadcaster (lazy import to avoid circular dependency)
_tracking_debug_broadcaster = None

def get_tracking_debug_broadcaster():
    global _tracking_debug_broadcaster
    if _tracking_debug_broadcaster is None:
        from routers.tracking_debug import tracking_debug_broadcaster
        _tracking_debug_broadcaster = tracking_debug_broadcaster
    return _tracking_debug_broadcaster


class BroadcastFrameRequest(BaseModel):
    camera_id: str
    frame_base64: str
    metadata: Optional[dict] = None


@router.post("/api/broadcast-detection")
async def broadcast_detection_frame(request: BroadcastFrameRequest):
    """
    Receive detection frame from worker and broadcast to all viewers
    
    This endpoint is called by the worker process (separate Python process)
    to send detection frames to the FastAPI server, which then broadcasts
    to all connected viewers.
    
    Additionally broadcasts tracking metadata to debug viewers.
    """
    try:
        # Broadcast frame to all viewers via the broadcaster service
        await broadcaster.broadcast_frame(
            camera_id=request.camera_id,
            frame_base64=request.frame_base64,
            metadata=request.metadata or {}
        )
        
        viewer_count = broadcaster.get_viewer_count(request.camera_id)
        logger.debug(f"📺 Broadcasted frame for camera {request.camera_id} to {viewer_count} viewers")
        
        # Also broadcast tracking metadata to debug viewers (if any)
        if request.metadata:
            try:
                debug_broadcaster = get_tracking_debug_broadcaster()
                await debug_broadcaster.broadcast_tracking_data(
                    camera_id=request.camera_id,
                    metadata=request.metadata
                )
                debug_viewer_count = debug_broadcaster.get_viewer_count(request.camera_id)
                if debug_viewer_count > 0:
                    logger.debug(f"🔍 Sent tracking data to {debug_viewer_count} debug viewers")
            except Exception as debug_error:
                logger.warning(f"Failed to send to debug viewers: {debug_error}")
        
        return {
            "success": True,
            "camera_id": request.camera_id,
            "viewer_count": viewer_count
        }
    
    except Exception as e:
        logger.error(f"Error broadcasting frame: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/broadcast-stats")
async def get_broadcast_stats():
    """
    Get broadcaster statistics
    """
    stats = await broadcaster.get_stats()
    return stats
