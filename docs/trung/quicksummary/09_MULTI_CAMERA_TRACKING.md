# Smart Parking System - Multi-Camera Tracking (MTMC)

## 🎯 Overview

The SmartParking system has evolved from **single-camera tracking** to **Multi-Target Multi-Camera (MTMC) tracking**, enabling unified vehicle identification across multiple camera views. This provides:

- **Global Vehicle IDs**: Same vehicle gets same ID across all cameras
- **Cross-Camera Tracking**: Track vehicles as they move between camera zones
- **Unified Monitoring**: Centralized view of all parking areas
- **License Plate Propagation**: Plate detected in one camera propagates to all views

## 🏗️ Architecture Comparison

### Old Architecture (Single Camera)

```
┌─────────────────────────────────────┐
│   FastAPI Backend (Port 8069)       │
│   - Processes ONE camera at a time  │
│   - Each camera has isolated IDs    │
│   - No cross-camera correlation     │
└─────────────────────────────────────┘
          ↓
    ┌──────────┐
    │ Camera 1 │ → IDs: 1, 2, 3, ...
    └──────────┘
    ┌──────────┐
    │ Camera 2 │ → IDs: 1, 2, 3, ... (different vehicles!)
    └──────────┘
```

**Problem**: Vehicle ID 5 in Camera A and Vehicle ID 5 in Camera B are completely different vehicles.

### New Architecture (Multi-Camera)

```
┌─────────────────────────────────────────────────────────┐
│         Live MTMC System (vehicle_mtmc/)                 │
│  Location: vehicle_mtmc/mtmc/run_live_mtmc.py           │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────▼─────┐     ┌─────▼──────┐    ┌────▼─────┐
   │ Camera A │     │ Camera B   │    │ Camera C │
   │  Worker  │     │  Worker    │    │  Worker  │
   │ (Thread) │     │ (Thread)   │    │ (Thread) │
   │ Local:1,2│     │ Local:3,4  │    │ Local:5,6│
   └────┬─────┘     └─────┬──────┘    └────┬─────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
              ┌───────────────────────┐
              │ LiveMTMCAggregator    │
              │ (Clustering Engine)   │
              │   Assigns Global IDs  │
              └───────────┬───────────┘
                          │
                   Global IDs:
                   Cam A: 1→100, 2→101
                   Cam B: 3→100, 4→102  ← Same vehicle as Cam A ID 1!
                   Cam C: 5→101, 6→103  ← Same vehicle as Cam A ID 2!
```

**Solution**: Vehicle gets **Global ID 100** across all cameras where it appears.

## 🔑 Key Components

### 1. VirtualClock (Frame Synchronization)

**File**: `vehicle_mtmc/mtmc/run_live_mtmc.py` (Lines 57-133)

**Purpose**: Synchronizes all camera threads to process frames at the same rate

**Why it's critical**:
- Without sync, fast cameras process far ahead of slow cameras
- MTMC clustering requires temporally aligned frames
- Prevents temporal constraint violations (e.g., vehicle can't be in Camera B before leaving Camera A)

**How it works**:
```python
class VirtualClock:
    def __init__(self, interval, max_skew, stall_seconds, worker_names):
        self.interval = interval      # 1/FPS (e.g., 0.1s for 10 FPS)
        self.max_skew = max_skew      # Max frame difference allowed (default: 1)
        self._tick = 0                # Current global tick
        self._seen = {}               # Last tick seen per worker
```

**Example Synchronization**:
```
Config: MAX_SKEW = 1, FPS = 10 (interval = 0.1s)

Time  | Tick | Cam A | Cam B | Cam C | Action
------|------|-------|-------|-------|--------
0.0s  |  0   |  0    |  0    |  0    | All start
0.1s  |  1   |  1    |  1    |  0    | Cam C slow, others wait
0.2s  |  2   |  1    |  1    |  1    | Cam C catches up
0.3s  |  3   |  2    |  2    |  1    | All proceed (within max_skew)
```

### 2. LiveMOTWorker (Per-Camera Thread)

**File**: `vehicle_mtmc/mtmc/run_live_mtmc.py` (Lines 272-402)

**Purpose**: Each camera runs in its own thread performing MOT (Multi-Object Tracking)

**Processing Pipeline**:
```python
def run(self):
    while not stopped:
        # 1. Wait for synchronized tick
        tick = self.vclock.wait_for_tick(self.name, self.frame_id)
        
        # 2. Read frame from video source
        ret, frame = self.cap.read()
        
        # 3. Detect vehicles (YOLO)
        detections = self.detector(frame)
        
        # 4. Extract ReID features (ResNet50/MobileNetV4)
        features = self.extractor(frame, detections)
        
        # 5. Update tracker (ByteTrack/DeepSORT)
        tracks = self.tracker.update(detections, features)
        
        # 6. Get global IDs from aggregator
        local_to_global = self.aggregator.update(self.cam_idx, tracks)
        
        # 7. Annotate frame with global IDs
        annotated = self._annotate(frame, tracks, local_to_global)
        
        # 8. Stream via MJPEG
        self.broadcaster.update_frame(self.name, jpeg_bytes)
        
        # 9. Mark tick complete
        self.vclock.mark(self.name, tick)
```

**Related Files**:
- `vehicle_mtmc/mot/tracker.py` - ByteTrack, DeepSORT implementations
- `vehicle_mtmc/detection/load_detector.py` - YOLO detector
- `vehicle_mtmc/reid/feature_extractor.py` - ReID model

### 3. LiveMTMCAggregator (Global ID Assignment)

**File**: `vehicle_mtmc/mtmc/run_live_mtmc.py` (Lines 136-210)

**Purpose**: Collects tracks from all cameras and assigns unified global IDs via hierarchical clustering

**Key Method**:
```python
def update(self, cam_idx: int, tracks: list) -> Dict[int, int]:
    """
    Called by each camera worker every frame.
    
    Args:
        cam_idx: Camera index (0, 1, 2, ...)
        tracks: List of active Track objects with local IDs
        
    Returns:
        Mapping from local track_id to global_id
        Example: {5: 100, 7: 100, 9: 101}
                 (local IDs 5,7 map to global 100)
    """
```

**Clustering Algorithm**:
```python
# Every cluster_interval seconds (e.g., 2.0s):
1. Collect all active tracks from all cameras
2. Filter tracks by minimum length (e.g., 3 frames)
3. Apply temporal constraints (camera layout)
4. Compute similarity matrix (cosine similarity of ReID features)
5. Run hierarchical clustering (single/average/complete linkage)
6. Merge tracks with similarity > MIN_SIM (e.g., 0.5)
7. Assign global IDs to merged clusters
8. Return local→global mapping to each worker
```

**Related Files**:
- `vehicle_mtmc/mtmc/mtmc_clustering.py` - Clustering algorithm
- `vehicle_mtmc/mtmc/cameras.py` - Camera layout constraints

### 4. MJPEGBroadcaster (HTTP Streaming)

**File**: `vehicle_mtmc/mtmc/run_live_mtmc.py` (Lines 213-269)

**Purpose**: HTTP server streaming annotated video with global IDs

**Endpoints**:
- `http://localhost:8080/` - Index page listing all cameras
- `http://localhost:8080/cam_entrance.mjpg` - Entrance camera stream
- `http://localhost:8080/cam_parking.mjpg` - Parking area stream
- `http://localhost:8080/cam_exit.mjpg` - Exit camera stream

**Protocol**: Standard MJPEG over HTTP (`multipart/x-mixed-replace`)

## 🔄 Complete Data Flow

### Frame-by-Frame Processing

```
┌─────────────────────────────────────────────────────────┐
│ LiveMOTWorker Thread (Per Camera)                       │
└─────────────────────────────────────────────────────────┘

Step 1: Synchronization
├─ VirtualClock.wait_for_tick() → Wait for global tick
├─ Ensures all cameras process same time window
└─ Prevents temporal violations

Step 2: Frame Capture
├─ VideoCapture.read() → Get BGR frame
└─ From video file, RTSP stream, or ESP32-CAM

Step 3: Object Detection
├─ YOLOv8.predict() → Bounding boxes
├─ Filter by: confidence (0.25), class (car/truck/bus), mask
└─ Output: List[Detection] with bbox, confidence, class

Step 4: Feature Extraction (ReID)
├─ ResNet50/MobileNetV4 → 512D or 2048D feature vector
├─ Batch processing (16-32 detections)
├─ FP16 precision for speed
└─ Output: numpy array per detection

Step 5: Tracking (Local IDs)
├─ ByteTrack/DeepSORT → Associate detections across frames
├─ Maintain track history
├─ Assign local track IDs (1, 2, 3, ...)
└─ Output: List[Track] with local IDs

Step 6: Global ID Assignment
├─ Aggregator.update() → Send tracks to clustering engine
├─ Periodic clustering (every 2s)
├─ Cosine similarity + hierarchical clustering
└─ Output: {local_id: global_id} mapping

Step 7: Annotation
├─ Draw bounding boxes with global IDs
├─ Draw tracking trails
├─ Add metadata (frame count, detection count)
└─ Output: Annotated BGR frame

Step 8: MJPEG Encoding
├─ cv2.imencode('.jpg') → JPEG bytes
├─ Broadcaster.update_frame() → Send to HTTP server
└─ HTTP clients receive updated frame

Step 9: Tick Completion
├─ VirtualClock.mark() → Signal frame processed
└─ Allow other cameras to proceed
```

## 📊 MTMC Clustering Details

### Similarity Computation

**ReID Feature Comparison**:
```python
def cosine_similarity(feature_a, feature_b):
    """
    Compare two ReID feature vectors (512D or 2048D)
    
    Returns: Similarity score 0.0 to 1.0
    - 1.0 = Identical appearance
    - 0.5 = Somewhat similar
    - 0.0 = Completely different
    """
    dot_product = np.dot(feature_a, feature_b)
    norm_a = np.linalg.norm(feature_a)
    norm_b = np.linalg.norm(feature_b)
    return dot_product / (norm_a * norm_b + 1e-12)
```

### Temporal Constraints

**Camera Layout File** (`config/examples/parking_camera_layout.txt`):
```
# Format: cam_id_from cam_id_to min_time max_time
# Times in seconds

0 1 2.0 10.0   # Entrance → Parking: 2-10 seconds
0 2 5.0 20.0   # Entrance → Exit: 5-20 seconds (direct route)
1 2 1.0 15.0   # Parking → Exit: 1-15 seconds

# FPS for each camera
fps 30 30 30

# Time offset (if videos not synchronized)
offset 0.0 0.0 0.0

# Scale factor (if videos sped up/slowed down)
scale 1.0 1.0 1.0
```

**Constraint Logic**:
```python
def can_match(track_a, track_b, camera_layout):
    """
    Check if two tracks can be the same vehicle
    """
    cam_a, cam_b = track_a.cam, track_b.cam
    
    if cam_a == cam_b:
        # Same camera: tracks must not overlap in time
        return track_a.end_time < track_b.start_time or \
               track_b.end_time < track_a.start_time
    
    # Different cameras: check transition time
    min_time, max_time = camera_layout.get_transition(cam_a, cam_b)
    travel_time = track_b.start_time - track_a.end_time
    
    return min_time <= travel_time <= max_time
```

### Hierarchical Clustering

**Algorithm** (Agglomerative Clustering):
```
1. Start: Each track is its own cluster
   Cam A: [Track1], [Track2]
   Cam B: [Track3], [Track4]
   Cam C: [Track5], [Track6]

2. Compute pairwise similarities (ReID features)
   Similarity Matrix:
   T1-T3: 0.85 ← High similarity!
   T1-T4: 0.30
   T2-T5: 0.78 ← High similarity!
   ...

3. Merge most similar clusters (if > MIN_SIM)
   Iteration 1: Merge T1 and T3 → Cluster_100: [T1(CamA), T3(CamB)]
   Iteration 2: Merge T2 and T5 → Cluster_101: [T2(CamA), T5(CamC)]

4. Continue until no more clusters can be merged

5. Assign global IDs:
   Cluster_100 → Global ID 100
   Cluster_101 → Global ID 101
```

**Linkage Methods**:
- **Single**: Min distance between any pair → Aggressive merging
- **Complete**: Max distance between any pair → Conservative merging
- **Average**: Average distance → Balanced (recommended)

## ⚙️ Configuration

### Live MTMC Config Example

**File**: `config/examples/live_parking.yaml`

```yaml
OUTPUT_DIR: "output/live_parking_mtmc"

SYSTEM:
  GPU_IDS: [0]  # GPU to use

MOT:
  # ReID Model (choose one for performance)
  REID_MODEL_OPTS: "models/mobilenetv4_small/opts.yaml"
  REID_MODEL_CKPT: "models/mobilenetv4_small/net_19.pth"
  REID_ONNX: "models/mobilenetv4_small/model.onnx"  # Recommended: 3x faster
  REID_BATCHSIZE: 16
  REID_FP16: true
  
  # Detection
  DETECTOR: "yolov8s"
  TRACKED_CLASSES: [2, 5, 7]  # car, bus, truck
  
  # Tracking
  TRACKER: "bytetrack_iou"  # Fast, good for live
  MIN_FRAMES: 1

MTMC:
  CAMERA_LAYOUT: 'config/examples/parking_camera_layout.txt'  # Required!
  LINKAGE: 'average'
  MIN_SIM: 0.5  # Merge tracks with similarity > 0.5

LIVE:
  FPS: 10                  # Target FPS per camera
  MAX_SKEW: 1              # Max frame difference between cameras
  CLUSTER_INTERVAL: 2.0    # Re-cluster every 2 seconds
  MIN_TRACK_FRAMES: 3      # Ignore very short tracks
  PORT: 8080               # HTTP server port
  STALL_SECONDS: 10.0      # Remove stalled cameras after 10s
  
  CAMERAS:
    - name: "cam_entrance"
      video: "datasets/entrance.mp4"  # or RTSP URL
      tracked_classes: [2, 5, 7]
      
    - name: "cam_parking"
      video: "datasets/parking.mp4"
      detection_mask: "masks/parking_mask.jpg"  # Optional
      
    - name: "cam_exit"
      video: "datasets/exit.mp4"
      tracked_classes: [2, 5, 7]
```

### Integration with SmartParking

**Scenario**: Replace single-camera tracking with MTMC in the main system

**Step 1**: Update Backend to Use MTMC

**File**: `server/services/mtmc_service.py` (NEW)
```python
import subprocess
import requests
from typing import Dict, List, Any

class MTMCService:
    """
    Service to integrate vehicle_mtmc with SmartParking backend
    """
    
    def __init__(self, mtmc_port: int = 8080):
        self.mtmc_port = mtmc_port
        self.process = None
    
    async def start_mtmc(self, cameras: List[Dict]):
        """
        Start Live MTMC process with camera streams
        
        Args:
            cameras: List of camera configs from Firebase
                     [{id, name, streamUrl, ...}, ...]
        """
        # Generate config file
        config = self._generate_config(cameras)
        config_path = "config/generated_live_parking.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        # Start Live MTMC process
        cmd = [
            "python", "vehicle_mtmc/mtmc/run_live_mtmc.py",
            "--config", config_path
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    
    async def get_detections(self, camera_id: str) -> List[Dict]:
        """
        Get current detections with global IDs for a camera
        
        Returns:
            List of detections with global track IDs
        """
        # MTMC streams MJPEG, not JSON detections
        # For detection data, need to add API endpoint to run_live_mtmc.py
        # OR parse from log files
        pass
    
    def _generate_config(self, cameras: List[Dict]) -> Dict:
        """Generate YAML config from Firebase cameras"""
        config = {
            "OUTPUT_DIR": "output/smartparking_mtmc",
            "SYSTEM": {"GPU_IDS": [0]},
            "MOT": {
                "REID_MODEL_OPTS": "models/mobilenetv4_small/opts.yaml",
                "REID_MODEL_CKPT": "models/mobilenetv4_small/net_19.pth",
                "REID_ONNX": "models/mobilenetv4_small/model.onnx",
                "REID_BATCHSIZE": 16,
                "REID_FP16": True,
                "DETECTOR": "yolov8s_car_custom.pt",
                "TRACKED_CLASSES": [0],  # Custom car class
                "TRACKER": "bytetrack_iou",
                "MIN_FRAMES": 1
            },
            "MTMC": {
                "CAMERA_LAYOUT": "config/smartparking_layout.txt",
                "LINKAGE": "average",
                "MIN_SIM": 0.5
            },
            "LIVE": {
                "FPS": 10,
                "MAX_SKEW": 1,
                "CLUSTER_INTERVAL": 2.0,
                "MIN_TRACK_FRAMES": 3,
                "PORT": 8080,
                "STALL_SECONDS": 10.0,
                "CAMERAS": []
            }
        }
        
        # Add cameras
        for cam in cameras:
            config["LIVE"]["CAMERAS"].append({
                "name": cam["id"],
                "video": cam["streamUrl"],  # ESP32 or RTSP URL
                "tracked_classes": [0]
            })
        
        return config
```

**Step 2**: Update Frontend to Display Global IDs

**File**: `frontend/src/pages/DetectionViewer.tsx` (UPDATE)
```typescript
// OLD: Single camera with local IDs
<div className="detection-label">
  Vehicle ID: {detection.trackId}  // Local ID, different per camera
</div>

// NEW: Multi-camera with global IDs
<div className="detection-label">
  Global ID: {detection.globalTrackId}  // Same across all cameras
  {detection.localTrackId && (
    <span className="text-xs">(Local: {detection.localTrackId})</span>
  )}
</div>
```

## 🚀 Running Multi-Camera Tracking

### Batch Processing (Offline Videos)

**Command**:
```bash
cd vehicle_mtmc
export PYTHONPATH=$(pwd)
python3 mtmc/run_express_mtmc.py --config examples/express_parking.yaml
```

**Output**:
```
output/parking_mtmc/
├── 0_cam_entrance/
│   ├── mot.pkl          # Single-camera tracks
│   ├── mtmc.pkl         # Multi-camera tracks with global IDs
│   └── mtmc.mp4         # Video with global IDs
├── 1_cam_parking/
│   ├── mot.pkl
│   ├── mtmc.pkl
│   └── mtmc.mp4
└── 2_cam_exit/
    ├── mot.pkl
    ├── mtmc.pkl
    └── mtmc.mp4
```

### Live Streaming

**Command**:
```bash
cd vehicle_mtmc
export PYTHONPATH=$(pwd)
python3 mtmc/run_live_mtmc.py --config examples/live_parking.yaml
```

**Access streams**:
- `http://localhost:8080/` - Index page
- `http://localhost:8080/cam_entrance.mjpg` - Live stream with global IDs
- `http://localhost:8080/cam_parking.mjpg`
- `http://localhost:8080/cam_exit.mjpg`

### Integration with SmartParking

**Terminal 1: Start MTMC**
```bash
cd vehicle_mtmc
conda activate vehicle_mtmc
export PYTHONPATH=$(pwd)
python3 mtmc/run_live_mtmc.py --config ../config/smartparking_live.yaml
```

**Terminal 2: Start SmartParking Backend**
```bash
cd server
conda activate scheduler
python main_fastapi.py
# Backend can proxy MTMC streams or use them directly
```

**Terminal 3: Start Frontend**
```bash
cd frontend
npm run dev
# Frontend can embed MTMC streams via iframe or fetch MJPEG directly
```

## 📈 Performance Optimization

### Speed Benchmarks

| Configuration | FPS per Camera | Total Throughput |
|--------------|----------------|------------------|
| ResNet50 + YOLOv8s (PyTorch) | 5 FPS | 15 FPS (3 cams) |
| MobileNetV4 + YOLOv8s (ONNX) | 15 FPS | 45 FPS (3 cams) |
| MobileNetV4 + YOLOv8s (TensorRT) | 25 FPS | 75 FPS (3 cams) |

**Hardware**: NVIDIA RTX 3090

### Optimization Tips

1. **Use ONNX ReID Model** (3x speedup)
   ```yaml
   MOT:
     REID_ONNX: "models/mobilenetv4_small/model.onnx"
   ```

2. **Enable FP16** (2x speedup)
   ```yaml
   MOT:
     REID_FP16: true
   ```

3. **Use Lightweight Models**
   - YOLOv8n instead of YOLOv8x
   - MobileNetV4 instead of ResNet50

4. **Increase Batch Size** (better GPU utilization)
   ```yaml
   MOT:
     REID_BATCHSIZE: 32  # Up from 16
   ```

5. **Reduce Clustering Frequency** (less overhead)
   ```yaml
   LIVE:
     CLUSTER_INTERVAL: 5.0  # Cluster every 5s instead of 2s
   ```

## 🐛 Common Issues

### Issue 1: Tracks Not Merging Across Cameras

**Symptom**: Same vehicle has different global IDs in each camera

**Causes**:
- `MIN_SIM` too high (tracks are similar but not enough)
- ReID features not distinctive enough
- Temporal constraints too strict

**Solutions**:
```yaml
MTMC:
  MIN_SIM: 0.4  # Lower from 0.5
  LINKAGE: 'single'  # Try more aggressive linkage
```

Update camera layout:
```
# Increase max_time to allow more travel time
0 1 2.0 15.0  # Was 2.0 10.0
```

### Issue 2: Cameras Out of Sync

**Symptom**: VirtualClock warnings "Worker X stalled"

**Causes**:
- One camera much slower than others
- Video file ended but others still running

**Solutions**:
```yaml
LIVE:
  MAX_SKEW: 2  # Allow more frame difference
  STALL_SECONDS: 20.0  # Longer timeout
```

Or reduce FPS:
```yaml
LIVE:
  FPS: 5  # Lower target FPS
```

### Issue 3: Low Detection Rate

**Symptom**: Many vehicles not detected or tracked

**Solutions**:
```yaml
MOT:
  DETECTOR: "yolov8x6"  # Larger, more accurate model
  TRACKED_CLASSES: [0, 1, 2, 3, 5, 7]  # Track more classes
  MIN_FRAMES: 1  # Show tracks immediately
```

## 🎓 Key Differences: Old vs New

| Aspect | Old (Single Camera) | New (Multi-Camera MTMC) |
|--------|---------------------|-------------------------|
| **Track IDs** | Local per camera | Global across all cameras |
| **ID Consistency** | No correlation | Same vehicle = same ID |
| **Processing** | Independent | Synchronized |
| **ReID Usage** | Optional | Required for matching |
| **Complexity** | Low | Medium |
| **Accuracy** | Good for single view | Excellent for overall tracking |
| **Plate Propagation** | No | Yes (detect once, show everywhere) |
| **System Location** | `server/` | `vehicle_mtmc/` |
| **Dependencies** | FastAPI, YOLO | FastAPI, YOLO, ReID, Clustering |

## 📚 Related Documentation

- [Part 1: MTMC Overview](../TRACKING/01_LIVE_MTMC_OVERVIEW.md)
- [Part 2: MTMC Setup](../TRACKING/02_LIVE_MTMC_SETUP.md)
- [Part 3: MTMC Config](../TRACKING/03_LIVE_MTMC_CONFIG.md)
- [Part 4: Running MTMC](../TRACKING/04_LIVE_MTMC_RUNNING.md)
- [Vehicle MTMC System](../TRACKING/VEHICLE_MTMC_SYSTEM.md)
- [Backend Architecture](04_BACKEND_ARCHITECTURE.md)
- [Technical Deep Dive](07_TECHNICAL_DEEP_DIVE.md)

---

**Summary**: The Multi-Camera Tracking (MTMC) system transforms SmartParking from isolated camera views into a unified tracking system with global vehicle identification, enabling true cross-camera monitoring and analytics.
