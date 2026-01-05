# ByteTrack Tracking Monitor - Quick Start Guide

## 🎯 Overview
Debug endpoint to monitor and visualize ByteTrack multi-object tracking in real-time.

## 🚀 Quick Start

### 1. Start the Backend Server
```bash
cd server
conda activate scheduler
python main_fastapi.py
```

### 2. Start a Mock Camera (Optional)
```bash
cd ESP32
python mock_esp32_server.py --port 5069
```

### 3. Access Tracking Monitor

#### Option A: Web UI (Recommended)
Open in browser:
```
http://localhost:8069/static/tracking_monitor.html
```

#### Option B: Direct Stream URL
Use in `<img>` tag or browser:
```
http://localhost:8069/stream/tracking?camera_url=http://localhost:5069&conf=0.25&fps=10
```

## 📡 API Endpoint

### GET `/stream/tracking`

**Description:** Stream with ByteTrack multi-object tracking

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `camera_url` | string | required | Camera URL (e.g., http://192.168.1.100) |
| `conf` | float | 0.25 | Confidence threshold (0.1-0.9) |
| `fps` | int | 10 | Target FPS (1-30) |
| `skip_frames` | int | 1 | Process every Nth frame |
| `show_labels` | bool | true | Show track IDs and labels |
| `show_trails` | bool | true | Show tracking trails |

**Examples:**

```bash
# Basic usage with mock camera
http://localhost:8069/stream/tracking?camera_url=http://localhost:5069

# High accuracy (slower)
http://localhost:8069/stream/tracking?camera_url=http://localhost:5069&conf=0.4&fps=5

# High speed (faster)
http://localhost:8069/stream/tracking?camera_url=http://localhost:5069&conf=0.15&fps=20&skip_frames=2

# Without trails
http://localhost:8069/stream/tracking?camera_url=http://localhost:5069&show_trails=false
```

## 🎨 Features

### Visual Elements
- ✅ **Bounding Boxes:** Color-coded per track ID
- ✅ **Track IDs:** Persistent IDs across frames
- ✅ **Tracking Trails:** Last 30 positions visualized
- ✅ **Statistics Overlay:**
  - Frame number
  - Active tracks count
  - Total tracks seen
  - Current detections
  - Real-time FPS

### ByteTrack Features
- ✅ **Persistent Tracking:** Same object keeps same ID
- ✅ **Multi-Object:** Track multiple objects simultaneously
- ✅ **Occlusion Handling:** Maintains ID through brief occlusions
- ✅ **ID Re-assignment:** Smart matching when objects reappear

## 📊 Monitoring

### Console Logs
The server logs tracking statistics every 30 frames:

```
🎯 [Track abc123] Frame 30 | Active: 3 | Total Seen: 5 | FPS: 9.8 | Process: 45.2ms
```

**Log format:**
- `Frame X`: Current frame number
- `Active: N`: Currently tracked objects
- `Total Seen: N`: Unique track IDs seen since start
- `FPS: X.X`: Actual processing FPS
- `Process: X.Xms`: Processing time per frame

### Statistics Tracking
- Active tracks in current frame
- Total unique tracks seen (lifetime)
- Frames with successful tracking
- Real-time performance metrics

## 🔧 Tuning for Different Scenarios

### Parking Lot Monitoring
```
conf=0.3&fps=10&skip_frames=1&show_trails=true
```
- Moderate confidence for vehicle detection
- 10 FPS for smooth monitoring
- Process every frame for accurate tracking
- Trails help visualize movement patterns

### High-Traffic Areas
```
conf=0.25&fps=15&skip_frames=2&show_trails=false
```
- Lower confidence to catch all vehicles
- Higher FPS for fast-moving objects
- Skip frames to maintain performance
- Disable trails to reduce visual clutter

### Accurate Counting
```
conf=0.4&fps=5&skip_frames=1&show_trails=true
```
- Higher confidence for accuracy
- Lower FPS to reduce false positives
- Process every frame for complete tracking
- Trails help verify continuous tracks

## 🆚 Comparison: Detection vs Tracking

### `/stream/detect` (Detection Only)
- ❌ No persistent IDs
- ❌ No tracking across frames
- ❌ Can't count unique objects
- ✅ Slightly faster
- ✅ Simpler

### `/stream/tracking` (ByteTrack)
- ✅ Persistent track IDs
- ✅ Tracks objects across frames
- ✅ Can count unique vehicles
- ✅ Handles occlusions
- ⚠️ Slightly slower (5-10ms overhead)

## 🐛 Troubleshooting

### Stream Not Loading
1. Check camera URL is accessible: `curl http://localhost:5069/stream`
2. Verify FastAPI server is running: `curl http://localhost:8069/health`
3. Check browser console for errors

### Low FPS
1. Reduce `fps` parameter (e.g., 10 → 5)
2. Increase `skip_frames` (e.g., 1 → 2)
3. Lower confidence threshold (e.g., 0.25 → 0.15)
4. Check GPU utilization: `nvidia-smi`

### No Tracks Detected
1. Lower confidence threshold (try 0.15)
2. Ensure camera has clear view of objects
3. Check if objects are in supported classes (car, motorcycle, bus, truck)
4. Verify YOLO model is loaded: Check server startup logs

### Track IDs Jumping
1. Increase confidence threshold for more stable detections
2. Reduce FPS to process more consistently
3. Check if objects are too similar (ByteTrack may confuse them)
4. Adjust ByteTrack parameters in `tracking_config.yaml`

## 📝 Example Usage

### HTML
```html
<img src="http://localhost:8069/stream/tracking?camera_url=http://localhost:5069" 
     alt="Tracking Stream" 
     style="width: 100%;">
```

### React/Vue
```jsx
<img 
  src={`http://localhost:8069/stream/tracking?camera_url=${cameraUrl}&conf=0.25`}
  alt="ByteTrack Stream"
/>
```

### Python (OpenCV)
```python
import cv2

url = "http://localhost:8069/stream/tracking?camera_url=http://localhost:5069"
cap = cv2.VideoCapture(url)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    cv2.imshow('Tracking', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

## 🎓 Understanding ByteTrack

### How It Works
1. **Detection:** YOLO detects objects in frame
2. **Matching:** ByteTrack matches detections to existing tracks
3. **Update:** Updates track positions and states
4. **ID Assignment:** Assigns persistent IDs to new tracks
5. **Cleanup:** Removes lost tracks after buffer expires

### Key Parameters (in tracking_config.yaml)
- `track_high_thresh`: High-confidence detections (confirmed tracks)
- `track_low_thresh`: Low-confidence detections (unconfirmed tracks)
- `track_buffer`: Frames to keep lost tracks before deletion
- `match_thresh`: IOU threshold for matching

## 📚 References
- ByteTrack Paper: https://arxiv.org/abs/2110.06864
- YOLO: https://github.com/ultralytics/ultralytics
- FastAPI: https://fastapi.tiangolo.com/

## 🎯 Next Steps
1. Test with different camera angles
2. Adjust parameters for your use case
3. Monitor performance metrics
4. Compare with `/stream/detect` endpoint
5. Integrate into your application
