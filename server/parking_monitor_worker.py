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
        check_interval: int = 5,  # Check every 5 seconds
        detection_url: str = "http://localhost:8069"
    ):
        """
        Initialize parking monitor worker
        
        Args:
            check_interval: Seconds between checks
            detection_url: URL of the main FastAPI server
        """
        self.check_interval = check_interval
        self.detection_url = detection_url
        
        # Initialize services
        self.firebase_service = FirebaseService()
        self.parking_service = ParkingSpaceService(self.firebase_service)
        self.ai_service = AIService()
        
        # Track active cameras
        self.active_cameras: Set[str] = set()
        self.camera_spaces_cache: Dict[str, List[Dict]] = {}
        
        # Running flag
        self.is_running = False
    
    async def load_ai_models(self):
        """Load AI models asynchronously"""
        logger.info("Loading AI models...")
        await self.ai_service.load_models()
        logger.info("✅ AI models loaded")
    
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
            logger.info(f"Processing camera: {camera_info['camera_name']} ({camera_id})")
            
            # Get parking spaces for this camera (use cache)
            if camera_id not in self.camera_spaces_cache:
                spaces = self.parking_service.get_parking_spaces_by_camera(camera_id)
                self.camera_spaces_cache[camera_id] = spaces
                logger.info(f"Loaded {len(spaces)} parking spaces for camera {camera_id}")
            else:
                spaces = self.camera_spaces_cache[camera_id]
            
            if not spaces:
                logger.warning(f"No parking spaces defined for camera {camera_id}")
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
            logger.info(f"Detected {len(detections)} vehicles in camera {camera_id}")
            
            # Match detections to parking spaces
            matched_detections, space_occupancy = self.parking_service.match_detections_to_spaces(
                detections=detections,
                parking_spaces=spaces,
                image_width=image_width,
                image_height=image_height,
                iou_threshold=0.5
            )
            
            # Update Firebase with occupancy status
            success = self.parking_service.update_space_occupancy(
                parking_id=parking_id,
                camera_id=camera_id,
                space_occupancy=space_occupancy
            )
            
            if success:
                occupied_count = sum(space_occupancy.values())
                total_count = len(space_occupancy)
                logger.info(f"✅ Updated occupancy for camera {camera_id}: {occupied_count}/{total_count} occupied")
            else:
                logger.error(f"Failed to update occupancy for camera {camera_id}")
            
        except Exception as e:
            logger.error(f"Error processing camera {camera_id}: {e}", exc_info=True)
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("🚀 Starting parking monitor worker...")
        logger.info(f"⏱️  Check interval: {self.check_interval} seconds")
        
        self.is_running = True
        
        while self.is_running:
            try:
                # Get active cameras
                active_cameras = await self.get_active_cameras()
                
                if not active_cameras:
                    logger.warning("No active cameras found. Waiting...")
                else:
                    logger.info(f"Found {len(active_cameras)} active cameras")
                    
                    # Process each camera
                    tasks = [self.process_camera(camera) for camera in active_cameras]
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Wait before next check
                logger.info(f"Waiting {self.check_interval} seconds before next check...")
                await asyncio.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping...")
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                # Wait a bit before retrying
                await asyncio.sleep(self.check_interval)
    
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
    parser.add_argument('--interval', type=int, default=5, help='Check interval in seconds (default: 5)')
    parser.add_argument('--detection-url', type=str, default='http://localhost:8069', 
                       help='FastAPI server URL (default: http://localhost:8069)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set log level
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start worker
    worker = ParkingMonitorWorker(
        check_interval=args.interval,
        detection_url=args.detection_url
    )
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Shutting down worker...")
        worker.stop()


if __name__ == "__main__":
    # Run the worker
    asyncio.run(main())
