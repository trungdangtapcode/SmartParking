# Live MTMC Tracking - Part 2: Installation and Setup

## Table of Contents
- [Part 1: Overview and Architecture](01_LIVE_MTMC_OVERVIEW.md)
- [Part 2: Installation and Setup](02_LIVE_MTMC_SETUP.md) ← **You are here**
- [Part 3: Configuration Guide](03_LIVE_MTMC_CONFIG.md)
- [Part 4: Running the System](04_LIVE_MTMC_RUNNING.md)
- [Part 5: Code Reference](05_LIVE_MTMC_CODE_REFERENCE.md)
- [Part 6: Troubleshooting](06_LIVE_MTMC_TROUBLESHOOTING.md)

---

## Prerequisites

### Hardware Requirements

**Minimum**:
- CPU: 4 cores
- RAM: 8 GB
- GPU: NVIDIA GPU with 4GB VRAM (GTX 1050 Ti or better)
- Storage: 10 GB free

**Recommended**:
- CPU: 8+ cores (Intel i7/i9, AMD Ryzen 7/9)
- RAM: 16 GB
- GPU: NVIDIA GPU with 8GB+ VRAM (RTX 3060 or better)
- Storage: 20 GB free

**For 3+ cameras**:
- CPU: 16+ cores
- RAM: 32 GB
- GPU: RTX 3080 or better (10GB+ VRAM)

### Software Requirements

**Operating System**:
- Linux (Ubuntu 20.04/22.04 recommended)
- Windows 10/11 (with CUDA support)

**NVIDIA Drivers**:
```bash
# Check NVIDIA driver
nvidia-smi
```
Should show CUDA 11.0 or higher.

**Python**:
- Python 3.10 (tested version)
- Python 3.8-3.11 may work

## Step-by-Step Installation

### 1. Clone Repository

**Location**: `/mnt/mmlab2024nas/vund/.svn/bin/vehicle_mtmc/`

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/regob/vehicle_mtmc.git
cd vehicle_mtmc

# If already cloned without submodules:
git submodule update --init --recursive
```

**Important submodules**:
- `detection/yolov5/` - YOLOv5 detector
- `reid/vehicle_reid/` - ReID training code

### 2. Create Virtual Environment

**Using Conda** (recommended):
```bash
conda create -n vehicle_mtmc python=3.10
conda activate vehicle_mtmc
```

**Using venv**:
```bash
python3.10 -m venv venv
source venv/bin/activate  # Linux
# or
venv\Scripts\activate  # Windows
```

### 3. Install Cython and NumPy

**Required before other packages**:

**File reference**: `requirements.txt` lists numpy version constraint

```bash
pip install cython "numpy>=1.18.5,<1.23.0"
```

**Why**: Other packages (scipy, cython_bbox) need these pre-installed.

### 4. Install Requirements

**File**: `vehicle_mtmc/requirements.txt`

```bash
pip install -r requirements.txt
```

**Key packages installed**:
- `torch==1.13.0` - PyTorch for deep learning
- `torchvision==0.14.0` - Vision utilities
- `opencv-python==4.5.5.64` - Computer vision
- `yacs>=0.1.8` - Configuration system (used in `config/defaults.py`)
- `imageio>=2.9.0` - Video I/O
- `motmetrics>=1.2.5` - Evaluation metrics
- `onnxruntime-gpu==1.16.3` - ONNX acceleration

### 5. Install Additional Packages

**For YOLOv8 support**:
```bash
pip install ultralytics
```
**Used in**: `detection/load_detector.py` (Lines 10-30)

**For ALPR (optional)**:
```bash
pip install fast-alpr
```
**Used in**: `mot/plate_recognition.py` (if exists)

**For TensorRT (optional, advanced)**:
```bash
# TensorRT installation is complex, see:
# https://developer.nvidia.com/tensorrt
```
**Used in**: `reid/tensorrt_feature_extractor.py` (Lines 1-50)

### 6. Download Pretrained Models

**Google Drive link**: https://drive.google.com/drive/folders/1ELQIlmrxrV3HmLzS3Og53ytRdu5kiscD

**Download and extract to**: `vehicle_mtmc/models/`

**Expected structure**:
```
vehicle_mtmc/
├── models/
│   ├── resnet50_mixstyle/
│   │   ├── opts.yaml          # Model config
│   │   ├── net_19.pth         # Checkpoint
│   │   └── model.onnx         # ONNX version (optional)
│   ├── efficientnetb0/
│   │   ├── opts.yaml
│   │   └── net_19.pth
│   ├── mobilenetv4_small/
│   │   ├── opts.yaml
│   │   └── net_19.pth
│   ├── color_svm.pkl          # Attribute classifier
│   ├── type_svm.pkl           # Attribute classifier
│   └── yolov8s_car_custom.pt  # Custom YOLO (if available)
```

**Referenced in**:
- Config file: `config/examples/live_parking.yaml` (Lines 5-6)
- Loading: `mot/run_tracker.py` (Lines 119-135)

### 7. Verify Installation

**Test script**:
```bash
# Set PYTHONPATH
export PYTHONPATH=$(pwd)

# Test imports
python3 -c "
import torch
import cv2
import yacs
from ultralytics import YOLO
print('✓ All imports successful')
print(f'✓ PyTorch: {torch.__version__}')
print(f'✓ CUDA available: {torch.cuda.is_available()}')
print(f'✓ CUDA device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')
"
```

**Expected output**:
```
✓ All imports successful
✓ PyTorch: 1.13.0+cu117
✓ CUDA available: True
✓ CUDA device: NVIDIA GeForce RTX 3080
```

## Configuration File Setup

### Default Config

**File**: `vehicle_mtmc/config/defaults.py`

Contains all default values. The LIVE section (Lines 175-190):

```python
# Live (online MOT + MTMC + streaming) config
_C.LIVE = CN()
_C.LIVE.TARGET_FPS = 8
_C.LIVE.MJPEG_PORT = 8080
_C.LIVE.SIMILARITY_THRESHOLD = 0.5
_C.LIVE.GLOBAL_FEATURE_EMA = 0.0
_C.LIVE.MAX_INACTIVE_SECS = 3.0
_C.LIVE.LOOP_VIDEO = True
_C.LIVE.SLEEP_ON_EMPTY = 0.02
_C.LIVE.MAX_SKEW_TICKS = 1
_C.LIVE.STALL_SECONDS = 5.0
_C.LIVE.MIN_TRACK_FRAMES = 5
_C.LIVE.CLUSTER_INTERVAL = 10.0
```

### Example Config

**File**: `vehicle_mtmc/config/examples/live_parking.yaml`

```yaml
OUTPUT_DIR: "output/live_parking"
DEBUG_RUN: false
FONTSIZE: 11

MOT:
  REID_MODEL_OPTS: "models/resnet50_mixstyle/opts.yaml"
  REID_BATCHSIZE: 16
  DETECTOR: "yolov8s_car_custom.pt"
  TRACKER: "bytetrack_iou"
  TRACKED_CLASSES: [0]
  MIN_FRAMES: 1
  REID_ONNX: "models/resnet50_mixstyle/model.onnx"

MTMC:
  CAMERA_LAYOUT: 'config/examples/parking_camera_layout.txt'
  LINKAGE: 'average'
  MIN_SIM: 0.5

EXPRESS:
  CAMERAS:
    - "video": "datasets/parking_a_75sec_8fps.mp4"
      "name": "cam_a"
      "detector": "yolov8s"
      "tracked_classes": [1, 2, 3, 5, 7]
    - "video": "datasets/parking_b_75sec_8fps.mp4"
      "name": "cam_b"
    - "video": "datasets/parking_c_75sec_8fps.mp4"
      "name": "cam_c"

LIVE:
  TARGET_FPS: 8
  MJPEG_PORT: 8080
  CLUSTER_INTERVAL: 10.0
```

### Camera Layout File

**File**: `vehicle_mtmc/config/examples/parking_camera_layout.txt`

Defines temporal constraints between cameras:

```
# Camera transitions (cam_from cam_to min_seconds max_seconds)
0 1 2.0 10.0    # Cam 0 → Cam 1: 2-10 seconds travel time
0 2 3.0 15.0    # Cam 0 → Cam 2: 3-15 seconds
1 2 1.0 8.0     # Cam 1 → Cam 2: 1-8 seconds

# Frame rates
fps 30 30 30

# Time offsets (if videos not synchronized)
offset 0.0 0.0 0.0

# Scale factors (if videos sped up/slowed down)
scale 1.0 1.0 1.0
```

**Used in**:
- `mtmc/cameras.py` - Loads and parses this file
- `mtmc/mtmc_clustering.py` - Uses constraints for matching

## Preparing Video Sources

### Option 1: Use Sample Videos

```bash
# Create datasets directory
mkdir -p datasets

# Download sample (example)
wget https://example.com/parking_video.mp4 -O datasets/parking_a.mp4
```

### Option 2: Use RTSP Streams

For live cameras:

```yaml
EXPRESS:
  CAMERAS:
    - video: "rtsp://192.168.1.100:554/stream1"
      name: "entrance_cam"
    - video: "rtsp://192.168.1.101:554/stream1"
      name: "parking_cam"
```

**Testing RTSP**:
```bash
# Test RTSP stream with ffplay
ffplay rtsp://192.168.1.100:554/stream1

# Or with OpenCV
python3 -c "
import cv2
cap = cv2.VideoCapture('rtsp://192.168.1.100:554/stream1')
ret, frame = cap.read()
print(f'Stream OK: {ret}, Frame shape: {frame.shape if ret else None}')
cap.release()
"
```

### Option 3: Convert Existing Videos

**Reduce FPS** (for faster processing):
```bash
ffmpeg -i input.mp4 -filter:v fps=8 -c:a copy output_8fps.mp4
```

**Resize** (for lower resolution):
```bash
ffmpeg -i input.mp4 -vf scale=1280:720 output_720p.mp4
```

**Trim video**:
```bash
# First 30 seconds
ffmpeg -i input.mp4 -t 30 -c copy output_30sec.mp4
```

## Directory Structure After Setup

```
vehicle_mtmc/
├── config/
│   ├── defaults.py              # Default config values
│   ├── config_tools.py          # Config utilities
│   ├── verify_config.py         # Validation
│   └── examples/
│       ├── live_parking.yaml    # Live MTMC config
│       ├── express_parking.yaml # Batch MTMC config
│       └── parking_camera_layout.txt
├── detection/
│   ├── load_detector.py         # YOLO loading
│   └── yolov5/                  # Submodule
├── mot/
│   ├── run_tracker.py           # MOT pipeline
│   ├── tracker.py               # Tracker implementations
│   └── tracklet.py              # Track data structure
├── mtmc/
│   ├── run_live_mtmc.py         # ← LIVE MTMC MAIN FILE
│   ├── run_express_mtmc.py      # Batch MTMC
│   ├── mtmc_clustering.py       # Clustering algorithm
│   └── cameras.py               # Camera constraints
├── reid/
│   ├── feature_extractor.py     # ReID extraction
│   ├── onnx_feature_extractor.py
│   └── vehicle_reid/            # Submodule
├── models/                       # Downloaded models
│   ├── resnet50_mixstyle/
│   ├── efficientnetb0/
│   └── *.pkl
├── datasets/                     # Your videos
│   ├── parking_a.mp4
│   ├── parking_b.mp4
│   └── parking_c.mp4
├── output/                       # Results
│   └── live_parking/
├── requirements.txt              # Dependencies
└── run_live_mtmc.sh             # Convenience script
```

## Quick Test Run

### 1. Prepare Test Videos

```bash
# Option A: Use existing videos
cp /path/to/your/videos/*.mp4 datasets/

# Option B: Download test videos (example)
# Place your 3 camera videos in datasets/
```

### 2. Update Config

Edit `config/examples/live_parking.yaml`:

```yaml
EXPRESS:
  CAMERAS:
    - video: "datasets/your_camera_a.mp4"  # ← Change these
      name: "cam_a"
    - video: "datasets/your_camera_b.mp4"
      name: "cam_b"
    - video: "datasets/your_camera_c.mp4"
      name: "cam_c"
```

### 3. Run Quick Test

```bash
export PYTHONPATH=$(pwd)
python3 mtmc/run_live_mtmc.py --config examples/live_parking.yaml
```

**Expected output**:
```
[INFO] Loading TensorRT ReID engine from models/resnet50_mixstyle/model.onnx
[INFO] Camera layout loaded with 3 cams.
[INFO] MJPEG server started on port 8080
[INFO] Starting camera cam_a
[INFO] Starting camera cam_b
[INFO] Starting camera cam_c
```

### 4. View Stream

Open browser:
```
http://localhost:8080/
```

You should see:
- Index page listing all cameras
- Click on camera links to view streams
- Videos with bounding boxes and global IDs

### 5. Stop System

```bash
# Press Ctrl+C in terminal
^C
[INFO] Stopping live MTMC...
```

## Next Steps

- **Part 3**: Learn about configuration options
- **Part 4**: Detailed running instructions
- **Part 5**: Code reference and customization
- **Part 6**: Troubleshooting common issues

---

**Previous**: [Part 1: Overview and Architecture](01_LIVE_MTMC_OVERVIEW.md)  
**Next**: [Part 3: Configuration Guide](03_LIVE_MTMC_CONFIG.md)
