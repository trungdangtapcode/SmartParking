"""
Detection Viewer WebSocket Router
Allows users to watch worker detection streams without additional GPU processing
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import logging

from services.detection_broadcaster import broadcaster

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/viewer/detection")
async def ws_viewer_detection(
    websocket: WebSocket,
    camera_id: str = Query(..., description="Camera ID to watch"),
    user_id: Optional[str] = Query(None, description="User ID for logging")
):
    """
    WebSocket endpoint for viewing worker detection streams.
    Multiple users can watch the same worker stream (GPU efficient).
    
    Query params:
        camera_id: Required - Camera ID to watch
        user_id: Optional - User ID for logging
    
    Messages sent to client:
        {"type": "frame", "data": "<base64_jpeg>", "metadata": {...}}
        {"type": "error", "message": "..."}
        {"type": "info", "message": "Worker not active for this camera"}
    
    Usage:
        const ws = new WebSocket('ws://localhost:8069/ws/viewer/detection?camera_id=cam123&user_id=user456');
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === 'frame') {
                const img = new Image();
                img.src = 'data:image/jpeg;base64,' + msg.data;
                // Display img...
            }
        };
    """
    await websocket.accept()
    logger.info(f"📺 Viewer connected: camera_id={camera_id}, user_id={user_id}")
    
    try:
        # Register viewer
        await broadcaster.register_viewer(camera_id, websocket)
        
        # Send initial info message
        viewer_count = broadcaster.get_viewer_count(camera_id)
        await websocket.send_json({
            "type": "info",
            "message": f"Connected to camera {camera_id}. Viewers: {viewer_count}",
            "camera_id": camera_id,
            "viewer_count": viewer_count
        })
        
        # Keep connection alive and wait for disconnect
        while True:
            # Receive messages from client (for keepalive/commands)
            try:
                data = await websocket.receive_text()
                # Handle client messages if needed (e.g., pause/resume)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error receiving from viewer: {e}")
                break
    
    except Exception as e:
        logger.error(f"Error in viewer WebSocket: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    
    finally:
        # Unregister viewer
        await broadcaster.unregister_viewer(camera_id, websocket)
        logger.info(f"📺 Viewer disconnected: camera_id={camera_id}")

@router.get("/viewer/stats")
async def get_viewer_stats():
    """Get viewer statistics"""
    return await broadcaster.get_stats()
