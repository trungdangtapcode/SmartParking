"""
Parking Space Service - Match detections with defined parking spaces
"""
from typing import Dict, List, Tuple, Optional
from services.firebase_service import FirebaseService


class ParkingSpaceService:
    """Service to manage parking space definitions and match with detections"""
    
    def __init__(self, firebase_service: FirebaseService):
        """
        Initialize Parking Space Service
        
        Args:
            firebase_service: Initialized FirebaseService instance
        """
        self.firebase = firebase_service
        self.db = firebase_service.db
        
        # Collection names
        self.PARKING_SPACE_DEFINITIONS = "parkingSpaceDefinitions"
        self.PARKING_SPACE_STATUS = "parkingSpaces"
    
    def get_parking_spaces_by_camera(self, camera_id: str) -> List[Dict]:
        """
        Get all parking space definitions for a specific camera
        
        Args:
            camera_id: Camera ID (ESP32 config ID)
            
        Returns:
            List of parking space definitions with normalized coordinates
        """
        try:
            spaces_ref = self.db.collection(self.PARKING_SPACE_DEFINITIONS)
            query = spaces_ref.where("cameraId", "==", camera_id)
            docs = query.stream()
            
            spaces = []
            for doc in docs:
                data = doc.to_dict()
                spaces.append(data)
            
            print(f"✅ Loaded {len(spaces)} parking spaces for camera: {camera_id}")
            return spaces
            
        except Exception as e:
            print(f"❌ Error loading parking spaces: {e}")
            return []
    
    def calculate_iou(
        self,
        box1: Dict[str, float],
        box2: Dict[str, float]
    ) -> float:
        """
        Calculate Intersection over Union (IoU) between two boxes
        
        Args:
            box1: Dict with keys {x, y, width, height} (normalized 0-1)
            box2: Dict with keys {x, y, width, height} (normalized 0-1)
            
        Returns:
            IoU value between 0 and 1
        """
        # Calculate intersection
        x1 = max(box1['x'], box2['x'])
        y1 = max(box1['y'], box2['y'])
        x2 = min(box1['x'] + box1['width'], box2['x'] + box2['width'])
        y2 = min(box1['y'] + box1['height'], box2['y'] + box2['height'])
        
        intersection_width = max(0, x2 - x1)
        intersection_height = max(0, y2 - y1)
        intersection_area = intersection_width * intersection_height
        
        # Calculate union
        box1_area = box1['width'] * box1['height']
        box2_area = box2['width'] * box2['height']
        union_area = box1_area + box2_area - intersection_area
        
        # Avoid division by zero
        if union_area == 0:
            return 0.0
        
        # Calculate IoU
        iou = intersection_area / union_area
        return iou
    
    def convert_detection_to_normalized(
        self,
        detection: Dict,
        image_width: int,
        image_height: int
    ) -> Dict[str, float]:
        """
        Convert detection bounding box from pixel coordinates to normalized (0-1)
        
        Args:
            detection: Detection dict with bbox in format [x1, y1, x2, y2] or [x, y, w, h]
            image_width: Image width in pixels
            image_height: Image height in pixels
            
        Returns:
            Normalized box dict {x, y, width, height}
        """
        bbox = detection.get('bbox', detection.get('box', []))
        
        # Handle different bbox formats
        if len(bbox) == 4:
            # Check if format is [x1, y1, x2, y2] or [x, y, w, h]
            if bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                # Likely [x1, y1, x2, y2]
                x1, y1, x2, y2 = bbox
                x = x1 / image_width
                y = y1 / image_height
                width = (x2 - x1) / image_width
                height = (y2 - y1) / image_height
            else:
                # Likely [x, y, w, h]
                x, y, w, h = bbox
                x = x / image_width
                y = y / image_height
                width = w / image_width
                height = h / image_height
        else:
            print(f"⚠️  Invalid bbox format: {bbox}")
            return {'x': 0, 'y': 0, 'width': 0, 'height': 0}
        
        return {
            'x': max(0, min(1, x)),
            'y': max(0, min(1, y)),
            'width': max(0, min(1, width)),
            'height': max(0, min(1, height))
        }
    
    def match_detections_to_spaces(
        self,
        detections: List[Dict],
        parking_spaces: List[Dict],
        image_width: int,
        image_height: int,
        iou_threshold: float = 0.5
    ) -> Tuple[List[Dict], Dict[str, bool]]:
        """
        Match vehicle detections to parking spaces
        
        Args:
            detections: List of detection dicts with bbox
            parking_spaces: List of parking space definitions
            image_width: Image width in pixels
            image_height: Image height in pixels
            iou_threshold: Minimum IoU to consider a match (default 0.5)
            
        Returns:
            Tuple of:
            - List of matched detections with added 'parking_space_id' field
            - Dict mapping space_id to occupancy status (True=occupied, False=available)
        """
        # Initialize all spaces as available
        space_occupancy = {space['id']: False for space in parking_spaces}
        matched_detections = []
        
        for detection in detections:
            # Convert detection to normalized coordinates
            det_box = self.convert_detection_to_normalized(
                detection, image_width, image_height
            )
            
            best_match = None
            best_iou = 0
            
            # Find best matching parking space
            for space in parking_spaces:
                space_box = {
                    'x': space['x'],
                    'y': space['y'],
                    'width': space['width'],
                    'height': space['height']
                }
                
                iou = self.calculate_iou(det_box, space_box)
                
                if iou > best_iou and iou >= iou_threshold:
                    best_iou = iou
                    best_match = space
            
            # Add match info to detection
            detection_copy = detection.copy()
            if best_match:
                detection_copy['parking_space_id'] = best_match['id']
                detection_copy['parking_space_name'] = best_match['name']
                detection_copy['iou'] = best_iou
                space_occupancy[best_match['id']] = True
            else:
                detection_copy['parking_space_id'] = None
                detection_copy['parking_space_name'] = None
                detection_copy['iou'] = 0
            
            matched_detections.append(detection_copy)
        
        return matched_detections, space_occupancy
    
    def update_space_occupancy(
        self,
        parking_id: str,
        camera_id: str,
        space_occupancy: Dict[str, bool]
    ) -> bool:
        """
        Update parking space occupancy status in Firebase
        
        Args:
            parking_id: Parking lot ID
            camera_id: Camera ID
            space_occupancy: Dict mapping space_id to occupancy status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from datetime import datetime
            
            for space_id, occupied in space_occupancy.items():
                # Reference to space status document
                status_ref = self.db.collection(self.PARKING_SPACE_STATUS).document(space_id)
                
                # Update or create status
                status_data = {
                    'spaceId': space_id,
                    'parkingId': parking_id,
                    'cameraId': camera_id,
                    'occupied': occupied,
                    'lastDetectionTime': datetime.now(),
                    'updatedAt': datetime.now()
                }
                
                status_ref.set(status_data, merge=True)
            
            print(f"✅ Updated occupancy for {len(space_occupancy)} spaces")
            return True
            
        except Exception as e:
            print(f"❌ Error updating space occupancy: {e}")
            return False
    
    def get_parking_summary(self, parking_id: str) -> Dict:
        """
        Get summary of parking lot occupancy
        
        Args:
            parking_id: Parking lot ID
            
        Returns:
            Dict with total, occupied, and available counts
        """
        try:
            # Query all spaces for this parking lot
            spaces_ref = self.db.collection(self.PARKING_SPACE_DEFINITIONS)
            query = spaces_ref.where("parkingId", "==", parking_id)
            total_spaces = len(list(query.stream()))
            
            # Query occupied spaces
            status_ref = self.db.collection(self.PARKING_SPACE_STATUS)
            query = status_ref.where("parkingId", "==", parking_id).where("occupied", "==", True)
            occupied_spaces = len(list(query.stream()))
            
            available_spaces = total_spaces - occupied_spaces
            
            return {
                'parking_id': parking_id,
                'total_spaces': total_spaces,
                'occupied_spaces': occupied_spaces,
                'available_spaces': available_spaces,
                'occupancy_rate': occupied_spaces / total_spaces if total_spaces > 0 else 0
            }
            
        except Exception as e:
            print(f"❌ Error getting parking summary: {e}")
            return {
                'parking_id': parking_id,
                'total_spaces': 0,
                'occupied_spaces': 0,
                'available_spaces': 0,
                'occupancy_rate': 0
            }


# Example usage
if __name__ == "__main__":
    # Initialize services
    firebase_service = FirebaseService()
    parking_service = ParkingSpaceService(firebase_service)
    
    # Example: Load parking spaces for a camera
    camera_id = "CAM001"
    spaces = parking_service.get_parking_spaces_by_camera(camera_id)
    print(f"Found {len(spaces)} parking spaces")
    
    # Example: Mock detections (would come from YOLO)
    mock_detections = [
        {'bbox': [100, 150, 200, 300], 'class': 'car', 'confidence': 0.95},
        {'bbox': [250, 150, 350, 300], 'class': 'car', 'confidence': 0.88},
    ]
    
    # Match detections to spaces
    image_width, image_height = 640, 480
    matched, occupancy = parking_service.match_detections_to_spaces(
        mock_detections, spaces, image_width, image_height
    )
    
    print(f"\nMatched detections: {len([d for d in matched if d['parking_space_id']])}")
    print(f"Occupied spaces: {sum(occupancy.values())}")
    print(f"Available spaces: {len(occupancy) - sum(occupancy.values())}")
    
    # Update Firebase
    # parking_service.update_space_occupancy("P01", camera_id, occupancy)
    
    # Get summary
    # summary = parking_service.get_parking_summary("P01")
    # print(f"\nParkig Summary: {summary}")
