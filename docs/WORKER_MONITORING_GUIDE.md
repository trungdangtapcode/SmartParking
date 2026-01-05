# Parking Monitor Worker - Monitoring & Verification Guide

## 📋 Overview

This guide explains how to verify that the `parking_monitor_worker.py` is actually working and where to find its outputs/results.

**File Location:** `/server/parking_monitor_worker.py`

---

## 🔍 How to Know the Worker is Working

The worker provides **multiple ways** to verify it's functioning correctly:

### 1. **Console Logs (Real-time Monitoring)** ✅ PRIMARY METHOD

When the worker is running, it outputs detailed logs to the console showing:

#### **Startup Logs:**
```
🚀 Starting parking monitor worker...
⏱️  Target FPS: 10 FPS per camera
Loading AI models...
✅ Models loaded successfully
```

#### **Camera Discovery Logs:**
```
Found worker-enabled camera: Parking Lot A Main Entrance (cam_001)
Found worker-enabled camera: Parking Lot B Level 2 (cam_002)
✅ Loaded 45 parking spaces for camera cam_001
✅ Loaded 38 parking spaces for camera cam_002
```

#### **Processing Logs:**
```
Processing camera: Parking Lot A Main Entrance (cam_001)
🚗 Detected 12 vehicles in camera cam_001
📺 Sent frame to FastAPI for camera cam_001
```

#### **If Firebase Updates Enabled:**
```
✅ Updated Firebase occupancy for camera cam_001: 8/45 occupied
```

#### **Warning/Error Logs:**
```
⚠️ No active cameras found. Waiting...
Failed to fetch frame from http://192.168.1.100/capture
```

**How to View Logs:**
- **Method 1:** Run worker directly in terminal:
  ```bash
  cd server
  python parking_monitor_worker.py
  ```

- **Method 2:** If running as background service, check logs:
  ```bash
  # If using systemd
  journalctl -u parking-worker -f
  
  # If using screen/tmux
  screen -r parking-worker  # or tmux attach
  ```

- **Method 3:** Enable debug logging for more details:
  ```bash
  python parking_monitor_worker.py --debug
  ```

---

### 2. **Visual Stream Output** 🎥 REAL-TIME VISUALIZATION

The worker broadcasts **annotated video frames** showing:
- ✅ Detection bounding boxes around vehicles
- ✅ Parking space boundaries
- ✅ Color-coded occupancy status (green = free, red = occupied)

**How to View Stream:**

#### **Option A: HTML Image Tag**
```html
<!-- In your web browser or HTML file -->
<img src="http://localhost:8069/stream/worker-detection?camera_id=cam_001&fps=10" 
     alt="Worker Detection Stream" 
     style="width: 100%; max-width: 800px;">
```

#### **Option B: Direct Browser URL**
```
http://localhost:8069/stream/worker-detection?camera_id=cam_001&fps=10
```
Replace `cam_001` with your actual camera ID.

#### **Option C: VLC Media Player**
```bash
vlc http://localhost:8069/stream/worker-detection?camera_id=cam_001&fps=10
```

**Stream Parameters:**
- `camera_id` (required): Camera ID to monitor
- `fps` (optional): Target FPS (1-30, default 10)

**Example URLs:**
```
# High-quality stream (30 FPS)
http://localhost:8069/stream/worker-detection?camera_id=cam_001&fps=30

# Low-bandwidth stream (5 FPS)
http://localhost:8069/stream/worker-detection?camera_id=cam_001&fps=5
```

---

### 3. **Firebase Database Updates** 🔥 PERSISTENT STORAGE

If `--update-firebase` flag is enabled, the worker updates Firebase in real-time.

**Database Structure:**
```
parkingLots/{parkingId}/cameras/{cameraId}/spaces/{spaceId}
  ├── occupied: true/false
  ├── lastUpdated: "2024-01-15T10:30:45Z"
  └── ... (other space properties)
```

**How to Check Firebase:**

#### **Option A: Firebase Console** (Web UI)
1. Go to https://console.firebase.google.com
2. Select your project
3. Navigate to **Firestore Database**
4. Browse to: `parkingLots > {your_parking_id} > cameras > {camera_id} > spaces`
5. Watch the `occupied` field change in real-time

#### **Option B: Firebase Admin SDK** (Python)
```python
from firebase_admin import firestore
import firebase_admin

# Initialize Firebase
cred = firebase_admin.credentials.Certificate('firebase_credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Watch a specific parking space
space_ref = db.collection('parkingLots').document('parking_001') \
             .collection('cameras').document('cam_001') \
             .collection('spaces').document('space_01')

# Get current status
space_data = space_ref.get().to_dict()
print(f"Space occupied: {space_data['occupied']}")

# Listen for changes (real-time)
def on_snapshot(doc_snapshot, changes, read_time):
    for doc in doc_snapshot:
        print(f"Space {doc.id}: {doc.to_dict()}")

space_ref.on_snapshot(on_snapshot)
```

**⚠️ Important Notes:**
- Firebase updates are **SLOW** (~300ms per camera)
- Enabling Firebase reduces FPS from **10 to ~0.3 FPS**
- Use `--update-firebase` flag only when persistence is needed
- For real-time monitoring, use **stream output** instead

---

### 4. **FastAPI Detection Broadcaster** 📡 INTERNAL SERVICE

The worker sends frames to FastAPI's `DetectionBroadcaster` service, which manages viewer connections.

**How to Check Viewer Count:**

The worker logs viewer activity:
```
📺 Camera cam_001 has 2 active viewers
📺 Starting worker detection stream: cam_001
📺 Worker detection stream closed: cam_001
```

**Broadcaster Endpoints (Internal):**
- `/api/worker/broadcast-frame` - Receives frames from worker (internal use)
- `/stream/worker-detection` - Serves MJPEG stream to viewers

---

## 🚀 Quick Verification Checklist

Follow these steps to verify your worker is running correctly:

### ✅ Step 1: Check Worker Process
```bash
# Check if worker is running
ps aux | grep parking_monitor_worker

# Expected output:
# user  12345  python parking_monitor_worker.py
```

### ✅ Step 2: View Console Logs
```bash
# Run worker in foreground
cd server
python parking_monitor_worker.py

# Expected output:
# 🚀 Starting parking monitor worker...
# ⏱️  Target FPS: 10 FPS per camera
# Found worker-enabled camera: ...
```

### ✅ Step 3: Open Detection Stream
Open in browser:
```
http://localhost:8069/stream/worker-detection?camera_id=YOUR_CAMERA_ID
```

**Expected Result:** Live video showing detection boxes and parking spaces

### ✅ Step 4: Check Firebase (if enabled)
1. Go to Firebase Console
2. Navigate to Firestore > parkingLots
3. Check if `occupied` field is updating

### ✅ Step 5: Monitor Performance
Check logs for:
- **Processing frequency:** Should process ~10 cameras per second (10 FPS)
- **Detection counts:** `🚗 Detected X vehicles in camera ...`
- **No errors:** Look for `❌ Error` or `⚠️ Warning` messages

---

## 📊 Expected Outputs Summary

| Output Type | Location | Update Frequency | Best For |
|------------|----------|------------------|----------|
| **Console Logs** | Terminal stdout | Real-time | Debugging, monitoring |
| **MJPEG Stream** | `http://localhost:8069/stream/worker-detection` | 10 FPS | Visual verification |
| **Firebase DB** | Firestore `parkingLots` collection | ~0.3 FPS (slow) | Persistence, history |
| **Broadcaster** | Internal FastAPI service | Real-time | Multi-viewer streaming |

---

## 🛠️ Running the Worker

### **Basic Usage:**
```bash
cd server
python parking_monitor_worker.py
```

### **With Custom FPS:**
```bash
python parking_monitor_worker.py --fps 15
```

### **With Firebase Updates (SLOW!):**
```bash
python parking_monitor_worker.py --update-firebase
```

### **With Debug Logging:**
```bash
python parking_monitor_worker.py --debug
```

### **Full Configuration:**
```bash
python parking_monitor_worker.py \
  --fps 10 \
  --detection-url http://localhost:8069 \
  --update-firebase \
  --debug
```

### **Command-Line Arguments:**
```
--interval FLOAT       Check interval in seconds (default: 0.1 for 10 FPS)
--fps INT             Target FPS per camera (default: 10)
--detection-url URL   FastAPI server URL (default: http://localhost:8069)
--update-firebase     Enable Firebase updates (reduces FPS to ~0.3)
--debug              Enable debug logging
```

---

## 📈 Performance Indicators

### **Healthy Worker:**
```
✅ Processing 10 cameras/second (10 FPS)
✅ Detecting vehicles consistently
✅ Sending frames to broadcaster
✅ No errors in logs
✅ Stream loads in browser
```

### **Problematic Worker:**
```
❌ "No active cameras found" (check Firebase camera settings)
❌ "Failed to fetch frame" (check ESP32/camera connection)
❌ FPS < 5 (check system resources or disable Firebase)
❌ "Error loading AI models" (check YOLO model files)
❌ Stream shows black/frozen frame (check camera URLs)
```

---

## 🔧 Troubleshooting

### **Problem: Worker starts but finds no cameras**

**Logs:**
```
⚠️ No active cameras found. Waiting...
```

**Solution:**
1. Check Firebase camera configuration
2. Ensure camera has `workerEnabled: true` field
3. Verify Firebase credentials in `firebase_credentials.json`

```python
# Check camera in Firebase
camera_ref = db.collection('parkingLots').document(parking_id) \
              .collection('cameras').document(camera_id)
camera_data = camera_ref.get().to_dict()
print(f"Worker enabled: {camera_data.get('workerEnabled', False)}")
```

---

### **Problem: Worker processes cameras but no detections**

**Logs:**
```
Processing camera: cam_001
🚗 Detected 0 vehicles in camera cam_001
```

**Solution:**
1. Check camera stream has visible vehicles
2. Verify YOLO model is loaded correctly
3. Check detection confidence threshold (default: 0.5)
4. Test with debug logging: `--debug`

---

### **Problem: Stream shows "No frames available"**

**Logs:**
```
⚠️ No frames available for camera cam_001
```

**Solution:**
1. Ensure worker is running
2. Check camera is being processed (look for "Processing camera: cam_001")
3. Verify broadcaster is receiving frames ("📺 Sent frame to FastAPI")
4. Check FastAPI server is running on port 8069

---

### **Problem: Very low FPS (< 1 FPS)**

**Possible Causes:**
- ✅ **Firebase updates enabled** (reduces to ~0.3 FPS)
- ✅ **High detection load** (too many vehicles)
- ✅ **Slow camera response** (ESP32 connection issues)
- ✅ **Insufficient system resources** (CPU/GPU overload)

**Solution:**
```bash
# Disable Firebase to test FPS
python parking_monitor_worker.py --fps 10  # Without --update-firebase

# Reduce target FPS
python parking_monitor_worker.py --fps 5

# Check system resources
htop  # or top
nvidia-smi  # if using GPU
```

---

## 📝 Example: Complete Monitoring Setup

### **Terminal 1: Run Worker with Logs**
```bash
cd server
python parking_monitor_worker.py --fps 10 --debug
```

### **Terminal 2: Monitor Logs (if background)**
```bash
tail -f logs/worker.log
# or
journalctl -u parking-worker -f
```

### **Browser 1: View Detection Stream**
```
http://localhost:8069/stream/worker-detection?camera_id=cam_001&fps=10
```

### **Browser 2: Firebase Console**
```
https://console.firebase.google.com/project/YOUR_PROJECT/firestore
```

---

## 🎯 Summary

**To verify the worker is working:**

1. **Check Logs:** Look for `🚀 Starting parking monitor worker...` and `Processing camera: ...`
2. **View Stream:** Open `http://localhost:8069/stream/worker-detection?camera_id=...` in browser
3. **Check Firebase:** See `occupied` field updating in Firestore (if enabled)
4. **Monitor Performance:** Should process ~10 FPS per camera without Firebase

**Primary Output Location:**
- **Real-time:** Console logs + MJPEG stream (`/stream/worker-detection`)
- **Persistent:** Firebase Firestore (only if `--update-firebase` flag is used)

**Best Practice:**
- Use **stream output** for monitoring and visualization
- Use **console logs** for debugging
- Use **Firebase** only when you need persistent storage (but expect slower FPS)

---

## 📚 Related Documentation

- **Worker Architecture:** `server/PARKING_MONITOR_WORKER.md`
- **Stream Switching:** `docs/STREAM_SWITCHING_FIX.md`
- **Worker Control:** `docs/WORKER_CONTROL.md`
- **Performance Tuning:** `docs/PERFORMANCE_TUNING.md`
- **FastAPI Setup:** `server/FASTAPI_SETUP.md`

---

**Last Updated:** 2024-01-15  
**File:** `parking_monitor_worker.py` (519 lines)  
**Stream Endpoint:** `routers/worker_detection_stream.py`
