"""
Detection Broadcaster Service
Allows multiple clients to watch the same detection stream without reprocessing.
Worker processes once, broadcasts to many viewers.
"""
import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class DetectionBroadcaster:
    """
    Manages broadcasting of detection frames from worker to multiple viewers.
    Single detection process -> Multiple viewers (GPU efficient)
    """
    
    def __init__(self):
        # camera_id -> set of connected WebSocket clients
        self._viewers: Dict[str, Set[WebSocket]] = {}
        # camera_id -> latest detection frame (base64 jpeg)
        self._latest_frames: Dict[str, bytes] = {}
        # camera_id -> frame metadata
        self._frame_metadata: Dict[str, dict] = {}
        self._lock = asyncio.Lock()
    
    async def register_viewer(self, camera_id: str, websocket: WebSocket):
        """Register a viewer for a specific camera"""
        async with self._lock:
            if camera_id not in self._viewers:
                self._viewers[camera_id] = set()
            self._viewers[camera_id].add(websocket)
            viewer_count = len(self._viewers[camera_id])
        
        logger.info(f"📺 Viewer registered for camera {camera_id} (total: {viewer_count})")
        
        # Send latest frame immediately if available
        if camera_id in self._latest_frames:
            try:
                await websocket.send_json({
                    "type": "frame",
                    "data": self._latest_frames[camera_id].decode('utf-8'),
                    "metadata": self._frame_metadata.get(camera_id, {})
                })
            except Exception as e:
                logger.error(f"Failed to send initial frame: {e}")
    
    async def unregister_viewer(self, camera_id: str, websocket: WebSocket):
        """Unregister a viewer"""
        async with self._lock:
            if camera_id in self._viewers:
                self._viewers[camera_id].discard(websocket)
                if not self._viewers[camera_id]:
                    del self._viewers[camera_id]
                    # Clean up old frame data
                    if camera_id in self._latest_frames:
                        del self._latest_frames[camera_id]
                    if camera_id in self._frame_metadata:
                        del self._frame_metadata[camera_id]
                    logger.info(f"📺 No more viewers for camera {camera_id}, cleaned up")
                else:
                    viewer_count = len(self._viewers[camera_id])
                    logger.info(f"📺 Viewer unregistered from camera {camera_id} (remaining: {viewer_count})")
    
    async def broadcast_frame(self, camera_id: str, frame_base64: str, metadata: dict = None):
        """
        Broadcast a detection frame to all viewers of this camera.
        Called by the worker when it processes a frame.
        
        Args:
            camera_id: Camera identifier
            frame_base64: Base64 encoded JPEG with detection annotations
            metadata: Optional frame metadata (vehicle count, timestamp, etc.)
        """
        async with self._lock:
            # Store latest frame
            self._latest_frames[camera_id] = frame_base64.encode('utf-8')
            if metadata:
                self._frame_metadata[camera_id] = metadata
            
            # Get viewers
            viewers = self._viewers.get(camera_id, set()).copy()
        
        if not viewers:
            return  # No viewers, skip broadcast
        
        # Broadcast to all viewers
        message = {
            "type": "frame",
            "data": frame_base64,
            "metadata": metadata or {}
        }
        
        disconnected = []
        for websocket in viewers:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to viewer: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected viewers
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    if camera_id in self._viewers:
                        self._viewers[camera_id].discard(ws)
    
    def get_viewer_count(self, camera_id: str) -> int:
        """Get number of active viewers for a camera"""
        return len(self._viewers.get(camera_id, set()))
    
    def get_active_cameras(self) -> list:
        """Get list of camera IDs with active viewers"""
        return list(self._viewers.keys())
    
    async def get_stats(self) -> dict:
        """Get broadcaster statistics"""
        async with self._lock:
            return {
                "active_cameras": len(self._viewers),
                "total_viewers": sum(len(viewers) for viewers in self._viewers.values()),
                "cameras": {
                    camera_id: len(viewers)
                    for camera_id, viewers in self._viewers.items()
                }
            }

# Global broadcaster instance
broadcaster = DetectionBroadcaster()
