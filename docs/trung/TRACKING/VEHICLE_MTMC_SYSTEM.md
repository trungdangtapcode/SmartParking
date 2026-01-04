# Vehicle MTMC (Multi-Target Multi-Camera) Tracking System

## Overview

The `vehicle_mtmc` system is a comprehensive multi-camera vehicle tracking solution that performs:
- **Single-camera tracking (MOT)**: Detection and tracking of vehicles in individual video streams
- **Multi-camera tracking (MTMC)**: Matching and tracking vehicles across multiple cameras
- **Vehicle Re-Identification (ReID)**: Using deep learning to identify the same vehicle across cameras
- **License Plate Recognition (ALPR)**: Detecting and recognizing license plates
- **Attribute Extraction**: Determining vehicle color, type, and speed

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Vehicle MTMC System                       │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
        ┌───────▼────────┐         ┌───────▼────────┐
        │  MOT Pipeline  │         │ MTMC Pipeline  │
        │ (Single Camera)│         │ (Multi-Camera) │
        └───────┬────────┘         └───────┬────────┘
                │                           │
    ┌───────────┼───────────┐              │
    │           │           │              │
┌───▼───┐  ┌───▼───┐  ┌───▼────┐    ┌────▼─────┐
│Detect │  │ ReID  │  │Tracker │    │Clustering│
│YOLO   │  │ResNet │  │DeepSORT│    │Hierarchi │
│       │  │Mobile │  │ByteTrack    │   cal    │
└───────┘  └───────┘  └────────┘    └──────────┘
```

### Pipeline Flow

#### 1. **Detection Phase** (per camera, per frame)
```
Video Frame → YOLOv5/YOLOv8 Detector → Bounding Boxes
```
- **Input**: Video frame (RGB image)
- **Models**: YOLOv5x6, YOLOv8s, or custom trained models
- **Output**: Bounding boxes with class labels and confidence scores
- **Filtering**: By confidence threshold, class labels, and detection masks

#### 2. **Feature Extraction Phase** (ReID)
```
Cropped Vehicles → ReID Network → 512/2048D Feature Vectors
```
- **Models**: 
  - ResNet50-IBN (2048D features)
  - EfficientNet-B0 (512D features)
  - MobileNetV4 (lightweight, 512D features)
- **Purpose**: Extract appearance features to match vehicles across frames/cameras
- **Optimization**: ONNX Runtime, FP16 precision, batch processing

#### 3. **Single-Camera Tracking (MOT)**
```
Detections + Features → Tracker → Track IDs + Trajectories
```
- **Trackers**:
  - **DeepSORT**: Uses both appearance (ReID) and motion features
  - **ByteTrack IOU**: Fast, IOU-based association (no deep features)
- **Tracking Logic**:
  - Associates detections across frames
  - Maintains track IDs for vehicles
  - Handles occlusions and temporary disappearances
- **Output**: Tracklets (sequences of detections with same ID)

#### 4. **Attribute Extraction** (Optional)
```
Vehicle Crops + ReID Features → SVM Classifiers → Attributes
```
- **Color Classification**: SVM trained on ReID embeddings
- **Type Classification**: Car, truck, bus, motorcycle
- **Speed Estimation**: Using camera calibration and homography

#### 5. **License Plate Recognition (ALPR)**
```
Vehicle Crops → Fast-ALPR → Plate Text
```
- **Enabled per camera** (typically entrance cameras only)
- **Library**: fast-alpr Python package
- **Propagation**: Plates detected in one camera are propagated to all cameras via MTMC

#### 6. **Multi-Camera Matching (MTMC)**
```
Single-Camera Tracks → Hierarchical Clustering → Global IDs
```
- **Input**: Tracklets from all cameras
- **Method**: Hierarchical agglomerative clustering
- **Similarity**: Cosine similarity of ReID feature vectors
- **Constraints**:
  - Temporal constraints (min/max travel time between cameras)
  - Spatial constraints (camera layout, possible transitions)
- **Output**: Unified track IDs across all cameras

## Key Files and Modules

### Detection Module (`detection/`)
- **`load_detector.py`**: Loads YOLO models (v5/v8)
- **`detection.py`**: Detection data structures
- **`yolov5/`**: YOLOv5 submodule

### MOT Module (`mot/`)
- **`run_tracker.py`**: Main MOT pipeline execution
- **`tracker.py`**: Tracker implementations (DeepSORT, ByteTrack)
- **`tracklet.py`**: Tracklet data structure
- **`attributes.py`**: Attribute extraction (color, type, speed)
- **`video_output.py`**: Video annotation and output
- **`deep_sort/`**: DeepSORT implementation
- **`byte_track/`**: ByteTrack implementation

### MTMC Module (`mtmc/`)
- **`run_express_mtmc.py`**: Express pipeline (MOT + MTMC)
- **`run_mtmc.py`**: MTMC only (requires MOT results)
- **`mtmc_clustering.py`**: Hierarchical clustering algorithm
- **`multicam_tracklet.py`**: Multi-camera track structure
- **`cameras.py`**: Camera layout and constraints
- **`output.py`**: Save results per camera

### ReID Module (`reid/`)
- **`vehicle_reid/`**: Vehicle ReID training submodule
- **`feature_extractor.py`**: PyTorch-based feature extraction
- **`onnx_feature_extractor.py`**: ONNX Runtime optimization
- **`tensorrt_feature_extractor.py`**: TensorRT acceleration

### Configuration (`config/`)
- **`defaults.py`**: Default configuration values
- **`config_tools.py`**: Configuration utilities
- **`verify_config.py`**: Configuration validation
- **`examples/`**: Example configuration files

## Configuration Files

### Example Config Structure

```yaml
OUTPUT_DIR: "output/parking_mtmc"  # Output directory

MOT:
  # ReID Model
  REID_MODEL_OPTS: "models/resnet50_mixstyle/opts.yaml"
  REID_MODEL_CKPT: "models/resnet50_mixstyle/net_19.pth"
  REID_ONNX: "models/resnet50_mixstyle/model.onnx"  # ONNX acceleration
  REID_BATCHSIZE: 32
  REID_FP16: true
  
  # Detector
  DETECTOR: "yolov8s"  # or "yolov5x6", "yolov8s_car_custom.pt"
  TRACKED_CLASSES: [1, 2, 3, 5, 7]  # COCO: car, motorcycle, bus, truck
  
  # Tracker
  TRACKER: "bytetrack_iou"  # or "deepsort"
  MIN_FRAMES: 3
  
  # Video I/O
  VIDEO: "path/to/video.mp4"
  VIDEO_OUTPUT: true
  SHOW: false
  
  # Optional
  DETECTION_MASK: "masks/camera_mask.jpg"  # Mask unwanted areas
  CALIBRATION: "calibration/camera.txt"    # For speed estimation
  
  # Attributes (optional)
  STATIC_ATTRIBUTES:
    - color: "models/color_svm.pkl"
    - type: "models/type_svm.pkl"

MTMC:
  CAMERA_LAYOUT: 'config/examples/parking_camera_layout.txt'
  LINKAGE: 'average'  # single, complete, average
  MIN_SIM: 0.5        # Minimum similarity to merge tracks

EXPRESS:
  FINAL_VIDEO_OUTPUT: true
  CAMERAS:
    - video: "datasets/camera_a.mp4"
      detector: "yolov8s"
      tracked_classes: [1, 2, 3, 5, 7]
      enable_alpr: true  # Enable plate recognition
      detection_mask: "masks/cam_a_mask.jpg"
    - video: "datasets/camera_b.mp4"
      detector: "yolov8s_car_custom.pt"
      tracked_classes: [0]
    - video: "datasets/camera_c.mp4"
      detector: "yolov8s_car_custom.pt"
      tracked_classes: [0]
```

### Camera Layout File

Defines temporal and spatial constraints between cameras:

```
# Format: camera_id_1 camera_id_2 min_time max_time
# Times in seconds
0 1 2.0 10.0   # Camera 0 → Camera 1: 2-10 seconds
0 2 3.0 15.0   # Camera 0 → Camera 2: 3-15 seconds
1 2 1.0 8.0    # Camera 1 → Camera 2: 1-8 seconds

# FPS for each camera
fps 30 30 30

# Time offset (for synchronized footage)
offset 0.0 0.0 0.0

# Scale factor (if videos are sped up/slowed down)
scale 1.0 1.0 1.0
```

## Installation

### Prerequisites
- **NVIDIA GPU** with CUDA support (check with `nvidia-smi`)
- **Python 3.10** (tested version)
- **CUDA ≥ 11.0** recommended

### Step-by-Step Installation

```bash
# 1. Clone repository with submodules
git clone --recurse-submodules https://github.com/regob/vehicle_mtmc.git
cd vehicle_mtmc

# 2. Create virtual environment (recommended)
conda create -n vehicle_mtmc python=3.10
conda activate vehicle_mtmc

# 3. Install dependencies
pip install cython "numpy>=1.18.5,<1.23.0"
pip install -r requirements.txt

# 4. Install additional packages
pip install ultralytics  # For YOLOv8
pip install fast-alpr    # For license plate recognition (optional)

# 5. Download pretrained models
# Download from: https://drive.google.com/drive/folders/1ELQIlmrxrV3HmLzS3Og53ytRdu5kiscD
# Extract to: models/
```

### Models Download

Download pretrained models from Google Drive and extract to `models/` directory:
- **ReID Models**: ResNet50-IBN, EfficientNet-B0, MobileNetV4
- **Attribute Classifiers**: Color SVM, Type SVM
- **Custom YOLO**: Fine-tuned vehicle detection models

## Running the System

### 1. Single-Camera Tracking (MOT)

```bash
export PYTHONPATH=$(pwd)
python3 mot/run_tracker.py --config examples/mot_highway.yaml
```

**Output**:
- `output/mot_highway/mot.pkl` - Pickled tracklets
- `output/mot_highway/mot.csv` - CSV format tracks
- `output/mot_highway/mot.txt` - MOTChallenge format
- `output/mot_highway/mot.mp4` - Annotated video

### 2. Multi-Camera Tracking (Express MTMC)

```bash
export PYTHONPATH=$(pwd)
python3 mtmc/run_express_mtmc.py --config examples/express_parking.yaml
```

**Process**:
1. Runs MOT on each camera independently
2. Saves MOT results to subdirectories: `0_camera_a/`, `1_camera_b/`, etc.
3. Runs MTMC clustering across all cameras
4. Saves final results with unified IDs

**Output per camera**:
- `output/parking_mtmc/0_camera_a/mot.pkl` - MOT results
- `output/parking_mtmc/0_camera_a/mtmc.pkl` - MTMC results
- `output/parking_mtmc/0_camera_a/mtmc.mp4` - Final video with global IDs

### 3. MTMC Only (with existing MOT results)

```bash
export PYTHONPATH=$(pwd)
python3 mtmc/run_mtmc.py --config examples/mtmc_only.yaml
```

**Requirements**: MOT must be run first to generate pickled tracklets.

### 4. Quick Run (Convenience Scripts)

```bash
# Express MTMC on parking dataset
bash run.sh

# Live streaming with MTMC
bash run_live_mtmc.sh
```

## Performance Optimization

### Speed Optimization Techniques

#### 1. **ONNX Runtime** (2-3x speedup for ReID)

```bash
# Export PyTorch model to ONNX
python3 reid/onnx_exporter.py \
  --opts models/mobilenetv4_small/opts.yaml \
  --checkpoint models/mobilenetv4_small/net_19.pth \
  --output models/mobilenetv4_small/model.onnx

# Enable in config
MOT:
  REID_ONNX: "models/mobilenetv4_small/model.onnx"
```

#### 2. **TensorRT** (5-10x speedup for ReID)

```bash
# Export to TensorRT
python3 reid/tensorrt_exporter.py \
  --onnx models/mobilenetv4_small/model.onnx \
  --output models/mobilenetv4_small/model.trt

# Enable in config
MOT:
  REID_TRT: "models/mobilenetv4_small/model.trt"
```

#### 3. **YOLOv8 ONNX Export** (2-3x speedup for detection)

```bash
python3 -c "
from ultralytics import YOLO
model = YOLO('yolov8s.pt')
model.export(format='onnx', half=True)
"

# Use in config
MOT:
  DETECTOR: "yolov8s.onnx"
```

#### 4. **Configuration Optimizations**

```yaml
MOT:
  REID_FP16: true           # Use half-precision
  REID_BATCHSIZE: 32        # Larger batch for better GPU utilization
  TRACKER: "bytetrack_iou"  # Faster than DeepSORT
  STATIC_ATTRIBUTES: []     # Disable if not needed
  VIDEO_OUTPUT: false       # Disable during development
```

### Expected Speedups

| Optimization | Speedup | Accuracy Impact |
|-------------|---------|-----------------|
| MobileNetV4 vs ResNet50 | 3-5x | Slight decrease |
| ONNX Runtime | 2-3x | None |
| TensorRT | 5-10x | None |
| FP16 Precision | 1.5-2x | Minimal |
| ByteTrack vs DeepSORT | 2-3x | Minimal |
| YOLO ONNX | 2-3x | None |
| **Combined** | **10-50x** | Minimal |

## Algorithm Details

### MOT Tracking Pipeline

```python
for frame in video:
    # 1. Detect vehicles
    detections = detector(frame)
    
    # 2. Filter by class, confidence, mask
    detections = filter_detections(detections)
    
    # 3. Extract ReID features
    features = reid_model(crop_detections(frame, detections))
    
    # 4. Extract attributes (optional)
    colors, types = attribute_extractors(crops, features)
    
    # 5. Update tracker
    tracker.update(detections, features)
    
    # 6. Get active tracks
    tracks = tracker.get_active_tracks()
```

### MTMC Clustering Algorithm

```python
def mtmc_clustering(tracks_per_camera, camera_layout, min_sim, linkage):
    """
    Hierarchical agglomerative clustering with constraints.
    """
    # 1. Initialize: each track is its own cluster
    clusters = [MulticamTrack([t]) for cam_tracks in tracks_per_camera 
                for t in cam_tracks]
    
    # 2. Compute pairwise similarities
    similarities = compute_all_similarities(clusters)
    
    # 3. Build priority queue of mergeable pairs
    merge_candidates = []
    for i, cluster_i in enumerate(clusters):
        for j, cluster_j in enumerate(clusters[i+1:], i+1):
            # Check constraints
            if not tracks_compatible(cluster_i, cluster_j, camera_layout):
                continue
            sim = multicam_track_similarity(cluster_i, cluster_j, linkage, similarities)
            if sim >= min_sim:
                heappush(merge_candidates, (-sim, i, j))
    
    # 4. Hierarchical merging
    while merge_candidates:
        neg_sim, i, j = heappop(merge_candidates)
        if already_merged(i, j):
            continue
        
        # Merge clusters
        new_cluster = merge(clusters[i], clusters[j])
        clusters.append(new_cluster)
        
        # Update merge candidates
        update_candidates(merge_candidates, new_cluster, clusters)
    
    return final_clusters
```

### Track Compatibility Constraints

Two tracks can be merged if:
1. **Different cameras**: Same vehicle cannot be in two places simultaneously
2. **Temporal constraint**: Travel time between cameras is within [min_time, max_time]
3. **Spatial constraint**: Camera transition is physically possible (defined in layout)

```python
def tracks_compatible(track1, track2, camera_layout):
    if track1.camera == track2.camera:
        return False  # Same camera
    
    # Check if track2 appears after track1 within valid time window
    travel_time = track2.start_time - track1.end_time
    min_time = camera_layout.min_travel_time[track1.camera][track2.camera]
    max_time = camera_layout.max_travel_time[track1.camera][track2.camera]
    
    if min_time <= travel_time <= max_time:
        return True
    
    # Check reverse direction
    travel_time_rev = track1.start_time - track2.end_time
    min_time_rev = camera_layout.min_travel_time[track2.camera][track1.camera]
    max_time_rev = camera_layout.max_travel_time[track2.camera][track1.camera]
    
    return min_time_rev <= travel_time_rev <= max_time_rev
```

## Output Formats

### 1. Pickle Format (.pkl)

Python pickle containing list of `Tracklet` or `MulticamTracklet` objects:

```python
class Tracklet:
    id: int                      # Track ID
    frames: List[int]            # Frame numbers
    bboxes: List[List[int]]      # [x, y, w, h] per frame
    features: List[np.ndarray]   # ReID features per frame
    mean_feature: np.ndarray     # Average feature
    attributes: Dict             # color, type, speed, plate
    cam: int                     # Camera ID (for MTMC)
```

### 2. CSV Format (.csv)

```csv
frame,id,x,y,w,h,color,type,speed,plate
1,5,100,200,50,80,white,car,45.2,ABC123
2,5,105,205,50,80,white,car,46.1,ABC123
1,7,300,150,60,90,black,suv,0.0,
```

### 3. MOTChallenge Format (.txt)

```
<frame>, <id>, <bb_left>, <bb_top>, <bb_width>, <bb_height>, <conf>, <x>, <y>, <z>
1,5,100,200,50,80,1,-1,-1,-1
2,5,105,205,50,80,1,-1,-1,-1
```

### 4. Annotated Video (.mp4)

Visual output with:
- Bounding boxes around vehicles
- Track IDs displayed
- License plates (if detected)
- Attributes (color, type)
- Speed (if calibrated)

## License Plate Recognition (ALPR)

### Integration

ALPR is integrated per-camera and results are propagated via MTMC:

```yaml
EXPRESS:
  CAMERAS:
    - video: "entrance.mp4"
      enable_alpr: true    # Detect plates at entrance
    - video: "parking_lot.mp4"
      enable_alpr: false   # Don't detect (will get via MTMC)
```

### How It Works

1. **Detection**: Camera A detects plates using fast-alpr
2. **Storage**: Plate text stored in tracklet
3. **Propagation**: MTMC matching copies plate to same vehicle in other cameras
4. **Display**: All cameras show the plate in their videos

### Installation

```bash
pip install fast-alpr
```

## Evaluation

If ground truth annotations are provided, the system automatically evaluates:

```yaml
EVAL:
  GROUND_TRUTHS:
    - "datasets/gt/camera_a.txt"
    - "datasets/gt/camera_b.txt"
    - "datasets/gt/camera_c.txt"
```

**Metrics**:
- **MOTA** (Multiple Object Tracking Accuracy)
- **IDF1** (ID F1 Score)
- **FP, FN** (False Positives, False Negatives)
- **ID Switches** (Track fragmentation)

## Troubleshooting

### Common Issues

#### 1. Out of Memory

```yaml
# Reduce batch sizes
MOT:
  REID_BATCHSIZE: 8
  ATTRIBUTE_INFER_BATCHSIZE: 8
```

#### 2. Slow Performance

- Use ONNX/TensorRT acceleration
- Use lighter models (MobileNet instead of ResNet)
- Use ByteTrack instead of DeepSORT
- Disable attribute extraction

#### 3. Poor Tracking Quality

- Increase `MIN_SIM` threshold for MTMC
- Use DeepSORT instead of ByteTrack
- Use larger ReID model (ResNet50 instead of MobileNet)
- Adjust camera layout constraints

#### 4. ALPR Not Working

```bash
# Check installation
pip install fast-alpr

# Verify in code
python3 -c "import fast_alpr; print('OK')"
```

## Advanced Features

### Camera Calibration

For speed estimation, calibrate cameras using [Cal_PNP](https://github.com/zhengthomastang/Cal_PnP):

```bash
# Generate homography matrix
python3 tools/calibrate_camera.py \
  --video camera.mp4 \
  --output calibration/camera.txt
```

### Zone Matching

Define zones in each camera to validate transitions:

```yaml
MOT:
  ZONE_MASK_DIR: "zones/"
  VALID_ZONEPATHS:
    - [0, 1]  # Zone 0 → Zone 1 allowed
    - [1, 2]  # Zone 1 → Zone 2 allowed
```

### Custom Training

Train custom ReID models using the [vehicle_reid](https://github.com/regob/vehicle_reid) submodule:

```bash
cd reid/vehicle_reid
python3 train.py --config configs/your_dataset.yaml
```

## References

### Citation

```bibtex
@article{szucs2023multi,
  title={Multi-Camera Trajectory Matching based on Hierarchical Clustering and Constraints},
  author={Sz{\H{u}}cs, G{\'a}bor and Borsodi, R{\'o}bert and Papp, D{\'a}vid},
  journal={Multimedia Tools and Applications},
  year={2023},
  doi={10.1007/s11042-023-17397-0}
}
```

### Acknowledgements

- [YOLOv5](https://github.com/ultralytics/yolov5) - Object detection
- [DeepSORT](https://github.com/nwojke/deep_sort) - Tracking algorithm
- [ByteTrack](https://github.com/ifzhang/ByteTrack) - Fast tracking
- [vehicle_reid](https://github.com/regob/vehicle_reid) - ReID training

## Project Structure

```
vehicle_mtmc/
├── config/               # Configuration files
│   ├── defaults.py      # Default config values
│   ├── examples/        # Example configs
│   └── verify_config.py # Config validation
├── detection/           # Object detection
│   ├── load_detector.py # YOLO loader
│   └── yolov5/         # YOLOv5 submodule
├── mot/                # Single-camera tracking
│   ├── run_tracker.py  # Main MOT pipeline
│   ├── tracker.py      # Tracker implementations
│   ├── tracklet.py     # Track data structure
│   ├── deep_sort/      # DeepSORT implementation
│   └── byte_track/     # ByteTrack implementation
├── mtmc/               # Multi-camera tracking
│   ├── run_express_mtmc.py    # Express pipeline
│   ├── run_mtmc.py            # MTMC only
│   ├── mtmc_clustering.py     # Clustering algorithm
│   └── multicam_tracklet.py   # Multi-cam tracks
├── reid/               # Re-identification
│   ├── feature_extractor.py  # PyTorch extractor
│   ├── onnx_feature_extractor.py  # ONNX Runtime
│   └── vehicle_reid/   # ReID training submodule
├── evaluate/           # Evaluation metrics
├── tools/              # Utilities
├── models/             # Pretrained models (download separately)
├── datasets/           # Input videos
└── output/             # Results
```

## Real-Time / Streaming Multi-Camera Tracking

### Overview

The **Live MTMC** system (`run_live_mtmc.py`) provides real-time multi-camera tracking with MJPEG video streaming. Unlike batch processing, it:
- **Processes frames in real-time** from multiple cameras simultaneously
- **Continuously updates global IDs** via periodic clustering
- **Streams annotated video** via HTTP/MJPEG for live monitoring
- **Synchronizes cameras** using a virtual clock system

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Live MTMC System                              │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼─────┐        ┌─────▼──────┐       ┌─────▼──────┐
   │ Camera 1 │        │ Camera 2   │       │ Camera 3   │
   │  Worker  │        │  Worker    │       │  Worker    │
   │ (Thread) │        │ (Thread)   │       │ (Thread)   │
   └────┬─────┘        └─────┬──────┘       └─────┬──────┘
        │                    │                     │
        │    ┌───────────────┴──────────────┐     │
        │    │                               │     │
        └────►  LiveMTMCAggregator          ◄─────┘
             │  (Periodic Clustering)        │
             └───────────────┬───────────────┘
                             │
                   ┌─────────▼──────────┐
                   │  MJPEG Broadcaster │
                   │  (HTTP Server)     │
                   └────────────────────┘
                             │
                   http://localhost:8080
```

### Key Components

#### 1. **VirtualClock** - Frame Synchronization

Ensures all cameras process frames at the same rate with bounded skew:

```python
class VirtualClock:
    """Synchronize multiple camera workers with controlled skew.
    
    Features:
    - Tick-based synchronization (one tick = one frame time)
    - Max skew control: prevents fast cameras from getting too far ahead
    - Stall detection: removes stuck/crashed workers automatically
    - Thread-safe coordination using condition variables
    """
    
    def wait_for_tick(self, worker: str, last_seen: int) -> int:
        """Wait for next allowed tick for this worker.
        
        Returns next_tick when:
        - Global clock has advanced
        - No worker is more than max_skew ticks behind
        - This worker hasn't stalled
        """
```

**Why Synchronization Matters:**
- Temporal constraints in MTMC require synchronized timestamps
- Prevents one camera from processing far ahead (breaks MTMC matching)
- Handles variable processing speeds (detection/tracking times differ)

#### 2. **LiveMOTWorker** - Per-Camera Thread

Each camera runs in its own thread:

```python
class LiveMOTWorker(threading.Thread):
    """Independent worker thread for one camera.
    
    Responsibilities:
    - Read frames from video source
    - Run detection (YOLO)
    - Run tracking (ByteTrack)
    - Extract ReID features
    - Update aggregator with tracks
    - Annotate frames with global IDs
    - Stream MJPEG output
    """
```

**Per-Frame Pipeline:**

```
┌─────────────────────────────────────────────────────┐
│              LiveMOTWorker Frame Loop                │
└─────────────────────────────────────────────────────┘
                      │
    1. Wait for tick  │  ◄── VirtualClock synchronization
                      ▼
    2. Read frame     │  ◄── cv2.VideoCapture
                      ▼
    3. YOLO detect    │  ◄── detector(frame)
                      ▼
    4. Filter boxes   │  ◄── by class, confidence
                      ▼
    5. Extract ReID   │  ◄── extractor(crops)
                      ▼
    6. Track (MOT)    │  ◄── ByteTrack.update()
                      ▼
    7. Update MTMC    │  ◄── aggregator.update()
                      ▼
    8. Get global IDs │  ◄── local_to_global mapping
                      ▼
    9. Annotate frame │  ◄── draw boxes + global IDs
                      ▼
   10. Stream MJPEG   │  ◄── broadcaster.update_frame()
                      │
                      └──► Loop back to step 1
```

#### 3. **LiveMTMCAggregator** - Global ID Assignment

Periodically clusters tracks across cameras:

```python
class LiveMTMCAggregator:
    """Aggregate tracks from multiple cameras and assign global IDs.
    
    Strategy:
    - Collects active tracks from all cameras
    - Runs hierarchical clustering periodically (every N seconds)
    - Maintains local_id → global_id mapping per camera
    - Thread-safe for concurrent updates
    """
    
    def update(self, cam_idx: int, tracks: list) -> Dict[int, int]:
        """Update tracks for one camera.
        
        Returns:
            Mapping from local track_id to global_id for this camera
        """
```

**Clustering Frequency Trade-off:**

| Interval | Pros | Cons |
|----------|------|------|
| High (1-2s) | Fast ID updates, responsive | High CPU usage, ID instability |
| Medium (5-10s) | Balanced | Default recommendation |
| Low (15-30s) | Low overhead, stable IDs | Slow to match new vehicles |

**Why Periodic Instead of Continuous:**
- MTMC clustering is O(N²) - expensive for many tracks
- IDs should be stable (avoid flickering in UI)
- Batch updates more efficient than per-frame

#### 4. **MJPEGBroadcaster** - HTTP Streaming

Serves live video streams over HTTP:

```python
class MJPEGBroadcaster:
    """HTTP server streaming MJPEG video.
    
    Endpoints:
    - http://localhost:8080/         → Index page with all cameras
    - http://localhost:8080/cam_a.mjpg → Camera A stream
    - http://localhost:8080/cam_b.mjpg → Camera B stream
    
    Protocol: multipart/x-mixed-replace (MJPEG over HTTP)
    """
```

**MJPEG Format:**
```
HTTP/1.1 200 OK
Content-Type: multipart/x-mixed-replace; boundary=--frame

--frame
Content-Type: image/jpeg
Content-Length: 45678

[JPEG bytes for frame 1]
--frame
Content-Type: image/jpeg
Content-Length: 46234

[JPEG bytes for frame 2]
--frame
...
```

### Configuration

```yaml
LIVE:
  # Frame rate for processing and streaming
  TARGET_FPS: 8  # Lower = less CPU, higher latency
  
  # HTTP port for MJPEG streaming
  MJPEG_PORT: 8080
  
  # MTMC clustering frequency (seconds)
  CLUSTER_INTERVAL: 10.0  # How often to recompute global IDs
  
  # Minimum frames before track is included in clustering
  MIN_TRACK_FRAMES: 5  # Filter out very short/noisy tracks
  
  # Camera synchronization
  MAX_SKEW_TICKS: 1  # Max frame difference between cameras
  STALL_SECONDS: 5.0  # Remove worker if no updates for N seconds
  
  # Video source behavior
  LOOP_VIDEO: true  # Restart video when it ends
  SLEEP_ON_EMPTY: 0.02  # Sleep time when no frames available
  
  # Similarity threshold for MTMC
  SIMILARITY_THRESHOLD: 0.5
  
  # Feature update method
  GLOBAL_FEATURE_EMA: 0.0  # 0=replace, >0=exponential moving average
  
  # Track expiry
  MAX_INACTIVE_SECS: 3.0  # Remove track if not seen for N seconds

EXPRESS:
  CAMERAS:
    - video: "rtsp://camera1/stream"  # Can be RTSP, file, etc.
      name: "cam_a"  # Human-readable name
      detector: "yolov8s"
      tracked_classes: [1, 2, 3, 5, 7]
    - video: "rtsp://camera2/stream"
      name: "cam_b"
      detector: "yolov8s_car_custom.pt"
      tracked_classes: [0]
    - video: "datasets/parking_c.mp4"  # Mix of live and recorded
      name: "cam_c"
      detector: "yolov8s_car_custom.pt"
      tracked_classes: [0]
```

### Running Live MTMC

#### 1. Start the System

```bash
export PYTHONPATH=$(pwd)
python3 mtmc/run_live_mtmc.py --config examples/live_parking.yaml
```

Or use the convenience script:

```bash
bash run_live_mtmc.sh
```

#### 2. View Streams

Open your browser:

**Index Page:**
```
http://localhost:8080/
```

**Individual Cameras:**
```
http://localhost:8080/cam_a.mjpg
http://localhost:8080/cam_b.mjpg
http://localhost:8080/cam_c.mjpg
```

#### 3. Embed in HTML

```html
<!DOCTYPE html>
<html>
<head><title>Parking Monitor</title></head>
<body>
  <h2>Camera A (Entrance)</h2>
  <img src="http://localhost:8080/cam_a.mjpg" width="640">
  
  <h2>Camera B (Parking Lot)</h2>
  <img src="http://localhost:8080/cam_b.mjpg" width="640">
  
  <h2>Camera C (Exit)</h2>
  <img src="http://localhost:8080/cam_c.mjpg" width="640">
</body>
</html>
```

### Real-Time Pipeline Flow

```
Time: t=0
Camera A: [Process Frame 0] → Track 5 detected
Camera B: [Process Frame 0] → Track 7 detected
Camera C: [Process Frame 0] → Track 9 detected
          ↓
Aggregator: Store tracks, no clustering yet (interval not reached)
          ↓
Broadcast: Stream annotated frames

Time: t=1
Camera A: [Process Frame 1] → Track 5 updated
Camera B: [Process Frame 1] → Track 7 updated
Camera C: [Process Frame 1] → Track 9 updated
          ↓
Aggregator: Store tracks
          ↓
Broadcast: Stream frames

...

Time: t=10 (CLUSTER_INTERVAL reached)
Camera A: [Process Frame 10] → Track 5 updated
Camera B: [Process Frame 10] → Track 7 updated  
Camera C: [Process Frame 10] → Track 9 updated
          ↓
Aggregator: RUN CLUSTERING!
           - Compare ReID features
           - Apply constraints (temporal, spatial)
           - Result: Track 5 (cam A) = Track 7 (cam B) = GLOBAL ID 100
           - Track 9 (cam C) = different vehicle = GLOBAL ID 101
          ↓
Workers: Update local_to_global mapping
         - Camera A: {5: 100}
         - Camera B: {7: 100}
         - Camera C: {9: 101}
          ↓
Annotate: Draw "ID: 100" on tracks 5 and 7
          Draw "ID: 101" on track 9
          ↓
Broadcast: Viewers see unified IDs across cameras!
```

### Performance Characteristics

#### Latency Sources

| Component | Latency | Optimization |
|-----------|---------|--------------|
| Frame capture | 0-50ms | Use RTSP vs file playback |
| Detection (YOLO) | 20-100ms | ONNX/TensorRT, smaller model |
| ReID extraction | 10-50ms | ONNX/TensorRT, FP16 |
| Tracking | 1-5ms | ByteTrack is fast |
| MTMC clustering | 10-500ms | Periodic (not per-frame) |
| JPEG encoding | 5-20ms | Hardware encoder if available |
| Network transmission | 10-100ms | Local network best |
| **Total per frame** | **50-200ms** | **~5-20 FPS possible** |

#### CPU/GPU Usage

**Multi-threaded Design:**
- Each camera uses one thread
- GPU shared across all cameras (detection + ReID)
- HTTP server runs in separate threads
- Clustering runs in main thread periodically

**Resource Scaling:**

| # Cameras | GPU Usage | CPU Usage | Bottleneck |
|-----------|-----------|-----------|------------|
| 1-3 | 30-60% | 40-80% | Detection |
| 4-8 | 70-90% | 100%+ | GPU saturated |
| 9+ | 100% | 100%+ | Need multiple GPUs |

### Synchronization Deep Dive

#### Why VirtualClock?

**Problem without sync:**
```
Time: 0s    1s    2s    3s    4s
Cam A: |----|----|----|----|----|  (5 fps, slow)
Cam B: |--|--|--|--|--|--|--|--|  (8 fps, fast)
Cam C: |-----|-----|-----|------|  (4 fps, very slow)

Result: 
- Cam B processes frame at t=3s
- Cam A still at t=1s  
- Cam C at t=0.8s
→ MTMC sees huge time gaps, can't match!
```

**Solution with VirtualClock:**
```
Virtual Tick:  0    1    2    3    4
Cam A:        [0]  [1]  [2]  [3]  [4]
Cam B:        [0]  [1]  [2]  [3]  [4]  ← waits if too fast
Cam C:        [0]  [1]  [2]  [3]  [4]  ← skips if too slow

Result: All cameras synchronized, MTMC can match properly!
```

#### Max Skew Control

```python
MAX_SKEW_TICKS = 1

Scenario:
- Cam A at tick 10
- Cam B at tick 10
- Cam C at tick 8 (2 ticks behind)

VirtualClock allows Cam A/B to advance to tick 11 but NOT 12
(because Cam C would be >1 tick behind)

When Cam C catches up to tick 9:
→ All cameras can advance again
```

**Benefits:**
- Prevents "runaway" fast cameras
- Ensures temporal constraints remain valid
- Gracefully handles variable processing speeds

### Differences from Batch Mode

| Aspect | Batch (Express) | Real-Time (Live) |
|--------|-----------------|------------------|
| **Input** | Recorded videos | Live streams or videos |
| **Processing** | Sequential (one cam at a time)( | Parallel all cams simultaneously) |
| **MTMC** | Once at the end | Periodic during processing |
| **IDs** | Stable (computed once) | Dynamic (update periodically) |
| **Output** | Video files | MJPEG streams |x
| **Latency** | N/A (offline) | 50-200ms per frame |
| **Use Case** | Analysis, evaluation | Monitoring, alerts |
| **Resource Usage** | Peak at one camera | Sustained across all |

### Use Cases

#### 1. **Live Parking Monitoring**

```yaml
# Monitor parking lot in real-time
LIVE:
  TARGET_FPS: 5  # Lower FPS = less CPU for long-running
  CLUSTER_INTERVAL: 15.0  # Stable IDs more important
  MJPEG_PORT: 8080

EXPRESS:
  CAMERAS:
    - video: "rtsp://entrance-cam/stream"
      name: "entrance"
    - video: "rtsp://lot-cam/stream"
      name: "parking_lot"
```

**Benefits:**
- Security guards see live feed
- Same vehicle ID across entrance and lot
- Can track dwell time, occupancy

#### 2. **Traffic Surveillance**

```yaml
# Monitor intersection
LIVE:
  TARGET_FPS: 10  # Higher FPS for fast vehicles
  CLUSTER_INTERVAL: 5.0  # Quick ID updates
  MIN_TRACK_FRAMES: 3  # Catch fast-moving vehicles

EXPRESS:
  CAMERAS:
    - video: "rtsp://north/stream"
      name: "north_approach"
    - video: "rtsp://south/stream"
      name: "south_approach"
    - video: "rtsp://intersection/stream"
      name: "intersection"
```

#### 3. **Vehicle Flow Analysis**

```yaml
# Count vehicles entering/exiting
LIVE:
  TARGET_FPS: 8
  CLUSTER_INTERVAL: 10.0

# Add zone definitions to count crossings
MOT:
  ZONE_MASK_DIR: "zones/"
  VALID_ZONEPATHS:
    - [0, 1]  # Entry → Parking
    - [1, 2]  # Parking → Exit
```

### Integration with Other Systems

#### REST API Wrapper (Example)

```python
from flask import Flask, jsonify
import threading

app = Flask(__name__)
aggregator = None  # Set by run_live()

@app.route('/api/tracks')
def get_tracks():
    """Get current tracks from all cameras."""
    with aggregator._lock:
        return jsonify({
            'cameras': len(aggregator._tracks_by_cam),
            'tracks': {
                f'cam_{i}': [
                    {
                        'id': t.track_id,
                        'global_id': aggregator._gid_map.get(i, {}).get(t.track_id),
                        'bbox': t.bboxes[-1],
                        'frames': len(t.frames)
                    }
                    for t in tracks
                ]
                for i, tracks in aggregator._tracks_by_cam.items()
            }
        })

@app.route('/api/stats')
def get_stats():
    """Get system statistics."""
    total_tracks = sum(len(t) for t in aggregator._tracks_by_cam.values())
    return jsonify({
        'total_tracks': total_tracks,
        'cameras': len(aggregator._tracks_by_cam),
        'last_cluster': aggregator._last_cluster_ts
    })

# Run Flask in separate thread
threading.Thread(target=lambda: app.run(port=5000), daemon=True).start()
```

#### WebSocket Streaming (Alternative)

For lower latency than MJPEG, implement WebSocket + WebRTC:

```python
# Instead of MJPEG, use aiortc for WebRTC
# Provides sub-100ms latency for live streaming
# See: https://github.com/aiortc/aiortc
```

### Monitoring and Debugging

#### Enable Detailed Logging

```bash
python3 mtmc/run_live_mtmc.py \
  --config examples/live_parking.yaml \
  --log-level DEBUG
```

#### Key Metrics to Watch

```python
# In LiveMOTWorker:
log.info(f"Cam {self.name}: Frame {self.frame_id}, "
         f"Detections: {len(detections)}, "
         f"Tracks: {len(tracks)}, "
         f"FPS: {1.0/elapsed:.1f}")

# In LiveMTMCAggregator:
log.info(f"MTMC: Clustered {total_filtered} tracks → {len(mtracks)} global IDs")
```

#### Common Issues

**1. Cameras Out of Sync**
```
Symptom: MTMC never matches vehicles
Fix: Check MAX_SKEW_TICKS, ensure all cameras at similar FPS
```

**2. High CPU Usage**
```
Symptom: System overloaded, frames dropping
Fix: Lower TARGET_FPS, use ONNX/TensorRT, reduce REID_BATCHSIZE
```

**3. Stream Lag/Buffering**
```
Symptom: MJPEG video lags behind
Fix: Reduce TARGET_FPS, check network bandwidth, use local browser
```

**4. IDs Keep Changing**
```
Symptom: Global IDs flicker/change constantly
Fix: Increase CLUSTER_INTERVAL, increase MIN_TRACK_FRAMES, tune MIN_SIM
```

### Advanced: Custom Processing Hook

```python
# Add custom processing per frame
class CustomLiveMOTWorker(LiveMOTWorker):
    def _process_frame(self, frame_bgr, frame_rgb):
        detections, tracks = super()._process_frame(frame_bgr, frame_rgb)
        
        # Custom logic: detect license plates
        for trk in tracks:
            if len(trk.bboxes) > 0:
                x, y, w, h = map(int, trk.bboxes[-1])
                crop = frame_rgb[y:y+h, x:x+w]
                plate = detect_plate(crop)  # Your ALPR function
                if plate:
                    trk.attributes['plate'] = plate
        
        return detections, tracks
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/regob/vehicle_mtmc/issues
- Original Paper: [Multi-Camera Trajectory Matching](https://doi.org/10.1007/s11042-023-17397-0)
