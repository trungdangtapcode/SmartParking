"""
Parking Lot Analysis Service
Analyzes parking lot occupancy and provides statistics
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from services.firebase_service import FirebaseService
from services.parking_space_service import ParkingSpaceService
from utils.tracking_config import get_tracking_config

logger = logging.getLogger(__name__)


class ParkingLotAnalysisService:
    """Service for analyzing parking lot occupancy and statistics"""
    
    def __init__(self, firebase_service: FirebaseService = None):
        """
        Initialize parking lot analysis service
        
        Args:
            firebase_service: Firebase service instance (creates new if None)
        """
        self.firebase_service = firebase_service or FirebaseService()
        self.parking_service = ParkingSpaceService(self.firebase_service)
        
        # Load config
        self.config = get_tracking_config()
        self.iou_threshold = self.config.get('parking.iou_threshold', 0.5)
        self.min_overlap_ratio = self.config.get('parking.min_overlap_ratio', 0.3)
        self.confidence_threshold = self.config.get('parking.confidence_threshold', 0.3)
        
        logger.info(f"✅ Parking lot analysis service initialized")
        logger.info(f"   IOU threshold: {self.iou_threshold}")
        logger.info(f"   Min overlap ratio: {self.min_overlap_ratio}")
        logger.info(f"   Confidence threshold: {self.confidence_threshold}")
    
    def analyze_parking_lot(
        self,
        parking_id: str,
        detections: List[Dict],
        image_width: int,
        image_height: int
    ) -> Dict:
        """
        Analyze parking lot occupancy based on detections
        
        Args:
            parking_id: Parking lot ID
            detections: List of vehicle detections
            image_width: Image width in pixels
            image_height: Image height in pixels
            
        Returns:
            Dict with analysis results
        """
        try:
            # Get all parking spaces in this lot
            spaces = self._get_parking_spaces_for_lot(parking_id)
            
            if not spaces:
                return {
                    "parking_id": parking_id,
                    "error": "No parking spaces found",
                    "total_spaces": 0,
                    "occupied_spaces": 0,
                    "available_spaces": 0,
                    "occupancy_rate": 0,
                    "spaces": []
                }
            
            # Filter detections by confidence
            filtered_detections = [
                d for d in detections
                if d.get('confidence', 0) >= self.confidence_threshold
            ]
            
            # Match detections to spaces
            space_analysis = []
            occupied_count = 0
            
            for space in spaces:
                # Check if space is occupied
                occupying_vehicle = self._find_occupying_vehicle(
                    space,
                    filtered_detections,
                    image_width,
                    image_height
                )
                
                is_occupied = occupying_vehicle is not None
                if is_occupied:
                    occupied_count += 1
                
                space_info = {
                    "space_id": space['id'],
                    "space_name": space.get('name', space['id']),
                    "camera_id": space.get('cameraId', 'unknown'),
                    "is_occupied": is_occupied,
                    "bbox": {
                        "x": space['x'],
                        "y": space['y'],
                        "width": space['width'],
                        "height": space['height']
                    }
                }
                
                if occupying_vehicle:
                    space_info["occupying_vehicle"] = {
                        "class": occupying_vehicle.get('class'),
                        "confidence": occupying_vehicle.get('confidence'),
                        "track_id": occupying_vehicle.get('track_id'),
                        "bbox": occupying_vehicle.get('bbox'),
                        "iou": occupying_vehicle.get('_iou')  # IOU calculated during matching
                    }
                
                space_analysis.append(space_info)
            
            total_spaces = len(spaces)
            available_spaces = total_spaces - occupied_count
            occupancy_rate = (occupied_count / total_spaces * 100) if total_spaces > 0 else 0
            
            return {
                "parking_id": parking_id,
                "timestamp": datetime.now().isoformat(),
                "total_spaces": total_spaces,
                "occupied_spaces": occupied_count,
                "available_spaces": available_spaces,
                "occupancy_rate": round(occupancy_rate, 2),
                "vehicle_count": len(filtered_detections),
                "spaces": space_analysis,
                "config": {
                    "iou_threshold": self.iou_threshold,
                    "min_overlap_ratio": self.min_overlap_ratio,
                    "confidence_threshold": self.confidence_threshold
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing parking lot {parking_id}: {e}", exc_info=True)
            return {
                "parking_id": parking_id,
                "error": str(e),
                "total_spaces": 0,
                "occupied_spaces": 0,
                "available_spaces": 0,
                "occupancy_rate": 0
            }
    
    def analyze_all_parking_lots(self, detections_by_camera: Dict[str, List[Dict]]) -> Dict:
        """
        Analyze all parking lots based on detections from multiple cameras
        
        Args:
            detections_by_camera: Dict mapping camera_id to list of detections
            
        Returns:
            Dict with analysis for all parking lots
        """
        try:
            # Get all parking lots
            parking_lots = self._get_all_parking_lots()
            
            results = {
                "timestamp": datetime.now().isoformat(),
                "parking_lots": [],
                "summary": {
                    "total_lots": 0,
                    "total_spaces": 0,
                    "total_occupied": 0,
                    "total_available": 0,
                    "average_occupancy_rate": 0
                }
            }
            
            total_occupancy_sum = 0
            
            for lot in parking_lots:
                lot_id = lot['id']
                
                # Collect detections from all cameras in this lot
                lot_detections = []
                for camera_id in lot.get('cameras', []):
                    if camera_id in detections_by_camera:
                        lot_detections.extend(detections_by_camera[camera_id])
                
                # Analyze this lot (assuming standard resolution, adjust if needed)
                lot_analysis = self.analyze_parking_lot(
                    parking_id=lot_id,
                    detections=lot_detections,
                    image_width=1920,  # Default resolution
                    image_height=1080
                )
                
                results["parking_lots"].append(lot_analysis)
                
                # Update summary
                results["summary"]["total_lots"] += 1
                results["summary"]["total_spaces"] += lot_analysis.get("total_spaces", 0)
                results["summary"]["total_occupied"] += lot_analysis.get("occupied_spaces", 0)
                results["summary"]["total_available"] += lot_analysis.get("available_spaces", 0)
                total_occupancy_sum += lot_analysis.get("occupancy_rate", 0)
            
            # Calculate average occupancy rate
            if results["summary"]["total_lots"] > 0:
                results["summary"]["average_occupancy_rate"] = round(
                    total_occupancy_sum / results["summary"]["total_lots"], 2
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error analyzing all parking lots: {e}", exc_info=True)
            return {
                "error": str(e),
                "parking_lots": [],
                "summary": {}
            }
    
    def _get_parking_spaces_for_lot(self, parking_id: str) -> List[Dict]:
        """Get all parking spaces for a parking lot"""
        try:
            spaces_ref = self.firebase_service.db.collection('parkingSpaces')
            query = spaces_ref.where('parkingId', '==', parking_id).stream()
            
            spaces = []
            for doc in query:
                space_data = doc.to_dict()
                space_data['id'] = doc.id
                spaces.append(space_data)
            
            return spaces
            
        except Exception as e:
            logger.error(f"Error getting parking spaces for lot {parking_id}: {e}")
            return []
    
    def _get_all_parking_lots(self) -> List[Dict]:
        """Get all active parking lots"""
        try:
            lots_ref = self.firebase_service.db.collection('parkingLots')
            query = lots_ref.where('status', '==', 'active').stream()
            
            lots = []
            for doc in query:
                lot_data = doc.to_dict()
                lot_data['id'] = doc.id
                lots.append(lot_data)
            
            return lots
            
        except Exception as e:
            logger.error(f"Error getting parking lots: {e}")
            return []
    
    def _find_occupying_vehicle(
        self,
        space: Dict,
        detections: List[Dict],
        image_width: int,
        image_height: int
    ) -> Optional[Dict]:
        """
        Find vehicle occupying a parking space
        
        Args:
            space: Parking space definition (normalized coordinates)
            detections: List of vehicle detections
            image_width: Image width
            image_height: Image height
            
        Returns:
            Detection dict if space is occupied, None otherwise
        """
        best_match = None
        best_iou = 0
        
        for detection in detections:
            # Convert detection to normalized coordinates
            det_box = self.parking_service.convert_detection_to_normalized(
                detection, image_width, image_height
            )
            
            space_box = {
                'x': space['x'],
                'y': space['y'],
                'width': space['width'],
                'height': space['height']
            }
            
            # Calculate IOU
            iou = self.parking_service.calculate_iou(det_box, space_box)
            
            # Check if this is the best match so far
            if iou > best_iou and iou >= self.iou_threshold:
                best_iou = iou
                best_match = detection.copy()
                best_match['_iou'] = iou
        
        return best_match
    
    def get_empty_spaces(self, parking_id: str) -> List[Dict]:
        """
        Get list of empty parking spaces in a parking lot
        
        Args:
            parking_id: Parking lot ID
            
        Returns:
            List of empty space dictionaries
        """
        # This would need current detection data - typically called after analyze_parking_lot
        # For now, return all spaces and let caller filter by is_occupied
        spaces = self._get_parking_spaces_for_lot(parking_id)
        return spaces
    
    def get_occupied_spaces(self, parking_id: str) -> List[Dict]:
        """
        Get list of occupied parking spaces in a parking lot
        
        Args:
            parking_id: Parking lot ID
            
        Returns:
            List of occupied space dictionaries
        """
        # Similar to get_empty_spaces - needs current detection data
        spaces = self._get_parking_spaces_for_lot(parking_id)
        return spaces


# Singleton instance
_parking_lot_analysis_service = None

def get_parking_lot_analysis_service() -> ParkingLotAnalysisService:
    """Get or create singleton parking lot analysis service"""
    global _parking_lot_analysis_service
    if _parking_lot_analysis_service is None:
        _parking_lot_analysis_service = ParkingLotAnalysisService()
    return _parking_lot_analysis_service
