"""
Vehicle Plate Tracking Service
Manages assignment of license plates to tracked vehicles and parking space occupancy
"""
import logging
import random
from typing import Dict, List, Optional, Any, Deque
from datetime import datetime, timedelta
from collections import deque
from services.firebase_service import FirebaseService

logger = logging.getLogger(__name__)


class VehiclePlateService:
    """Service for tracking vehicles with their assigned license plates"""
    
    def __init__(self, firebase_service: FirebaseService):
        self.firebase = firebase_service
        # In-memory cache: {camera_id: {track_id: plate_info}}
        self.vehicle_plates: Dict[str, Dict[int, Dict[str, Any]]] = {}
        # Track which vehicles are in barrier zones: {camera_id: {track_id: detection_count}}
        self.barrier_detections: Dict[str, Dict[int, int]] = {}
        
        # 🆕 QUEUE: Store recently detected plates {parking_id: deque([plate_info])}
        # When a parking slot becomes occupied, assign the most recent plate from queue
        self.plate_queue: Dict[str, Deque[Dict[str, Any]]] = {}
        # Track previous parking space occupancy to detect new occupations
        self.previous_space_occupancy: Dict[str, Dict[str, bool]] = {}  # {camera_id: {space_id: occupied}}
        
    def add_plate_to_queue(self, parking_id: str, plate: str, confidence: float, timestamp: datetime = None):
        """
        Add a detected plate to the queue for future assignment
        
        Args:
            parking_id: Parking lot ID
            plate: License plate text
            confidence: Detection confidence
            timestamp: Detection time
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        if parking_id not in self.plate_queue:
            self.plate_queue[parking_id] = deque(maxlen=10)  # Keep last 10 plates
        
        plate_info = {
            'plate': plate,
            'confidence': confidence,
            'detected_at': timestamp.isoformat(),
            'assigned': False
        }
        
        self.plate_queue[parking_id].append(plate_info)
        logger.info(f"📋 Added plate '{plate}' to queue for parking {parking_id} (queue size: {len(self.plate_queue[parking_id])})")
    
    def get_next_plate_from_queue(self, parking_id: str) -> Optional[str]:
        """
        Get the most recent unassigned plate from queue
        
        Args:
            parking_id: Parking lot ID
        
        Returns:
            Plate number or None if queue is empty
        """
        if parking_id not in self.plate_queue or not self.plate_queue[parking_id]:
            return None
        
        # Get the most recent plate (from right side)
        for i in range(len(self.plate_queue[parking_id]) - 1, -1, -1):
            plate_info = self.plate_queue[parking_id][i]
            if not plate_info.get('assigned', False):
                plate_info['assigned'] = True
                logger.info(f"✅ Retrieved plate '{plate_info['plate']}' from queue for parking {parking_id}")
                return plate_info['plate']
        
        return None
    
    def detect_new_occupancy(
        self,
        camera_id: str,
        parking_id: str,
        current_space_occupancy: Dict[str, bool],
        spaces: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect parking spaces that just became occupied (heuristic trick)
        
        Args:
            camera_id: Camera ID
            parking_id: Parking lot ID
            current_space_occupancy: Current occupancy state {space_id: occupied}
            spaces: List of parking space configs
        
        Returns:
            List of newly occupied spaces with assigned plates
        """
        newly_occupied = []
        
        # Initialize previous state if needed
        if camera_id not in self.previous_space_occupancy:
            self.previous_space_occupancy[camera_id] = {}
        
        prev_occupancy = self.previous_space_occupancy[camera_id]
        
        # Find spaces that changed from free to occupied
        for space in spaces:
            space_id = space['id']
            is_occupied_now = current_space_occupancy.get(space_id, False)
            was_occupied_before = prev_occupancy.get(space_id, False)
            
            # Newly occupied space detected!
            if is_occupied_now and not was_occupied_before:
                logger.info(f"🆕 NEW OCCUPATION DETECTED: Space {space.get('name', space_id)} on camera {camera_id}")
                
                # 🎓 EXAM MODE: Don't auto-assign immediately
                # Will use random assignment to occupied spaces with 30s+ occupation
        
        # Update previous state
        self.previous_space_occupancy[camera_id] = current_space_occupancy.copy()
        
        return newly_occupied
    
    async def assign_plates_to_random_available_spaces(
        self,
        parking_id: str
    ) -> List[Dict[str, Any]]:
        """
        🎓 EXAM MODE FAKE: Randomly pick AVAILABLE spaces and mark as OCCUPIED with plates
        SIMPLE & FAST - Just for demo!
        
        Args:
            parking_id: Parking lot ID
        
        Returns:
            List of spaces that were assigned plates
        """
        assigned_spaces = []
        
        # Get plates from queue
        if parking_id not in self.plate_queue or not self.plate_queue[parking_id]:
            logger.info(f"📋 No plates in queue for parking {parking_id}")
            return assigned_spaces
        
        try:
            # Get ALL AVAILABLE parking spaces (not occupied, no plate)
            spaces_ref = self.firebase.db.collection('parkingSpaces')\
                .where('parkingId', '==', parking_id)\
                .where('isOccupied', '==', False)\
                .stream()
            
            available_spaces = []
            
            for space_doc in spaces_ref:
                space_data = space_doc.to_dict()
                space_id = space_doc.id
                
                available_spaces.append({
                    'id': space_id,
                    'name': space_data.get('name', space_id)
                })
            
            if not available_spaces:
                logger.warning(f"⚠️ No available spaces found!")
                return assigned_spaces
            
            logger.info(f"✅ Found {len(available_spaces)} available spaces")
            
            # Randomly shuffle available spaces
            random.shuffle(available_spaces)
            
            # Assign plates to random available spaces
            for space in available_spaces:
                plate = self.get_next_plate_from_queue(parking_id)
                
                if not plate:
                    logger.info("📋 No more plates in queue")
                    break
                
                # 🎓 FAKE IT: Mark as OCCUPIED + assign plate
                try:
                    space_ref = self.firebase.db.collection('parkingSpaces').document(space['id'])
                    now = datetime.utcnow().isoformat()
                    space_ref.update({
                        'isOccupied': True,
                        'vehiclePlate': plate,
                        'occupiedAt': now,
                        'updatedAt': now
                    })
                    
                    assigned_spaces.append({
                        'space_id': space['id'],
                        'space_name': space['name'],
                        'plate': plate
                    })
                    
                    logger.info(f"🎓 FAKE EXAM MODE: Space {space['name']} → OCCUPIED with plate '{plate}'")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to fake occupy space {space['id']}: {e}")
            
            return assigned_spaces
            
        except Exception as e:
            logger.error(f"❌ Failed to get available spaces: {e}")
            return assigned_spaces
        
    def detect_new_occupancy(
        self,
        camera_id: str,
        parking_id: str,
        current_space_occupancy: Dict[str, bool],
        spaces: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect parking spaces that just became occupied (heuristic trick)
        
        Args:
            camera_id: Camera ID
            parking_id: Parking lot ID
            current_space_occupancy: Current occupancy state {space_id: occupied}
            spaces: List of parking space configs
        
        Returns:
            List of newly occupied spaces with assigned plates
        """
        newly_occupied = []
        
        # Initialize previous state if needed
        if camera_id not in self.previous_space_occupancy:
            self.previous_space_occupancy[camera_id] = {}
        
        prev_occupancy = self.previous_space_occupancy[camera_id]
        
        # Find spaces that changed from free to occupied
        for space in spaces:
            space_id = space['id']
            is_occupied_now = current_space_occupancy.get(space_id, False)
            was_occupied_before = prev_occupancy.get(space_id, False)
            
            # Newly occupied space detected!
            if is_occupied_now and not was_occupied_before:
                logger.info(f"🆕 NEW OCCUPATION DETECTED: Space {space.get('name', space_id)} on camera {camera_id}")
                
                # Don't auto-assign here anymore - we'll do it randomly later
                # Get next plate from queue
                # plate = self.get_next_plate_from_queue(parking_id)
                
                # if plate:
                #     newly_occupied.append({
                #         'space_id': space_id,
                #         'space_name': space.get('name', space_id),
                #         'plate': plate,
                #         'occupied_at': datetime.utcnow().isoformat()
                #     })
                #     logger.info(f"🎯 Auto-assigned plate '{plate}' to space {space.get('name', space_id)}")
                # else:
                #     logger.warning(f"⚠️ No plate in queue for newly occupied space {space.get('name', space_id)}")
        
        # Update previous state
        self.previous_space_occupancy[camera_id] = current_space_occupancy.copy()
        
        return newly_occupied
        
    def is_vehicle_in_barrier_zone(
        self,
        camera_id: str,
        track_id: int,
        vehicle_bbox: List[float],
        barrier_boxes: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if a tracked vehicle overlaps with any barrier box
        
        Args:
            camera_id: Camera ID
            track_id: Vehicle track ID
            vehicle_bbox: [x, y, width, height] normalized 0-1
            barrier_boxes: List of barrier box configs from Firebase
        
        Returns:
            True if vehicle is in barrier zone
        """
        if not barrier_boxes:
            return False
        
        vx, vy, vw, vh = vehicle_bbox
        v_center_x = vx + vw / 2
        v_center_y = vy + vh / 2
        
        for barrier in barrier_boxes:
            # Barrier box coordinates (normalized)
            bx = barrier.get('x', 0)
            by = barrier.get('y', 0)
            bw = barrier.get('width', 0)
            bh = barrier.get('height', 0)
            
            # Check if vehicle center is inside barrier box
            if (bx <= v_center_x <= bx + bw) and (by <= v_center_y <= by + bh):
                logger.debug(f"Vehicle track_id={track_id} is in barrier zone on camera {camera_id}")
                return True
        
        return False
    
    async def register_barrier_detection(
        self,
        camera_id: str,
        track_id: int,
        vehicle_bbox: List[float],
        parking_id: str
    ) -> bool:
        """
        Register that a vehicle has been detected in the barrier zone
        Returns True if this is a new detection that should trigger ALPR
        
        Args:
            camera_id: Camera ID
            track_id: Vehicle track ID
            vehicle_bbox: Vehicle bounding box
            parking_id: Parking lot ID
        
        Returns:
            True if ALPR should be triggered for this vehicle
        """
        # Initialize camera tracking if needed
        if camera_id not in self.barrier_detections:
            self.barrier_detections[camera_id] = {}
        
        # Check if this vehicle already has a plate assigned
        if self.has_assigned_plate(camera_id, track_id):
            logger.debug(f"Vehicle track_id={track_id} already has plate assigned, skipping ALPR")
            return False
        
        # Increment detection count
        if track_id not in self.barrier_detections[camera_id]:
            self.barrier_detections[camera_id][track_id] = 0
        
        self.barrier_detections[camera_id][track_id] += 1
        detection_count = self.barrier_detections[camera_id][track_id]
        
        # Trigger ALPR after 3 consecutive detections to avoid false positives
        if detection_count == 3:
            logger.info(f"🚧 Vehicle track_id={track_id} confirmed in barrier zone, triggering ALPR")
            return True
        
        return False
    
    def has_assigned_plate(self, camera_id: str, track_id: int) -> bool:
        """Check if a vehicle already has an assigned plate"""
        if camera_id not in self.vehicle_plates:
            return False
        return track_id in self.vehicle_plates[camera_id]
    
    async def assign_plate_to_vehicle(
        self,
        camera_id: str,
        parking_id: str,
        track_id: int,
        plate_number: str,
        confidence: float,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Assign a license plate to a tracked vehicle
        
        Args:
            camera_id: Camera ID
            parking_id: Parking lot ID
            track_id: Vehicle track ID
            plate_number: Detected plate number
            confidence: Detection confidence
            timestamp: Detection timestamp
        
        Returns:
            True if assignment was successful
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Initialize camera tracking
        if camera_id not in self.vehicle_plates:
            self.vehicle_plates[camera_id] = {}
        
        # Store in memory
        self.vehicle_plates[camera_id][track_id] = {
            'plate': plate_number,
            'confidence': confidence,
            'assigned_at': timestamp.isoformat(),
            'parking_id': parking_id,
            'camera_id': camera_id,
            'parking_space_id': None,  # Updated when vehicle parks
            'status': 'in_barrier'  # in_barrier, moving, parked, exited
        }
        
        # Store in Firebase
        try:
            vehicle_ref = self.firebase.db.collection('vehicle_tracking').document(
                f"{camera_id}_{track_id}"
            )
            
            vehicle_ref.set({
                'cameraId': camera_id,
                'parkingId': parking_id,
                'trackId': track_id,
                'plate': plate_number,
                'confidence': confidence,
                'assignedAt': timestamp.isoformat(),
                'updatedAt': timestamp.isoformat(),
                'parkingSpaceId': None,
                'status': 'in_barrier'
            })
            
            logger.info(f"✅ Assigned plate '{plate_number}' to track_id={track_id} on camera {camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to store vehicle-plate assignment: {e}")
            return False
    
    def get_vehicle_plate(self, camera_id: str, track_id: int) -> Optional[str]:
        """Get the assigned plate for a tracked vehicle"""
        if camera_id not in self.vehicle_plates:
            return None
        
        vehicle_info = self.vehicle_plates[camera_id].get(track_id)
        if vehicle_info:
            return vehicle_info['plate']
        
        return None
    
    async def update_vehicle_parking_space(
        self,
        camera_id: str,
        track_id: int,
        parking_space_id: str,
        status: str = 'parked'
    ) -> bool:
        """
        Update the parking space for a tracked vehicle
        
        Args:
            camera_id: Camera ID
            track_id: Vehicle track ID
            parking_space_id: Parking space ID where vehicle is parked
            status: Vehicle status ('moving', 'parked', 'exited')
        
        Returns:
            True if update was successful
        """
        # Update in-memory cache
        if camera_id in self.vehicle_plates and track_id in self.vehicle_plates[camera_id]:
            self.vehicle_plates[camera_id][track_id]['parking_space_id'] = parking_space_id
            self.vehicle_plates[camera_id][track_id]['status'] = status
            self.vehicle_plates[camera_id][track_id]['updated_at'] = datetime.utcnow().isoformat()
            
            plate = self.vehicle_plates[camera_id][track_id]['plate']
            
            # Update Firebase
            try:
                # Update vehicle tracking
                vehicle_ref = self.firebase.db.collection('vehicle_tracking').document(
                    f"{camera_id}_{track_id}"
                )
                vehicle_ref.update({
                    'parkingSpaceId': parking_space_id,
                    'status': status,
                    'updatedAt': datetime.utcnow().isoformat()
                })
                
                # Update parking space with plate number
                if parking_space_id and status == 'parked':
                    space_ref = self.firebase.db.collection('parkingSpaces').document(parking_space_id)
                    space_ref.update({
                        'isOccupied': True,
                        'vehiclePlate': plate,
                        'trackId': track_id,
                        'occupiedAt': datetime.utcnow().isoformat()
                    })
                    logger.info(f"🅿️ Vehicle '{plate}' (track_id={track_id}) parked in space {parking_space_id}")
                
                # If vehicle exited, clear the parking space
                elif status == 'exited' and parking_space_id:
                    space_ref = self.firebase.db.collection('parkingSpaces').document(parking_space_id)
                    space_ref.update({
                        'isOccupied': False,
                        'vehiclePlate': None,
                        'trackId': None,
                        'occupiedAt': None
                    })
                    logger.info(f"🚗 Vehicle '{plate}' (track_id={track_id}) exited from space {parking_space_id}")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to update vehicle parking space: {e}")
                return False
        
        return False
    
    def cleanup_lost_tracks(self, camera_id: str, active_track_ids: List[int]):
        """
        Remove tracking data for vehicles that are no longer detected
        
        Args:
            camera_id: Camera ID
            active_track_ids: List of currently active track IDs
        """
        if camera_id not in self.vehicle_plates:
            return
        
        # Find lost tracks
        lost_tracks = [
            track_id for track_id in self.vehicle_plates[camera_id].keys()
            if track_id not in active_track_ids
        ]
        
        for track_id in lost_tracks:
            logger.info(f"🔄 Track {track_id} lost on camera {camera_id}, marking as exited")
            
            # Mark as exited in Firebase
            vehicle_info = self.vehicle_plates[camera_id][track_id]
            parking_space_id = vehicle_info.get('parking_space_id')
            
            if parking_space_id:
                # Update parking space to free
                try:
                    space_ref = self.firebase.db.collection('parkingSpaces').document(parking_space_id)
                    space_ref.update({
                        'isOccupied': False,
                        'vehiclePlate': None,
                        'trackId': None,
                        'occupiedAt': None
                    })
                except Exception as e:
                    logger.error(f"❌ Failed to clear parking space {parking_space_id}: {e}")
            
            # Remove from memory
            del self.vehicle_plates[camera_id][track_id]
            
            # Remove from barrier detections
            if camera_id in self.barrier_detections and track_id in self.barrier_detections[camera_id]:
                del self.barrier_detections[camera_id][track_id]
    
    async def get_barrier_boxes(self, parking_id: str, camera_id: str) -> List[Dict[str, Any]]:
        """
        Get barrier boxes for a specific camera
        
        Args:
            parking_id: Parking lot ID
            camera_id: Camera ID
        
        Returns:
            List of barrier box configurations
        """
        try:
            barrier_docs = self.firebase.db.collection('barrierBoxes')\
                .where('parkingId', '==', parking_id)\
                .where('cameraId', '==', camera_id)\
                .stream()
            
            barriers = []
            for doc in barrier_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                barriers.append(data)
            
            return barriers
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch barrier boxes: {e}")
            return []
