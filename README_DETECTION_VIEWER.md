# 🎯 Detection Viewer with Logging - Quick Start

## What Was Built

A complete detection viewing system with:
- ✅ **Live MJPEG streaming** with bounding boxes
- ✅ **Real-time metadata** (vehicle count, occupancy)
- ✅ **Automatic logging** to .log files
- ✅ **Dual view mode** (detection/raw)
- ✅ **Scalable broadcasting** (100 viewers = same GPU load)

## Quick Start (3 Steps)

### 1. Start Backend Services

```bash
# Terminal 1: FastAPI Server
cd server
conda activate scheduler
python main_fastapi.py

# Terminal 2: Worker with Logging (10 FPS)
cd server
python parking_monitor_worker.py --fps 10
```

### 2. Start Frontend

```bash
# Terminal 3: Frontend
cd frontend
npm run dev
```

### 3. Open in Browser

```
Main UI:     http://localhost:5169/detection-viewer
Test Page:   http://localhost:8069/static/detection_viewer_test.html
```

## What You'll See

### Detection Viewer UI
- Select parking lot from dropdown
- View all cameras in grid layout
- Toggle between **Detection View** (with bounding boxes) and **Raw Stream**
- Real-time stats: Vehicles | Occupied | Available
- Worker status indicator

### Detection Logs
Automatically saved to: `server/logs/detections/detection_cam001_2026-01-05.log`

Each log entry includes:
- Timestamp
- Vehicle count and locations (bounding boxes)
- Parking space occupancy
- Confidence scores
- Frame metadata

## View Detection Logs

### Command Line
```bash
# View latest logs
tail -n 50 server/logs/detections/detection_cam001_2026-01-05.log | jq

# Monitor in real-time
tail -f server/logs/detections/detection_cam001_2026-01-05.log | jq

# Check log statistics
curl http://localhost:8069/logs/stats | jq
```

### Via API
```bash
# Get recent detections
curl "http://localhost:8069/logs/detections?camera_id=cam001&limit=100" | jq

# Get log stats
curl http://localhost:8069/logs/stats | jq

# Cleanup old logs (older than 7 days)
curl -X POST "http://localhost:8069/logs/cleanup?days=7"
```

## Worker Options

```bash
# Basic (10 FPS, logging enabled)
python parking_monitor_worker.py --fps 10

# High FPS
python parking_monitor_worker.py --fps 30

# Disable logging (not recommended)
python parking_monitor_worker.py --fps 10 --no-logging

# With Firebase updates (slow, reduces to ~0.3 FPS)
python parking_monitor_worker.py --fps 10 --update-firebase

# Debug mode
python parking_monitor_worker.py --fps 10 --debug
```

## Key Features

### 1. Efficient Broadcasting
**Problem:** 100 clients = 100x GPU load ❌  
**Solution:** Worker processes once, broadcasts to all ✅  
**Result:** Same GPU load for 1 or 100 viewers!

### 2. Automatic Logging
- Every detection is logged automatically
- JSON format (one entry per line)
- One file per camera per day
- Includes: bounding boxes, confidence, occupancy, metadata

### 3. Dual View Mode
- **Detection View:** Shows bounding boxes, parking spaces, statistics
- **Raw Stream:** Shows original camera feed
- Toggle instantly without reloading

### 4. Real-time Statistics
- Vehicle count
- Occupied spaces
- Available spaces
- Occupancy rate
- Last update timestamp

## Architecture

```
Browser (Detection Viewer)
    ↓ MJPEG Stream + WebSocket
FastAPI Server (/stream/worker-detection, /ws/viewer/detection)
    ↓ Broadcast
DetectionBroadcaster (shares frames to all viewers)
    ↑ Annotated frames
Parking Monitor Worker (10 FPS)
    ├─→ Detect vehicles (YOLO)
    ├─→ Draw bounding boxes
    ├─→ Log to .log files
    └─→ (Optional) Update Firebase
```

## Files Created/Modified

### Frontend
- ✅ `frontend/src/pages/DetectionViewerPage.tsx` - Enhanced UI

### Backend (New)
- ✅ `server/services/detection_logger.py` - Logging service
- ✅ `server/routers/detection_logs.py` - Log API
- ✅ `server/static/detection_viewer_test.html` - Test page

### Backend (Modified)
- ✅ `server/parking_monitor_worker.py` - Added logging
- ✅ `server/main_fastapi.py` - Added detection_logs router

### Documentation
- ✅ `docs/DETECTION_VIEWER_UI.md` - Complete guide
- ✅ `docs/DETECTION_VIEWER_IMPLEMENTATION.md` - Implementation summary

## API Endpoints

### Streaming
```
GET  /stream/worker-detection?camera_id=cam001&fps=10  (MJPEG stream)
WS   /ws/viewer/detection?camera_id=cam001             (Metadata updates)
```

### Logs
```
GET  /logs/stats                                       (Log file statistics)
GET  /logs/detections?camera_id=cam001&limit=100      (Recent detections)
POST /logs/cleanup?days=7                             (Delete old logs)
```

## Troubleshooting

### No video stream?
1. Check worker is running: `ps aux | grep parking_monitor_worker`
2. Check worker logs for "🚀 Starting parking monitor worker..."
3. Verify camera has `workerEnabled: true` in Firebase
4. Check FastAPI is running: `curl http://localhost:8069/health`

### Metadata not updating?
1. Check WebSocket connection in browser console (F12)
2. Verify worker is processing: Look for "🚗 Detected X vehicles"
3. Check camera_id matches between frontend and worker

### Worker not logging?
1. Check logs directory exists: `ls -la server/logs/detections/`
2. Look for "📝 Logged detection" in worker console
3. Verify `--no-logging` flag is NOT used

### Low FPS?
1. Disable Firebase: Remove `--update-firebase` flag
2. Reduce target FPS: Use `--fps 5`
3. Check system resources: `htop` or `nvidia-smi`

## Performance Tips

| Configuration | FPS | GPU Load | Logging | Firebase |
|--------------|-----|----------|---------|----------|
| Recommended | 10 | Low | ✅ | ❌ |
| High FPS | 30 | Medium | ✅ | ❌ |
| With Firebase | 0.3 | Low | ✅ | ✅ |

**Best Practices:**
- ✅ Keep logging enabled (minimal overhead)
- ✅ Use 10 FPS for balanced performance
- ❌ Avoid Firebase updates unless persistence is critical
- ✅ Use MJPEG streaming for multiple viewers

## Example: Analyze Logs

```python
import json
from collections import Counter

# Load log file
with open('logs/detections/detection_cam001_2026-01-05.log') as f:
    entries = [json.loads(line) for line in f]

# Calculate statistics
vehicle_counts = [e['summary']['vehicle_count'] for e in entries]
avg_vehicles = sum(vehicle_counts) / len(vehicle_counts)

occupancy_rates = [
    float(e['summary']['occupancy_rate'].strip('%'))
    for e in entries
]
avg_occupancy = sum(occupancy_rates) / len(occupancy_rates)

print(f"Total detections: {len(entries)}")
print(f"Average vehicles: {avg_vehicles:.1f}")
print(f"Average occupancy: {avg_occupancy:.1f}%")

# Find peak hours
hours = Counter(e['timestamp'][:13] for e in entries)  # Group by hour
print(f"Peak hour: {hours.most_common(1)[0]}")
```

## Documentation

- **Complete Guide:** `docs/DETECTION_VIEWER_UI.md`
- **Implementation Details:** `docs/DETECTION_VIEWER_IMPLEMENTATION.md`
- **Worker Monitoring:** `docs/WORKER_MONITORING_GUIDE.md`
- **Worker Architecture:** `server/PARKING_MONITOR_WORKER.md`

## Summary

✅ **What it does:**
- Shows live detection results with bounding boxes
- Logs all detections to files automatically
- Scales to 100+ viewers without increasing GPU load
- Provides both detection and raw camera views

✅ **How to use:**
1. Start FastAPI + Worker
2. Open http://localhost:5169/detection-viewer
3. Select parking lot and watch cameras
4. Check logs at `server/logs/detections/`

✅ **Access:**
- **Main UI:** http://localhost:5169/detection-viewer
- **Test Page:** http://localhost:8069/static/detection_viewer_test.html
- **Logs:** `server/logs/detections/`
- **API:** http://localhost:8069/logs/*

---

**Built:** 2026-01-05  
**Status:** ✅ Complete and working
