# Smart Parking System - Architecture Details

## 🏗️ System Architecture

### Three-Tier Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      PRESENTATION TIER                          │
│                    (Frontend - React)                           │
│  - User Interface                                              │
│  - Real-time Visualization                                     │
│  - State Management                                            │
└────────────────────────────────────────────────────────────────┘
                              ↓ ↑
                    REST API + WebSocket
                              ↓ ↑
┌────────────────────────────────────────────────────────────────┐
│                      APPLICATION TIER                           │
│                    (Backend - FastAPI)                          │
│  - Business Logic                                              │
│  - AI Processing                                               │
│  - API Endpoints                                               │
│  - Background Workers                                          │
└────────────────────────────────────────────────────────────────┘
                              ↓ ↑
                    Database + Video Sources
                              ↓ ↑
┌────────────────────────────────────────────────────────────────┐
│                        DATA TIER                                │
│  - Firebase/Firestore (NoSQL)                                  │
│  - ESP32-CAM Streams (Video)                                   │
│  - File System (Logs)                                          │
└────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
SmartParking/
│
├── frontend/                      # React TypeScript Frontend
│   ├── src/
│   │   ├── components/           # Reusable UI components
│   │   ├── pages/                # Page components (19 pages)
│   │   ├── services/             # API client services
│   │   ├── context/              # React Context (Auth, etc.)
│   │   ├── config/               # Firebase config
│   │   ├── types/                # TypeScript type definitions
│   │   └── utils/                # Utility functions
│   ├── public/                   # Static assets
│   ├── package.json              # npm dependencies
│   └── vite.config.ts            # Vite configuration
│
├── server/                        # FastAPI Python Backend
│   ├── main_fastapi.py           # Main application entry point
│   ├── parking_monitor_worker.py # Background worker process
│   │
│   ├── services/                 # Business logic services
│   │   ├── ai_service.py         # YOLO + ALPR + Tracking
│   │   ├── firebase_service.py   # Firestore operations
│   │   ├── parking_space_service.py # Parking logic
│   │   ├── stream_broadcaster.py # WebSocket broadcasting
│   │   ├── detection_broadcaster.py # Detection streaming
│   │   └── detection_logger.py   # Log detections to files
│   │
│   ├── routers/                  # API route modules
│   │   ├── health.py             # Health check endpoints
│   │   ├── streams.py            # Video streaming
│   │   ├── websocket_streams.py  # WebSocket streams
│   │   ├── ai_detection.py       # AI detection API
│   │   ├── firebase.py           # Firebase API
│   │   ├── esp32.py              # ESP32 hardware API
│   │   ├── user_config.py        # User configuration
│   │   ├── detection_viewer.py   # Detection viewer WebSocket
│   │   ├── worker_broadcast.py   # Worker broadcast endpoints
│   │   └── tracking_debug.py     # Debug tracking info
│   │
│   ├── models/                   # Data models
│   │   └── stream_tracking.py    # Stream connection tracking
│   │
│   ├── middleware/               # Custom middleware
│   │   └── disconnect_watcher.py # Client disconnect detection
│   │
│   ├── config/                   # Configuration files
│   │   └── tracking_config.yaml  # ByteTrack configuration
│   │
│   ├── utils/                    # Utility modules
│   │   └── tracking_config.py    # Config loader
│   │
│   ├── logs/                     # Detection log files
│   ├── static/                   # Static files
│   ├── requirements.txt          # Python dependencies
│   └── environment.yml           # Conda environment
│
├── ESP32/                         # ESP32-CAM Integration
│   ├── esp32_cam_firmware.ino    # Arduino firmware
│   ├── config_template.h         # Hardware config
│   ├── mock_esp32_server.py      # Mock server (development)
│   ├── esp32_client.py           # Python client library
│   ├── start_mock.py             # Quick start script
│   ├── test_esp32_connection.py  # Connection test
│   ├── stream/                   # Video files for mock
│   └── docs/                     # ESP32 documentation
│
├── docs/                          # Project Documentation
│   ├── FIREBASE_ARCHITECTURE.md
│   ├── BYTETRACK_INTEGRATION.md
│   ├── PARKING_SPACE_SUMMARY.md
│   ├── WORKER_MONITORING_GUIDE.md
│   ├── DETECTION_VIEWER_SYSTEM.md
│   ├── PERFORMANCE_TUNING.md
│   └── [many more...]
│
├── vehicle_mtmc/                  # Vehicle Multi-Target Multi-Camera
│   └── [tracking algorithms]
│
└── README.md                      # Main documentation
```

## 🔄 Data Flow Architecture

### 1. Video Streaming Pipeline

```
┌─────────────┐
│  ESP32-CAM  │ (Hardware Camera)
│  Port: 81   │
└──────┬──────┘
       │ MJPEG Stream
       ↓
┌─────────────────────┐
│  Mock ESP32 Server  │ (Development)
│  Port: 5069         │
└──────┬──────────────┘
       │ HTTP GET /stream
       ↓
┌─────────────────────────────────────┐
│  Backend (main_fastapi.py)          │
│  Port: 8069                         │
│  ├─ /stream (raw proxy)             │
│  ├─ /stream/detect (with AI)        │
│  └─ /ws/stream (WebSocket)          │
└──────┬──────────────────────────────┘
       │ HTTP/WebSocket
       ↓
┌─────────────────────┐
│  Frontend (React)   │
│  Port: 5169         │
│  - <img> tag        │
│  - WebSocket client │
└─────────────────────┘
```

### 2. AI Processing Pipeline

```
┌──────────────┐
│ Video Frame  │
└──────┬───────┘
       │
       ↓
┌─────────────────────────────┐
│  AIService.detect_objects() │
│  - Load frame               │
│  - Preprocess (resize)      │
│  - Run YOLO (GPU)           │
│  - NMS filtering            │
└──────┬──────────────────────┘
       │
       ↓
┌─────────────────────────────┐
│  ByteTrack Tracking         │
│  - Match detections         │
│  - Assign track IDs         │
│  - Update trajectories      │
└──────┬──────────────────────┘
       │
       ↓
┌──────────────────────────────┐
│  Parking Space Matching      │
│  - Load parking spaces       │
│  - Calculate IoU             │
│  - Determine occupancy       │
└──────┬───────────────────────┘
       │
       ↓
┌──────────────────────────────┐
│  Results                     │
│  - Detections with track IDs │
│  - Occupancy status          │
│  - Annotated frame           │
└──────────────────────────────┘
```

### 3. Worker Processing Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  parking_monitor_worker.py (Background Process)              │
│                                                              │
│  Main Loop (runs continuously):                             │
│  1. Fetch active cameras from Firebase                      │
│  2. For each camera:                                         │
│     ├─ Fetch frame from ESP32                               │
│     ├─ Run AI detection (YOLO + ByteTrack)                  │
│     ├─ Load parking spaces from cache                       │
│     ├─ Match detections to spaces (IoU)                     │
│     ├─ Draw annotations on frame                            │
│     ├─ Broadcast frame to viewers (WebSocket)               │
│     ├─ Log detections to file (optional)                    │
│     └─ Update Firebase occupancy (optional, slow)           │
│  3. Sleep for interval (e.g., 0.1s for 10 FPS)              │
│  4. Repeat                                                   │
└──────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  Outputs:       │
                    ├─────────────────┤
                    │ • WebSocket     │
                    │ • Log files     │
                    │ • Firebase      │
                    └─────────────────┘
```

### 4. Detection Broadcasting Architecture

```
┌────────────────────────────────────────────────────────┐
│  Worker Processing                                      │
│  (Single GPU process)                                   │
│  • Detect vehicles                                      │
│  • Draw annotations                                     │
│  • Encode to JPEG                                       │
└────────────┬───────────────────────────────────────────┘
             │
             ↓
┌────────────────────────────────────────────────────────┐
│  DetectionBroadcaster Service                          │
│  • Maintains viewer registry per camera                │
│  • Stores latest frame                                 │
│  • Broadcasts to all viewers                           │
└────────────┬───────────────────────────────────────────┘
             │
             ├─────────┬─────────┬─────────┐
             ↓         ↓         ↓         ↓
         [Viewer1] [Viewer2] [Viewer3] [Viewer N]
         (WebSocket connections)
         
Benefits:
✅ One detection → Unlimited viewers
✅ No extra GPU load per viewer
✅ Efficient resource usage
✅ Real-time streaming
```

## 🔌 API Architecture

### REST API Endpoints

```
Health & Debug:
GET  /health                    # Backend health check
GET  /debug/streams             # Active stream connections

Video Streaming:
GET  /stream                    # Raw proxy from ESP32
GET  /stream/detect             # Stream with AI detection
GET  /stream/proxy              # Direct proxy

WebSocket Streams:
WS   /ws/stream                 # WebSocket video stream
WS   /ws/viewer/detection       # Detection viewer stream

AI Detection:
POST /api/plate-detect          # Detect license plates
POST /api/object-tracking       # Track objects in video
POST /api/detect-spaces         # Detect parking spaces

Firebase Operations:
GET  /api/firebase/history      # Get detection history
GET  /api/firebase/plates       # Get plate history
GET  /api/firebase/spaces       # Get parking spaces

User Configuration:
POST /api/user/config/save      # Save user ESP32 config
GET  /api/user/config/get       # Get user ESP32 config
POST /api/user/config/delete    # Delete user ESP32 config

ESP32 Hardware:
GET  /api/esp32/snapshot        # Capture snapshot
GET  /api/esp32/status          # Camera status
POST /api/esp32/test            # Test connection

Worker Management:
GET  /api/worker/frame          # Get latest worker frame
GET  /api/worker/stats          # Worker statistics
GET  /stream/worker-detection   # Worker detection stream

Detection Logs:
GET  /api/detection-logs/list   # List log files
GET  /api/detection-logs/read   # Read log content

Tracking Debug:
GET  /api/tracking/stats        # Tracking statistics
GET  /api/tracking/history      # Track history
```

### WebSocket Protocols

```
Detection Viewer Protocol:
Connect: ws://localhost:8069/ws/viewer/detection?camera_id=cam1&user_id=uid

Messages received:
{
  "type": "frame",
  "camera_id": "cam1",
  "frame": "base64_encoded_jpeg",
  "metadata": {
    "detected_count": 5,
    "occupied_spaces": 3,
    "total_spaces": 10,
    "timestamp": "2026-01-07T10:30:00Z"
  }
}

Stream Protocol:
Connect: ws://localhost:8069/ws/stream?camera_id=cam1

Messages received:
- Binary: JPEG frame data
- Text: Status messages
```

## 🗄️ Database Schema (Firebase/Firestore)

### Collections Structure

```
Firestore
│
├── users/                              # User accounts
│   └── {userId}/
│       ├── email: string
│       ├── role: "user" | "admin"
│       ├── createdAt: timestamp
│       └── displayName: string
│
├── parkingLots/                        # Parking lot definitions
│   └── {parkingLotId}/
│       ├── name: string
│       ├── location: string
│       ├── totalSpaces: number
│       ├── cameras: string[]
│       └── createdAt: timestamp
│
├── cameras/                            # Camera configurations
│   └── {cameraId}/
│       ├── name: string
│       ├── parkingLotId: string
│       ├── streamUrl: string
│       ├── enabled: boolean
│       ├── workerEnabled: boolean      # Worker monitoring
│       ├── userId: string              # Owner
│       └── settings: {
│           fps: number
│           resolution: string
│       }
│
├── parkingSpaceDefinitions/            # Parking space layouts
│   └── {spaceId}/
│       ├── parkingLotId: string
│       ├── cameraId: string
│       ├── name: string
│       ├── x: number (0-1)             # Normalized coordinates
│       ├── y: number (0-1)
│       ├── width: number (0-1)
│       ├── height: number (0-1)
│       ├── occupied: boolean
│       └── lastUpdated: timestamp
│
├── detections/                         # Detection records
│   └── {detectionId}/
│       ├── cameraId: string
│       ├── timestamp: timestamp
│       ├── vehicleCount: number
│       ├── detections: [
│       │   {
│       │     bbox: {x, y, w, h}
│       │     class: string
│       │     confidence: number
│       │     trackId: number
│       │   }
│       │]
│       └── frameUrl: string (optional)
│
├── plateHistory/                       # License plate records
│   └── {plateId}/
│       ├── plateText: string
│       ├── cameraId: string
│       ├── timestamp: timestamp
│       ├── confidence: number
│       ├── vehicleType: string
│       └── imageUrl: string (optional)
│
├── alerts/                             # System alerts
│   └── {alertId}/
│       ├── type: string
│       ├── severity: "low" | "medium" | "high"
│       ├── message: string
│       ├── cameraId: string
│       ├── resolved: boolean
│       └── timestamp: timestamp
│
└── workerStatus/                       # Worker monitoring
    └── {workerId}/
        ├── status: "running" | "stopped"
        ├── lastHeartbeat: timestamp
        ├── camerasMonitored: string[]
        ├── fps: number
        └── detectionCount: number
```

## 🔧 Service Architecture

### Backend Services

#### 1. AIService (`services/ai_service.py`)
```python
Responsibilities:
- Load and manage YOLO models
- Load and manage ALPR models
- Detect objects with ByteTrack tracking
- Draw annotations on frames
- GPU/CUDA management
- Track history maintenance

Key Methods:
- load_models(): Initialize AI models
- detect_objects(frame, use_tracking=True): Run detection
- detect_license_plates(frame): Run ALPR
- draw_detections(frame, detections): Annotate frame
- reset_tracking(): Clear tracking state
```

#### 2. FirebaseService (`services/firebase_service.py`)
```python
Responsibilities:
- Firebase Admin SDK initialization
- Firestore CRUD operations
- Authentication verification
- Data persistence

Key Methods:
- save_plate_detection(result): Save plate data
- get_detection_history(limit): Retrieve history
- save_detection(data): Save detection record
- get_parking_spaces(camera_id): Load spaces
- update_space_occupancy(space_id, occupied): Update status
```

#### 3. ParkingSpaceService (`services/parking_space_service.py`)
```python
Responsibilities:
- Parking space management
- IoU calculation
- Detection-to-space matching
- Occupancy updates

Key Methods:
- get_parking_spaces_by_camera(camera_id): Load spaces
- calculate_iou(box1, box2): Intersection over Union
- match_detections_to_spaces(detections, spaces): Match logic
- update_space_occupancy(space_id, occupied): Update Firebase
- get_parking_summary(camera_id): Statistics
```

#### 4. StreamBroadcaster (`services/stream_broadcaster.py`)
```python
Responsibilities:
- Manage WebSocket connections
- Broadcast frames to viewers
- Connection lifecycle management

Key Methods:
- register_client(stream_id, websocket): Add viewer
- unregister_client(stream_id, websocket): Remove viewer
- broadcast_frame(stream_id, frame): Send to all viewers
- cleanup_all(): Shutdown all connections
```

#### 5. DetectionBroadcaster (`services/detection_broadcaster.py`)
```python
Responsibilities:
- Manage detection stream viewers
- Store latest frame per camera
- Efficient frame distribution

Key Methods:
- register_viewer(camera_id, websocket): Add viewer
- unregister_viewer(camera_id, websocket): Remove viewer
- broadcast_frame(camera_id, frame, metadata): Broadcast
- get_viewer_count(camera_id): Count active viewers
```

#### 6. DetectionLogger (`services/detection_logger.py`)
```python
Responsibilities:
- Log detections to files
- Structured logging format
- File rotation and management

Key Methods:
- log_detection(camera_id, detections, metadata): Write log
- get_log_files(camera_id): List available logs
- read_log_file(file_path): Read log contents
```

### Frontend Services

#### 1. apiService (`services/apiService.ts`)
```typescript
Responsibilities:
- REST API client
- HTTP request handling
- Error handling

Key Methods:
- detectPlate(imageData): Call plate detection
- trackObjects(videoFile): Call object tracking
- getDetectionHistory(): Fetch history
```

#### 2. parkingSpaceService (`services/parkingSpaceService.ts`)
```typescript
Responsibilities:
- Parking space CRUD operations
- Firestore integration
- IoU calculations

Key Methods:
- saveParkingSpace(space): Save to Firestore
- getParkingSpacesByCamera(cameraId): Load spaces
- deleteParkingSpace(spaceId): Remove space
- checkOverlap(detection, space): IoU check
```

#### 3. cameraService (`services/cameraService.ts`)
```typescript
Responsibilities:
- Camera configuration management
- Stream URL handling
- Camera status monitoring

Key Methods:
- getCameraById(id): Fetch camera config
- updateCamera(id, data): Update config
- listCameras(): Get all cameras
```

## 🔐 Security Architecture

### Authentication Flow
```
1. User Login (Firebase Auth)
   └─> Frontend calls Firebase SDK
       └─> Firebase returns JWT token
           └─> Token stored in browser

2. API Request
   └─> Frontend includes token in Authorization header
       └─> Backend verifies token (optional, if implemented)
           └─> Request processed

3. Firestore Access
   └─> Client uses Firebase SDK
       └─> Firebase Security Rules enforce access
           └─> Data returned based on rules
```

### Security Rules (Firestore)
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users can read their own data
    match /users/{userId} {
      allow read: if request.auth.uid == userId;
      allow write: if request.auth.uid == userId;
    }
    
    // Cameras: Users own their cameras
    match /cameras/{cameraId} {
      allow read: if request.auth != null;
      allow write: if request.auth.uid == resource.data.userId;
    }
    
    // Parking spaces: Read all, write only if admin
    match /parkingSpaceDefinitions/{spaceId} {
      allow read: if request.auth != null;
      allow write: if request.auth.token.role == "admin";
    }
    
    // Detection history: Read only for authenticated users
    match /detections/{detectionId} {
      allow read: if request.auth != null;
      allow write: if false; // Only backend can write
    }
  }
}
```

## 🚀 Deployment Architecture

### Development Environment
```
Local Machine
├─ Frontend Dev Server (Vite HMR): :5169
├─ Backend Dev Server (uvicorn reload): :8069
├─ Mock ESP32 Server: :5069
└─ Firebase Local Emulator (optional): :8080
```

### Production Environment (Proposed)
```
Cloud Infrastructure
├─ Frontend: Static hosting (Vercel/Netlify/Firebase Hosting)
├─ Backend: Cloud server with GPU (AWS EC2 G4/G5, GCP with GPU)
├─ ESP32 Cameras: Local network with port forwarding
├─ Database: Firebase Production
└─ CDN: Cloudflare for static assets
```

## 📊 Monitoring & Observability

### Logging Strategy
```
Backend:
- Console logs (development)
- File logs (logs/ directory)
- Detection logs (logs/detections_YYYYMMDD_*.log)
- Structured logging format

Frontend:
- Browser console (development)
- Error tracking service (production - TODO)

Worker:
- Console output
- Detection logs
- Performance metrics
```

### Health Checks
```
GET /health
Response:
{
  "status": "healthy",
  "timestamp": "2026-01-07T10:30:00Z",
  "services": {
    "ai": "loaded",
    "firebase": "connected",
    "esp32": "connected"
  },
  "gpu": {
    "available": true,
    "device": "CUDA",
    "name": "NVIDIA GeForce RTX 3080"
  }
}
```

## 🎯 Performance Optimizations

### Backend Optimizations
1. **Model Loading**: Load once at startup
2. **GPU Utilization**: All inference on GPU
3. **Frame Skipping**: Configurable FPS
4. **Broadcasting**: Single detection → many viewers
5. **Async Operations**: Non-blocking I/O
6. **Connection Pooling**: Reuse HTTP connections
7. **Caching**: Cache parking spaces, camera configs

### Frontend Optimizations
1. **Code Splitting**: Lazy load pages
2. **Image Optimization**: Responsive images
3. **Memoization**: React.memo, useMemo, useCallback
4. **Virtual Scrolling**: Large lists
5. **Debouncing**: User input
6. **WebSocket Reuse**: Single connection per stream

### Database Optimizations
1. **Indexes**: On frequently queried fields
2. **Batch Operations**: Group writes
3. **Realtime Listeners**: Only for active data
4. **Pagination**: Limit query results
5. **Caching**: Cache reads in backend

This architecture provides a scalable, maintainable, and performant system for smart parking management.
