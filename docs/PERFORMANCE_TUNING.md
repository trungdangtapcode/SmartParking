# Performance Tuning Guide

## Quick Fix for Lag

If your system is laggy, click **⚡ Fast/Low CPU** preset in Detection Settings!

---

## Performance Presets

### 🚀 High Quality
- **Target FPS**: 15
- **Frame Skip**: 1 (process all frames)
- **Confidence**: 0.25
- **Best for**: Powerful systems, highest accuracy
- **CPU Usage**: ~100% per stream
- **Latency**: Low

### ⚖️ Balanced (Default)
- **Target FPS**: 10
- **Frame Skip**: 2 (process every 2nd frame)
- **Confidence**: 0.35
- **Best for**: Most systems, good balance
- **CPU Usage**: ~50% per stream
- **Latency**: Medium

### ⚡ Fast/Low CPU
- **Target FPS**: 5
- **Frame Skip**: 5 (process every 5th frame)
- **Confidence**: 0.5
- **Best for**: Slow systems, multiple streams
- **CPU Usage**: ~20% per stream
- **Latency**: Higher but acceptable

---

## How Frame Skipping Works

```
Without Skip (skip_frames=1):
Frame: 1  2  3  4  5  6  7  8  9  10
Detect: ✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅
Speed: Slowest, highest quality

With Skip=2 (every 2nd frame):
Frame: 1  2  3  4  5  6  7  8  9  10
Detect: ✅ ❌ ✅ ❌ ✅ ❌ ✅ ❌ ✅ ❌
Speed: 2x faster

With Skip=5 (every 5th frame):
Frame: 1  2  3  4  5  6  7  8  9  10
Detect: ✅ ❌ ❌ ❌ ❌ ✅ ❌ ❌ ❌ ❌
Speed: 5x faster
```

**Skipped frames use cached detection** from the last processed frame, so you still see smooth video with detection overlays!

---

## URL Parameters

### Manual Configuration

You can customize settings via URL:

```
# Default
http://localhost:8069/stream/detect

# High quality
http://localhost:8069/stream/detect?fps=15&skip_frames=1&conf=0.25

# Balanced
http://localhost:8069/stream/detect?fps=10&skip_frames=2&conf=0.35

# Fast/Low CPU
http://localhost:8069/stream/detect?fps=5&skip_frames=5&conf=0.5

# Maximum performance (if desperate)
http://localhost:8069/stream/detect?fps=3&skip_frames=10&conf=0.7
```

### Parameters:

- **fps** (1-30): Target frames per second
  - Lower = less CPU, smoother on slow systems
  - Higher = more responsive, needs more CPU

- **skip_frames** (1-10): Process every Nth frame
  - 1 = All frames (slowest, best quality)
  - 2 = Every 2nd frame (2x faster)
  - 5 = Every 5th frame (5x faster)
  - 10 = Every 10th frame (10x faster)

- **conf** (0.1-0.9): Detection confidence threshold
  - Lower = more detections (including false positives)
  - Higher = fewer detections (only confident ones)

- **show_labels** (true/false): Show class names and confidence scores

---

## Performance Impact

### CPU Usage Comparison

| Preset | FPS | Skip | CPU/Stream | 1 Stream | 3 Streams |
|--------|-----|------|------------|----------|-----------|
| High Quality | 15 | 1 | 100% | ✅ | ❌ |
| Balanced | 10 | 2 | 50% | ✅ | ✅ |
| Fast/Low CPU | 5 | 5 | 20% | ✅ | ✅ |
| Custom (3 FPS, skip 10) | 3 | 10 | 10% | ✅ | ✅ |

### Latency Comparison

| Preset | Latency | Detections/sec | Use Case |
|--------|---------|----------------|----------|
| High Quality | 50ms | 15 | Real-time tracking |
| Balanced | 100ms | 5 | General monitoring |
| Fast/Low CPU | 200ms | 1 | Background surveillance |

---

## Troubleshooting

### System Still Laggy?

Try these steps in order:

1. **Use Fast/Low CPU preset** ⚡
   - Click the preset button in Detection Settings

2. **Lower FPS further**
   - Advanced Settings → Target FPS → 3

3. **Increase frame skip**
   - Advanced Settings → Process Every → Every 10th frame

4. **Raise confidence threshold**
   - Confidence Threshold → 0.7

5. **Use Raw Stream instead**
   - Switch to "Raw Stream" mode (no detection)

### Multiple Streams Causing Lag?

- Use **Balanced** or **Fast/Low CPU** for all streams
- Or keep 1 stream on High Quality, others on Fast/Low CPU
- Close unused streams

### SSH Still Disconnecting?

```bash
# Check CPU usage
top

# If Python using >200% CPU:
# 1. Close all browser tabs with streams
# 2. Restart backend:
pkill -f main_fastapi
cd server && python main_fastapi.py

# 3. Reopen with Fast/Low CPU preset
```

### Backend Not Stopping After Tab Close?

Check backend logs. Should see:
```
🔌 Client disconnected after XX processed frames
```

If not seeing disconnect messages:
1. Make sure you're using latest code
2. Try hard refresh: Ctrl+Shift+R
3. Clear browser cache
4. Restart backend server

---

## Advanced Optimizations

### For Multiple Concurrent Users:

```python
# In main_fastapi.py
# Set default to lower performance
fps: int = Query(5, description="Target FPS")  # Was: 10
skip_frames: int = Query(5, description="Process every Nth frame")  # Was: 2
```

### For Powerful GPU Servers:

```python
# Enable batch processing (future feature)
# Process multiple frames in one YOLO call
results = ai_service.yolo_model(
    [frame1, frame2, frame3],  # Batch of frames
    conf=conf,
    device='cuda',
    half=True  # FP16 for 2x speed
)
```

### For Resource-Limited Systems:

Use a smaller YOLO model:
```bash
# In server directory
# Download smaller model
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt

# Edit ai_service.py to use yolov8n (nano) instead of yolov8s (small)
```

---

## Monitoring Performance

### Watch Backend Logs:

```
✅ Detection started (processing every 2 frames)
📹 Processed 50 frames (skipped 50)
📹 Processed 100 frames (skipped 100)
🔌 Client disconnected after 150 processed frames
```

- **processed frames**: Frames that ran YOLO detection
- **skipped frames**: Frames that used cached detection
- Total frames = processed + skipped

### Monitor System Resources:

```bash
# Terminal 1: Backend
cd server && python main_fastapi.py

# Terminal 2: Monitor
cd server && python monitor_streams.py

# Watch for:
# - CPU should be <80%
# - RAM should be stable
# - Connections should match browser tabs
```

---

## Summary

**Default Settings (Balanced):**
- ✅ Works for most systems
- ✅ 10 FPS, skip every 2nd frame
- ✅ ~50% CPU per stream

**If Laggy:**
- ⚡ Use Fast/Low CPU preset
- ⚡ 5 FPS, skip every 5th frame
- ⚡ ~20% CPU per stream

**If Need Quality:**
- 🚀 Use High Quality preset
- 🚀 15 FPS, process all frames
- 🚀 ~100% CPU per stream

**Remember:**
- Skipped frames still show detection (from cache)
- Lower FPS = less CPU but still smooth
- Higher confidence = fewer false positives
