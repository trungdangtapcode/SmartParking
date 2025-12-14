"""
Tracking Manager
Manages multiple TrackingProcessor instances (one per camera)
Handles lifecycle (start/stop) and provides access to tracked frames
"""
from typing import Dict, Optional, Any, List
from pathlib import Path
from .tracking_processor import TrackingProcessor
from .firebase_service import FirebaseService


class TrackingManager:
    """
    Singleton manager for multiple tracking processors.
    Each camera gets its own TrackingProcessor instance.
    """
    
    def __init__(self, yolo_model=None, plate_assigner=None):
        """
        Initialize tracking manager.
        
        Args:
            yolo_model: Shared YOLO model instance (loaded once, reused for all cameras)
            plate_assigner: PlateTrackAssigner instance for plate-to-track mapping
        """
        self.yolo_model = yolo_model
        self.plate_assigner = plate_assigner
        self.processors: Dict[str, TrackingProcessor] = {}  # camera_id -> TrackingProcessor
        self.firebase_service = FirebaseService()  # For loading barrier zones
        print("✅ TrackingManager initialized")
    
    def set_yolo_model(self, model):
        """Set or update YOLO model (must be called before starting tracking)."""
        self.yolo_model = model
        print("✅ YOLO model set for TrackingManager")
    
    def set_plate_assigner(self, assigner):
        """Set or update PlateTrackAssigner."""
        self.plate_assigner = assigner
        print("✅ PlateTrackAssigner set for TrackingManager")
    
    def start_tracking(
        self,
        camera_id: str,
        video_path: str,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        frame_skip: int = 1,
        resize_width: Optional[int] = None,
        max_fps: int = 30,
        barrier_zone: Optional[Dict] = None,
        owner_id: Optional[str] = None
    ) -> bool:
        """
        Start tracking for a specific camera.
        
        Args:
            camera_id: Unique camera identifier
            video_path: Path to video file
            conf_threshold: Detection confidence threshold
            iou_threshold: IOU threshold for tracking
            frame_skip: Process every Nth frame (1 = all frames)
            resize_width: Resize frame width for processing (None = no resize)
            max_fps: Maximum FPS for output stream
            barrier_zone: Dict with entry/exit zones loaded from Firestore (optional)
            owner_id: Owner ID to load barrier zones from Firestore (optional)
        
        Returns:
            True if started successfully, False if already running or error
        """
        # Check if already tracking this camera
        if camera_id in self.processors:
            if self.processors[camera_id].is_running():
                print(f"⚠️  Camera {camera_id} is already being tracked")
                return False
            else:
                # Remove old processor if stopped
                del self.processors[camera_id]
        
        # Check if YOLO model is loaded
        if self.yolo_model is None:
            print("❌ YOLO model not loaded! Call set_yolo_model() first")
            return False
        
        # Verify video path exists
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            print(f"❌ Video file not found: {video_path}")
            return False
        
        # Try to load barrier zone from Firestore if not provided
        if barrier_zone is None and owner_id:
            barrier_zone = self._load_barrier_zone_from_firestore(camera_id, owner_id)
        
        try:
            # Create new processor
            processor = TrackingProcessor(
                video_source=str(video_path),
                yolo_model=self.yolo_model,
                camera_id=camera_id,
                conf_threshold=conf_threshold,
                iou_threshold=iou_threshold,
                frame_skip=frame_skip,
                resize_width=resize_width,
                max_fps=max_fps,
                barrier_zones=barrier_zone,  # Pass as barrier_zones (plural)
                plate_assigner=self.plate_assigner
            )
            
            # Start processor
            processor.start()
            
            # Store processor
            self.processors[camera_id] = processor
            
            print(f"✅ Started tracking for camera: {camera_id}")
            return True
        
        except Exception as e:
            print(f"❌ Failed to start tracking for {camera_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def stop_tracking(self, camera_id: str) -> bool:
        """
        Stop tracking for a specific camera.
        
        Args:
            camera_id: Camera identifier
        
        Returns:
            True if stopped successfully, False if not found or error
        """
        if camera_id not in self.processors:
            print(f"⚠️  Camera {camera_id} is not being tracked")
            return False
        
        try:
            processor = self.processors[camera_id]
            processor.stop()
            del self.processors[camera_id]
            
            print(f"✅ Stopped tracking for camera: {camera_id}")
            return True
        
        except Exception as e:
            print(f"❌ Failed to stop tracking for {camera_id}: {e}")
            return False
    
    def stop_all(self):
        """Stop all tracking processors."""
        camera_ids = list(self.processors.keys())
        for camera_id in camera_ids:
            self.stop_tracking(camera_id)
        print("✅ Stopped all tracking processors")
    
    def get_annotated_frame(self, camera_id: str) -> Optional[Any]:
        """
        Get latest annotated frame for a camera.
        
        Args:
            camera_id: Camera identifier
        
        Returns:
            Annotated frame (numpy array) or None if not available
        """
        if camera_id not in self.processors:
            return None
        
        processor = self.processors[camera_id]
        if not processor.is_running():
            return None
        
        return processor.get_latest_annotated()
    
    def get_stats(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tracking statistics for a camera.
        
        Args:
            camera_id: Camera identifier
        
        Returns:
            Statistics dict or None if not found
        """
        if camera_id not in self.processors:
            return None
        
        processor = self.processors[camera_id]
        return processor.get_stats()
    
    def is_tracking(self, camera_id: str) -> bool:
        """
        Check if a camera is currently being tracked.
        
        Args:
            camera_id: Camera identifier
        
        Returns:
            True if tracking, False otherwise
        """
        if camera_id not in self.processors:
            return False
        
        return self.processors[camera_id].is_running()
    
    def get_active_cameras(self) -> list:
        """
        Get list of camera IDs currently being tracked.
        
        Returns:
            List of camera IDs
        """
        return [
            camera_id for camera_id, processor in self.processors.items()
            if processor.is_running()
        ]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all active cameras.
        
        Returns:
            Dictionary mapping camera_id to stats
        """
        all_stats = {}
        for camera_id in self.get_active_cameras():
            stats = self.get_stats(camera_id)
            if stats:
                all_stats[camera_id] = stats
        return all_stats
    
    def get_vehicles_in_barrier(self, camera_id: str) -> Optional[List[Dict]]:
        """
        Get vehicles in barrier zone for a specific camera.
        
        Args:
            camera_id: Camera identifier
        
        Returns:
            List of vehicles in barrier zone or None if camera not found
        """
        if camera_id not in self.processors:
            return None
        
        processor = self.processors[camera_id]
        return processor.get_vehicles_in_barrier_zone()
    
    def _load_barrier_zone_from_firestore(self, camera_id: str, owner_id: str) -> Optional[Dict]:
        """
        Load barrier zones (entry & exit) from Firestore detection record.
        
        Args:
            camera_id: Camera identifier
            owner_id: Owner identifier
        
        Returns:
            Dict with entry and exit zones: {
                'entry': {'x': int, 'y': int, 'width': int, 'height': int},
                'exit': {'x': int, 'y': int, 'width': int, 'height': int}
            }
            Returns None if no zones are defined
        """
        try:
            # Build detection doc ID: {ownerId}__{cameraId}
            doc_id = f"{owner_id}__{camera_id}"
            
            print(f"📥 Loading barrier zones from Firestore: detections/{doc_id}")
            
            # Get detection record
            detection = self.firebase_service.get_detection_by_id(doc_id)
            
            if not detection:
                print(f"⚠️  No detection record found for {doc_id}")
                return None
            
            # Check if barrier zones exist
            barrier_zones_raw = detection.get('barrierZones', {})
            
            if not barrier_zones_raw:
                print(f"ℹ️  No barrier zones defined for {camera_id}")
                return None
            
            # Process entry and exit zones
            result = {}
            
            for zone_type in ['entry', 'exit']:
                zone_data = barrier_zones_raw.get(zone_type)
                if zone_data:
                    bbox = zone_data.get('bbox')
                    if bbox and len(bbox) == 4:
                        x, y, width, height = bbox
                        result[zone_type] = {
                            'x': int(x),
                            'y': int(y),
                            'width': int(width),
                            'height': int(height)
                        }
                        print(f"✅ Loaded {zone_type} zone: x={x}, y={y}, w={width}, h={height}")
                    else:
                        print(f"⚠️  Invalid bbox format for {zone_type} zone: {bbox}")
            
            if not result:
                print(f"⚠️  No valid barrier zones found for {camera_id}")
                return None
            
            print(f"✅ Loaded {len(result)} barrier zone(s) for {camera_id}")
            return result
            
        except Exception as e:
            print(f"❌ Failed to load barrier zones from Firestore: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def cleanup(self):
        """Cleanup all resources (call on shutdown)."""
        print("🧹 Cleaning up TrackingManager...")
        self.stop_all()
        self.processors.clear()
        print("✅ TrackingManager cleaned up")
