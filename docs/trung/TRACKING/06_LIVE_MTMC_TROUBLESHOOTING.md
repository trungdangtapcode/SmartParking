# Live MTMC Tracking - Part 6: Troubleshooting

## Table of Contents
- [Part 1: Overview and Architecture](01_LIVE_MTMC_OVERVIEW.md)
- [Part 2: Installation and Setup](02_LIVE_MTMC_SETUP.md)
- [Part 3: Configuration Guide](03_LIVE_MTMC_CONFIG.md)
- [Part 4: Running the System](04_LIVE_MTMC_RUNNING.md)
- [Part 5: Code Reference](05_LIVE_MTMC_CODE_REFERENCE.md)
- [Part 6: Troubleshooting](06_LIVE_MTMC_TROUBLESHOOTING.md) ← **You are here**

---

## Common Issues and Solutions

### 1. Camera Not Starting

**Symptom**:
```
[ERROR] Camera cam_a: cannot open video datasets/parking_a.mp4
[ERROR] Camera cam_a exiting due to bad source
```

**Location**: `mtmc/run_live_mtmc.py` Lines 293-300

**Causes**:
1. Video file doesn't exist
2. Incorrect path
3. Corrupted video file
4. Unsupported codec

**Solutions**:

```bash
# Check file exists
ls -lh datasets/parking_a.mp4

# Test with ffplay
ffplay datasets/parking_a.mp4

# Check codec info
ffprobe datasets/parking_a.mp4

# Convert to compatible format if needed
ffmpeg -i input.mp4 -c:v libx264 -c:a aac output.mp4
```

**For RTSP streams**:
```bash
# Test RTSP connection
ffplay rtsp://192.168.1.100:554/stream1

# Check credentials
ffplay rtsp://username:password@192.168.1.100:554/stream1

# If timeout, check network/firewall
ping 192.168.1.100
telnet 192.168.1.100 554
```

### 2. CUDA Out of Memory

**Symptom**:
```
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB
```

**Location**: Any CUDA operation (detection, ReID, etc.)

**Solutions**:

**A. Reduce batch sizes**:

Edit `config/examples/live_parking.yaml`:
```yaml
MOT:
  REID_BATCHSIZE: 8  # Was 16 or 32
```

**B. Use smaller models**:
```yaml
MOT:
  REID_MODEL_OPTS: "models/mobilenetv4_small/opts.yaml"  # Instead of ResNet50
  DETECTOR: "yolov8n"  # Instead of yolov8s or yolov8m
```

**C. Reduce video resolution**:
```bash
# Resize videos to 720p
ffmpeg -i input.mp4 -vf scale=1280:720 output.mp4
```

**D. Free GPU memory**:
```bash
# Kill other processes using GPU
nvidia-smi
kill -9 <PID>

# Or restart
sudo systemctl restart nvidia-persistenced
```

### 3. Cameras Out of Sync

**Symptom**:
```
[WARNING] Camera cam_b: 5 ticks behind cam_a
[ERROR] MTMC: No matches found (temporal constraints violated)
```

**Location**: `mtmc/run_live_mtmc.py` VirtualClock

**Causes**:
- Processing time varies too much between cameras
- One camera much slower than others
- MAX_SKEW too small

**Solutions**:

**A. Increase MAX_SKEW**:
```yaml
LIVE:
  MAX_SKEW_TICKS: 2  # Was 1
```

**B. Lower FPS**:
```yaml
LIVE:
  TARGET_FPS: 5  # Was 8
```

**C. Balance camera loads**:
```yaml
EXPRESS:
  CAMERAS:
    - video: "cam_a.mp4"
      detector: "yolov8n"  # Lighter model for slow camera
    - video: "cam_b.mp4"
      detector: "yolov8s"  # Heavier model for fast camera
```

**D. Check per-camera processing times**:

Add logging in `LiveMOTWorker._process_frame()`:
```python
import time
start = time.time()
# ... processing ...
elapsed = time.time() - start
if elapsed > 0.2:  # More than 200ms
    log.warning(f"Cam {self.name}: Slow frame {elapsed*1000:.0f}ms")
```

### 4. No Global IDs Assigned

**Symptom**:
- Videos show `ID: -1` for all vehicles
- No MTMC matches

**Location**: `mtmc/run_live_mtmc.py` LiveMTMCAggregator

**Causes**:
1. CLUSTER_INTERVAL not reached yet
2. MIN_TRACK_FRAMES too high (filters out all tracks)
3. MIN_SIM too high (nothing matches)
4. Camera layout constraints too strict

**Solutions**:

**A. Wait longer**:
- Default CLUSTER_INTERVAL is 10 seconds
- First clustering happens after 10 seconds
- Check logs for `[INFO] MTMC: Clustered X tracks`

**B. Reduce MIN_TRACK_FRAMES**:
```yaml
LIVE:
  MIN_TRACK_FRAMES: 3  # Was 5 or 10
```

**C. Reduce MIN_SIM**:
```yaml
MTMC:
  MIN_SIM: 0.4  # Was 0.5
```

**D. Check camera layout**:

File: `config/examples/parking_camera_layout.txt`

```
# Make sure transitions are possible
# Example: If vehicles take 5-20 seconds to travel
0 1 3.0 25.0  # Was 5.0 15.0 (too strict)
```

**E. Force immediate clustering** (for testing):

Edit `mtmc/run_live_mtmc.py` Line 164:
```python
# Temporarily disable interval check
# if now - self._last_cluster_ts < self.cluster_interval:
#     return
```

### 5. MJPEG Stream Not Loading

**Symptom**:
- Browser shows "Cannot connect" or blank page
- `http://localhost:8080/` doesn't load

**Location**: `mtmc/run_live_mtmc.py` MJPEGBroadcaster

**Causes**:
1. Port already in use
2. Firewall blocking
3. Server not started
4. Wrong port number

**Solutions**:

**A. Check port in use**:
```bash
lsof -i :8080
# or
netstat -tulpn | grep 8080
```

**B. Kill process using port**:
```bash
kill -9 <PID>
```

**C. Change port**:
```yaml
LIVE:
  MJPEG_PORT: 8081  # Use different port
```

**D. Check firewall**:
```bash
# Ubuntu
sudo ufw allow 8080/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --reload
```

**E. Test with curl**:
```bash
curl -I http://localhost:8080/
# Should return HTTP/1.0 200 OK
```

**F. Access from remote machine**:
- Use server IP instead of localhost
- Example: `http://192.168.1.100:8080/`
- Make sure firewall allows external access

### 6. IDs Keep Changing

**Symptom**:
- Same vehicle gets different global IDs every few seconds
- IDs flicker between numbers

**Location**: `mtmc/run_live_mtmc.py` LiveMTMCAggregator

**Causes**:
- CLUSTER_INTERVAL too short
- MIN_SIM too low (wrong matches)
- Tracks too short (filtered out, then re-added with new ID)

**Solutions**:

**A. Increase cluster interval**:
```yaml
LIVE:
  CLUSTER_INTERVAL: 20.0  # Was 10.0 (more stable IDs)
```

**B. Increase MIN_SIM**:
```yaml
MTMC:
  MIN_SIM: 0.6  # Was 0.5 (stricter matching)
```

**C. Increase MIN_TRACK_FRAMES**:
```yaml
LIVE:
  MIN_TRACK_FRAMES: 10  # Was 5 (only confident tracks)
```

**D. Use better ReID model**:
```yaml
MOT:
  REID_MODEL_OPTS: "models/resnet50_mixstyle/opts.yaml"  # Better than MobileNet
```

### 7. High CPU Usage

**Symptom**:
- CPU at 100%
- System unresponsive
- Frame drops

**Location**: Various (detection, ReID, clustering)

**Solutions**:

**A. Lower FPS**:
```yaml
LIVE:
  TARGET_FPS: 5  # Was 8 or 10
```

**B. Reduce cameras**:
- Start with 2 cameras, add more if CPU allows

**C. Use GPU acceleration**:
```yaml
MOT:
  REID_ONNX: "models/resnet50_mixstyle/model.onnx"  # GPU accelerated
```

**D. Disable attributes**:
```yaml
MOT:
  STATIC_ATTRIBUTES: []  # Remove color/type classification
```

**E. Monitor per-component CPU**:
```bash
# Install if needed
pip install py-spy

# Profile running process
py-spy top --pid <PID>
```

### 8. Stream Lag/Delay

**Symptom**:
- Video in browser lags behind real-time
- 5-10 second delay

**Location**: MJPEG streaming, network

**Causes**:
- Network bandwidth
- Browser buffering
- High JPEG quality
- Too many clients

**Solutions**:

**A. Lower JPEG quality**:

Edit `mtmc/run_live_mtmc.py` Line 347:
```python
# Change from default quality (95)
ok, buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
```

**B. Reduce resolution**:

Resize before encoding:
```python
annotated = cv2.resize(annotated, (640, 480))  # Before imencode
```

**C. Use local network**:
- Avoid WiFi if possible
- Connect via Ethernet
- Use gigabit switches

**D. Limit concurrent viewers**:
- Each stream copy uses bandwidth
- Max 2-3 viewers per stream

### 9. Import Errors

**Symptom**:
```
ImportError: No module named 'yacs'
ModuleNotFoundError: No module named 'ultralytics'
```

**Solutions**:

```bash
# Activate environment
conda activate vehicle_mtmc

# Reinstall requirements
pip install -r requirements.txt

# Install missing packages
pip install ultralytics
pip install yacs

# Verify
python3 -c "import yacs; import ultralytics; print('OK')"
```

### 10. ONNX Runtime Errors

**Symptom**:
```
[ERROR] Failed to load ONNX model
ONNXRuntimeError: The parameter is incorrect
```

**Location**: `reid/onnx_feature_extractor.py`

**Solutions**:

**A. Check ONNX file exists**:
```bash
ls -lh models/resnet50_mixstyle/model.onnx
```

**B. Reinstall ONNX Runtime**:
```bash
pip uninstall onnxruntime onnxruntime-gpu
pip install onnxruntime-gpu==1.16.3
```

**C. Fallback to PyTorch**:
```yaml
MOT:
  REID_ONNX: ""  # Disable ONNX
  # Will use PyTorch model instead
```

**D. Regenerate ONNX**:
```bash
python3 reid/onnx_exporter.py \
  --opts models/resnet50_mixstyle/opts.yaml \
  --checkpoint models/resnet50_mixstyle/net_19.pth \
  --output models/resnet50_mixstyle/model.onnx
```

## Performance Tuning Guide

### Measure Current Performance

**Add timing logs**:

```python
# In LiveMOTWorker._process_frame()
import time

timings = {}
start = time.time()

# Detection
det_start = time.time()
res = self.detector(frame_bgr)
timings['detection'] = time.time() - det_start

# ReID
reid_start = time.time()
features = self.extractor(frame_rgb, boxes_tlwh)
timings['reid'] = time.time() - reid_start

# Tracking
track_start = time.time()
self.tracker.update(...)
timings['tracking'] = time.time() - track_start

# Clustering
cluster_start = time.time()
gid_map = self.aggregator.update(...)
timings['clustering'] = time.time() - cluster_start

total = time.time() - start
log.info(f"Cam {self.name}: det={timings['detection']*1000:.0f}ms, "
         f"reid={timings['reid']*1000:.0f}ms, "
         f"track={timings['tracking']*1000:.0f}ms, "
         f"total={total*1000:.0f}ms")
```

### Optimization Priority

Based on measured timings:

**If detection is slowest** (>100ms):
- Use lighter YOLO model
- Export to ONNX: `model.export(format='onnx')`
- Reduce input resolution

**If ReID is slowest** (>50ms):
- Use ONNX Runtime
- Use smaller model (MobileNet)
- Reduce batch size if OOM

**If clustering is slowest** (>200ms):
- Increase CLUSTER_INTERVAL
- Increase MIN_TRACK_FRAMES (fewer tracks)
- Reduce number of cameras

## Debug Mode

Enable detailed logging:

```bash
python3 mtmc/run_live_mtmc.py \
  --config examples/live_parking.yaml \
  --log-level DEBUG
```

**Debug output shows**:
- Frame-by-frame processing
- Detection counts
- Track associations
- Clustering decisions
- Timing information

## Getting Help

### Collect System Info

```bash
# Create debug report
cat > debug_report.txt << 'EOF'
=== System Info ===
OS: $(uname -a)
Python: $(python3 --version)
CUDA: $(nvidia-smi | head -5)

=== Package Versions ===
$(pip list | grep -E 'torch|opencv|yacs|ultralytics|onnx')

=== Config ===
$(cat config/examples/live_parking.yaml)

=== Recent Logs ===
$(tail -50 output/live_parking/run.log)
EOF
```

### Check GitHub Issues

Search existing issues: https://github.com/regob/vehicle_mtmc/issues

### Report New Issue

Include:
1. System info (OS, GPU, Python version)
2. Config file
3. Error message
4. Steps to reproduce
5. Expected vs actual behavior

---

**Previous**: [Part 5: Code Reference](05_LIVE_MTMC_CODE_REFERENCE.md)  
**Back to**: [Part 1: Overview](01_LIVE_MTMC_OVERVIEW.md)
