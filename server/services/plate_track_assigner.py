"""
Plate-to-Track Assignment Service
Manages mapping between license plates and track IDs for vehicle tracking
"""
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
import threading


class PlateTrackAssigner:
    """
    Singleton service for managing plate number to track ID assignments.
    Stores mappings in-memory for real-time tracking.
    """
    
    def __init__(self):
        """Initialize the assigner with empty mappings."""
        # Core mappings
        self.plate_to_track: Dict[str, int] = {}  # plate -> track_id
        self.track_to_plate: Dict[int, str] = {}  # track_id -> plate (reverse lookup)
        
        # Metadata for each assignment
        self.assignments: Dict[str, dict] = {}  # plate -> {track_id, camera_id, timestamp, ...}
        
        # Thread safety
        self.lock = threading.Lock()
        
        print("✅ PlateTrackAssigner initialized")
    
    def assign_plate_to_track(
        self,
        plate: str,
        track_id: int,
        camera_id: str,
        bbox: Optional[List[int]] = None
    ) -> bool:
        """
        Assign a license plate to a track ID.
        
        Args:
            plate: License plate number (e.g., "51A-12345")
            track_id: Track ID from YOLO tracking
            camera_id: Camera identifier
            bbox: Bounding box [x, y, w, h] (optional)
        
        Returns:
            True if assignment successful, False if track_id already has a plate
        """
        with self.lock:
            # Check if track_id already has a plate assigned
            if track_id in self.track_to_plate:
                existing_plate = self.track_to_plate[track_id]
                print(f"⚠️  Track ID {track_id} already has plate: {existing_plate}")
                return False
            
            # Check if plate is already assigned to another track
            if plate in self.plate_to_track:
                old_track_id = self.plate_to_track[plate]
                print(f"ℹ️  Plate {plate} was assigned to track {old_track_id}, reassigning to {track_id}")
                # Remove old assignment
                del self.track_to_plate[old_track_id]
            
            # Create new assignment
            self.plate_to_track[plate] = track_id
            self.track_to_plate[track_id] = plate
            
            # Store metadata
            self.assignments[plate] = {
                'track_id': track_id,
                'camera_id': camera_id,
                'timestamp': datetime.now().isoformat(),
                'bbox': bbox
            }
            
            print(f"✅ Assigned plate '{plate}' to Track ID {track_id} (Camera: {camera_id})")
            return True
    
    def get_plate_for_track(self, track_id: int) -> Optional[str]:
        """
        Get license plate for a track ID.
        
        Args:
            track_id: Track ID
        
        Returns:
            License plate or None if not assigned
        """
        with self.lock:
            return self.track_to_plate.get(track_id)
    
    def get_track_for_plate(self, plate: str) -> Optional[int]:
        """
        Get track ID for a license plate.
        
        Args:
            plate: License plate number
        
        Returns:
            Track ID or None if not assigned
        """
        with self.lock:
            return self.plate_to_track.get(plate)
    
    def get_all_mappings(self) -> Dict[str, int]:
        """
        Get all plate-to-track mappings.
        
        Returns:
            Dictionary mapping plates to track IDs
        """
        with self.lock:
            return self.plate_to_track.copy()
    
    def get_all_assignments(self) -> Dict[str, dict]:
        """
        Get all assignments with metadata.
        
        Returns:
            Dictionary of plates to assignment metadata
        """
        with self.lock:
            return self.assignments.copy()
    
    def remove_assignment(self, plate: str) -> bool:
        """
        Remove a plate assignment.
        
        Args:
            plate: License plate number
        
        Returns:
            True if removed, False if not found
        """
        with self.lock:
            if plate not in self.plate_to_track:
                return False
            
            track_id = self.plate_to_track[plate]
            del self.plate_to_track[plate]
            del self.track_to_plate[track_id]
            
            if plate in self.assignments:
                del self.assignments[plate]
            
            print(f"🗑️  Removed assignment for plate '{plate}' (was Track ID {track_id})")
            return True
    
    def remove_by_track_id(self, track_id: int) -> bool:
        """
        Remove assignment by track ID.
        
        Args:
            track_id: Track ID
        
        Returns:
            True if removed, False if not found
        """
        with self.lock:
            if track_id not in self.track_to_plate:
                return False
            
            plate = self.track_to_plate[track_id]
            del self.track_to_plate[track_id]
            del self.plate_to_track[plate]
            
            if plate in self.assignments:
                del self.assignments[plate]
            
            print(f"🗑️  Removed assignment for Track ID {track_id} (was plate '{plate}')")
            return True
    
    def cleanup_old_assignments(self, max_age_minutes: int = 30):
        """
        Remove assignments older than max_age_minutes.
        
        Args:
            max_age_minutes: Maximum age in minutes
        
        Returns:
            Number of assignments removed
        """
        with self.lock:
            now = datetime.now()
            to_remove = []
            
            for plate, metadata in self.assignments.items():
                timestamp_str = metadata.get('timestamp')
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    age = now - timestamp
                    if age > timedelta(minutes=max_age_minutes):
                        to_remove.append(plate)
            
            # Remove old assignments
            for plate in to_remove:
                track_id = self.plate_to_track.get(plate)
                if track_id:
                    del self.track_to_plate[track_id]
                del self.plate_to_track[plate]
                del self.assignments[plate]
            
            if to_remove:
                print(f"🧹 Cleaned up {len(to_remove)} old assignments (>{max_age_minutes}min)")
            
            return len(to_remove)
    
    def clear_all(self):
        """Clear all assignments."""
        with self.lock:
            count = len(self.plate_to_track)
            self.plate_to_track.clear()
            self.track_to_plate.clear()
            self.assignments.clear()
            print(f"🗑️  Cleared all {count} assignments")
    
    def get_stats(self) -> dict:
        """
        Get statistics about current assignments.
        
        Returns:
            Dictionary with statistics
        """
        with self.lock:
            return {
                'total_assignments': len(self.plate_to_track),
                'plates': list(self.plate_to_track.keys()),
                'track_ids': list(self.track_to_plate.keys())
            }
