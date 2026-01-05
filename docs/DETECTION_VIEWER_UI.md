# Detection Viewer UI - Complete Guide

## 🎯 Overview

The Detection Viewer UI provides a real-time visualization interface for monitoring parking detection results from worker processes. It features:

- **Live MJPEG streaming** with bounding boxes and parking space overlays
- **Dual view modes**: Detection view (with annotations) and Raw camera view
- **Real-time occupancy statistics** per camera
- **Efficient broadcasting**: 100 viewers watching the same stream = same GPU load as 1 viewer
- **Detection logging**: All results saved to `.log` files for analysis

**Access URL:** `http://localhost:5169/detection-viewer`

---

## 🎨 Features

### 1. **Detection View Mode** 🎯
Shows worker detection results with:
- ✅ **Bounding boxes** around detected vehicles
- ✅ **Parking space boundaries** (color-coded)
- ✅ **Real-time occupancy status** (green = available, red = occupied)
- ✅ **Statistics dashboard**: Vehicle count, occupied spaces, available spaces
- ✅ **Worker status indicator**: Shows if worker is active

### 2. **Raw Stream Mode** 📹
Shows original camera feed without detection overlays:
- Direct camera stream without processing
- Useful for comparing with detection results
- Lower latency (no worker processing delay)

### 3. **Multi-Camera Grid View**
- Displays all cameras in selected parking lot
- Responsive grid layout (1-3 columns based on screen size)
- Independent status indicators per camera
- Real-time metadata updates

---

## 🚀 How to Use

### **Step 1: Start the Backend Services**

#### Start FastAPI Server:
```bash
cd server
conda activate scheduler  # or your environment
python main_fastapi.py
```
Server will run on: `http://localhost:8069`

#### Start Parking Monitor Worker:
```bash
cd server
python parking_monitor_worker.py --fps 10
```

**Worker Options:**
```bash
# Basic (10 FPS, logging enabled)
python parking_monitor_worker.py --fps 10

# High FPS with logging
python parking_monitor_worker.py --fps 30

# With Firebase updates (slow)
python parking_monitor_worker.py --fps 10 --update-firebase

# Disable logging (not recommended)
python parking_monitor_worker.py --fps 10 --no-logging

# Debug mode
python parking_monitor_worker.py --fps 10 --debug
```

### **Step 2: Start Frontend**
```bash
cd frontend
npm run dev
```
Frontend will run on: `http://localhost:5169`

### **Step 3: Access Detection Viewer**
1. Open browser: `http://localhost:5169/detection-viewer`
2. Select a parking lot from dropdown
3. Cameras will load automatically
4. Toggle between **Detection View** and **Raw Stream** modes

---

## 📊 UI Components

### **Top Bar**
```
📺 Detection Viewer                           [🎯 Detection View] [📹 Raw Stream]
Watch worker detection results with bounding boxes and occupancy info
```

### **Parking Lot Selector**
```
Select Parking Lot:
[Dropdown: Choose parking lot...]
```

### **Camera Grid**
Each camera card shows:

```
┌─────────────────────────────────────────┐
│ 🎯 Camera Name                    🟢 connected │
│ ┌─────────────────────────────────────┐ │
│ │ Vehicles: 5  Occupied: 12  Free: 8  │ │
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │                                     │ │
│ │      [Live Video Stream]            │ │
│ │      with bounding boxes            │ │
│ │                                     │ │
│ └─────────────────────────────────────┘ │
│ ✅ Worker Active                        │
│ IP Address: http://192.168.1.100       │
│ Last Update: 14:30:15                   │
└─────────────────────────────────────────┘
```

---

## 🔧 Technical Architecture

### **Frontend (React + TypeScript)**
**File:** `frontend/src/pages/DetectionViewerPage.tsx`

**Key Features:**
- WebSocket connection for real-time metadata updates
- MJPEG `<img>` tag for efficient video streaming
- View mode toggle (detection/raw)
- Connection status management
- Automatic cleanup on unmount

**WebSocket Flow:**
```
Client → ws://localhost:8069/ws/viewer/detection?camera_id=cam001
         ↓
Server sends: {"type": "frame", "metadata": {...}}
         ↓
Client updates: vehicle count, occupancy stats
```

**MJPEG Stream URL:**
```
Detection: http://localhost:8069/stream/worker-detection?camera_id=cam001&fps=10
Raw:       http://192.168.1.100/stream  (direct camera)
```

### **Backend (FastAPI + Python)**

#### **1. Worker Detection Stream** (`server/routers/worker_detection_stream.py`)
```python
@router.get("/stream/worker-detection")
async def stream_worker_detection(camera_id: str, fps: int = 10)
```
- Serves MJPEG stream with detection annotations
- Efficient broadcasting (shared frames)
- Rate limiting per viewer

#### **2. Detection Viewer WebSocket** (`server/routers/detection_viewer.py`)
```python
@router.websocket("/ws/viewer/detection")
async def ws_viewer_detection(websocket: WebSocket, camera_id: str)
```
- Sends metadata to connected clients
- Manages viewer registration/unregistration
- Broadcasts frame metadata (not frame data itself)

#### **3. Detection Logger** (`server/services/detection_logger.py`)
```python
class DetectionLogger:
    async def log_detection(camera_id, detections, parking_spaces, space_occupancy)
```
- Logs detection results to `.log` files
- One file per camera per day
- JSON format (one entry per line)

#### **4. Parking Monitor Worker** (`server/parking_monitor_worker.py`)
```python
class ParkingMonitorWorker:
    async def process_camera(camera_info):
        # 1. Fetch frame
        # 2. Detect vehicles
        # 3. Match to parking spaces
        # 4. Broadcast annotated frame
        # 5. Log results
```

---

## 📝 Detection Logging

### **Log File Location**
```
server/logs/detections/
├── detection_cam001_2026-01-05.log
├── detection_cam002_2026-01-05.log
└── detection_cam003_2026-01-05.log
```

### **Log Format**
Each line is a JSON object:
```json
{
  "timestamp": "2026-01-05T14:30:15.123456",
  "camera_id": "cam001",
  "summary": {
    "vehicle_count": 5,
    "total_spaces": 20,
    "occupied_spaces": 12,
    "available_spaces": 8,
    "occupancy_rate": "60.0%"
  },
  "detections": [
    {
      "bbox": [100, 200, 150, 250],
      "confidence": 0.95,
      "class": "car"
    }
  ],
  "space_occupancy": {
    "space_01": true,
    "space_02": false
  },
  "metadata": {
    "frame_size": "1920x1080",
    "parking_id": "parking_001",
    "camera_name": "Main Entrance"
  }
}
```

### **Log Management API**

#### Get Log Statistics:
```bash
curl http://localhost:8069/logs/stats
```

Response:
```json
{
  "log_directory": "logs/detections",
  "log_files": [
    {
      "filename": "detection_cam001_2026-01-05.log",
      "size_mb": 2.5,
      "entries": 1500,
      "modified": "2026-01-05T14:30:00"
    }
  ],
  "total_size_mb": 10.2
}
```

#### Get Recent Detections:
```bash
curl "http://localhost:8069/logs/detections?camera_id=cam001&limit=100"
```

#### Cleanup Old Logs:
```bash
curl -X POST "http://localhost:8069/logs/cleanup?days=7"
```

---

## 🎥 Streaming Architecture

### **Key Design: Efficient Broadcasting**

**Problem:** 100 clients watching = 100x GPU load ❌

**Solution:** Worker processes once, broadcasts to all ✅

```
┌──────────────────────────────────────────────────────────────┐
│                    Parking Monitor Worker                    │
│  - Fetches camera frame (10 FPS)                            │
│  - Detects vehicles (YOLO)                                  │
│  - Draws bounding boxes                                     │
│  - Logs to .log file                                        │
└─────────────────────┬────────────────────────────────────────┘
                      │ Broadcast annotated frame
                      ▼
┌──────────────────────────────────────────────────────────────┐
│              DetectionBroadcaster (singleton)                │
│  - Stores latest frame per camera                           │
│  - Manages WebSocket viewers                                │
└───────┬─────────────┬─────────────┬──────────────────────────┘
        │             │             │
        ▼             ▼             ▼
   [Viewer 1]    [Viewer 2]    [Viewer 100]
   
GPU Load: Same for 1 viewer or 100 viewers! 🎉
```

### **MJPEG vs WebSocket**

**MJPEG Stream** (used for video):
- Efficient for image data
- Browser-native decoding
- Simple `<img>` tag implementation
- Automatic reconnection

**WebSocket** (used for metadata):
- Real-time metadata updates
- Connection status
- Bidirectional communication
- JSON message format

---

## 🔍 Monitoring & Debugging

### **Check Worker Status**

#### Console Logs:
```
🚀 Starting parking monitor worker...
⏱️  Target FPS: 10 FPS per camera
Found worker-enabled camera: Main Entrance (cam001)
✅ Loaded 20 parking spaces for camera cam001
Processing camera: Main Entrance (cam001)
🚗 Detected 5 vehicles in camera cam001
📺 Sent frame to FastAPI for camera cam001
📝 Logged detection for cam001: 5 vehicles, 12/20 occupied
```

#### Check if Worker is Running:
```bash
ps aux | grep parking_monitor_worker
```

#### View Recent Log Entries:
```bash
tail -f server/logs/detections/detection_cam001_2026-01-05.log | jq
```

### **Frontend Debugging**

#### Open Browser Console (F12):
```
✅ WebSocket connected for Main Entrance
🎥 Starting detection stream for camera: Main Entrance
ℹ️ Connected to camera cam001. Viewers: 1
```

#### Check Network Tab:
- WebSocket: `ws://localhost:8069/ws/viewer/detection`
- MJPEG Stream: `http://localhost:8069/stream/worker-detection`

---

## ⚡ Performance Optimization

### **Worker Performance**

| Configuration | FPS | GPU Load | Logging | Firebase |
|--------------|-----|----------|---------|----------|
| Default | 10 | Low | ✅ | ❌ |
| High FPS | 30 | Medium | ✅ | ❌ |
| With Firebase | 0.3 | Low | ✅ | ✅ |

**Recommendations:**
- ✅ **Use default 10 FPS** for balanced performance
- ✅ **Keep logging enabled** (minimal impact)
- ❌ **Avoid Firebase updates** unless persistence is critical
- ✅ **Use MJPEG streaming** for multiple viewers

### **Viewer Scalability**

| Viewers | GPU Load | Network Bandwidth |
|---------|----------|-------------------|
| 1 | 100% | 1x |
| 10 | 100% | 10x |
| 100 | 100% | 100x |

**GPU load is constant!** Only network bandwidth increases per viewer.

---

## 🐛 Troubleshooting

### **Problem: No video stream**

**Symptoms:**
- Black screen or "Stream Error"
- "⏳ Waiting for worker..."

**Solutions:**
1. Check worker is running: `ps aux | grep parking_monitor_worker`
2. Check worker logs for errors
3. Verify camera has `workerEnabled: true` in Firebase
4. Check FastAPI is running: `curl http://localhost:8069/health`

### **Problem: Metadata not updating**

**Symptoms:**
- Video plays but stats don't update
- "Vehicles: 0, Occupied: 0" always

**Solutions:**
1. Check WebSocket connection in browser console
2. Verify worker is processing: Look for "🚗 Detected X vehicles"
3. Check camera_id matches between frontend and worker

### **Problem: Worker not detecting vehicles**

**Symptoms:**
- Worker logs "🚗 Detected 0 vehicles"
- Stream shows cars but no bounding boxes

**Solutions:**
1. Check YOLO model is loaded: "✅ AI models loaded"
2. Verify camera stream has visible vehicles
3. Check detection confidence threshold
4. Enable debug logging: `--debug`

### **Problem: Low FPS**

**Symptoms:**
- Video is choppy
- Worker logs "Processing" slowly

**Solutions:**
1. **Disable Firebase**: Remove `--update-firebase` flag
2. **Reduce target FPS**: Use `--fps 5`
3. **Check system resources**: `htop` or `nvidia-smi`
4. **Reduce viewer count** (if bandwidth is issue)

---

## 📚 API Reference

### **Detection Viewer Endpoints**

#### **GET /stream/worker-detection**
Stream MJPEG with detection annotations

**Query Params:**
- `camera_id` (required): Camera ID
- `fps` (optional): Target FPS (1-30, default 10)

**Example:**
```
http://localhost:8069/stream/worker-detection?camera_id=cam001&fps=15
```

#### **WebSocket /ws/viewer/detection**
Receive real-time metadata updates

**Query Params:**
- `camera_id` (required): Camera ID
- `user_id` (optional): User ID for logging

**Messages:**
```json
{
  "type": "frame",
  "metadata": {
    "vehicle_count": 5,
    "occupied_spaces": 12,
    "total_spaces": 20,
    "timestamp": "2026-01-05T14:30:15.123456"
  }
}
```

#### **GET /logs/stats**
Get detection log statistics

#### **GET /logs/detections**
Get recent detection entries

**Query Params:**
- `camera_id` (required): Camera ID
- `limit` (optional): Max entries (default 100)

#### **POST /logs/cleanup**
Delete old log files

**Query Params:**
- `days` (optional): Delete older than N days (default 7)

---

## 🎓 Usage Examples

### **Example 1: Basic Usage**
```bash
# Terminal 1: Start FastAPI
cd server && python main_fastapi.py

# Terminal 2: Start Worker
cd server && python parking_monitor_worker.py --fps 10

# Terminal 3: Start Frontend
cd frontend && npm run dev

# Browser: Open http://localhost:5169/detection-viewer
```

### **Example 2: High FPS Setup**
```bash
# Use high FPS for smooth video
python parking_monitor_worker.py --fps 30
```

### **Example 3: View Detection Logs**
```bash
# View latest logs
tail -n 100 server/logs/detections/detection_cam001_2026-01-05.log | jq

# Monitor in real-time
tail -f server/logs/detections/detection_cam001_2026-01-05.log | jq

# Get log stats via API
curl http://localhost:8069/logs/stats | jq
```

### **Example 4: Analyze Occupancy Trends**
```python
import json

# Load log file
with open('logs/detections/detection_cam001_2026-01-05.log') as f:
    entries = [json.loads(line) for line in f]

# Calculate average occupancy
occupancy_rates = [
    float(e['summary']['occupancy_rate'].strip('%'))
    for e in entries
]
avg_occupancy = sum(occupancy_rates) / len(occupancy_rates)
print(f"Average occupancy: {avg_occupancy:.1f}%")
```

---

## 📁 File Structure

```
server/
├── parking_monitor_worker.py        # Main worker process
├── routers/
│   ├── worker_detection_stream.py   # MJPEG streaming endpoint
│   ├── detection_viewer.py          # WebSocket metadata endpoint
│   └── detection_logs.py            # Log management API
├── services/
│   ├── detection_logger.py          # Logging service
│   ├── detection_broadcaster.py     # Broadcasting service
│   └── ai_service.py                # YOLO detection
└── logs/
    └── detections/
        └── detection_cam001_*.log   # Log files

frontend/
└── src/
    └── pages/
        └── DetectionViewerPage.tsx  # Main UI component
```

---

## 🎯 Summary

**Detection Viewer UI provides:**
- ✅ Real-time detection visualization with bounding boxes
- ✅ Efficient multi-viewer broadcasting (GPU-friendly)
- ✅ Dual mode: Detection view & Raw stream
- ✅ Automatic logging to .log files
- ✅ Easy-to-use API for log analysis
- ✅ Responsive grid layout for multiple cameras

**Access:** `http://localhost:5169/detection-viewer`

**Documentation:** See also:
- `docs/WORKER_MONITORING_GUIDE.md` - Worker monitoring
- `server/PARKING_MONITOR_WORKER.md` - Worker architecture
- `docs/PERFORMANCE_TUNING.md` - Performance tips

---

**Last Updated:** 2026-01-05  
**Author:** Parking Detection System Team
