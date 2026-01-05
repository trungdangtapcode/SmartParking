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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from services.firebase_service import FirebaseService
from services.parking_space_service import ParkingSpaceService
from services.ai_service import AIService
from services.detection_logger import detection_logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ParkingMonitorWorker:
    """Background worker that monitors parking spaces"""
    
    def __init__(
        self,
        check_interval: float = 0.1,  # Check every 0.1 seconds (10 FPS)
        detection_url: str = "http://localhost:8069",
        update_firebase: bool = False,  # ❌ Disable slow Firebase writes for high FPS
        enable_logging: bool = True  # ✅ Enable detection logging to .log files
    ):
        """
        Initialize parking monitor worker
        
        Args:
            check_interval: Seconds between checks (default: 0.1 for 10 FPS)
            detection_url: URL of the main FastAPI server
            update_firebase: Whether to update Firebase (slow! disables high FPS)
            enable_logging: Whether to log detections to .log files
        """
        self.check_interval = check_interval
        self.detection_url = detection_url
        self.update_firebase = update_firebase
        self.enable_logging = enable_logging
        
        # Initialize services
        self.firebase_service = FirebaseService()
        self.parking_service = ParkingSpaceService(self.firebase_service)
        self.ai_service = AIService()
        
        # Track active cameras
        self.active_cameras: Set[str] = set()
        self.camera_spaces_cache: Dict[str, List[Dict]] = {}
        
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
        Get list of active cameras from Firebase
        Returns cameras that have workerEnabled=true
        """
        try:
            # Query cameras that have been recently active
            # Check parkingLots collection for cameras
            parking_lots = self.firebase_service.db.collection('parkingLots').stream()
            
            active_cameras = []
            for lot_doc in parking_lots:
                lot_data = lot_doc.to_dict()
                
                # Only process active parking lots
                if lot_data.get('status') != 'active':
                    logger.debug(f"Skipping inactive parking lot: {lot_doc.id}")
                    continue
                
                # Get cameras for this parking lot
                camera_ids = lot_data.get('cameras', [])
                
                for camera_id in camera_ids:
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
            
            return active_cameras
            
        except Exception as e:
            logger.error(f"Error getting active cameras: {e}")
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
                
                logger.debug(f"Fetching frame from: {capture_url}")
                
                async with session.get(capture_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        image_bytes = await response.read()
                        logger.debug(f"Fetched {len(image_bytes)} bytes from camera")
                        return image_bytes
                    else:
                        logger.warning(f"Failed to fetch frame from {capture_url}: HTTP {response.status}")
                        return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching frame from {camera_url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching frame from {camera_url}: {e}")
            return None
    
    async def detect_vehicles_in_frame(self, image_input) -> List[Dict]:
        """
        Run YOLO detection on a frame
        
        Args:
            image_input: Either image bytes or numpy array frame
            
        Returns:
            List of detections
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
            
            # Run detection
            detections = await self.ai_service.detect_objects(frame)
            
            # Filter for vehicles only
            vehicle_classes = ['car', 'truck', 'bus', 'motorcycle']
            vehicles = [d for d in detections if d.get('class') in vehicle_classes]
            
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
        
        try:
            # Rate limiting: skip if processed too recently
            import time
            current_time = time.time()
            last_time = self.last_processed.get(camera_id, 0)
            
            if current_time - last_time < self.min_process_interval:
                # Skip this frame - too soon since last processing
                return
            
            self.last_processed[camera_id] = current_time
            
            logger.debug(f"Processing camera: {camera_info['camera_name']} ({camera_id})")

            
            # Get parking spaces for this camera (use cache)
            if camera_id not in self.camera_spaces_cache:
                spaces = self.parking_service.get_parking_spaces_by_camera(camera_id)
                self.camera_spaces_cache[camera_id] = spaces
                logger.info(f"✅ Loaded {len(spaces)} parking spaces for camera {camera_id}")
            else:
                spaces = self.camera_spaces_cache[camera_id]
            
            if not spaces:
                logger.warning(f"No parking spaces defined for camera {camera_id}")
                # Send an info message to UI about missing parking spaces
                await self.broadcast_no_spaces_message(camera_id, camera_info.get('camera_name', camera_id))
                return
            
            # Fetch frame from camera
            frame_bytes = await self.fetch_camera_frame(camera_url)
            if not frame_bytes:
                logger.warning(f"Could not fetch frame from {camera_url}")
                return
            
            # Decode image first to check if valid
            import numpy as np
            import cv2
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                logger.error(f"Failed to decode image from {camera_url} - invalid image data")
                return
            
            image_height, image_width = frame.shape[:2]
            logger.debug(f"Frame dimensions: {image_width}x{image_height}")
            
            # Detect vehicles (pass the decoded frame, not bytes)
            detections = await self.detect_vehicles_in_frame(frame)
            logger.debug(f"🚗 Detected {len(detections)} vehicles in camera {camera_id}")
            
            # Match detections to parking spaces
            matched_detections, space_occupancy = self.parking_service.match_detections_to_spaces(
                detections=detections,
                parking_spaces=spaces,
                image_width=image_width,
                image_height=image_height,
                iou_threshold=0.5
            )
            
            # Draw detections and parking spaces on frame for broadcasting
            annotated_frame = self.draw_detections_on_frame(
                frame=frame.copy(),
                detections=detections,
                parking_spaces=spaces,
                space_occupancy=space_occupancy,
                image_width=image_width,
                image_height=image_height
            )
            
            # Broadcast annotated frame to viewers
            await self.broadcast_frame_to_viewers(
                camera_id=camera_id,
                frame=annotated_frame,
                metadata={
                    "vehicle_count": len(detections),
                    "occupied_spaces": sum(space_occupancy.values()),
                    "total_spaces": len(spaces),
                    "timestamp": datetime.now().isoformat()
                }
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
        Draw detection boxes and parking spaces on frame
        
        Args:
            frame: OpenCV image (numpy array)
            detections: List of vehicle detections
            parking_spaces: List of parking space definitions
            space_occupancy: Dict mapping space_id to occupied status
            image_width: Frame width
            image_height: Frame height
        
        Returns:
            Annotated frame (numpy array)
        """
        import cv2
        import numpy as np
        
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
            
            # Draw rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{space.get('name', space_id)}: {'Occupied' if is_occupied else 'Free'}"
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, color, 1, cv2.LINE_AA)
        
        # Draw vehicle detections
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
        logger.info("🚀 Starting parking monitor worker...")
        logger.info(f"⏱️  Target FPS: {int(1/self.min_process_interval)} FPS per camera")
        
        self.is_running = True
        currently_processing_cameras: Set[str] = set()
        
        while self.is_running:
            try:
                # Get active cameras (cache this to avoid repeated Firebase calls)
                active_cameras = await self.get_active_cameras()
                
                if not active_cameras:
                    # Clear status for previously processed cameras
                    if currently_processing_cameras:
                        await self.clear_worker_status(list(currently_processing_cameras))
                        currently_processing_cameras.clear()
                    
                    logger.warning("No active cameras found. Waiting...")
                    await asyncio.sleep(1.0)  # Wait longer if no cameras
                    continue
                
                # Update worker status in Firebase
                camera_ids = [cam['camera_id'] for cam in active_cameras]
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
        enable_logging=not args.no_logging
    )
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Shutting down worker...")
        worker.stop()


if __name__ == "__main__":
    # Run the worker
    asyncio.run(main())
