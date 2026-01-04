# Live MTMC Tracking - Part 3: Configuration Guide

## Table of Contents
- [Part 1: Overview and Architecture](01_LIVE_MTMC_OVERVIEW.md)
- [Part 2: Installation and Setup](02_LIVE_MTMC_SETUP.md)
- [Part 3: Configuration Guide](03_LIVE_MTMC_CONFIG.md) ← **You are here**
- [Part 4: Running the System](04_LIVE_MTMC_RUNNING.md)
- [Part 5: Code Reference](05_LIVE_MTMC_CODE_REFERENCE.md)
- [Part 6: Troubleshooting](06_LIVE_MTMC_TROUBLESHOOTING.md)

---

## Configuration System Overview

**Files involved**:
- `config/defaults.py` - All default values and schema
- `config/config_tools.py` - Config loading utilities
- `config/verify_config.py` - Validation functions
- `config/examples/*.yaml` - Example configurations

**How it works**:
1. Load defaults from `defaults.py`
2. Merge with your YAML file
3. Validate with `verify_config.py`
4. Expand relative paths with `config_tools.py`

## Configuration Sections

### SYSTEM Section

**File**: `config/defaults.py` (Lines 20-30)

```yaml
SYSTEM:
  GPU_IDS: [0]           # Which GPUs to use (0 = first GPU)
  CFG_DIR: "config/"     # Where config files are located
```

**Used in**:
- `mtmc/run_live_mtmc.py` (Line 308): Select GPU device
- All scripts: Load config files

**Example**:
```yaml
SYSTEM:
  GPU_IDS: [0, 1]  # Use 2 GPUs (round-robin for cameras)
```

### MOT Section

**File**: `config/defaults.py` (Lines 35-80)

Controls single-camera tracking behavior.

#### ReID Model Settings

```yaml
MOT:
  # Model files
  REID_MODEL_OPTS: "models/resnet50_mixstyle/opts.yaml"
  REID_MODEL_CKPT: "models/resnet50_mixstyle/net_19.pth"
  
  # Acceleration (choose one)
  REID_ONNX: "models/resnet50_mixstyle/model.onnx"  # 2-3x faster
  REID_TRT: ""  # TensorRT engine (5-10x faster, leave empty if not available)
  
  # Performance tuning
  REID_BATCHSIZE: 16    # Process N detections at once (higher = faster GPU use)
  REID_FP16: true       # Use half precision (2x faster, minimal accuracy loss)
```

**Loaded in**: `mtmc/run_live_mtmc.py` `build_extractor()` function (Lines 25-45)

**Model comparison**:

| Model | Feature Dim | Speed | Accuracy | File |
|-------|-------------|-------|----------|------|
| ResNet50-IBN | 2048 | Baseline | Best | `models/resnet50_mixstyle/` |
| EfficientNet-B0 | 512 | 2x faster | Good | `models/efficientnetb0/` |
| MobileNetV4 | 512 | 5x faster | Acceptable | `models/mobilenetv4_small/` |

#### Detector Settings

```yaml
MOT:
  DETECTOR: "yolov8s"  # or "yolov5x6", "yolov8s.pt", custom model
  TRACKED_CLASSES: [1, 2, 3, 5, 7]  # COCO classes to track
```

**COCO class IDs**:
- 0: person
- 1: bicycle
- 2: car
- 3: motorcycle
- 5: bus
- 7: truck

**Loaded in**: `mtmc/run_live_mtmc.py` (Line 280)

**Custom models**:
```yaml
MOT:
  DETECTOR: "yolov8s_car_custom.pt"  # Your fine-tuned model
  TRACKED_CLASSES: [0]  # Custom class 0 = car
```

#### Tracker Settings

```yaml
MOT:
  TRACKER: "bytetrack_iou"  # or "deepsort"
  MIN_FRAMES: 1  # Minimum frames before track is confirmed
```

**Used in**: `mtmc/run_live_mtmc.py` (Line 282)

**Tracker comparison**:

| Tracker | Speed | Accuracy | Uses ReID | File |
|---------|-------|----------|-----------|------|
| bytetrack_iou | Fast | Good | No | `mot/byte_track/` |
| deepsort | Slower | Better | Yes | `mot/deep_sort/` |

**Recommendation**: Use `bytetrack_iou` for live streaming (faster).

#### Optional Features

```yaml
MOT:
  DETECTION_MASK: "masks/camera_a_mask.jpg"  # Ignore certain areas
  CALIBRATION: "calibration/camera_a.txt"    # For speed estimation
  
  STATIC_ATTRIBUTES:  # Vehicle color/type classification
    - color: "models/color_svm.pkl"
    - type: "models/type_svm.pkl"
```

**Note**: Attributes slow down processing. Usually disabled for live streaming.

### MTMC Section

**File**: `config/defaults.py` (Lines 130-145)

Controls multi-camera matching.

```yaml
MTMC:
  CAMERA_LAYOUT: 'config/examples/parking_camera_layout.txt'  # Required!
  LINKAGE: 'average'   # Clustering method: 'single', 'complete', 'average'
  MIN_SIM: 0.5         # Minimum similarity to merge tracks (0-1)
```

**Used in**:
- `mtmc/run_live_mtmc.py` (Lines 413-420): Load camera layout and create aggregator
- `mtmc/mtmc_clustering.py` (Lines 73-191): Perform clustering

#### Camera Layout File Format

**File**: `config/examples/parking_camera_layout.txt`

```
# Format: cam_from cam_to min_travel_seconds max_travel_seconds
0 1 2.0 10.0   # From cam 0 to cam 1: takes 2-10 seconds
0 2 3.0 15.0
1 2 1.0 8.0

# Frame rates (if different per camera)
fps 30 30 30

# Time offsets (if videos not synchronized)
offset 0.0 0.0 0.0

# Scale factors (if videos sped up/slowed down)
scale 1.0 1.0 1.0
```

**How to determine travel times**:
1. Watch your videos
2. Note when same vehicle appears in different cameras
3. Calculate time difference
4. Add buffer (min = fastest route, max = slowest + detours)

**Parsed in**: `mtmc/cameras.py` `CameraLayout` class

#### Linkage Methods

**File**: `mtmc/mtmc_clustering.py` (Lines 43-67)

```yaml
MTMC:
  LINKAGE: 'average'
```

| Linkage | Description | When to use |
|---------|-------------|-------------|
| `single` | Min distance between any pair | Noisy data, want to merge similar |
| `complete` | Max distance between any pair | Clean data, want strict matching |
| `average` | **Average distance (recommended)** | **General use** |

#### Similarity Threshold

```yaml
MTMC:
  MIN_SIM: 0.5  # Range: 0.0 (merge everything) to 1.0 (only identical)
```

**Effect**:
- **Lower (0.3-0.4)**: More merging, risk of wrong matches
- **Medium (0.5-0.6)**: Balanced (recommended)
- **Higher (0.7-0.8)**: Conservative, may miss some matches

**Tuning**:
- Start with 0.5
- If too many wrong matches → increase
- If vehicles not matched across cameras → decrease

### EXPRESS Section

**File**: `config/defaults.py` (Lines 150-160)

Defines camera sources.

```yaml
EXPRESS:
  FINAL_VIDEO_OUTPUT: false  # Don't save videos in live mode
  CAMERAS:
    - video: "datasets/parking_a.mp4"
      name: "cam_a"
      detector: "yolov8s"
      tracked_classes: [1, 2, 3, 5, 7]
      detection_mask: "masks/cam_a_mask.jpg"  # Optional
      enable_alpr: true  # Optional (if ALPR supported)
    
    - video: "datasets/parking_b.mp4"
      name: "cam_b"
      # Inherits MOT defaults if not specified
    
    - video: "rtsp://192.168.1.100/stream"
      name: "entrance_cam"
      detector: "yolov8s_car_custom.pt"
      tracked_classes: [0]
```

**Per-camera overrides**:
- `video`: Source (required)
- `name`: Display name (optional, defaults to `cam_0`, `cam_1`, ...)
- `detector`: Override MOT.DETECTOR
- `tracked_classes`: Override MOT.TRACKED_CLASSES
- `detection_mask`: Per-camera mask
- `enable_alpr`: Enable plate recognition

**Used in**: `mtmc/run_live_mtmc.py` (Lines 425-435)

### LIVE Section

**File**: `config/defaults.py` (Lines 175-190)

Controls live streaming behavior.

```yaml
LIVE:
  # Frame rate
  TARGET_FPS: 8  # Process and stream at 8 FPS
  
  # HTTP server
  MJPEG_PORT: 8080  # Stream at http://localhost:8080
  
  # Camera synchronization
  MAX_SKEW_TICKS: 1  # Max frame difference between cameras
  STALL_SECONDS: 5.0  # Remove worker if stalled
  
  # Video source
  LOOP_VIDEO: true  # Restart video when finished
  SLEEP_ON_EMPTY: 0.02  # Sleep time when no frames
  
  # MTMC clustering
  CLUSTER_INTERVAL: 10.0  # Recluster every N seconds
  MIN_TRACK_FRAMES: 5  # Ignore short tracks
  
  # Track management
  MAX_INACTIVE_SECS: 3.0  # Remove track if not seen
  SIMILARITY_THRESHOLD: 0.5  # Same as MTMC.MIN_SIM (legacy)
  GLOBAL_FEATURE_EMA: 0.0  # Feature update: 0=replace, >0=EMA
```

**Used in**: `mtmc/run_live_mtmc.py` (Lines 405-420)

#### Performance Tuning

**TARGET_FPS**:
```yaml
LIVE:
  TARGET_FPS: 5   # Lower = less CPU, higher latency
  TARGET_FPS: 10  # Higher = more CPU, lower latency
  TARGET_FPS: 15  # Very high, may drop frames
```

**Used in**: `mtmc/run_live_mtmc.py` (Line 327) - Frame pacing

**CLUSTER_INTERVAL**:
```yaml
LIVE:
  CLUSTER_INTERVAL: 5.0   # Fast ID updates, high CPU
  CLUSTER_INTERVAL: 10.0  # Balanced (recommended)
  CLUSTER_INTERVAL: 20.0  # Slow updates, stable IDs
```

**Used in**: `mtmc/run_live_mtmc.py` (Line 164) - Clustering trigger

**MIN_TRACK_FRAMES**:
```yaml
LIVE:
  MIN_TRACK_FRAMES: 3   # Include more tracks (noisier)
  MIN_TRACK_FRAMES: 5   # Balanced
  MIN_TRACK_FRAMES: 10  # Only confident tracks
```

**Used in**: `mtmc/run_live_mtmc.py` (Line 179) - Track filtering

## Complete Example Configs

### Low-End System (1-2 cameras)

**File**: Create `config/examples/live_lowend.yaml`

```yaml
OUTPUT_DIR: "output/live_lowend"

SYSTEM:
  GPU_IDS: [0]

MOT:
  REID_MODEL_OPTS: "models/mobilenetv4_small/opts.yaml"
  REID_MODEL_CKPT: "models/mobilenetv4_small/net_19.pth"
  REID_ONNX: "models/mobilenetv4_small/model.onnx"
  REID_BATCHSIZE: 8
  REID_FP16: true
  DETECTOR: "yolov8n"  # Smallest YOLO
  TRACKER: "bytetrack_iou"
  TRACKED_CLASSES: [2]  # Cars only
  STATIC_ATTRIBUTES: []  # Disabled

MTMC:
  CAMERA_LAYOUT: 'config/examples/parking_camera_layout.txt'
  LINKAGE: 'average'
  MIN_SIM: 0.5

EXPRESS:
  CAMERAS:
    - video: "datasets/cam_a.mp4"
      name: "cam_a"
    - video: "datasets/cam_b.mp4"
      name: "cam_b"

LIVE:
  TARGET_FPS: 5
  MJPEG_PORT: 8080
  CLUSTER_INTERVAL: 15.0
  MIN_TRACK_FRAMES: 5
```

### High-End System (4+ cameras)

**File**: Create `config/examples/live_highend.yaml`

```yaml
OUTPUT_DIR: "output/live_highend"

SYSTEM:
  GPU_IDS: [0]

MOT:
  REID_MODEL_OPTS: "models/resnet50_mixstyle/opts.yaml"
  REID_MODEL_CKPT: "models/resnet50_mixstyle/net_19.pth"
  REID_TRT: "models/resnet50_mixstyle/model.trt"  # TensorRT
  REID_BATCHSIZE: 32
  REID_FP16: true
  DETECTOR: "yolov8m"  # Medium YOLO
  TRACKER: "deepsort"  # Better accuracy
  TRACKED_CLASSES: [1, 2, 3, 5, 7]
  STATIC_ATTRIBUTES:
    - color: "models/color_svm.pkl"
    - type: "models/type_svm.pkl"

MTMC:
  CAMERA_LAYOUT: 'config/examples/multi_camera_layout.txt'
  LINKAGE: 'average'
  MIN_SIM: 0.55

EXPRESS:
  CAMERAS:
    - video: "rtsp://192.168.1.100/stream"
      name: "entrance"
      detector: "yolov8m"
    - video: "rtsp://192.168.1.101/stream"
      name: "parking_lot"
    - video: "rtsp://192.168.1.102/stream"
      name: "exit"
    - video: "rtsp://192.168.1.103/stream"
      name: "side_lane"

LIVE:
  TARGET_FPS: 10
  MJPEG_PORT: 8080
  CLUSTER_INTERVAL: 8.0
  MIN_TRACK_FRAMES: 5
```

### RTSP Streaming Config

**File**: Create `config/examples/live_rtsp.yaml`

```yaml
OUTPUT_DIR: "output/live_rtsp"

MOT:
  REID_MODEL_OPTS: "models/resnet50_mixstyle/opts.yaml"
  REID_MODEL_CKPT: "models/resnet50_mixstyle/net_19.pth"
  REID_ONNX: "models/resnet50_mixstyle/model.onnx"
  REID_BATCHSIZE: 16
  DETECTOR: "yolov8s"
  TRACKER: "bytetrack_iou"
  TRACKED_CLASSES: [1, 2, 3, 5, 7]

MTMC:
  CAMERA_LAYOUT: 'config/examples/parking_camera_layout.txt'
  LINKAGE: 'average'
  MIN_SIM: 0.5

EXPRESS:
  CAMERAS:
    - video: "rtsp://admin:password@192.168.1.100:554/stream1"
      name: "entrance_cam"
    - video: "rtsp://admin:password@192.168.1.101:554/stream1"
      name: "parking_cam"
    - video: "rtsp://admin:password@192.168.1.102:554/stream1"
      name: "exit_cam"

LIVE:
  TARGET_FPS: 8
  MJPEG_PORT: 8080
  LOOP_VIDEO: false  # RTSP streams don't loop
  CLUSTER_INTERVAL: 10.0
```

## Validation

**File**: `config/verify_config.py`

Checks config before running:

```python
def check_mot_config(cfg):
    """Validate MOT section."""
    # Checks:
    # - REID model files exist
    # - DETECTOR is valid
    # - TRACKED_CLASSES is list
    # - VIDEO exists (for single camera)
```

**Used in**: `mtmc/run_live_mtmc.py` (implicit via config system)

**Common errors**:
```
[ERROR] REID_MODEL_OPTS file not found: models/xxx/opts.yaml
[ERROR] DETECTOR 'yolov9' not recognized
[ERROR] VIDEO file not found: datasets/missing.mp4
```

## Configuration Precedence

**Order** (later overrides earlier):
1. `config/defaults.py` - Base defaults
2. Your YAML file - Your settings
3. Command-line args - Runtime overrides

**Example**:
```bash
python3 mtmc/run_live_mtmc.py \
  --config examples/live_parking.yaml \
  --log-level DEBUG \
  --output-dir /tmp/test
```

## Next: Running the System

Now that configuration is understood, proceed to Part 4 for detailed running instructions.

---

**Previous**: [Part 2: Installation and Setup](02_LIVE_MTMC_SETUP.md)  
**Next**: [Part 4: Running the System](04_LIVE_MTMC_RUNNING.md)
