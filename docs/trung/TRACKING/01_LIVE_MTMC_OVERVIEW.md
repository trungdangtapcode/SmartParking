# Live MTMC Tracking - Part 1: Overview and Architecture

## Table of Contents
- [Part 1: Overview and Architecture](01_LIVE_MTMC_OVERVIEW.md) ← **You are here**
- [Part 2: Installation and Setup](02_LIVE_MTMC_SETUP.md)
- [Part 3: Configuration Guide](03_LIVE_MTMC_CONFIG.md)
- [Part 4: Running the System](04_LIVE_MTMC_RUNNING.md)
- [Part 5: Code Reference](05_LIVE_MTMC_CODE_REFERENCE.md)
- [Part 6: Troubleshooting](06_LIVE_MTMC_TROUBLESHOOTING.md)

---

## What is Live MTMC?

**Live MTMC** (Multi-Target Multi-Camera) is a real-time vehicle tracking system that:
- Processes multiple camera streams **simultaneously**
- Assigns **unified global IDs** to vehicles across all cameras
- Streams **live annotated video** via HTTP/MJPEG
- Runs at **5-20 FPS** depending on hardware

**Location**: `/mnt/mmlab2024nas/vund/.svn/bin/vehicle_mtmc/mtmc/run_live_mtmc.py`

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              Live MTMC System (run_live_mtmc.py)        │
│  Location: vehicle_mtmc/mtmc/run_live_mtmc.py           │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────▼─────┐     ┌─────▼──────┐    ┌────▼─────┐
   │ Camera 1 │     │ Camera 2   │    │ Camera 3 │
   │  Worker  │     │  Worker    │    │  Worker  │
   │ (Thread) │     │ (Thread)   │    │ (Thread) │
   └────┬─────┘     └─────┬──────┘    └────┬─────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
              ┌───────────────────────┐
              │ LiveMTMCAggregator    │
              │ (Clustering Engine)   │
              │ Line 136-210          │
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │  MJPEGBroadcaster     │
              │  (HTTP Server)        │
              │  Line 213-269         │
              └───────────────────────┘
                          │
                    Port 8080
            http://localhost:8080/cam_a.mjpg
```

## Key Components

### 1. VirtualClock (Lines 57-133)

**File**: `vehicle_mtmc/mtmc/run_live_mtmc.py` (Lines 57-133)

**Purpose**: Synchronizes all camera threads to process frames at the same rate

**Why it exists**: 
- Without sync, fast cameras process far ahead of slow ones
- MTMC clustering requires synchronized timestamps
- Prevents temporal constraint violations

**How it works**:
```python
class VirtualClock:
    def __init__(self, interval, max_skew, stall_seconds, worker_names):
        self.interval = interval      # 1/FPS (e.g., 0.125s for 8 FPS)
        self.max_skew = max_skew      # Max frame difference allowed
        self._tick = 0                # Current global tick
        self._seen = {}               # Last tick seen per worker
```

**Key method**:
```python
def wait_for_tick(self, worker: str, last_seen: int) -> Optional[int]:
    """
    Worker calls this to get next tick to process.
    Returns None if clock is stopped.
    Blocks if worker is too far ahead.
    """
```

**Example**:
```
Config: MAX_SKEW = 1, FPS = 8

Time  | Tick | Cam A | Cam B | Cam C | Action
------|------|-------|-------|-------|--------
0.0s  |  0   |  0    |  0    |  0    | All start
0.125s|  1   |  1    |  1    |  0    | Cam C slow, others wait
0.25s |  2   |  1    |  1    |  1    | Cam C catches up
0.375s|  3   |  2    |  2    |  1    | All can proceed (max_skew=1)
```

### 2. LiveMOTWorker (Lines 272-402)

**File**: `vehicle_mtmc/mtmc/run_live_mtmc.py` (Lines 272-402)

**Purpose**: Per-camera thread that runs MOT (Multi-Object Tracking)

**Related files**:
- `vehicle_mtmc/mot/tracker.py` - Tracker implementations (ByteTrack, DeepSORT)
- `vehicle_mtmc/detection/load_detector.py` - YOLO detector loading
- `vehicle_mtmc/reid/feature_extractor.py` - ReID feature extraction

**Key attributes**:
```python
class LiveMOTWorker(threading.Thread):
    def __init__(self, cam_idx, cam_cfg, base_cfg, aggregator, broadcaster):
        self.cam_idx = cam_idx              # Camera index (0, 1, 2, ...)
        self.name = cam_cfg.get("name")     # Human-readable name
        self.detector = load_yolo(...)      # YOLO model
        self.tracker = ByteTrackerIOU(...)  # Tracker
        self.extractor = build_extractor()  # ReID model
        self.vclock = None                  # Set by main thread
```

**Processing loop** (Lines 323-356):
```python
def run(self):
    while not self.stop_event.is_set():
        # 1. Wait for synchronized tick
        tick = self.vclock.wait_for_tick(self.name, self.frame_id)
        
        # 2. Read frame
        ret, frame = self.cap.read()
        
        # 3. Process frame (detection + tracking + ReID)
        detections, tracks = self._process_frame(frame, frame_rgb)
        
        # 4. Annotate with global IDs
        annotated = self._annotate(frame, tracks)
        
        # 5. Stream MJPEG
        ok, buf = cv2.imencode('.jpg', annotated)
        self.broadcaster.update_frame(self.name, buf.tobytes())
        
        # 6. Mark tick complete
        self.vclock.mark(self.name, tick)
```

### 3. LiveMTMCAggregator (Lines 136-210)

**File**: `vehicle_mtmc/mtmc/run_live_mtmc.py` (Lines 136-210)

**Purpose**: Collects tracks from all cameras and assigns global IDs via clustering

**Related files**:
- `vehicle_mtmc/mtmc/mtmc_clustering.py` - Hierarchical clustering algorithm
- `vehicle_mtmc/mtmc/cameras.py` - Camera layout and constraints
- `vehicle_mtmc/mot/tracklet.py` - Tracklet data structure

**Key method**:
```python
def update(self, cam_idx: int, tracks: list) -> Dict[int, int]:
    """
    Called by each camera worker every frame.
    
    Args:
        cam_idx: Camera index
        tracks: List of active tracks for this camera
        
    Returns:
        Mapping from local track_id to global_id
        Example: {5: 100, 7: 100, 9: 101}
                 (local IDs 5,7 → global 100, local 9 → global 101)
    """
```

**Clustering trigger** (Line 164-167):
```python
if now - self._last_cluster_ts < self.cluster_interval:
    return  # Not time to recluster yet

# Otherwise, run clustering...
```

### 4. MJPEGBroadcaster (Lines 213-269)

**File**: `vehicle_mtmc/mtmc/run_live_mtmc.py` (Lines 213-269)

**Purpose**: HTTP server that streams MJPEG video

**Protocol**: Uses `multipart/x-mixed-replace` (standard MJPEG over HTTP)

**Endpoints**:
- `http://localhost:8080/` - Index page listing all cameras
- `http://localhost:8080/cam_a.mjpg` - Camera A stream
- `http://localhost:8080/cam_b.mjpg` - Camera B stream

**Related**: Standard HTTP server, no external files

## Data Flow

### Frame-by-Frame Pipeline

```
┌─────────────────────────────────────────────────────────┐
│ LiveMOTWorker Thread (Per Camera)                       │
└─────────────────────────────────────────────────────────┘

Step 1: Wait for Tick
├─ Call: self.vclock.wait_for_tick(self.name, self.frame_id)
├─ File: run_live_mtmc.py, Line 334
└─ Blocks until synchronized with other cameras

Step 2: Read Frame
├─ Call: self.cap.read()
├─ File: run_live_mtmc.py, Line 337
└─ Uses OpenCV VideoCapture

Step 3: YOLO Detection
├─ Call: self.detector(frame_bgr)
├─ File: run_live_mtmc.py, Line 358
├─ Related: detection/load_detector.py
└─ Returns: bounding boxes, scores, classes

Step 4: Filter Detections
├─ File: run_live_mtmc.py, Lines 359-368
└─ Filter by: confidence, class, (optional mask)

Step 5: ReID Feature Extraction
├─ Call: self.extractor(frame_rgb, boxes_tlwh)
├─ File: run_live_mtmc.py, Line 372
├─ Related: reid/feature_extractor.py
└─ Returns: 512D or 2048D feature vectors

Step 6: Tracking (ByteTrack)
├─ Call: self.tracker.update(frame_id, detections, ...)
├─ File: run_live_mtmc.py, Line 376
├─ Related: mot/tracker.py, mot/byte_track/
└─ Returns: List of active tracks with local IDs

Step 7: Update Aggregator
├─ Call: self.aggregator.update(self.cam_idx, tracks)
├─ File: run_live_mtmc.py, Line 381
├─ Related: mtmc_clustering.py (called periodically)
└─ Returns: local_id → global_id mapping

Step 8: Annotate Frame
├─ Call: self._annotate(frame, tracks)
├─ File: run_live_mtmc.py, Lines 386-401
└─ Draws boxes + global IDs

Step 9: MJPEG Streaming
├─ Call: self.broadcaster.update_frame(self.name, jpeg_bytes)
├─ File: run_live_mtmc.py, Line 349
└─ HTTP clients receive updated frame
```

## Comparison: Batch vs Live

| Aspect | Batch (run_express_mtmc.py) | Live (run_live_mtmc.py) |
|--------|----------------------------|-------------------------|
| **File** | `mtmc/run_express_mtmc.py` | `mtmc/run_live_mtmc.py` |
| **Execution** | Sequential (one cam at a time) | Parallel (all cams simultaneously) |
| **Threading** | Single-threaded | Multi-threaded (1 thread per camera) |
| **MTMC** | Once at end (Line 57) | Periodic during processing (every N seconds) |
| **Sync** | Not needed (offline) | VirtualClock required |
| **Output** | Video files (.mp4) | HTTP streams (.mjpg) |
| **Config file** | `examples/express_parking.yaml` | `examples/live_parking.yaml` |
| **Speed** | Processes as fast as possible | Real-time (5-20 FPS) |
| **Use case** | Post-processing, evaluation | Monitoring, dashboards |

## File References Summary

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Main script | `mtmc/run_live_mtmc.py` | 1-475 | Entry point, orchestrates everything |
| VirtualClock | `mtmc/run_live_mtmc.py` | 57-133 | Frame synchronization |
| LiveMTMCAggregator | `mtmc/run_live_mtmc.py` | 136-210 | Global ID assignment |
| MJPEGBroadcaster | `mtmc/run_live_mtmc.py` | 213-269 | HTTP streaming |
| LiveMOTWorker | `mtmc/run_live_mtmc.py` | 272-402 | Per-camera thread |
| MTMC Clustering | `mtmc/mtmc_clustering.py` | 1-191 | Hierarchical clustering algorithm |
| Camera Layout | `mtmc/cameras.py` | 1-100+ | Temporal/spatial constraints |
| Tracker | `mot/tracker.py` | 1-169 | ByteTrack/DeepSORT implementations |
| Detector | `detection/load_detector.py` | 1-100 | YOLO loading |
| ReID | `reid/feature_extractor.py` | 1-100+ | Feature extraction |
| Config defaults | `config/defaults.py` | 175-190 | LIVE section defaults |
| Example config | `config/examples/live_parking.yaml` | 1-46 | Sample configuration |

---

**Next**: [Part 2: Installation and Setup](02_LIVE_MTMC_SETUP.md)
