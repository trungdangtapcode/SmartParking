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
