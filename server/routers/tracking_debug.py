"""
Tracking Debug Router
WebSocket endpoint for debugging tracking information in real-time
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Optional
import asyncio
import logging
import json
from datetime import datetime
from services.parking_lot_analysis_service import get_parking_lot_analysis_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["Tracking Debug"])


class TrackingDebugBroadcaster:
    """Manages WebSocket connections for tracking debug viewers"""
    
    def __init__(self):
        # camera_id -> set of WebSocket connections
        self.viewers: Dict[str, set] = {}
        # camera_id -> latest tracking data
        self.latest_data: Dict[str, dict] = {}
    
    async def add_viewer(self, camera_id: str, websocket: WebSocket):
        """Add viewer to debug stream"""
        if camera_id not in self.viewers:
            self.viewers[camera_id] = set()
        
        await websocket.accept()
        self.viewers[camera_id].add(websocket)
        
        logger.info(f"🔍 Debug viewer connected for camera {camera_id}: {len(self.viewers[camera_id])} total")
        
        # Send latest data immediately if available
        if camera_id in self.latest_data:
            try:
                await websocket.send_json({
                    "type": "tracking_data",
                    "data": self.latest_data[camera_id]
                })
            except Exception as e:
                logger.warning(f"Failed to send initial data: {e}")
    
    def remove_viewer(self, camera_id: str, websocket: WebSocket):
        """Remove viewer from debug stream"""
        if camera_id in self.viewers:
            self.viewers[camera_id].discard(websocket)
            logger.info(f"🔍 Debug viewer disconnected from camera {camera_id}: {len(self.viewers[camera_id])} remaining")
            
            # Cleanup empty sets
            if not self.viewers[camera_id]:
                del self.viewers[camera_id]
    
    async def broadcast_tracking_data(self, camera_id: str, metadata: dict):
        """Broadcast tracking data to all debug viewers"""
        if camera_id not in self.viewers or not self.viewers[camera_id]:
            return
        
        # Store latest data
        self.latest_data[camera_id] = metadata
        
        # Prepare debug message with enhanced information
        debug_message = {
            "type": "tracking_data",
            "camera_id": camera_id,
            "timestamp": metadata.get('timestamp', datetime.now().isoformat()),
            "data": {
                # Summary statistics
                "summary": {
                    "vehicle_count": metadata.get('vehicle_count', 0),
                    "occupied_spaces": metadata.get('occupied_spaces', 0),
                    "total_spaces": metadata.get('total_spaces', 0),
                    "occupancy_rate": (
                        metadata.get('occupied_spaces', 0) / metadata.get('total_spaces', 1)
                        if metadata.get('total_spaces', 0) > 0 else 0
                    ),
                    "tracking_enabled": metadata.get('tracking_enabled', False)
                },
                
                # Detailed detections
                "detections": metadata.get('detections', []),
                
                # Space occupancy
                "space_occupancy": metadata.get('space_occupancy', []),
                
                # Matched detections (vehicle-space associations)
                "matched_detections": metadata.get('matched_detections', []),
                
                # Additional statistics
                "statistics": {
                    "vehicles_by_type": self._count_by_type(metadata.get('detections', [])),
                    "tracked_vehicle_count": len([
                        d for d in metadata.get('detections', []) 
                        if d.get('track_id') is not None
                    ]),
                    "track_ids": [
                        d.get('track_id') for d in metadata.get('detections', [])
                        if d.get('track_id') is not None
                    ],
                    "occupied_space_names": [
                        s.get('space_name') for s in metadata.get('space_occupancy', [])
                        if s.get('is_occupied')
                    ],
                    "available_space_names": [
                        s.get('space_name') for s in metadata.get('space_occupancy', [])
                        if not s.get('is_occupied')
                    ]
                }
            }
        }
        
        # Send to all viewers
        disconnected = []
        for viewer in self.viewers[camera_id]:
            try:
                await asyncio.wait_for(
                    viewer.send_json(debug_message),
                    timeout=0.5
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout sending to debug viewer")
                disconnected.append(viewer)
            except Exception as e:
                logger.warning(f"Failed to send to debug viewer: {e}")
                disconnected.append(viewer)
        
        # Remove disconnected viewers
        for viewer in disconnected:
            self.viewers[camera_id].discard(viewer)
    
    def _count_by_type(self, detections):
        """Count vehicles by type"""
        counts = {}
        for detection in detections:
            vehicle_class = detection.get('class', 'unknown')
            counts[vehicle_class] = counts.get(vehicle_class, 0) + 1
        return counts
    
    def get_viewer_count(self, camera_id: str) -> int:
        """Get number of debug viewers for camera"""
        return len(self.viewers.get(camera_id, set()))


# Global broadcaster instance
tracking_debug_broadcaster = TrackingDebugBroadcaster()


@router.websocket("/ws/tracking/{camera_id}")
async def tracking_debug_stream(
    websocket: WebSocket,
    camera_id: str
):
    """
    WebSocket endpoint for debugging tracking information
    
    Usage:
        ws://localhost:8069/debug/ws/tracking/CAM1
    
    Message Format:
        {
            "type": "tracking_data",
            "camera_id": "CAM1",
            "timestamp": "2026-01-07T12:30:45.123456",
            "data": {
                "summary": {
                    "vehicle_count": 3,
                    "occupied_spaces": 2,
                    "total_spaces": 4,
                    "occupancy_rate": 0.5,
                    "tracking_enabled": true
                },
                "detections": [...],
                "space_occupancy": [...],
                "matched_detections": [...],
                "statistics": {
                    "vehicles_by_type": {"car": 2, "motorcycle": 1},
                    "tracked_vehicle_count": 3,
                    "track_ids": [42, 43, 44],
                    "occupied_space_names": ["A1", "A2"],
                    "available_space_names": ["A3", "A4"]
                }
            }
        }
    """
    await tracking_debug_broadcaster.add_viewer(camera_id, websocket)
    
    try:
        # Keep connection alive
        while True:
            try:
                # Wait for client messages (ping/pong for keepalive)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")
                    logger.debug(f"🏓 Debug ping/pong for {camera_id}")
            
            except asyncio.TimeoutError:
                # Send keepalive if no message received
                try:
                    await websocket.send_text("keepalive")
                    logger.debug(f"💓 Debug keepalive for {camera_id}")
                except:
                    break
    
    except WebSocketDisconnect:
        logger.info(f"🔍 Debug viewer disconnected from {camera_id}")
    
    except Exception as e:
        logger.error(f"Error in tracking debug stream for {camera_id}: {e}")
    
    finally:
        tracking_debug_broadcaster.remove_viewer(camera_id, websocket)


@router.get("/tracking-info/{camera_id}")
async def get_latest_tracking_info(camera_id: str):
    """
    Get latest tracking information for a camera (HTTP endpoint)
    
    Usage:
        GET /debug/tracking-info/CAM1
    
    Returns:
        Latest tracking data received from worker
    """
    if camera_id not in tracking_debug_broadcaster.latest_data:
        return {
            "camera_id": camera_id,
            "error": "No tracking data available",
            "message": "Camera may not be active or no data received yet"
        }
    
    data = tracking_debug_broadcaster.latest_data[camera_id]
    
    return {
        "camera_id": camera_id,
        "timestamp": data.get('timestamp'),
        "summary": {
            "vehicle_count": data.get('vehicle_count', 0),
            "occupied_spaces": data.get('occupied_spaces', 0),
            "total_spaces": data.get('total_spaces', 0),
            "tracking_enabled": data.get('tracking_enabled', False)
        },
        "detections": data.get('detections', []),
        "space_occupancy": data.get('space_occupancy', []),
        "matched_detections": data.get('matched_detections', []),
        "viewer_count": tracking_debug_broadcaster.get_viewer_count(camera_id)
    }


@router.get("/active-cameras")
async def get_active_cameras_with_tracking():
    """
    Get list of cameras with active tracking data or worker enabled
    
    Usage:
        GET /debug/active-cameras
    
    Returns:
        List of cameras that have sent tracking data or have workerEnabled=true
    """
    cameras = []
    seen_camera_ids = set()
    
    # First, add cameras that have sent tracking data (they're actively processing)
    for camera_id, data in tracking_debug_broadcaster.latest_data.items():
        cameras.append({
            "camera_id": camera_id,
            "camera_name": f"Camera {camera_id[:8]}...",
            "parking_id": "unknown",
            "last_update": data.get('timestamp'),
            "vehicle_count": data.get('vehicle_count', 0),
            "occupied_spaces": data.get('occupied_spaces', 0),
            "total_spaces": data.get('total_spaces', 0),
            "tracking_enabled": data.get('tracking_enabled', False),
            "debug_viewers": tracking_debug_broadcaster.get_viewer_count(camera_id),
            "status": "active"
        })
        seen_camera_ids.add(camera_id)
    
    # Try to fetch worker-enabled cameras from Firebase
    try:
        from services.firebase_service import FirebaseService
        firebase_service = FirebaseService()
        
        # Query parking lots
        parking_lots = list(firebase_service.db.collection('parkingLots').stream())
        
        for lot_doc in parking_lots:
            try:
                lot_data = lot_doc.to_dict()
                
                # Only process active parking lots
                if lot_data.get('status') != 'active':
                    continue
                
                # Get cameras for this parking lot
                camera_ids = lot_data.get('cameras', [])
                
                for camera_id in camera_ids:
                    if camera_id in seen_camera_ids:
                        continue  # Already added from tracking data
                    
                    try:
                        # Get camera config
                        camera_ref = firebase_service.db.collection('esp32_configs').document(camera_id)
                        camera_doc = camera_ref.get()
                        
                        if camera_doc.exists:
                            camera_data = camera_doc.to_dict()
                            
                            # Only add if worker is enabled
                            if camera_data.get('workerEnabled', False):
                                cameras.append({
                                    "camera_id": camera_id,
                                    "camera_name": camera_data.get('name', camera_id),
                                    "parking_id": lot_doc.id,
                                    "last_update": None,
                                    "vehicle_count": 0,
                                    "occupied_spaces": 0,
                                    "total_spaces": 0,
                                    "tracking_enabled": False,
                                    "debug_viewers": 0,
                                    "status": "enabled_no_data"
                                })
                                seen_camera_ids.add(camera_id)
                    except Exception as cam_error:
                        logger.debug(f"Error fetching camera {camera_id}: {cam_error}")
            except Exception as lot_error:
                logger.debug(f"Error processing parking lot: {lot_error}")
    except Exception as e:
        logger.warning(f"Could not fetch cameras from Firebase: {e}")
    
    return {
        "cameras": cameras,
        "total": len(cameras),
        "active_with_data": len([c for c in cameras if c['status'] == 'active']),
        "worker_enabled": len([c for c in cameras if c['status'] == 'enabled_no_data'])
    }


@router.get("/parking-lot-analysis/{parking_id}")
async def analyze_parking_lot(parking_id: str):
    """
    Analyze parking lot occupancy based on latest detection data
    
    Args:
        parking_id: Parking lot ID
    
    Usage:
        GET /debug/parking-lot-analysis/{parking_id}
    
    Returns:
        Detailed analysis of parking lot occupancy including:
        - Total/occupied/available spaces
        - Occupancy rate
        - List of spaces with status
        - Vehicles occupying spaces (with track IDs if tracking enabled)
    """
    try:
        analysis_service = get_parking_lot_analysis_service()
        
        # Collect detections from all cameras in this parking lot
        # Get cameras for this lot
        from services.firebase_service import FirebaseService
        firebase_service = FirebaseService()
        
        lot_ref = firebase_service.db.collection('parkingLots').document(parking_id)
        lot_doc = lot_ref.get()
        
        if not lot_doc.exists:
            return {
                "error": "Parking lot not found",
                "parking_id": parking_id
            }
        
        lot_data = lot_doc.to_dict()
        camera_ids = lot_data.get('cameras', [])
        
        # Collect detections from all cameras
        all_detections = []
        image_width = 1920  # Default
        image_height = 1080
        
        for camera_id in camera_ids:
            if camera_id in tracking_debug_broadcaster.latest_data:
                camera_data = tracking_debug_broadcaster.latest_data[camera_id]
                detections = camera_data.get('detections', [])
                all_detections.extend(detections)
        
        # Analyze parking lot
        result = analysis_service.analyze_parking_lot(
            parking_id=parking_id,
            detections=all_detections,
            image_width=image_width,
            image_height=image_height
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing parking lot {parking_id}: {e}", exc_info=True)
        return {
            "error": str(e),
            "parking_id": parking_id
        }


@router.get("/parking-lot-analysis")
async def analyze_all_parking_lots():
    """
    Analyze all parking lots based on latest detection data
    
    Usage:
        GET /debug/parking-lot-analysis
    
    Returns:
        Analysis for all parking lots with summary statistics
    """
    try:
        analysis_service = get_parking_lot_analysis_service()
        
        # Collect detections by camera from latest data
        detections_by_camera = {}
        
        for camera_id, camera_data in tracking_debug_broadcaster.latest_data.items():
            detections = camera_data.get('detections', [])
            detections_by_camera[camera_id] = detections
        
        # Analyze all lots
        result = analysis_service.analyze_all_parking_lots(detections_by_camera)
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing all parking lots: {e}", exc_info=True)
        return {
            "error": str(e),
            "parking_lots": [],
            "summary": {}
        }


@router.get("/empty-spaces/{parking_id}")
async def get_empty_spaces(parking_id: str):
    """
    Get list of empty parking spaces in a parking lot
    
    Args:
        parking_id: Parking lot ID
    
    Usage:
        GET /debug/empty-spaces/{parking_id}
    
    Returns:
        List of available (empty) parking spaces
    """
    try:
        # First analyze the lot to get current occupancy
        lot_analysis = await analyze_parking_lot(parking_id)
        
        if "error" in lot_analysis:
            return lot_analysis
        
        # Filter for empty spaces
        empty_spaces = [
            space for space in lot_analysis.get('spaces', [])
            if not space.get('is_occupied', True)
        ]
        
        return {
            "parking_id": parking_id,
            "timestamp": lot_analysis.get('timestamp'),
            "empty_spaces": empty_spaces,
            "count": len(empty_spaces),
            "total_spaces": lot_analysis.get('total_spaces', 0)
        }
        
    except Exception as e:
        logger.error(f"Error getting empty spaces for {parking_id}: {e}")
        return {
            "error": str(e),
            "parking_id": parking_id
        }


@router.get("/occupied-spaces/{parking_id}")
async def get_occupied_spaces(parking_id: str):
    """
    Get list of occupied parking spaces in a parking lot
    
    Args:
        parking_id: Parking lot ID
    
    Usage:
        GET /debug/occupied-spaces/{parking_id}
    
    Returns:
        List of occupied parking spaces with vehicle information
    """
    try:
        # First analyze the lot to get current occupancy
        lot_analysis = await analyze_parking_lot(parking_id)
        
        if "error" in lot_analysis:
            return lot_analysis
        
        # Filter for occupied spaces
        occupied_spaces = [
            space for space in lot_analysis.get('spaces', [])
            if space.get('is_occupied', False)
        ]
        
        return {
            "parking_id": parking_id,
            "timestamp": lot_analysis.get('timestamp'),
            "occupied_spaces": occupied_spaces,
            "count": len(occupied_spaces),
            "total_spaces": lot_analysis.get('total_spaces', 0)
        }
        
    except Exception as e:
        logger.error(f"Error getting occupied spaces for {parking_id}: {e}")
        return {
            "error": str(e),
            "parking_id": parking_id
        }
