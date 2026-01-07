# Smart Parking System - Backend Architecture

## 🔧 Backend Overview

The backend is a FastAPI-based Python application that handles AI processing, video streaming, and data management for the Smart Parking System.

## 🛠️ Technology Stack

### Core Technologies
- **Framework**: FastAPI (Python 3.10+)
- **AI/ML**: 
  - Ultralytics YOLO (YOLOv8/v11)
  - ByteTrack (Multi-object tracking)
  - Fast-ALPR (License plate recognition)
- **Computer Vision**: OpenCV (cv2)
- **Deep Learning**: PyTorch with CUDA
- **Database**: Firebase Admin SDK (Firestore)
- **Async**: asyncio, aiohttp
- **Video**: MJPEG streaming
- **Environment**: Conda (scheduler environment)

### Key Dependencies
```python
# requirements.txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
ultralytics>=8.0.0
torch>=2.0.0
opencv-python>=4.8.0
fast-alpr>=1.0.0
firebase-admin>=6.0.0
python-dotenv>=1.0.0
aiohttp>=3.9.0
pyyaml>=6.0
```

## 📁 Backend Structure

```
server/
├── main_fastapi.py                   # Main application entry (169 lines)
├── parking_monitor_worker.py         # Background worker (898 lines)
│
├── services/                         # Business logic layer
│   ├── ai_service.py                 # AI detection & tracking (651 lines)
│   ├── firebase_service.py           # Firestore operations (450 lines)
│   ├── parking_space_service.py      # Parking logic
│   ├── stream_broadcaster.py         # WebSocket broadcasting
│   ├── detection_broadcaster.py      # Detection streaming
│   └── detection_logger.py           # File-based logging
│
├── routers/                          # API endpoints layer
│   ├── health.py                     # Health check
│   ├── streams.py                    # Video streaming
│   ├── websocket_streams.py          # WebSocket streams
│   ├── ai_detection.py               # AI endpoints
│   ├── firebase.py                   # Firebase endpoints
│   ├── esp32.py                      # ESP32 hardware
│   ├── user_config.py                # User settings
│   ├── detection_viewer.py           # Detection viewer WebSocket
│   ├── worker_broadcast.py           # Worker endpoints
│   ├── detection_logs.py             # Log file access
│   └── tracking_debug.py             # Debug endpoints
│
├── middleware/                       # Custom middleware
│   └── disconnect_watcher.py         # Client disconnect detection
│
├── models/                           # Data models
│   └── stream_tracking.py            # Connection tracking
│
├── config/                           # Configuration
│   └── tracking_config.yaml          # ByteTrack settings
│
├── utils/                            # Utility functions
│   └── tracking_config.py            # Config loader
│
├── logs/                             # Log files
│   └── detections_*.log              # Detection logs
│
├── static/                           # Static files
│
├── .env                              # Environment variables
├── requirements.txt                  # Python dependencies
└── environment.yml                   # Conda environment
```

## 🚀 Application Lifecycle

### Main Application (`main_fastapi.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager - initialize on startup, cleanup on shutdown"""
    global ai_service, firebase_service, esp32_client
    
    # STARTUP
    print("🚀 Starting FastAPI SmartParking Server...")
    
    # 1. Load AI models (YOLO, ALPR)
    ai_service = AIService()
    await ai_service.load_models()
    
    # 2. Initialize Firebase Admin SDK
    firebase_service = FirebaseService()
    
    # 3. Initialize ESP32 client
    esp32_client = ESP32Client(ESP32_URL)
    
    # 4. Initialize routers with services
    health.init_router(ai_service, firebase_service, ESP32_URL)
    streams.init_router(ai_service, firebase_service, ESP32_URL)
    # ... more routers
    
    yield  # Server runs here
    
    # SHUTDOWN
    print("🛑 Shutting down server...")
    await broadcast_manager.cleanup_all()
    if ai_service:
        ai_service.cleanup()

# Create app
app = FastAPI(
    title="SmartParking API",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# Include routers
app.include_router(health.router)
app.include_router(streams.router)
# ... more routers
```

## 🤖 AI Service Architecture

### AIService Class (`services/ai_service.py`)

```python
class AIService:
    """AI Service manages YOLO and ALPR models with CUDA support"""
    
    def __init__(self):
        self.yolo_model = None
        self.alpr_model = None
        self.device = None  # 'cuda', 'mps', or 'cpu'
        self.track_history = {}  # Store track trails
        self.frame_count = 0
    
    def _get_device(self):
        """Detect and return best available device"""
        if torch.cuda.is_available():
            device = 'cuda'
            gpu_name = torch.cuda.get_device_name(0)
            print(f"🚀 CUDA available: {gpu_name}")
        elif torch.backends.mps.is_available():
            device = 'mps'
            print(f"🚀 MPS (Apple Silicon) available")
        else:
            device = 'cpu'
            print(f"⚠️  No GPU detected, using CPU")
        return device
    
    async def load_models(self):
        """Load YOLO and ALPR models once at startup"""
        self.device = self._get_device()
        
        # Load YOLO model
        model_path = "yolov8s_car_custom.pt" or "yolov8n.pt"
        self.yolo_model = YOLO(model_path)
        self.yolo_model.to(self.device)
        
        # Load ALPR model
        self.alpr_model = ALPR(
            detector_model="yolo-v9-t-384-license-plate-end2end",
            ocr_model="global-plates-mobile-vit-v2-model"
        )
        
        print("✅ AI models loaded successfully")
    
    async def detect_objects(
        self,
        frame: np.ndarray,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        classes: List[int] = None,
        use_tracking: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Detect objects in frame with optional tracking
        
        Args:
            frame: Input image (numpy array)
            conf_threshold: Confidence threshold (0-1)
            iou_threshold: IoU threshold for NMS
            classes: List of class IDs to detect (None = all)
            use_tracking: Whether to use ByteTrack tracking
        
        Returns:
            List of detections with bounding boxes, classes, confidences,
            and track IDs (if tracking enabled)
        """
        # Run YOLO inference
        results = self.yolo_model.predict(
            frame,
            conf=conf_threshold,
            iou=iou_threshold,
            classes=classes,
            device=self.device,
            verbose=False,
            stream=False
        )
        
        detections = []
        
        if use_tracking:
            # ByteTrack tracking mode
            # Returns results with track IDs
            boxes = results[0].boxes
            
            if hasattr(boxes, 'id') and boxes.id is not None:
                # Tracking enabled - has track IDs
                for box, track_id in zip(boxes.data, boxes.id):
                    x1, y1, x2, y2, conf, cls = box[:6]
                    
                    detection = {
                        'bbox': {
                            'x1': float(x1),
                            'y1': float(y1),
                            'x2': float(x2),
                            'y2': float(y2)
                        },
                        'confidence': float(conf),
                        'class': int(cls),
                        'class_name': self.yolo_model.names[int(cls)],
                        'track_id': int(track_id)
                    }
                    
                    # Store track history for trail visualization
                    track_id_int = int(track_id)
                    center = ((x1 + x2) / 2, (y1 + y2) / 2)
                    
                    if track_id_int not in self.track_history:
                        self.track_history[track_id_int] = []
                    
                    self.track_history[track_id_int].append(center)
                    
                    # Keep only last 30 points
                    if len(self.track_history[track_id_int]) > 30:
                        self.track_history[track_id_int].pop(0)
                    
                    detections.append(detection)
        else:
            # Detection only mode (no tracking)
            boxes = results[0].boxes
            
            for box in boxes.data:
                x1, y1, x2, y2, conf, cls = box[:6]
                
                detection = {
                    'bbox': {
                        'x1': float(x1),
                        'y1': float(y1),
                        'x2': float(x2),
                        'y2': float(y2)
                    },
                    'confidence': float(conf),
                    'class': int(cls),
                    'class_name': self.yolo_model.names[int(cls)]
                }
                
                detections.append(detection)
        
        self.frame_count += 1
        return detections
    
    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
        draw_trails: bool = True,
        draw_labels: bool = True
    ) -> np.ndarray:
        """
        Draw bounding boxes, labels, and tracking trails on frame
        
        Args:
            frame: Input image
            detections: List of detections from detect_objects()
            draw_trails: Whether to draw tracking trails
            draw_labels: Whether to draw labels
        
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        
        for det in detections:
            bbox = det['bbox']
            x1, y1 = int(bbox['x1']), int(bbox['y1'])
            x2, y2 = int(bbox['x2']), int(bbox['y2'])
            
            # Get color based on track ID (consistent per track)
            if 'track_id' in det:
                color = self._get_track_color(det['track_id'])
            else:
                color = (0, 255, 0)  # Green for detection only
            
            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            if draw_labels:
                label = f"{det['class_name']} {det['confidence']:.2f}"
                if 'track_id' in det:
                    label = f"ID:{det['track_id']} {label}"
                
                # Label background
                (text_w, text_h), _ = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                )
                cv2.rectangle(
                    annotated,
                    (x1, y1 - text_h - 8),
                    (x1 + text_w + 4, y1),
                    color,
                    -1
                )
                
                # Label text
                cv2.putText(
                    annotated,
                    label,
                    (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )
            
            # Draw tracking trail
            if draw_trails and 'track_id' in det:
                track_id = det['track_id']
                if track_id in self.track_history:
                    points = self.track_history[track_id]
                    for i in range(1, len(points)):
                        pt1 = tuple(map(int, points[i - 1]))
                        pt2 = tuple(map(int, points[i]))
                        cv2.line(annotated, pt1, pt2, color, 2)
        
        return annotated
    
    async def detect_license_plates(
        self,
        frame: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Detect and recognize license plates in frame
        
        Args:
            frame: Input image
        
        Returns:
            List of plate detections with text and confidence
        """
        # Run ALPR
        alpr_results = self.alpr_model.predict(frame)
        
        plates = []
        for result in alpr_results:
            plate_data = {
                'text': result['text'],
                'confidence': result['confidence'],
                'bbox': result['bbox']
            }
            plates.append(plate_data)
        
        return plates
    
    def reset_tracking(self):
        """Clear tracking history"""
        self.track_history.clear()
        self.frame_count = 0
    
    def _get_track_color(self, track_id: int) -> Tuple[int, int, int]:
        """Get consistent color for track ID"""
        # Generate color based on track ID
        np.random.seed(track_id)
        color = tuple(map(int, np.random.randint(0, 255, 3)))
        return color
    
    def cleanup(self):
        """Cleanup resources"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
```

## 🔥 Firebase Service Architecture

### FirebaseService Class (`services/firebase_service.py`)

```python
class FirebaseService:
    """Firebase Service manages Firestore operations"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        self.db = None
        self._initialize_firebase(credentials_path)
    
    def _initialize_firebase(self, credentials_path: Optional[str] = None):
        """Initialize Firebase Admin SDK"""
        # Check if already initialized
        if firebase_admin._apps:
            self.db = firestore.client()
            return
        
        # Find credentials file
        if not credentials_path:
            possible_paths = [
                "firebase_credentials.json",
                "serviceAccountKey.json",
                "firebase-adminsdk.json"
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    credentials_path = path
                    break
        
        # Initialize with service account
        if credentials_path:
            cred = credentials.Certificate(credentials_path)
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()
        
        self.db = firestore.client()
        print("✅ Firebase Firestore connected")
    
    # ========== PLATE DETECTION ==========
    
    async def save_plate_detection(
        self,
        detection_result: Dict[str, Any]
    ) -> str:
        """Save plate detection to Firestore"""
        doc_data = {
            "timestamp": firestore.SERVER_TIMESTAMP,
            "plates": detection_result.get("plates", []),
            "plate_count": len(detection_result.get("plates", [])),
            "source": "esp32_camera",
            "processed": True
        }
        
        if doc_data["plates"]:
            doc_data["plate_texts"] = [p["text"] for p in doc_data["plates"]]
        
        doc_ref = self.db.collection("plateHistory").add(doc_data)
        return doc_ref[1].id
    
    async def get_plate_history(
        self,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get plate detection history"""
        docs = (
            self.db.collection("plateHistory")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        
        history = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            history.append(data)
        
        return history
    
    # ========== OBJECT DETECTION ==========
    
    async def save_detection(
        self,
        detection_data: Dict[str, Any]
    ) -> str:
        """Save object detection to Firestore"""
        doc_ref = self.db.collection("detections").add(detection_data)
        return doc_ref[1].id
    
    # ========== PARKING SPACES ==========
    
    async def get_parking_spaces(
        self,
        camera_id: str
    ) -> List[Dict[str, Any]]:
        """Get parking spaces for camera"""
        docs = (
            self.db.collection("parkingSpaceDefinitions")
            .where("cameraId", "==", camera_id)
            .stream()
        )
        
        spaces = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            spaces.append(data)
        
        return spaces
    
    async def update_space_occupancy(
        self,
        space_id: str,
        occupied: bool
    ) -> None:
        """Update parking space occupancy status"""
        self.db.collection("parkingSpaceDefinitions").document(space_id).update({
            "occupied": occupied,
            "lastUpdated": firestore.SERVER_TIMESTAMP
        })
```

## 🅿️ Parking Space Service

### ParkingSpaceService Class

```python
class ParkingSpaceService:
    """Service for parking space logic"""
    
    def __init__(self, firebase_service: FirebaseService):
        self.firebase = firebase_service
    
    async def get_parking_spaces_by_camera(
        self,
        camera_id: str
    ) -> List[Dict[str, Any]]:
        """Load parking spaces from Firebase"""
        return await self.firebase.get_parking_spaces(camera_id)
    
    def calculate_iou(
        self,
        box1: Dict[str, float],
        box2: Dict[str, float]
    ) -> float:
        """
        Calculate Intersection over Union between two boxes
        
        Args:
            box1: {x1, y1, x2, y2}
            box2: {x1, y1, x2, y2}
        
        Returns:
            IoU value (0-1)
        """
        # Calculate intersection
        x1 = max(box1['x1'], box2['x1'])
        y1 = max(box1['y1'], box2['y1'])
        x2 = min(box1['x2'], box2['x2'])
        y2 = min(box1['y2'], box2['y2'])
        
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        
        # Calculate union
        box1_area = (box1['x2'] - box1['x1']) * (box1['y2'] - box1['y1'])
        box2_area = (box2['x2'] - box2['x1']) * (box2['y2'] - box2['y1'])
        union = box1_area + box2_area - intersection
        
        # Calculate IoU
        if union == 0:
            return 0.0
        
        iou = intersection / union
        return iou
    
    def convert_detection_to_normalized(
        self,
        bbox: Dict[str, float],
        frame_width: int,
        frame_height: int
    ) -> Dict[str, float]:
        """Convert pixel coordinates to normalized (0-1)"""
        return {
            'x1': bbox['x1'] / frame_width,
            'y1': bbox['y1'] / frame_height,
            'x2': bbox['x2'] / frame_width,
            'y2': bbox['y2'] / frame_height
        }
    
    def match_detections_to_spaces(
        self,
        detections: List[Dict[str, Any]],
        spaces: List[Dict[str, Any]],
        frame_width: int,
        frame_height: int,
        iou_threshold: float = 0.3
    ) -> Dict[str, Any]:
        """
        Match vehicle detections to parking spaces
        
        Args:
            detections: List of YOLO detections
            spaces: List of parking space definitions
            frame_width: Frame width in pixels
            frame_height: Frame height in pixels
            iou_threshold: Minimum IoU to consider a match
        
        Returns:
            {
                'occupied_spaces': [...],
                'empty_spaces': [...],
                'matches': [...]
            }
        """
        occupied_space_ids = set()
        matches = []
        
        for detection in detections:
            det_bbox = detection['bbox']
            
            # Convert detection to normalized coordinates
            det_norm = self.convert_detection_to_normalized(
                det_bbox,
                frame_width,
                frame_height
            )
            
            best_match = None
            best_iou = iou_threshold
            
            for space in spaces:
                # Space is already in normalized coordinates
                space_bbox = {
                    'x1': space['x'],
                    'y1': space['y'],
                    'x2': space['x'] + space['width'],
                    'y2': space['y'] + space['height']
                }
                
                iou = self.calculate_iou(det_norm, space_bbox)
                
                if iou > best_iou:
                    best_iou = iou
                    best_match = space
            
            if best_match:
                occupied_space_ids.add(best_match['id'])
                matches.append({
                    'detection': detection,
                    'space': best_match,
                    'iou': best_iou
                })
        
        occupied_spaces = [s for s in spaces if s['id'] in occupied_space_ids]
        empty_spaces = [s for s in spaces if s['id'] not in occupied_space_ids]
        
        return {
            'occupied_spaces': occupied_spaces,
            'empty_spaces': empty_spaces,
            'matches': matches
        }
    
    async def update_space_occupancy(
        self,
        space_id: str,
        occupied: bool
    ) -> None:
        """Update parking space occupancy in Firebase"""
        await self.firebase.update_space_occupancy(space_id, occupied)
```

## 🔄 Worker Process Architecture

### Parking Monitor Worker (`parking_monitor_worker.py`)

```python
class ParkingMonitorWorker:
    """Background worker that monitors parking spaces"""
    
    def __init__(
        self,
        check_interval: float = 0.1,  # 10 FPS
        detection_url: str = "http://localhost:8069",
        update_firebase: bool = False,  # Disabled for high FPS
        enable_logging: bool = True,
        use_tracking: bool = True
    ):
        self.check_interval = check_interval
        self.detection_url = detection_url
        self.update_firebase = update_firebase
        self.enable_logging = enable_logging
        self.use_tracking = use_tracking
        
        # Load configuration
        self.tracking_config = get_tracking_config()
        
        # Initialize services
        self.firebase_service = FirebaseService()
        self.parking_service = ParkingSpaceService(self.firebase_service)
        self.ai_service = AIService()
        
        # Cache
        self.active_cameras: Set[str] = set()
        self.camera_spaces_cache: Dict[str, List[Dict]] = {}
    
    async def start(self):
        """Start the worker process"""
        print("🚀 Starting parking monitor worker...")
        print(f"⏱️  Target FPS: {1/self.check_interval:.1f} FPS per camera")
        
        # Load AI models
        await self.ai_service.load_models()
        print("✅ Models loaded successfully")
        
        # Main loop
        while True:
            try:
                # 1. Get active cameras
                cameras = await self.get_active_cameras()
                
                if not cameras:
                    await asyncio.sleep(5)
                    continue
                
                # 2. Process each camera
                tasks = [
                    self.process_camera(camera)
                    for camera in cameras
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # 3. Sleep for interval
                await asyncio.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                print("\n🛑 Stopping worker...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(1)
    
    async def process_camera(self, camera: Dict[str, Any]):
        """Process single camera"""
        camera_id = camera['id']
        stream_url = camera['streamUrl']
        
        try:
            # 1. Fetch frame
            frame = await self.fetch_frame(stream_url)
            if frame is None:
                return
            
            # 2. Run AI detection
            detections = await self.ai_service.detect_objects(
                frame,
                conf_threshold=self.tracking_config.conf_threshold,
                iou_threshold=self.tracking_config.iou_threshold,
                use_tracking=self.use_tracking
            )
            
            logger.info(f"🚗 Detected {len(detections)} vehicles in {camera_id}")
            
            # 3. Load parking spaces (cached)
            if camera_id not in self.camera_spaces_cache:
                spaces = await self.parking_service.get_parking_spaces_by_camera(camera_id)
                self.camera_spaces_cache[camera_id] = spaces
            else:
                spaces = self.camera_spaces_cache[camera_id]
            
            # 4. Match detections to spaces
            height, width = frame.shape[:2]
            match_result = self.parking_service.match_detections_to_spaces(
                detections,
                spaces,
                width,
                height
            )
            
            # 5. Draw annotations
            annotated_frame = self.draw_detections_on_frame(
                frame,
                detections,
                spaces,
                match_result
            )
            
            # 6. Broadcast to viewers (if any watching)
            await self.broadcast_frame_to_viewers(
                camera_id,
                annotated_frame,
                len(detections),
                len(match_result['occupied_spaces']),
                len(spaces)
            )
            
            # 7. Log detections (optional)
            if self.enable_logging:
                detection_logger.log_detection(
                    camera_id,
                    detections,
                    {'occupied': len(match_result['occupied_spaces']), 'total': len(spaces)}
                )
            
            # 8. Update Firebase (optional, slow!)
            if self.update_firebase:
                for space in match_result['occupied_spaces']:
                    await self.parking_service.update_space_occupancy(
                        space['id'],
                        True
                    )
                for space in match_result['empty_spaces']:
                    await self.parking_service.update_space_occupancy(
                        space['id'],
                        False
                    )
            
        except Exception as e:
            logger.error(f"Error processing camera {camera_id}: {e}")
```

## 📡 Streaming Architecture

### Detection Broadcasting

```python
class DetectionBroadcaster:
    """Manages WebSocket connections for detection viewing"""
    
    def __init__(self):
        self.viewers: Dict[str, Set[WebSocket]] = {}
        self.latest_frames: Dict[str, Dict] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
    
    async def register_viewer(
        self,
        camera_id: str,
        websocket: WebSocket
    ):
        """Register a new viewer"""
        if camera_id not in self.viewers:
            self.viewers[camera_id] = set()
            self.locks[camera_id] = asyncio.Lock()
        
        self.viewers[camera_id].add(websocket)
        
        # Send latest frame immediately if available
        if camera_id in self.latest_frames:
            await websocket.send_json(self.latest_frames[camera_id])
    
    async def unregister_viewer(
        self,
        camera_id: str,
        websocket: WebSocket
    ):
        """Unregister a viewer"""
        if camera_id in self.viewers:
            self.viewers[camera_id].discard(websocket)
            
            # Cleanup if no viewers left
            if not self.viewers[camera_id]:
                del self.viewers[camera_id]
                del self.locks[camera_id]
                if camera_id in self.latest_frames:
                    del self.latest_frames[camera_id]
    
    async def broadcast_frame(
        self,
        camera_id: str,
        frame_base64: str,
        metadata: Dict[str, Any]
    ):
        """Broadcast frame to all viewers"""
        if camera_id not in self.viewers:
            return
        
        message = {
            "type": "frame",
            "camera_id": camera_id,
            "frame": frame_base64,
            "metadata": metadata
        }
        
        # Store latest frame
        self.latest_frames[camera_id] = message
        
        # Send to all viewers
        async with self.locks[camera_id]:
            disconnected = []
            for websocket in self.viewers[camera_id]:
                try:
                    await websocket.send_json(message)
                except:
                    disconnected.append(websocket)
            
            # Remove disconnected viewers
            for ws in disconnected:
                self.viewers[camera_id].discard(ws)
    
    def get_viewer_count(self, camera_id: str) -> int:
        """Get number of viewers for camera"""
        return len(self.viewers.get(camera_id, set()))
```

## 🔌 API Router Examples

### Streams Router (`routers/streams.py`)

```python
router = APIRouter(prefix="/stream", tags=["Streaming"])

# Global service instances
ai_service = None
firebase_service = None
ESP32_URL = None

def init_router(ai_svc, firebase_svc, esp32_url):
    global ai_service, firebase_service, ESP32_URL
    ai_service = ai_svc
    firebase_service = firebase_svc
    ESP32_URL = esp32_url

@router.get("/detect")
async def stream_with_detection(
    request: Request,
    conf: float = Query(0.25, ge=0.0, le=1.0),
    iou: float = Query(0.45, ge=0.0, le=1.0),
    classes: Optional[str] = Query(None)
):
    """
    Stream video with AI object detection overlay
    
    Query params:
        conf: Confidence threshold (0-1)
        iou: IoU threshold for NMS (0-1)
        classes: Comma-separated class IDs (e.g., "2,7")
    """
    async def generate_frames():
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ESP32_URL}/stream") as resp:
                async for chunk in resp.content.iter_any():
                    # Check if client disconnected
                    if await request.is_disconnected():
                        break
                    
                    # Parse MJPEG frame
                    frame = parse_mjpeg_frame(chunk)
                    if frame is None:
                        continue
                    
                    # Run AI detection
                    detections = await ai_service.detect_objects(
                        frame,
                        conf_threshold=conf,
                        iou_threshold=iou,
                        classes=parse_classes(classes)
                    )
                    
                    # Draw bounding boxes
                    annotated = ai_service.draw_detections(frame, detections)
                    
                    # Encode to JPEG
                    _, buffer = cv2.imencode('.jpg', annotated)
                    
                    # Send as MJPEG
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' +
                        buffer.tobytes() +
                        b'\r\n'
                    )
    
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
```

## 🔧 Configuration Management

### Tracking Configuration (`config/tracking_config.yaml`)

```yaml
# ByteTrack Tracking Configuration

bytetrack:
  track_high_thresh: 0.6      # High confidence threshold
  track_low_thresh: 0.1       # Low confidence threshold  
  new_track_thresh: 0.7       # New track threshold
  track_buffer: 30            # Frames to keep lost tracks
  match_thresh: 0.8           # Matching threshold

detection:
  conf_threshold: 0.25        # Detection confidence
  iou_threshold: 0.45         # NMS IoU threshold
  classes: [2, 5, 7]         # car, bus, truck

performance:
  fps: 10                     # Target FPS
  skip_frames: 0              # Skip N frames
  imgsz: 640                  # Image size
  device: "cuda"              # cuda, mps, cpu

visualization:
  draw_trails: true           # Draw tracking trails
  trail_length: 30            # Points in trail
  draw_labels: true           # Draw class labels
  colors:
    detection: [0, 255, 0]    # Green
    tracking: [255, 0, 0]     # Blue

logging:
  log_detections: true        # Log to files
  log_tracks: true            # Log track info
  log_level: "INFO"           # DEBUG, INFO, WARNING
```

This backend architecture provides a robust, scalable foundation for the Smart Parking System with efficient AI processing and real-time streaming capabilities.
