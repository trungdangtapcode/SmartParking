# Live MTMC Tracking - Part 4: Running the System

## Table of Contents
- [Part 1: Overview and Architecture](01_LIVE_MTMC_OVERVIEW.md)
- [Part 2: Installation and Setup](02_LIVE_MTMC_SETUP.md)
- [Part 3: Configuration Guide](03_LIVE_MTMC_CONFIG.md)
- [Part 4: Running the System](04_LIVE_MTMC_RUNNING.md) ← **You are here**
- [Part 5: Code Reference](05_LIVE_MTMC_CODE_REFERENCE.md)
- [Part 6: Troubleshooting](06_LIVE_MTMC_TROUBLESHOOTING.md)

---

## Starting Live MTMC

### Method 1: Direct Python

**File**: `vehicle_mtmc/mtmc/run_live_mtmc.py`

```bash
cd /mnt/mmlab2024nas/vund/.svn/bin/vehicle_mtmc

# Set PYTHONPATH
export PYTHONPATH=$(pwd)

# Run with config
python3 mtmc/run_live_mtmc.py --config examples/live_parking.yaml
```

**Command-line arguments**:

| Argument | Default | Description |
|----------|---------|-------------|
| `--config` | None (required) | Path to YAML config |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `--log-filename` | `run.log` | Log file name |
| `--no-log-stdout` | False | Disable console logging |
| `--output-dir` | From config | Override output directory |

**Parsed in**: `tools/util.py` `parse_args()` function

**Examples**:
```bash
# Debug mode
python3 mtmc/run_live_mtmc.py \
  --config examples/live_parking.yaml \
  --log-level DEBUG

# Custom output
python3 mtmc/run_live_mtmc.py \
  --config examples/live_parking.yaml \
  --output-dir /tmp/live_test

# Silent mode (log file only)
python3 mtmc/run_live_mtmc.py \
  --config examples/live_parking.yaml \
  --no-log-stdout
```

### Method 2: Shell Script

**File**: `vehicle_mtmc/run_live_mtmc.sh`

```bash
#!/usr/bin/env bash
export LD_LIBRARY_PATH=/path/to/TensorRT/lib:$LD_LIBRARY_PATH
export PYTHONPATH=$(pwd)
python3 mtmc/run_live_mtmc.py --config examples/live_parking.yaml
```

**Run it**:
```bash
chmod +x run_live_mtmc.sh
./run_live_mtmc.sh
```

### Method 3: Background Service

**Create systemd service** (Linux):

File: `/etc/systemd/system/live-mtmc.service`

```ini
[Unit]
Description=Live MTMC Tracking Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/mnt/mmlab2024nas/vund/.svn/bin/vehicle_mtmc
Environment="PYTHONPATH=/mnt/mmlab2024nas/vund/.svn/bin/vehicle_mtmc"
ExecStart=/usr/bin/python3 mtmc/run_live_mtmc.py --config examples/live_parking.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Control service**:
```bash
# Enable and start
sudo systemctl enable live-mtmc
sudo systemctl start live-mtmc

# Check status
sudo systemctl status live-mtmc

# View logs
sudo journalctl -u live-mtmc -f

# Stop
sudo systemctl stop live-mtmc
```

## Startup Sequence

**File**: `mtmc/run_live_mtmc.py` `run_live()` function (Lines 405-455)

### 1. Configuration Loading

```
[INFO] Loading config from: config/examples/live_parking.yaml
[INFO] Output directory: output/live_parking
```

**Code**: Lines 462-471

### 2. Model Loading

```
[INFO] Loading ONNX ReID model from models/resnet50_mixstyle/model.onnx
[INFO] ONNX Runtime using GPU: cuda:0
```

**Code**: `build_extractor()` function (Lines 25-45)

**Time**: 2-5 seconds

### 3. Camera Layout

```
[INFO] Camera layout loaded with 3 cams.
```

**Code**: Line 413  
**File**: `mtmc/cameras.py` `CameraLayout.__init__()`

### 4. HTTP Server Start

```
[INFO] MJPEG server started on port 8080
```

**Code**: Line 421  
**Class**: `MJPEGBroadcaster` (Lines 213-269)

### 5. Worker Thread Creation

```
[INFO] Starting camera cam_a
[INFO] Starting camera cam_b  
[INFO] Starting camera cam_c
```

**Code**: Lines 425-438  
**Class**: `LiveMOTWorker` (Lines 272-402)

### 6. Processing Start

```
[INFO] Camera cam_a: Frame 0, Detections: 5, Tracks: 3
[INFO] Camera cam_b: Frame 0, Detections: 8, Tracks: 5
```

Workers start processing frames in parallel.

## Viewing Streams

### Web Browser

**Index page**:
```
http://localhost:8080/
```

Shows list of all cameras with clickable links.

**Individual streams**:
```
http://localhost:8080/cam_a.mjpg
http://localhost:8080/cam_b.mjpg
http://localhost:8080/cam_c.mjpg
```

**What you'll see**:
- Bounding boxes around vehicles
- Global ID numbers above boxes
- Frame counter in top-left
- Color-coded by ID

### VLC Media Player

```bash
vlc http://localhost:8080/cam_a.mjpg
```

**Network stream dialog**:
1. Media → Open Network Stream
2. Enter: `http://localhost:8080/cam_a.mjpg`
3. Click Play

### FFmpeg

**Save stream to file**:
```bash
ffmpeg -i http://localhost:8080/cam_a.mjpg \
  -c:v libx264 -preset fast \
  output.mp4
```

**Re-stream to RTSP**:
```bash
ffmpeg -i http://localhost:8080/cam_a.mjpg \
  -f rtsp rtsp://localhost:8554/cam_a
```

### HTML Embed

**File**: Create `viewer.html`

```html
<!DOCTYPE html>
<html>
<head>
  <title>Live MTMC Viewer</title>
  <style>
    .camera { display: inline-block; margin: 10px; }
    img { border: 2px solid #333; }
    h3 { margin: 5px 0; }
  </style>
</head>
<body>
  <h1>Multi-Camera Tracking</h1>
  
  <div class="camera">
    <h3>Camera A (Entrance)</h3>
    <img src="http://localhost:8080/cam_a.mjpg" width="640" height="480">
  </div>
  
  <div class="camera">
    <h3>Camera B (Parking Lot)</h3>
    <img src="http://localhost:8080/cam_b.mjpg" width="640" height="480">
  </div>
  
  <div class="camera">
    <h3>Camera C (Exit)</h3>
    <img src="http://localhost:8080/cam_c.mjpg" width="640" height="480">
  </div>
</body>
</html>
```

Open in browser: `file:///path/to/viewer.html`

## Monitoring

### Log File

**Location**: `output/live_parking/run.log`

**Tail logs in real-time**:
```bash
tail -f output/live_parking/run.log
```

**Important log messages**:

```
[INFO] Camera cam_a: Frame 100, Detections: 3, Tracks: 2, FPS: 7.8
[INFO] MTMC: Clustered 45 tracks → 15 global IDs
[WARNING] Camera cam_b: Frame read failed, retrying...
[ERROR] Camera cam_c: Cannot open video source
```

### System Resources

**GPU usage**:
```bash
watch -n 1 nvidia-smi
```

**CPU/Memory**:
```bash
htop
# or
top
```

**Network (if RTSP)**:
```bash
iftop -i eth0
```

### Performance Metrics

**Add logging in code**:

Edit `mtmc/run_live_mtmc.py` around Line 350:

```python
# In LiveMOTWorker._process_frame()
import time
start = time.time()

# ... processing ...

elapsed = time.time() - start
log.info(f"Cam {self.name}: Frame {self.frame_id}, "
         f"Detections: {len(detections)}, "
         f"Tracks: {len(tracks)}, "
         f"Process time: {elapsed*1000:.1f}ms, "
         f"FPS: {1.0/elapsed:.1f}")
```

## Stopping the System

### Graceful Shutdown

**Press `Ctrl+C` in terminal**:

```
^C
[INFO] Stopping live MTMC...
[INFO] Camera cam_a stopped
[INFO] Camera cam_b stopped
[INFO] Camera cam_c stopped
[INFO] MJPEG server stopped
[INFO] VirtualClock stopped
```

**Code**: Lines 444-449 (exception handler)

### Kill Process

```bash
# Find process
ps aux | grep run_live_mtmc

# Kill by PID
kill -9 <PID>

# Or by name
pkill -f run_live_mtmc
```

### Stop Systemd Service

```bash
sudo systemctl stop live-mtmc
```

## Running Multiple Instances

### Different Configs

**Terminal 1**:
```bash
python3 mtmc/run_live_mtmc.py --config examples/parking_live.yaml
# Uses port 8080
```

**Terminal 2**:
```bash
python3 mtmc/run_live_mtmc.py --config examples/traffic_live.yaml
# Change MJPEG_PORT to 8081 in config
```

### Different Ports

Edit configs:

**parking_live.yaml**:
```yaml
LIVE:
  MJPEG_PORT: 8080
```

**traffic_live.yaml**:
```yaml
LIVE:
  MJPEG_PORT: 8081
```

Access:
- Parking: `http://localhost:8080/`
- Traffic: `http://localhost:8081/`

## Integration Examples

### REST API Wrapper

**File**: Create `rest_api_wrapper.py`

```python
from flask import Flask, jsonify, Response
from flask_cors import CORS
import threading
import sys

# Import Live MTMC
sys.path.insert(0, '/mnt/mmlab2024nas/vund/.svn/bin/vehicle_mtmc')
from mtmc.run_live_mtmc import run_live, LiveMTMCAggregator
from config.defaults import get_cfg_defaults
from config.config_tools import expand_relative_paths

app = Flask(__name__)
CORS(app)
aggregator = None

@app.route('/api/tracks')
def get_tracks():
    """Get all active tracks."""
    if aggregator is None:
        return jsonify({'error': 'System not running'}), 503
    
    with aggregator._lock:
        return jsonify({
            'timestamp': time.time(),
            'cameras': {
                f'cam_{i}': [
                    {
                        'local_id': t.track_id,
                        'global_id': aggregator._gid_map.get(i, {}).get(t.track_id, -1),
                        'bbox': t.bboxes[-1] if t.bboxes else None,
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
    if aggregator is None:
        return jsonify({'error': 'System not running'}), 503
    
    total_tracks = sum(len(t) for t in aggregator._tracks_by_cam.values())
    return jsonify({
        'total_tracks': total_tracks,
        'cameras': len(aggregator._tracks_by_cam),
        'last_cluster': aggregator._last_cluster_ts
    })

@app.route('/api/stream/<camera>')
def stream_camera(camera):
    """Proxy to MJPEG stream."""
    import requests
    url = f"http://localhost:8080/{camera}.mjpg"
    req = requests.get(url, stream=True)
    return Response(req.iter_content(chunk_size=1024),
                   content_type=req.headers['Content-Type'])

if __name__ == '__main__':
    # Start Live MTMC in background
    cfg = get_cfg_defaults()
    cfg.merge_from_file('config/examples/live_parking.yaml')
    cfg = expand_relative_paths(cfg)
    cfg.freeze()
    
    # Get aggregator reference
    # (You'll need to modify run_live() to return aggregator)
    
    # Start Flask
    app.run(host='0.0.0.0', port=5000, debug=False)
```

**Usage**:
```bash
python3 rest_api_wrapper.py

# Query from another script
curl http://localhost:5000/api/tracks
curl http://localhost:5000/api/stats
```

### WebSocket Real-Time Updates

**File**: Create `websocket_server.py`

```python
import asyncio
import websockets
import json
import time

connected_clients = set()

async def track_updates(websocket, path):
    """Send track updates to connected clients."""
    connected_clients.add(websocket)
    try:
        while True:
            # Get current tracks from aggregator
            tracks = get_current_tracks()  # Your function
            
            # Send to client
            await websocket.send(json.dumps(tracks))
            await asyncio.sleep(0.5)  # Update every 500ms
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.remove(websocket)

async def main():
    async with websockets.serve(track_updates, "0.0.0.0", 8765):
        await asyncio.Future()  # Run forever

if __name__ == '__main__':
    asyncio.run(main())
```

**JavaScript client**:
```javascript
const ws = new WebSocket('ws://localhost:8765');

ws.onmessage = (event) => {
  const tracks = JSON.parse(event.data);
  console.log('Updated tracks:', tracks);
  // Update UI
};
```

### Database Logging

**File**: Create `db_logger.py`

```python
import sqlite3
import time
import threading

class TrackLogger:
    def __init__(self, db_path='tracks.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._setup_db()
        
    def _setup_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                camera_id INTEGER,
                local_id INTEGER,
                global_id INTEGER,
                bbox TEXT,
                attributes TEXT
            )
        ''')
        self.conn.commit()
    
    def log_tracks(self, camera_id, tracks, gid_map):
        """Log tracks from one camera."""
        ts = time.time()
        for track in tracks:
            gid = gid_map.get(track.track_id, -1)
            bbox = str(track.bboxes[-1]) if track.bboxes else None
            attrs = str(track.attributes) if hasattr(track, 'attributes') else None
            
            self.cursor.execute('''
                INSERT INTO tracks (timestamp, camera_id, local_id, global_id, bbox, attributes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ts, camera_id, track.track_id, gid, bbox, attrs))
        
        self.conn.commit()
    
    def close(self):
        self.conn.close()

# Integrate into LiveMOTWorker
# In _process_frame(), after getting gid_map:
# self.db_logger.log_tracks(self.cam_idx, tracks, gid_map)
```

## Advanced Usage

### Custom Processing Hook

Modify `LiveMOTWorker` to add custom processing:

**File**: `mtmc/run_live_mtmc.py` (modify or subclass)

```python
class CustomLiveMOTWorker(LiveMOTWorker):
    def _process_frame(self, frame_bgr, frame_rgb):
        # Call parent
        detections, tracks = super()._process_frame(frame_bgr, frame_rgb)
        
        # Custom: Count vehicles in zone
        for track in tracks:
            if len(track.bboxes) > 0:
                x, y, w, h = map(int, track.bboxes[-1])
                if self.is_in_zone(x, y, w, h):
                    self.zone_count += 1
        
        return detections, tracks
    
    def is_in_zone(self, x, y, w, h):
        # Your zone logic
        return 100 < x < 500 and 200 < y < 600
```

### Custom Annotation

Modify `_annotate()` method:

```python
def _annotate(self, frame_bgr, tracks):
    vis = frame_bgr.copy()
    for trk in tracks:
        if len(trk.bboxes) == 0:
            continue
        x, y, w, h = map(int, trk.bboxes[-1])
        gid = self.local_to_global.get(trk.track_id, -1)
        
        # Custom: Different color based on vehicle type
        if hasattr(trk, 'attributes') and 'type' in trk.attributes:
            vtype = trk.attributes['type']
            color = {
                'car': (0, 255, 0),
                'truck': (0, 0, 255),
                'bus': (255, 0, 0)
            }.get(vtype, (255, 255, 255))
        else:
            color = self._color_for_gid(gid)
        
        # Draw
        cv2.rectangle(vis, (x, y), (x + w, y + h), color, 2)
        cv2.putText(vis, f"ID:{gid}", (x, y - 6),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    
    return vis
```

---

**Previous**: [Part 3: Configuration Guide](03_LIVE_MTMC_CONFIG.md)  
**Next**: [Part 5: Code Reference](05_LIVE_MTMC_CODE_REFERENCE.md)
