# Multi-Camera Tracking (MTMC) - Quick Start Guide

## What is MTMC?

**Multi-Target Multi-Camera (MTMC) tracking** enables the SmartParking system to track vehicles across multiple cameras with **unified global IDs**.

### Problem It Solves

**Before (Single-Camera)**:
- Camera A: Vehicle ID 5
- Camera B: Vehicle ID 5 (different vehicle!)
- Camera C: Vehicle ID 5 (yet another vehicle!)
- ❌ No way to know if these are the same vehicle

**After (Multi-Camera MTMC)**:
- Camera A: Local ID 5 → **Global ID 100**
- Camera B: Local ID 3 → **Global ID 100** (same vehicle!)
- Camera C: Local ID 7 → **Global ID 100** (same vehicle!)
- ✅ Same vehicle has same ID everywhere

## Quick Start

### 1. Navigate to vehicle_mtmc Directory

```bash
cd vehicle_mtmc
export PYTHONPATH=$(pwd)
```

### 2. Create Conda Environment

```bash
conda create -n vehicle_mtmc python=3.10
conda activate vehicle_mtmc
pip install cython "numpy>=1.18.5,<1.23.0"
pip install -r requirements.txt
```

### 3. Download Models

Download from: https://drive.google.com/drive/folders/1ELQIlmrxrV3HmLzS3Og53ytRdu5kiscD

Extract to: `vehicle_mtmc/models/`

**Required models**:
- ResNet50-IBN ReID model: `models/resnet50_mixstyle/`
- OR MobileNetV4 (faster): `models/mobilenetv4_small/`

### 4. Create Configuration File

**File**: `config/examples/smartparking_live.yaml`

```yaml
OUTPUT_DIR: "output/smartparking_mtmc"

SYSTEM:
  GPU_IDS: [0]

MOT:
  # Use lightweight model for speed
  REID_MODEL_OPTS: "models/mobilenetv4_small/opts.yaml"
  REID_MODEL_CKPT: "models/mobilenetv4_small/net_19.pth"
  REID_ONNX: "models/mobilenetv4_small/model.onnx"  # Optional: 3x faster
  REID_BATCHSIZE: 16
  REID_FP16: true
  
  DETECTOR: "yolov8s"
  TRACKED_CLASSES: [2, 5, 7]  # car, bus, truck
  TRACKER: "bytetrack_iou"
  MIN_FRAMES: 1

MTMC:
  CAMERA_LAYOUT: 'config/examples/smartparking_layout.txt'
  LINKAGE: 'average'
  MIN_SIM: 0.5

LIVE:
  FPS: 10
  MAX_SKEW: 1
  CLUSTER_INTERVAL: 2.0
  MIN_TRACK_FRAMES: 3
  PORT: 8080
  STALL_SECONDS: 10.0
  
  CAMERAS:
    - name: "cam_entrance"
      video: "../ESP32/videos/entrance.mp4"  # or RTSP URL
      
    - name: "cam_parking"
      video: "../ESP32/videos/parking.mp4"
      
    - name: "cam_exit"
      video: "../ESP32/videos/exit.mp4"
```

### 5. Create Camera Layout File

**File**: `config/examples/smartparking_layout.txt`

```
# Camera transition constraints
# Format: cam_from cam_to min_time max_time

0 1 2.0 10.0   # Entrance → Parking: 2-10 seconds
0 2 5.0 20.0   # Entrance → Exit: 5-20 seconds
1 2 1.0 15.0   # Parking → Exit: 1-15 seconds

# FPS per camera
fps 30 30 30

# Time offset (if videos not synced)
offset 0.0 0.0 0.0

# Scale factor
scale 1.0 1.0 1.0
```

### 6. Run Live MTMC

```bash
cd vehicle_mtmc
conda activate vehicle_mtmc
export PYTHONPATH=$(pwd)
python3 mtmc/run_live_mtmc.py --config examples/smartparking_live.yaml
```

### 7. View Streams

Open browser:
- **http://localhost:8080/** - Index page with all cameras
- **http://localhost:8080/cam_entrance.mjpg** - Entrance stream
- **http://localhost:8080/cam_parking.mjpg** - Parking stream
- **http://localhost:8080/cam_exit.mjpg** - Exit stream

**Watch for**:
- ✅ Vehicles have **global IDs** in all cameras
- ✅ Same vehicle keeps same ID across cameras
- ✅ Different vehicles have different IDs

## Key Concepts

### 1. VirtualClock (Synchronization)

**Purpose**: Keep all cameras processing same time window

**Config**:
```yaml
LIVE:
  FPS: 10         # Process 10 frames/second per camera
  MAX_SKEW: 1     # Max 1 frame difference allowed
```

### 2. ReID (Re-Identification)

**Purpose**: Extract appearance features to match vehicles

**Models** (choose one):
- **ResNet50-IBN**: Best accuracy (slow)
- **MobileNetV4**: Good speed/accuracy balance ⭐ Recommended
- **EfficientNet-B0**: Balanced

### 3. Hierarchical Clustering

**Purpose**: Group tracks from different cameras

**How it works**:
1. Compute similarity between all track pairs (ReID features)
2. Merge tracks with similarity > MIN_SIM
3. Assign global IDs to merged clusters

**Config**:
```yaml
MTMC:
  MIN_SIM: 0.5      # Merge if similarity > 0.5
  LINKAGE: 'average' # How to compute cluster distance
```

### 4. Camera Layout Constraints

**Purpose**: Only match tracks that make physical sense

**Example**: Vehicle can't be in Exit before entering Entrance

**Format**: `cam_from cam_to min_time max_time`

## Performance Tips

### Speed Up Processing (3-10x faster)

1. **Use ONNX ReID Model**:
   ```bash
   python3 reid/onnx_exporter.py \
     --opts models/mobilenetv4_small/opts.yaml \
     --checkpoint models/mobilenetv4_small/net_19.pth \
     --output models/mobilenetv4_small/model.onnx
   ```
   
   Then enable in config:
   ```yaml
   MOT:
     REID_ONNX: "models/mobilenetv4_small/model.onnx"
   ```

2. **Enable FP16** (half precision):
   ```yaml
   MOT:
     REID_FP16: true
   ```

3. **Use Lightweight Models**:
   - YOLOv8n instead of YOLOv8x
   - MobileNetV4 instead of ResNet50

4. **Increase Batch Size** (better GPU utilization):
   ```yaml
   MOT:
     REID_BATCHSIZE: 32  # Up from 16
   ```

### Accuracy Improvements

1. **Lower MIN_SIM** (more aggressive matching):
   ```yaml
   MTMC:
     MIN_SIM: 0.4  # Down from 0.5
   ```

2. **Use Better ReID Model**:
   ```yaml
   MOT:
     REID_MODEL_OPTS: "models/resnet50_mixstyle/opts.yaml"
     REID_MODEL_CKPT: "models/resnet50_mixstyle/net_19.pth"
   ```

3. **Adjust Camera Layout** (more relaxed constraints):
   ```
   0 1 1.0 15.0  # Was 2.0 10.0 - wider time window
   ```

## Troubleshooting

### Tracks Not Merging

**Symptom**: Same vehicle has different IDs in each camera

**Solutions**:
1. Lower `MIN_SIM` from 0.5 to 0.4
2. Check camera layout constraints (times too strict?)
3. Try `LINKAGE: 'single'` (more aggressive)

### Cameras Out of Sync

**Symptom**: "Worker X stalled" warnings

**Solutions**:
1. Increase `MAX_SKEW` from 1 to 2
2. Increase `STALL_SECONDS` from 10 to 20
3. Lower `FPS` from 10 to 5

### Low FPS

**Symptom**: Processing slower than real-time

**Solutions**:
1. Export ReID model to ONNX
2. Enable `REID_FP16: true`
3. Use MobileNetV4 instead of ResNet50
4. Use YOLOv8n instead of YOLOv8s

## Integration with SmartParking

### Option 1: Proxy MTMC Streams (Easiest)

**Frontend** can directly embed MTMC streams:

```typescript
// frontend/src/pages/MultiCameraView.tsx
<img 
  src="http://localhost:8080/cam_entrance.mjpg"
  alt="Entrance Camera with Global IDs"
/>
```

### Option 2: MTMC Service (Advanced)

**Backend** spawns MTMC process and proxies streams:

```python
# server/services/mtmc_service.py
class MTMCService:
    def __init__(self):
        self.process = None
    
    async def start(self, cameras: List[Dict]):
        # Generate config
        config = self._generate_config(cameras)
        
        # Start MTMC process
        self.process = subprocess.Popen([
            "python", "vehicle_mtmc/mtmc/run_live_mtmc.py",
            "--config", "config/generated.yaml"
        ])
```

## Complete Documentation

For detailed information, see:
- **[09_MULTI_CAMERA_TRACKING.md](../quicksummary/09_MULTI_CAMERA_TRACKING.md)** - Complete MTMC guide
- **[01_LIVE_MTMC_OVERVIEW.md](01_LIVE_MTMC_OVERVIEW.md)** - Architecture overview
- **[02_LIVE_MTMC_SETUP.md](02_LIVE_MTMC_SETUP.md)** - Detailed setup
- **[03_LIVE_MTMC_CONFIG.md](03_LIVE_MTMC_CONFIG.md)** - Configuration reference
- **[VEHICLE_MTMC_SYSTEM.md](VEHICLE_MTMC_SYSTEM.md)** - System details

## Next Steps

1. ✅ Get MTMC running with example videos
2. ✅ Understand global ID assignment
3. ✅ Optimize for your hardware (ONNX, FP16)
4. ✅ Integrate with SmartParking frontend
5. ✅ Add real camera streams (RTSP/ESP32)

---

**Success Criteria**: When you see vehicles with **same global ID** appearing in multiple camera streams! 🎉
