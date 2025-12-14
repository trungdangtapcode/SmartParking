# 🎯 Multi-Camera Tracking Testing Guide

Hướng dẫn test tính năng tracking real-time cho SmartParking system.

---

## ✅ Prerequisites Checklist

### Backend
- [ ] Python environment activated
- [ ] Dependencies installed: `pip install -r server/requirements.txt`
- [ ] YOLO model exists: `server/yolov8s_car_custom.pt`
- [ ] Video files exist in `server/stream/`:
  - `parking_a.mp4` (~166MB)
  - `parking_b.mp4` (~166MB)
  - `parking_c.mp4` (~164MB)

### Frontend
- [ ] Node modules installed: `cd frontend && npm install`
- [ ] Frontend running: `npm run dev` (port 5173)

---

## 🚀 Quick Start Test

### Step 1: Start Backend

```bash
cd server
# Activate environment first if using conda/venv
python main_fastapi.py
```

**Expected output:**
```
🚀 Starting FastAPI SmartParking Server...
📦 Loading AI models...
✅ Using custom trained model: F:\...\yolov8s_car_custom.pt
✅ YOLO model loaded successfully
🔥 Initializing Firebase Admin SDK...
✅ Firebase initialized
🎯 Initializing Tracking Manager...
✅ Tracking Manager initialized
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Start Frontend

```bash
cd frontend
npm run dev
```

### Step 3: Access Multi-Camera Viewer

Open browser: `http://localhost:5173/stream/multi`

---

## 📋 Test Scenarios

### Test 1: Basic Streaming (No Tracking)

**Goal:** Verify video streaming works

1. Click "➕ Thêm Stream Mới"
2. Select "Video File" → "Video 2 - Parking B"
3. Enter Camera ID: `CAM_B`
4. **KHÔNG check** "Sử dụng camera này cho Check-in"
5. Click "➕ Thêm Stream"
6. Click "▶️ START ALL STREAMS"

**Expected Result:**
- ✅ Video stream appears (without tracking annotations)
- ✅ Status shows "🟢 Live"
- ✅ No tracking controls visible (not enabled yet)

---

### Test 2: Single Camera Tracking

**Goal:** Test tracking on 1 camera

1. Continue from Test 1 (stream already running)
2. In the camera tile, find "🎯 Enable Tracking" toggle
3. Check the toggle ✅

**Expected Result:**
- ✅ Stream URL changes to include `&tracking=true&camera_id=CAM_B`
- ✅ "TRACKING" badge appears (purple, animated)
- ✅ After ~1-2 seconds, bounding boxes appear on vehicles
- ✅ Each vehicle has:
  - Colored bounding box
  - Track ID (e.g., "ID:1 car 0.95")
- ✅ Statistics appear below toggle:
  - FPS: ~20-30
  - Objects: number of vehicles detected
  - Unique: number of unique track IDs
  - Latency: ~50-100ms

**Backend Console Output:**
```
📹 Producer started: 1920x1080 @ 25fps
🎯 Consumer started for CAM_B
ℹ️  Custom model detected (1 class): detecting all classes
🎯 Started tracking for CAM_B with video: parking_b.mp4
📊 CAM_B: FPS=24.5, Objects=3, Unique=3
```

---

### Test 3: Multi-Camera Tracking (2 cameras)

**Goal:** Test tracking on 2 cameras simultaneously

1. Add another stream:
   - Video File → "Video 3 - Parking C"
   - Camera ID: `CAM_C`
   - **KHÔNG check** check-in camera
2. Click "➕ Thêm Stream"
3. Enable tracking for CAM_C (check the toggle)
4. Wait 2-3 seconds

**Expected Result:**
- ✅ Both cameras show tracking annotations
- ✅ Both cameras have separate statistics
- ✅ Track IDs are independent per camera (CAM_B: ID 1,2,3; CAM_C: ID 1,2,3)
- ✅ No lag or stutter in either stream
- ✅ FPS remains stable (~20-30 for each)

**Performance Metrics:**
- CPU usage: ~40-60% (on modern CPU)
- Memory: ~2-3GB
- Latency: <100ms per camera

---

### Test 4: Check-in Camera (No Tracking)

**Goal:** Verify check-in cameras don't show tracking toggle

1. Add new stream:
   - Video File → "Video 1 - Parking A"
   - Camera ID: `CAM_A`
   - **✅ CHECK** "Sử dụng camera này cho Check-in"
2. Click "➕ Thêm Stream"

**Expected Result:**
- ✅ Check-in section appears (Test Capture, Check-in buttons)
- ❌ **NO tracking toggle** (because it's check-in camera)
- ✅ Can perform check-in operations normally

---

### Test 5: Start/Stop Tracking

**Goal:** Test tracking lifecycle

1. With CAM_B tracking enabled, uncheck "🎯 Enable Tracking"

**Expected Result:**
- ✅ Stream switches back to raw video (no annotations)
- ✅ Statistics disappear
- ✅ Backend logs: "🛑 Stopping TrackingProcessor for CAM_B..."

2. Re-enable tracking (check toggle again)

**Expected Result:**
- ✅ Tracking restarts
- ✅ New track IDs assigned (may be different from before)
- ✅ Statistics reappear

---

### Test 6: Stop All Streams

**Goal:** Test cleanup

1. Click "⏹ STOP" button
2. Wait 2 seconds

**Expected Result:**
- ✅ All streams stop
- ✅ Backend logs: "🛑 Stopping TrackingProcessor for ..."
- ✅ Tracking processors cleanup properly

---

## 🔍 API Testing (Advanced)

### Get Tracking Stats

```bash
# Stats for specific camera
curl http://localhost:8000/api/tracking/stats?camera_id=CAM_B

# Stats for all cameras
curl http://localhost:8000/api/tracking/stats
```

**Expected Response:**
```json
{
  "success": true,
  "camera_id": "CAM_B",
  "stats": {
    "fps": 24.5,
    "objects_tracked": 3,
    "unique_tracks_count": 5,
    "latency_ms": 85.2,
    "frames_processed": 245,
    "frames_dropped": 0
  }
}
```

### Manual Start/Stop Tracking

```bash
# Start tracking
curl -X POST http://localhost:8000/api/tracking/start \
  -H "Content-Type: application/json" \
  -d '{"camera_id": "CAM_TEST", "video_file": "parking_b.mp4"}'

# Stop tracking
curl -X POST http://localhost:8000/api/tracking/stop \
  -H "Content-Type: application/json" \
  -d '{"camera_id": "CAM_TEST"}'
```

---

## 🐛 Troubleshooting

### Issue: "Video file not found"

**Solution:**
- Verify files exist: `dir server\stream\parking_*.mp4`
- Check file names match exactly

### Issue: "YOLO model not loaded"

**Solution:**
- Check model exists: `dir server\yolov8s_car_custom.pt`
- Restart backend server

### Issue: Tracking very slow (FPS < 10)

**Possible Solutions:**

**Option 1: Reduce resolution**
Edit `main_fastapi.py` line ~360:
```python
tracking_manager.start_tracking(
    ...
    resize_width=640,  # Add this (was None)
    ...
)
```

**Option 2: Increase frame skip**
```python
frame_skip=2,  # Process every 2nd frame (was 1)
```

**Option 3: Use OpenVINO model**
Check if `server/yolov8s_car_custom_openvino_model/` exists.
If yes, modify AI service to use it.

### Issue: No tracking annotations appear

**Check:**
1. Backend console for errors
2. Camera ID is set correctly
3. Video is actually streaming (not stuck)
4. Try refreshing browser

### Issue: Statistics not updating

**Check:**
1. Browser console for errors (F12)
2. API endpoint working: `curl http://localhost:8000/api/tracking/stats?camera_id=CAM_B`
3. Camera ID matches exactly

---

## 📊 Performance Benchmarks

### Expected Performance (Intel i5/i7 or Ryzen 5/7)

| Scenario | FPS | CPU % | Memory | Latency |
|----------|-----|-------|--------|---------|
| 1 camera, 1920x1080, no resize | 20-25 | 30-40% | 1.5GB | 60-80ms |
| 1 camera, 1920x1080, resize 640 | 28-30 | 20-30% | 1.2GB | 40-60ms |
| 2 cameras, 1920x1080, no resize | 18-22 | 50-70% | 2.5GB | 80-100ms |
| 2 cameras, 1920x1080, resize 640 | 25-28 | 35-50% | 2.0GB | 50-70ms |

### Optimization Tips

**For better FPS:**
- Use `resize_width=640` or `resize_width=854`
- Use `frame_skip=2` (process every 2nd frame)
- Use OpenVINO model if available

**For better accuracy:**
- Use full resolution (`resize_width=None`)
- Use `frame_skip=1` (all frames)
- Keep default confidence threshold (0.25)

---

## ✅ Success Criteria

All tests passed if:
- ✅ Can stream 2 cameras simultaneously
- ✅ Can enable/disable tracking on each camera independently
- ✅ Check-in cameras don't show tracking toggle
- ✅ Tracking annotations appear correctly (bounding boxes + IDs)
- ✅ Statistics update in real-time
- ✅ FPS ≥ 20 for single camera
- ✅ FPS ≥ 15 for 2 cameras
- ✅ No memory leaks after 5 minutes
- ✅ Can stop/restart streams without errors

---

## 📝 Next Steps

After successful testing:
1. Adjust performance settings if needed
2. Test with real ESP32-CAM (if available)
3. Deploy to production environment
4. Monitor performance metrics

---

**Happy Testing! 🎉**
