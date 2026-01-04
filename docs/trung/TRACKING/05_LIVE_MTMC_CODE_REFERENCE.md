# Live MTMC Tracking - Part 5: Code Reference

## Table of Contents
- [Part 1: Overview and Architecture](01_LIVE_MTMC_OVERVIEW.md)
- [Part 2: Installation and Setup](02_LIVE_MTMC_SETUP.md)
- [Part 3: Configuration Guide](03_LIVE_MTMC_CONFIG.md)
- [Part 4: Running the System](04_LIVE_MTMC_RUNNING.md)
- [Part 5: Code Reference](05_LIVE_MTMC_CODE_REFERENCE.md) ← **You are here**
- [Part 6: Troubleshooting](06_LIVE_MTMC_TROUBLESHOOTING.md)

---

## Main File: run_live_mtmc.py

**Location**: `vehicle_mtmc/mtmc/run_live_mtmc.py` (475 lines)

### File Structure

```python
# Lines 1-22: Imports
import os, sys, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import numpy as np, torch, cv2
from yacs.config import CfgNode
# ... etc

# Lines 25-45: build_extractor() - Load ReID model
def build_extractor(cfg: CfgNode, device: torch.device):
    """Build ReID feature extractor with ONNX/TensorRT/PyTorch fallback."""

# Lines 48-54: cosine_sim() - Similarity function
def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""

# Lines 57-133: VirtualClock class
class VirtualClock:
    """Synchronize camera workers with controlled skew."""

# Lines 136-210: LiveMTMCAggregator class
class LiveMTMCAggregator:
    """Aggregate tracks from cameras and assign global IDs."""

# Lines 213-269: MJPEGBroadcaster class
class MJPEGBroadcaster:
    """HTTP server for MJPEG streaming."""

# Lines 272-402: LiveMOTWorker class
class LiveMOTWorker(threading.Thread):
    """Per-camera worker thread."""

# Lines 405-455: run_live() function
def run_live(cfg: CfgNode):
    """Main orchestration function."""

# Lines 458-475: __main__ entry point
if __name__ == "__main__":
    # Parse args, load config, start system
```

## Class: VirtualClock

**Lines**: 57-133  
**Purpose**: Synchronize camera threads

### Initialization

```python
def __init__(self, interval: float, max_skew: int, stall_seconds: float, worker_names):
    """
    Args:
        interval: Time between ticks (1/FPS)
        max_skew: Max tick difference between fastest and slowest worker
        stall_seconds: Remove worker if no updates for N seconds
        worker_names: List of worker names to track
    """
    self.interval = interval
    self.max_skew = max_skew
    self._cv = threading.Condition()  # For thread synchronization
    self._tick = 0  # Current global tick
    self._running = False
    self._thread = None
    self._seen = {name: 0 for name in worker_names}  # Last tick per worker
    self._last_ts = {name: time.time() for name in worker_names}  # Last update time
    self.stall_seconds = stall_seconds
```

**Related config**: `LIVE.TARGET_FPS`, `LIVE.MAX_SKEW_TICKS`, `LIVE.STALL_SECONDS`

### Key Methods

#### start()

**Line**: 64

```python
def start(self):
    """Start the clock thread."""
    if self._running:
        return
    self._running = True
    self._thread = threading.Thread(target=self._run, daemon=True)
    self._thread.start()
```

#### _run()

**Lines**: 69-78

```python
def _run(self):
    """Internal thread that increments tick every interval."""
    next_time = time.time() + self.interval
    while self._running:
        now = time.time()
        sleep_for = max(0.0, next_time - now)
        time.sleep(sleep_for)
        with self._cv:
            self._tick += 1
            self._cv.notify_all()  # Wake up waiting workers
        next_time += self.interval
```

**Called by**: Background thread (daemon)

#### wait_for_tick()

**Lines**: 80-101

```python
def wait_for_tick(self, worker: str, last_seen: int) -> Optional[int]:
    """
    Worker calls this to get next tick to process.
    Blocks if worker is too far ahead.
    
    Args:
        worker: Worker name
        last_seen: Last tick this worker processed
        
    Returns:
        Next tick to process, or None if clock stopped
    """
    with self._cv:
        while self._running:
            now = time.time()
            # Remove stalled workers
            stale = [w for w, ts in self._last_ts.items() 
                     if now - ts > self.stall_seconds]
            for w in stale:
                self._seen.pop(w, None)
                self._last_ts.pop(w, None)

            target_tick = self._tick
            min_seen = min(self._seen.values()) if self._seen else target_tick
            allowed_tick = min_seen + self.max_skew
            next_tick = min(target_tick, allowed_tick)

            if next_tick > last_seen:
                return next_tick

            self._cv.wait(timeout=0.5)  # Wait for clock or timeout
        return None
```

**Called by**: `LiveMOTWorker.run()` (Line 334)

#### mark()

**Lines**: 103-108

```python
def mark(self, worker: str, tick: int):
    """Worker reports completed tick."""
    with self._cv:
        if worker in self._seen:
            self._seen[worker] = tick
            self._last_ts[worker] = time.time()
        self._cv.notify_all()
```

**Called by**: `LiveMOTWorker.run()` (Line 353)

#### retire()

**Lines**: 110-115

```python
def retire(self, worker: str):
    """Worker is stopping, remove from tracking."""
    with self._cv:
        self._seen.pop(worker, None)
        self._last_ts.pop(worker, None)
        self._cv.notify_all()
```

**Called by**: `LiveMOTWorker.run()` finally block (Line 355)

#### stop()

**Lines**: 117-122

```python
def stop(self):
    """Stop the clock."""
    self._running = False
    with self._cv:
        self._cv.notify_all()
    if self._thread:
        self._thread.join(timeout=2)
```

**Called by**: `run_live()` cleanup (Line 448)

## Class: LiveMTMCAggregator

**Lines**: 136-210  
**Purpose**: Periodic MTMC clustering and global ID assignment

### Initialization

```python
def __init__(self, cams: Optional[CameraLayout], min_sim: float, linkage: str,
             min_track_frames: int, cluster_interval: float):
    """
    Args:
        cams: Camera layout (constraints)
        min_sim: Minimum similarity to merge tracks
        linkage: Clustering method ('single', 'complete', 'average')
        min_track_frames: Filter out tracks with fewer frames
        cluster_interval: Seconds between re-clustering
    """
    self.cams = cams
    self.min_sim = min_sim
    self.linkage = linkage
    self.min_track_frames = min_track_frames
    self.cluster_interval = cluster_interval
    self._lock = threading.Lock()  # Thread safety
    self._tracks_by_cam = {}  # {cam_idx: [tracks]}
    self._gid_map = {}  # {cam_idx: {local_id: global_id}}
    self._last_cluster_ts = 0.0
```

**Related config**: `MTMC.MIN_SIM`, `MTMC.LINKAGE`, `LIVE.CLUSTER_INTERVAL`, `LIVE.MIN_TRACK_FRAMES`

### Key Methods

#### update()

**Lines**: 148-160

```python
def update(self, cam_idx: int, tracks: list) -> Dict[int, int]:
    """
    Update tracks for a camera and recompute global IDs.
    
    Args:
        cam_idx: Camera index
        tracks: List of active tracks
        
    Returns:
        Mapping from local track_id to global_id
    """
    with self._lock:
        self._tracks_by_cam[cam_idx] = list(tracks)
        self._recompute()
        return dict(self._gid_map.get(cam_idx, {}))
```

**Called by**: `LiveMOTWorker._process_frame()` (Line 381)

#### _recompute()

**Lines**: 162-210

```python
def _recompute(self):
    """Internal method to run clustering."""
    now = time.time()
    
    # Check if it's time to recluster
    if now - self._last_cluster_ts < self.cluster_interval:
        return  # Too soon
    
    # Prepare tracks
    n_cams = self.cams.n_cams if self.cams else max(self._tracks_by_cam.keys()) + 1
    tracks_list = [self._tracks_by_cam.get(i, []) for i in range(n_cams)]
    
    # Filter short tracks
    filtered_tracks = []
    for cam_tracks in tracks_list:
        filtered_tracks.append([t for t in cam_tracks 
                               if len(t.frames) >= self.min_track_frames])
    
    if sum(len(t) for t in filtered_tracks) == 0:
        return  # No tracks to cluster
    
    # Run clustering
    mtracks = mtmc_clustering(filtered_tracks, self.cams, 
                             min_sim=self.min_sim, linkage=self.linkage)
    
    # Build global ID mapping
    gid_map = {i: {} for i in range(n_cams)}
    for mt in mtracks:
        gid = mt.id
        for trk in mt.tracks:
            orig = getattr(trk, "orig_id", trk.track_id)
            gid_map[trk.cam][orig] = gid
    
    self._gid_map = gid_map
    self._last_cluster_ts = now
```

**Related file**: `mtmc/mtmc_clustering.py` `mtmc_clustering()` function

## Class: MJPEGBroadcaster

**Lines**: 213-269  
**Purpose**: HTTP server for MJPEG streaming

### Initialization

```python
def __init__(self, port: int):
    """
    Args:
        port: HTTP port to listen on
    """
    self.port = port
    self.frames = {}  # {camera_name: jpeg_bytes}
    self._lock = threading.Lock()
    self._server = None
    self._thread = None
    self._running = threading.Event()
```

**Related config**: `LIVE.MJPEG_PORT`

### Key Methods

#### update_frame()

**Lines**: 219-221

```python
def update_frame(self, name: str, frame_bytes: bytes):
    """Update JPEG bytes for a camera."""
    with self._lock:
        self.frames[name] = frame_bytes
```

**Called by**: `LiveMOTWorker.run()` (Line 349)

#### _handler_factory()

**Lines**: 223-261

```python
def _handler_factory(self):
    """Create HTTP request handler class."""
    outer = self
    
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.lstrip("/") or "index"
            cam_name = path.split(".")[0]
            
            if cam_name == "index":
                # Serve index page with camera links
                # ...
            
            # Serve MJPEG stream
            boundary = "--frame"
            self.send_response(200)
            self.send_header("Content-Type", 
                           f"multipart/x-mixed-replace; boundary={boundary}")
            # ...
            
            try:
                while outer._running.is_set():
                    with outer._lock:
                        buf = outer.frames.get(cam_name)
                    if buf is None:
                        time.sleep(0.05)
                        continue
                    # Send JPEG frame
                    self.wfile.write(boundary.encode() + b"\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(buf)}\r\n\r\n".encode())
                    self.wfile.write(buf)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass
    
    return Handler
```

#### start()

**Lines**: 263-269

```python
def start(self):
    """Start HTTP server."""
    self._running.set()
    handler = self._handler_factory()
    self._server = ThreadingHTTPServer(("0.0.0.0", self.port), handler)
    self._server.daemon_threads = True
    self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
    self._thread.start()
    log.info(f"MJPEG server started on port {self.port}")
```

**Called by**: `run_live()` (Line 421)

## Class: LiveMOTWorker

**Lines**: 272-402  
**Purpose**: Per-camera processing thread

### Initialization

```python
def __init__(self, cam_idx: int, cam_cfg: CfgNode, base_cfg: CfgNode,
             aggregator, broadcaster: MJPEGBroadcaster):
    """
    Args:
        cam_idx: Camera index
        cam_cfg: Per-camera config dict
        base_cfg: Base configuration
        aggregator: LiveMTMCAggregator instance
        broadcaster: MJPEGBroadcaster instance
    """
    super().__init__(daemon=True)
    self.cam_idx = cam_idx
    self.cam_cfg = cam_cfg
    self.base_cfg = base_cfg
    self.aggregator = aggregator
    self.broadcaster = broadcaster
    self.name = cam_cfg.get("name", f"cam_{cam_idx}")
    
    # Load models
    self.device = self._select_device(base_cfg)
    self.detector = load_yolo(cam_cfg.get("detector", base_cfg.MOT.DETECTOR)).to(self.device)
    self.tracked_classes = cam_cfg.get("tracked_classes", base_cfg.MOT.TRACKED_CLASSES)
    self.tracker = ByteTrackerIOU(frame_rate=30)
    self.extractor = build_extractor(base_cfg, self.device)
    
    # Video source
    self.video_path = cam_cfg.get("video")
    self.cap = cv2.VideoCapture(self.video_path)
    
    # State
    self.target_interval = 1.0 / float(base_cfg.LIVE.TARGET_FPS)
    self.min_confid = 0.05
    self.local_to_global = {}  # {local_id: global_id}
    self.gid_colors = {}  # {global_id: (r,g,b)}
    self.stop_event = threading.Event()
    self.frame_id = 0
    self.vclock = None  # Set by main thread
    self.bad_source = False
```

**Related files**:
- `detection/load_detector.py` - `load_yolo()`
- `mot/tracker.py` - `ByteTrackerIOU`
- `reid/feature_extractor.py` - Via `build_extractor()`

### Key Methods

#### run()

**Lines**: 323-356

```python
def run(self):
    """Main processing loop."""
    log.info("Starting camera %s", self.name)
    last_ts = time.time()
    
    try:
        if self.bad_source:
            log.error("Camera %s exiting due to bad source", self.name)
            return
        
        while not self.stop_event.is_set():
            # 1. Wait for synchronized tick
            tick = self.vclock.wait_for_tick(self.name, self.frame_id)
            if tick is None:
                break
            
            # 2. Read frame
            ret, frame = self.cap.read()
            if not ret:
                if self.base_cfg.LIVE.LOOP_VIDEO:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                log.info("Camera %s ended", self.name)
                break

            # 3. Process
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            detections, tracks = self._process_frame(frame, frame_rgb)
            
            # 4. Annotate
            annotated = self._annotate(frame, tracks)

            # 5. Stream
            ok, buf = cv2.imencode('.jpg', annotated)
            if ok:
                self.broadcaster.update_frame(self.name, buf.tobytes())

            # 6. Pace output
            elapsed = time.time() - last_ts
            sleep_for = max(0.0, self.target_interval - elapsed)
            time.sleep(sleep_for)
            last_ts = time.time()
            
            # 7. Mark tick complete
            self.frame_id = tick
            self.vclock.mark(self.name, tick)
    finally:
        if self.vclock:
            self.vclock.retire(self.name)
```

#### _process_frame()

**Lines**: 358-384

```python
def _process_frame(self, frame_bgr, frame_rgb):
    """Run detection, tracking, ReID, and MTMC update."""
    
    # 1. Detection
    res = self.detector(frame_bgr).xywh[0].cpu().numpy()
    boxes_raw = [t[:4] for t in res]
    scores_raw = [t[4] for t in res]
    classes_raw = [t[5] for t in res]

    # 2. Filter
    filtered = []
    for bbox, score, cl in zip(boxes_raw, scores_raw, classes_raw):
        if score < self.min_confid or cl not in self.tracked_classes:
            continue
        filtered.append((bbox, score, cl))

    # 3. Convert to tlwh format
    boxes_tlwh = [[int(x - w / 2), int(y - h / 2), w, h] 
                  for (x, y, w, h), _, _ in filtered]
    scores = [s for _, s, _ in filtered]
    classes = [c for _, _, c in filtered]

    # 4. ReID features
    features = self.extractor(frame_rgb, boxes_tlwh) if len(boxes_tlwh) > 0 else []
    detections = [Detection(bbox, score, clname, feature)
                  for bbox, score, clname, feature in zip(boxes_tlwh, scores, classes, features)]

    # 5. Tracking
    self.tracker.update(self.frame_id, detections, None, None)
    tracks = self.tracker.active_tracks
    
    # 6. Compute mean features (for clustering)
    for trk in tracks:
        trk.compute_mean_feature()
    
    # 7. Update aggregator, get global IDs
    gid_map = self.aggregator.update(self.cam_idx, tracks)
    for lid, gid in gid_map.items():
        self.local_to_global[lid] = gid
    
    return detections, tracks
```

**Related files**:
- `detection/detection.py` - `Detection` class
- `mot/tracklet.py` - `compute_mean_feature()`

#### _annotate()

**Lines**: 386-401

```python
def _annotate(self, frame_bgr, tracks):
    """Draw bounding boxes and global IDs on frame."""
    vis = frame_bgr.copy()
    for trk in tracks:
        if len(trk.bboxes) == 0:
            continue
        x, y, w, h = map(int, trk.bboxes[-1])
        gid = self.local_to_global.get(trk.track_id, -1)
        color = self._color_for_gid(gid)
        
        # Draw box and ID
        cv2.rectangle(vis, (x, y), (x + w, y + h), color, 2)
        cv2.putText(vis, f"{gid}", (x, y - 6),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    
    # Draw frame number
    cv2.putText(vis, f"t={self.frame_id}", (8, 24),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return vis
```

## Function: run_live()

**Lines**: 405-455  
**Purpose**: Orchestrate entire system

```python
def run_live(cfg: CfgNode):
    """Main function to start live MTMC system."""
    
    # 1. Create VirtualClock
    worker_names = [cam.get("name", f"cam_{idx}") 
                   for idx, cam in enumerate(cfg.EXPRESS.CAMERAS)]
    vclock = VirtualClock(interval=1.0 / float(cfg.LIVE.TARGET_FPS),
                         max_skew=cfg.LIVE.MAX_SKEW_TICKS,
                         stall_seconds=cfg.LIVE.STALL_SECONDS,
                         worker_names=worker_names)

    # 2. Load camera layout
    cams = CameraLayout(cfg.MTMC.CAMERA_LAYOUT) if cfg.MTMC.CAMERA_LAYOUT else None
    
    # 3. Create aggregator
    aggregator = LiveMTMCAggregator(cams,
                                   min_sim=cfg.MTMC.MIN_SIM,
                                   linkage=cfg.MTMC.LINKAGE,
                                   min_track_frames=cfg.LIVE.MIN_TRACK_FRAMES,
                                   cluster_interval=cfg.LIVE.CLUSTER_INTERVAL)

    # 4. Start MJPEG server
    broadcaster = MJPEGBroadcaster(port=cfg.LIVE.MJPEG_PORT)
    broadcaster.start()

    # 5. Start clock
    vclock.start()

    # 6. Create and start workers
    workers = []
    for idx, cam_info in enumerate(cfg.EXPRESS.CAMERAS):
        cam_cfg = dict(cam_info)
        worker = LiveMOTWorker(idx, cam_cfg, cfg, aggregator, broadcaster)
        worker.vclock = vclock
        workers.append(worker)
        broadcaster.update_frame(cam_cfg.get("name", f"cam_{idx}"), None)

    for w in workers:
        w.start()

    # 7. Wait for completion or Ctrl+C
    try:
        while any(w.is_alive() for w in workers):
            time.sleep(0.5)
    except KeyboardInterrupt:
        log.info("Stopping live MTMC...")
    finally:
        for w in workers:
            w.stop()
        vclock.stop()
        broadcaster.stop()
```

---

**Previous**: [Part 4: Running the System](04_LIVE_MTMC_RUNNING.md)  
**Next**: [Part 6: Troubleshooting](06_LIVE_MTMC_TROUBLESHOOTING.md)
