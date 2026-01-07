"""
Parking Monitor Worker Service
Continuously monitors active cameras and updates parking space occupancy
"""
import asyncio
import aiohttp
from typing import Dict, List, Set
from datetime import datetime
import logging
from pathlib import Path
import sys
import concurrent.futures
import functools

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from services.firebase_service import FirebaseService
from services.parking_space_service import ParkingSpaceService
from services.ai_service import AIService
from services.detection_logger import detection_logger
from utils.tracking_config import get_tracking_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_with_timeout(func, timeout_seconds=10):
    """
    Run a blocking function with timeout using ThreadPoolExecutor
    
    Args:
        func: Function to run
        timeout_seconds: Timeout in seconds
        
    Returns:
        Result of the function or None if timeout
        
    Raises:
        TimeoutError: If function takes longer than timeout_seconds
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            logger.error(f"⏱️ Function {func.__name__} timed out after {timeout_seconds} seconds")
            raise TimeoutError(f"Function execution exceeded {timeout_seconds} seconds")


class ParkingMonitorWorker:
    """Background worker that monitors parking spaces"""
    
    def __init__(
        self,
        check_interval: float = 0.1,  # Check every 0.1 seconds (10 FPS)
        detection_url: str = "http://localhost:8069",
        update_firebase: bool = False,  # ❌ Disable slow Firebase writes for high FPS
        enable_logging: bool = True,  # ✅ Enable detection logging to .log files
        use_tracking: bool = True  # ✅ Enable ByteTrack tracking (vs detection only)
    ):
        """
        Initialize parking monitor worker
        
        Args:
            check_interval: Seconds between checks (default: 0.1 for 10 FPS)
            detection_url: URL of the main FastAPI server
            update_firebase: Whether to update Firebase (slow! disables high FPS)
            enable_logging: Whether to log detections to .log files
            use_tracking: Whether to use ByteTrack tracking (default: True)
        """
        self.check_interval = check_interval
        self.detection_url = detection_url
        self.update_firebase = update_firebase
        self.enable_logging = enable_logging
        self.use_tracking = use_tracking
        
        # Load tracking configuration
        self.tracking_config = get_tracking_config()
        if self.use_tracking:
            logger.info("🎯 ByteTrack tracking ENABLED")
            self.tracking_config.print_summary()
        else:
            logger.info("🔍 Detection only mode (tracking disabled)")
        
        # Initialize services
        self.firebase_service = FirebaseService()
        self.parking_service = ParkingSpaceService(self.firebase_service)
        self.ai_service = AIService()
        
        # Track active cameras
        self.active_cameras: Set[str] = set()
        self.camera_spaces_cache: Dict[str, List[Dict]] = {}
        self.active_cameras_cache: List[Dict] = []  # Cache for active cameras list
        self.last_cameras_refresh: float = 0  # Last time we refreshed camera list
        self.cameras_refresh_interval: float = 30.0  # Refresh camera list every 30 seconds
        
        # Running flag
        self.is_running = False
        
        # Last processed time for each camera (for rate limiting)
        self.last_processed: Dict[str, float] = {}
        self.min_process_interval: float = 0.1  # Minimum 0.1s between processing same camera (10 FPS max)
        
        # Track last worker status update time
        self.last_worker_status_update: float = 0
        self.worker_status_update_interval: float = 5.0  # Update every 5 seconds
    
    async def load_ai_models(self):
        """Load AI models asynchronously"""
        logger.info("Loading AI models...")
        await self.ai_service.load_models()
        logger.info("✅ AI models loaded")
    
    async def update_worker_status(self, camera_ids: List[str]):
        """
        Update worker status in Firebase for cameras being processed
        This lets the UI know which cameras have active workers
        
        Args:
            camera_ids: List of camera IDs being processed by this worker
        """
        try:
            import time
            current_time = time.time()
            
            # Only update every N seconds to avoid excessive Firebase writes
            if current_time - self.last_worker_status_update < self.worker_status_update_interval:
                return
            
            self.last_worker_status_update = current_time
            
            # Update each camera's worker status
            from datetime import datetime
            timestamp = datetime.now().isoformat()
            
            for camera_id in camera_ids:
                try:
                    camera_ref = self.firebase_service.db.collection('esp32_configs').document(camera_id)
                    camera_ref.update({
                        'workerActive': True,
                        'lastWorkerUpdate': timestamp
                    })
                    logger.debug(f"✅ Updated worker status for camera {camera_id}")
                except Exception as e:
                    logger.error(f"Failed to update worker status for {camera_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error updating worker status: {e}")
    
    async def clear_worker_status(self, camera_ids: List[str]):
        """
        Clear worker status when worker stops or camera is no longer being processed
        
        Args:
            camera_ids: List of camera IDs to mark as inactive
        """
        try:
            for camera_id in camera_ids:
                try:
                    camera_ref = self.firebase_service.db.collection('esp32_configs').document(camera_id)
                    camera_ref.update({
                        'workerActive': False,
                        'lastWorkerUpdate': datetime.now().isoformat()
                    })
                    logger.debug(f"🔴 Cleared worker status for camera {camera_id}")
                except Exception as e:
                    logger.error(f"Failed to clear worker status for {camera_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error clearing worker status: {e}")
    
    async def get_active_cameras(self) -> List[Dict]:
        """
        Get list of active cameras from Firebase (with caching to avoid quota issues)
        Returns cameras that have workerEnabled=true
        """
        try:
            import time
            current_time = time.time()
            
            # Use cached cameras if recent enough (within 30 seconds)
            if current_time - self.last_cameras_refresh < self.cameras_refresh_interval:
                if self.active_cameras_cache:
                    logger.debug(f"Using cached camera list ({len(self.active_cameras_cache)} cameras)")
                    return self.active_cameras_cache
            
            # Refresh camera list from Firebase
            logger.info("🔄 Refreshing camera list from Firebase...")
            
            # Query cameras that have been recently active
            # Check parkingLots collection for cameras
            try:
                logger.debug("Querying parkingLots collection...")
                
                # Wrap Firebase query in timeout (10 seconds max)
                def query_parking_lots():
                    return list(self.firebase_service.db.collection('parkingLots').stream())
                
                try:
                    # Run blocking Firebase query in thread pool with timeout
                    loop = asyncio.get_event_loop()
                    parking_lots = await asyncio.wait_for(
                        loop.run_in_executor(None, query_parking_lots),
                        timeout=10.0
                    )
                    logger.debug(f"Found {len(parking_lots)} parking lots")
                except asyncio.TimeoutError:
                    logger.error("⏱️ Firebase query timed out after 10 seconds!")
                    logger.error("💡 This usually means:")
                    logger.error("   1. No internet connection")
                    logger.error("   2. Firebase credentials are invalid")
                    logger.error("   3. Firestore security rules blocking access")
                    if self.active_cameras_cache:
                        logger.warning(f"Using cached camera list ({len(self.active_cameras_cache)} cameras)")
                        return self.active_cameras_cache
                    else:
                        logger.error("No cached cameras available, returning empty list")
                        return []
                        
            except Exception as query_error:
                logger.error(f"Firebase query failed: {query_error}")
                if "429" in str(query_error) or "quota" in str(query_error).lower():
                    logger.error("⚠️ Firebase quota exceeded! Using cached data and increasing cache interval...")
                    # Increase cache interval to 60 seconds if hitting quota limits
                    self.cameras_refresh_interval = 60.0
                if self.active_cameras_cache:
                    logger.warning(f"Using cached camera list ({len(self.active_cameras_cache)} cameras)")
                    return self.active_cameras_cache
                else:
                    logger.error("No cached cameras available, returning empty list")
                    return []
            
            active_cameras = []
            for lot_doc in parking_lots:
                try:
                    lot_data = lot_doc.to_dict()
                    
                    # Only process active parking lots
                    if lot_data.get('status') != 'active':
                        logger.debug(f"Skipping inactive parking lot: {lot_doc.id}")
                        continue
                    
                    logger.debug(f"Processing parking lot: {lot_doc.id}")
                    
                    # Get cameras for this parking lot
                    camera_ids = lot_data.get('cameras', [])
                    logger.debug(f"Parking lot {lot_doc.id} has {len(camera_ids)} cameras")
                    
                    for camera_id in camera_ids:
                        try:
                            # Get camera config from esp32_configs
                            camera_ref = self.firebase_service.db.collection('esp32_configs').document(camera_id)
                            camera_doc = camera_ref.get()
                            
                            if camera_doc.exists:
                                camera_data = camera_doc.to_dict()
                                
                                # Check if worker is enabled for this camera
                                worker_enabled = camera_data.get('workerEnabled', False)
                                
                                if not worker_enabled:
                                    logger.debug(f"Skipping camera with worker disabled: {camera_data.get('name', camera_id)}")
                                    continue
                                
                                logger.info(f"Found worker-enabled camera: {camera_data.get('name', camera_id)}")
                                active_cameras.append({
                                    'camera_id': camera_id,
                                    'parking_id': lot_doc.id,
                                    'camera_name': camera_data.get('name', camera_id),
                                    'ip_address': camera_data.get('ipAddress', ''),
                                })
                            else:
                                logger.warning(f"Camera config not found: {camera_id}")
                        except Exception as camera_error:
                            logger.error(f"Error processing camera {camera_id}: {camera_error}")
                            continue
                except Exception as lot_error:
                    logger.error(f"Error processing parking lot {lot_doc.id}: {lot_error}")
                    continue
            
            # Update cache
            self.active_cameras_cache = active_cameras
            self.last_cameras_refresh = current_time
            logger.info(f"✅ Refreshed camera list: {len(active_cameras)} active cameras")
            
            return active_cameras
            
        except Exception as e:
            logger.error(f"Error getting active cameras: {e}")
            # Return cached cameras if available, empty list otherwise
            if self.active_cameras_cache:
                logger.warning(f"Using cached camera list due to error ({len(self.active_cameras_cache)} cameras)")
                return self.active_cameras_cache
            return []
    
    async def fetch_camera_frame(self, camera_url: str) -> bytes:
        """
        Fetch a single frame from camera stream
        
        Args:
            camera_url: Camera IP address (e.g., http://localhost:5069)
            
        Returns:
            Image bytes
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Use /capture endpoint to get a single frame
                if not camera_url.startswith('http'):
                    camera_url = f'http://{camera_url}'
                
                # Ensure we're using the base URL
                base_url = camera_url.rstrip('/')
                capture_url = f'{base_url}/capture'
                
                logger.debug(f"  → Requesting: {capture_url}")
                
                async with session.get(capture_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        image_bytes = await response.read()
                        logger.debug(f"  ✅ Fetched {len(image_bytes)} bytes")
                        return image_bytes
                    else:
                        logger.error(f"  ❌ HTTP {response.status} from {capture_url}")
                        return None
        except asyncio.TimeoutError:
            logger.error(f"  ⏱️  Timeout (10s) fetching from {camera_url}")
            return None
        except aiohttp.ClientConnectorError as e:
            logger.error(f"  ❌ Connection error to {camera_url}: {e}")
            logger.error(f"     Is the ESP32 server running on this port?")
            return None
        except Exception as e:
            logger.error(f"  ❌ Error fetching from {camera_url}: {type(e).__name__}: {e}")
            return None
    
    async def detect_vehicles_in_frame(self, image_input) -> List[Dict]:
        """
        Run YOLO detection or ByteTrack tracking on a frame
        
        Args:
            image_input: Either image bytes or numpy array frame
            
        Returns:
            List of detections (with track_id if tracking enabled)
        """
        try:
            import numpy as np
            import cv2
            
            # Handle both bytes and numpy array input
            if isinstance(image_input, bytes):
                # Decode image from bytes
                nparr = np.frombuffer(image_input, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is None:
                    logger.error("Failed to decode image")
                    return []
            else:
                # Assume it's already a numpy array
                frame = image_input
            
            # Run detection or tracking based on config
            if self.use_tracking:
                # Use ByteTrack tracking
                detections = await self.ai_service.detect_objects(
                    frame,
                    conf_threshold=self.tracking_config.conf_threshold,
                    iou_threshold=self.tracking_config.iou_threshold,
                    use_tracking=True  # Enable ByteTrack
                )
                logger.debug(f"🎯 Tracked {len(detections)} objects (with track IDs)")
            else:
                # Detection only (no tracking)
                detections = await self.ai_service.detect_objects(
                    frame,
                    use_tracking=False
                )
                logger.debug(f"🔍 Detected {len(detections)} objects (no tracking)")
            
            # Filter for vehicles only
            vehicle_classes = ['car', 'truck', 'bus', 'motorcycle']
            vehicles = [d for d in detections if d.get('class') in vehicle_classes]
            
            # Log track IDs if tracking enabled
            if self.use_tracking and vehicles:
                track_ids = [d.get('track_id') for d in vehicles if d.get('track_id') is not None]
                if track_ids:
                    logger.debug(f"  Track IDs: {track_ids}")
            
            return vehicles
            
        except Exception as e:
            logger.error(f"Error detecting vehicles: {e}")
            return []
    
    async def process_camera(self, camera_info: Dict):
        """
        Process a single camera: fetch frame, detect vehicles, update occupancy
        
        Args:
            camera_info: Camera information dict
        """
        camera_id = camera_info['camera_id']
        parking_id = camera_info['parking_id']
        camera_url = camera_info['ip_address']
        camera_name = camera_info.get('camera_name', camera_id)
        
        try:
            # Rate limiting: skip if processed too recently
            import time
            current_time = time.time()
            last_time = self.last_processed.get(camera_id, 0)
            
            if current_time - last_time < self.min_process_interval:
                # Skip this frame - too soon since last processing
                return
            
            self.last_processed[camera_id] = current_time
            
            # Get parking spaces for this camera (use cache)
            if camera_id not in self.camera_spaces_cache:
                spaces = self.parking_service.get_parking_spaces_by_camera(camera_id)
                self.camera_spaces_cache[camera_id] = spaces
            else:
                spaces = self.camera_spaces_cache[camera_id]
            
            if not spaces:
                logger.warning(f"⚠️ {camera_name:<25} | No parking spaces defined")
                await self.broadcast_no_spaces_message(camera_id, camera_info.get('camera_name', camera_id))
                return
            
            # Fetch frame from camera
            frame_bytes = await self.fetch_camera_frame(camera_url)
            if not frame_bytes:
                logger.error(f"❌ {camera_name:<25} | Could not fetch frame (check ESP32)")
                return
            
            # Decode image first to check if valid
            import numpy as np
            import cv2
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                logger.error(f"❌ {camera_name:<25} | Invalid image data")
                return
            
            image_height, image_width = frame.shape[:2]
            
            # Detect vehicles (pass the decoded frame, not bytes)
            detections = await self.detect_vehicles_in_frame(frame)
            
            # Match detections to parking spaces
            matched_detections, space_occupancy = self.parking_service.match_detections_to_spaces(
                detections=detections,
                parking_spaces=spaces,
                image_width=image_width,
                image_height=image_height,
                iou_threshold=0.3,  # Lower threshold works better with IoA
                use_ioa=True,  # ✅ Use IoA instead of IoU
                ioa_mode='detection'  # What % of car is in parking space?
            )
            
            # Beautiful aligned log
            num_vehicles = len(detections)
            occupied = sum(space_occupancy.values())
            total_spaces = len(space_occupancy)
            
            logger.info(f"📹 {camera_name:<25} | {num_vehicles:2d} vehicles | {occupied:2d}/{total_spaces:2d} occupied")
            
            # Draw detections and parking spaces on frame for broadcasting
            annotated_frame = self.draw_detections_on_frame(
                frame=frame.copy(),
                detections=detections,
                parking_spaces=spaces,
                space_occupancy=space_occupancy,
                image_width=image_width,
                image_height=image_height
            )
            
            # Prepare detailed tracking information for backend
            tracking_info = {
                "vehicle_count": len(detections),
                "occupied_spaces": sum(space_occupancy.values()),
                "total_spaces": len(spaces),
                "timestamp": datetime.now().isoformat(),
                "detections": [
                    {
                        "class": det.get('class'),
                        "confidence": det.get('confidence'),
                        "bbox": det.get('bbox'),  # [x, y, width, height]
                        "track_id": det.get('track_id'),  # None if tracking disabled
                        "center": [
                            det['bbox'][0] + det['bbox'][2] / 2,
                            det['bbox'][1] + det['bbox'][3] / 2
                        ]
                    }
                    for det in detections
                ],
                "space_occupancy": [
                    {
                        "space_id": space['id'],
                        "space_name": space.get('name', space['id']),
                        "is_occupied": space_occupancy.get(space['id'], False),
                        "bbox": {
                            "x": space['x'],
                            "y": space['y'],
                            "width": space['width'],
                            "height": space['height']
                        }
                    }
                    for space in spaces
                ],
                "matched_detections": [
                    {
                        "detection": {
                            "class": det.get('class'),
                            "confidence": det.get('confidence'),
                            "bbox": det.get('bbox'),
                            "track_id": det.get('track_id')
                        },
                        "space_id": det.get('parking_space_id'),
                        "space_name": det.get('parking_space_name'),
                        "iou": det.get('iou', 0)
                    }
                    for det in matched_detections
                    if det.get('parking_space_id') is not None
                ],
                "tracking_enabled": self.use_tracking
            }
            
            # Broadcast annotated frame + tracking info to backend
            await self.broadcast_frame_to_viewers(
                camera_id=camera_id,
                frame=annotated_frame,
                metadata=tracking_info
            )
            
            # Log detection results to file (async, non-blocking)
            if self.enable_logging:
                await detection_logger.log_detection(
                    camera_id=camera_id,
                    detections=detections,
                    parking_spaces=spaces,
                    space_occupancy=space_occupancy,
                    metadata={
                        "frame_size": f"{image_width}x{image_height}",
                        "parking_id": parking_id,
                        "camera_name": camera_info.get('camera_name', camera_id)
                    }
                )
            
            # Update Firebase with occupancy status (SLOW! Only if enabled)
            if self.update_firebase:
                success = self.parking_service.update_space_occupancy(
                    parking_id=parking_id,
                    camera_id=camera_id,
                    space_occupancy=space_occupancy
                )
                
                if success:
                    occupied_count = sum(space_occupancy.values())
                    total_count = len(space_occupancy)
                    logger.debug(f"✅ Updated Firebase occupancy for camera {camera_id}: {occupied_count}/{total_count} occupied")
                else:
                    logger.error(f"Failed to update Firebase occupancy for camera {camera_id}")
            
        except Exception as e:
            logger.error(f"Error processing camera {camera_id}: {e}", exc_info=True)
    
    def draw_detections_on_frame(
        self,
        frame,
        detections: List[Dict],
        parking_spaces: List[Dict],
        space_occupancy: Dict[str, bool],
        image_width: int,
        image_height: int
    ):
        """
        Draw detection boxes, tracking info, and parking spaces on frame
        
        Args:
            frame: OpenCV image (numpy array)
            detections: List of vehicle detections (may include track_id)
            parking_spaces: List of parking space definitions
            space_occupancy: Dict mapping space_id to occupied status
            image_width: Frame width
            image_height: Frame height
        
        Returns:
            Annotated frame (numpy array)
        """
        import cv2
        import numpy as np
        
        # If tracking is enabled, use AI service's draw function for better visualization
        if self.use_tracking:
            # Draw detections with tracking trails
            frame = self.ai_service.draw_detections(
                frame,
                detections,
                show_trails=self.tracking_config.get('visualization.show_trail', True),
                show_track_id=self.tracking_config.get('visualization.show_track_id', True)
            )
        else:
            # Draw vehicle detections (simple boxes)
            for detection in detections:
                bbox = detection['bbox']
                x, y, w, h = bbox
                x1, y1 = int(x), int(y)
                x2, y2 = int(x + w), int(y + h)
                
                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                
                # Draw label
                label = f"{detection.get('class', 'vehicle')}: {detection.get('confidence', 0):.2f}"
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                           0.5, (255, 0, 0), 1, cv2.LINE_AA)
        
        # Draw parking spaces (rectangles from normalized x, y, width, height)
        for space in parking_spaces:
            space_id = space['id']
            is_occupied = space_occupancy.get(space_id, False)
            
            # Convert normalized coordinates to pixels
            x = int(space['x'] * image_width)
            y = int(space['y'] * image_height)
            w = int(space['width'] * image_width)
            h = int(space['height'] * image_height)
            
            x1, y1 = x, y
            x2, y2 = x + w, y + h
            
            # Color: Red if occupied, Green if free
            color = (0, 0, 255) if is_occupied else (0, 255, 0)
            
            # Draw rectangle (thicker for better visibility)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            
            # Draw label with background
            label = f"{space.get('name', space_id)}: {'Occupied' if is_occupied else 'Free'}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            
            # Draw text background
            cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 6, y1), color, -1)
            
            # Draw text
            cv2.putText(frame, label, (x1 + 3, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.6, (255, 255, 255), 2, cv2.LINE_AA)
        
        return frame
    
    async def broadcast_frame_to_viewers(self, camera_id: str, frame, metadata: dict):
        """
        Send annotated frame to FastAPI server which will broadcast to viewers
        
        Args:
            camera_id: Camera identifier
            frame: Annotated frame (numpy array)
            metadata: Frame metadata
        """
        import cv2
        import base64
        
        try:
            # Encode frame to JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # Send to FastAPI server via HTTP POST
            async with aiohttp.ClientSession() as session:
                broadcast_url = f'{self.detection_url}/api/broadcast-detection'
                payload = {
                    'camera_id': camera_id,
                    'frame_base64': frame_base64,
                    'metadata': metadata
                }
                
                async with session.post(broadcast_url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        logger.debug(f"📺 Sent frame to FastAPI for camera {camera_id}")
                    else:
                        logger.warning(f"Failed to send frame to FastAPI: HTTP {response.status}")
        
        except asyncio.TimeoutError:
            logger.warning(f"Timeout sending frame to FastAPI")
        except Exception as e:
            logger.error(f"Error broadcasting frame: {e}")
    
    async def broadcast_no_spaces_message(self, camera_id: str, camera_name: str):
        """
        Broadcast an error message when camera has no parking spaces
        
        Args:
            camera_id: Camera identifier
            camera_name: Camera display name
        """
        import cv2
        import base64
        import numpy as np
        
        try:
            # Create a simple error image
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            img[:] = (40, 40, 40)  # Dark gray background
            
            # Add text
            text1 = "No Parking Spaces Defined"
            text2 = f"Camera: {camera_name}"
            text3 = "Please add parking spaces in the editor"
            
            cv2.putText(img, text1, (80, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 2)
            cv2.putText(img, text2, (120, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
            cv2.putText(img, text3, (60, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
            
            # Encode to JPEG
            _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # Send to FastAPI
            async with aiohttp.ClientSession() as session:
                broadcast_url = f'{self.detection_url}/api/broadcast-detection'
                payload = {
                    'camera_id': camera_id,
                    'frame_base64': frame_base64,
                    'metadata': {
                        'error': True,
                        'message': 'No parking spaces defined',
                        'vehicle_count': 0,
                        'occupied_spaces': 0,
                        'total_spaces': 0,
                        'timestamp': datetime.now().isoformat()
                    }
                }
                
                async with session.post(broadcast_url, json=payload, timeout=aiohttp.ClientTimeout(total=2)) as response:
                    if response.status == 200:
                        logger.debug(f"📺 Sent no-spaces message for camera {camera_id}")
        
        except Exception as e:
            logger.debug(f"Error sending no-spaces message: {e}")
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("=" * 80)
        logger.info("🚀 PARKING MONITOR WORKER STARTED")
        logger.info("=" * 80)
        logger.info(f"⏱️  Target FPS: {int(1/self.min_process_interval)} FPS per camera")
        logger.info(f"🔥 Firebase updates: {'ENABLED' if self.update_firebase else 'DISABLED (recommended for high FPS)'}")
        logger.info(f"📝 Detection logging: {'ENABLED' if self.enable_logging else 'DISABLED'}")
        logger.info(f"🎯 ByteTrack tracking: {'ENABLED' if self.use_tracking else 'DISABLED'}")
        logger.info(f"🌐 FastAPI server: {self.detection_url}")
        logger.info(f"🐛 Debug UI: {self.detection_url}/static/tracking_debug.html")
        logger.info("=" * 80)
        
        self.is_running = True
        currently_processing_cameras: Set[str] = set()
        loop_count = 0
        
        while self.is_running:
            try:
                loop_count += 1
                
                # Log status every 100 loops
                if loop_count % 100 == 0:
                    logger.info(f"📊 Worker alive - Loop #{loop_count} | Processing {len(currently_processing_cameras)} cameras")
                
                # Get active cameras (cache this to avoid repeated Firebase calls)
                active_cameras = await self.get_active_cameras()
                
                if not active_cameras:
                    # Clear status for previously processed cameras
                    if currently_processing_cameras:
                        logger.warning(f"❌ No active cameras found. Clearing status for {len(currently_processing_cameras)} cameras...")
                        await self.clear_worker_status(list(currently_processing_cameras))
                        currently_processing_cameras.clear()
                    
                    if loop_count % 10 == 0:  # Log every 10 loops when no cameras
                        logger.warning("⚠️  No active cameras with workerEnabled=true. Waiting...")
                        logger.info("💡 Enable worker in Firebase: parkingLots > cameras > workerEnabled = true")
                    await asyncio.sleep(1.0)  # Wait longer if no cameras
                    continue
                
                # Log camera info when cameras change
                camera_ids = [cam['camera_id'] for cam in active_cameras]
                if set(camera_ids) != currently_processing_cameras:
                    logger.info("=" * 80)
                    logger.info(f"📹 PROCESSING {len(active_cameras)} ACTIVE CAMERAS:")
                    for cam in active_cameras:
                        logger.info(f"   • {cam['camera_name']} (ID: {cam['camera_id']})")
                        logger.info(f"     URL: {cam['ip_address']}")
                        logger.info(f"     Parking: {cam['parking_id']}")
                    logger.info(f"🐛 View tracking data: {self.detection_url}/static/tracking_debug.html")
                    logger.info("=" * 80)
                
                # Update worker status in Firebase
                await self.update_worker_status(camera_ids)
                currently_processing_cameras = set(camera_ids)
                
                # Process each camera (rate limiting is handled inside process_camera)
                tasks = [self.process_camera(camera) for camera in active_cameras]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Short sleep to avoid busy-waiting, but fast enough for high FPS
                await asyncio.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping...")
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                # Wait a bit before retrying
                await asyncio.sleep(1.0)
        
        # Clear worker status on shutdown
        if currently_processing_cameras:
            logger.info("Clearing worker status for all cameras...")
            await self.clear_worker_status(list(currently_processing_cameras))

    
    async def start(self):
        """Start the worker"""
        try:
            # Load AI models first
            await self.load_ai_models()
            
            # Start monitoring loop
            await self.monitor_loop()
            
        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
        except Exception as e:
            logger.error(f"Fatal error in worker: {e}", exc_info=True)
        finally:
            logger.info("Cleaning up...")
            if self.ai_service:
                self.ai_service.cleanup()
    
    def stop(self):
        """Stop the worker"""
        logger.info("Stopping worker...")
        self.is_running = False


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Parking Monitor Worker')
    parser.add_argument('--interval', type=float, default=0.1, 
                       help='Check interval in seconds (default: 0.1 for 10 FPS)')
    parser.add_argument('--fps', type=int, default=10, 
                       help='Target FPS per camera (default: 10)')
    parser.add_argument('--detection-url', type=str, default='http://localhost:8069', 
                       help='FastAPI server URL (default: http://localhost:8069)')
    parser.add_argument('--update-firebase', action='store_true', 
                       help='Enable Firebase updates (SLOW! reduces FPS to ~0.3)')
    parser.add_argument('--no-logging', action='store_true', 
                       help='Disable detection logging to .log files')
    parser.add_argument('--no-tracking', action='store_true', 
                       help='Disable ByteTrack tracking (detection only)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Calculate interval from FPS if provided
    if args.fps:
        check_interval = 1.0 / args.fps
    else:
        check_interval = args.interval
    
    # Set log level
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start worker
    worker = ParkingMonitorWorker(
        check_interval=check_interval,
        detection_url=args.detection_url,
        update_firebase=args.update_firebase,
        enable_logging=not args.no_logging,
        use_tracking=not args.no_tracking
    )
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Shutting down worker...")
        worker.stop()


if __name__ == "__main__":
    # Run the worker
    asyncio.run(main())
