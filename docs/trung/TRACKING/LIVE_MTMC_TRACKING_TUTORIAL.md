# Live MTMC Tracking - Complete Tutorial

**Complete documentation for real-time multi-camera vehicle tracking system**

---

## Documentation Structure

This tutorial is split into 6 parts to provide comprehensive coverage without hitting length limits:

### 📚 [Part 1: Overview and Architecture](01_LIVE_MTMC_OVERVIEW.md)
- What is Live MTMC?
- System architecture and components
- VirtualClock synchronization
- LiveMOTWorker, LiveMTMCAggregator, MJPEGBroadcaster
- Data flow and pipeline
- Comparison with batch processing

### ⚙️ [Part 2: Installation and Setup](02_LIVE_MTMC_SETUP.md)
- Hardware and software requirements
- Step-by-step installation guide
- Virtual environment setup
- Model downloads
- Configuration file setup
- Directory structure
- Quick test run

### 🔧 [Part 3: Configuration Guide](03_LIVE_MTMC_CONFIG.md)
- Configuration system overview
- SYSTEM, MOT, MTMC, EXPRESS, LIVE sections
- ReID models and detectors
- Camera layout files
- Performance tuning parameters
- Complete example configs
- Configuration validation

### 🚀 [Part 4: Running the System](04_LIVE_MTMC_RUNNING.md)
- Starting Live MTMC (3 methods)
- Startup sequence explained
- Viewing streams (browser, VLC, FFmpeg)
- HTML embed examples
- Monitoring and logging
- Stopping the system
- Integration examples (REST API, WebSocket, Database)

### 📖 [Part 5: Code Reference](05_LIVE_MTMC_CODE_REFERENCE.md)
- Complete code walkthrough
- VirtualClock class (lines 57-133)
- LiveMTMCAggregator class (lines 136-210)
- MJPEGBroadcaster class (lines 213-269)
- LiveMOTWorker class (lines 272-402)
- run_live() function (lines 405-455)
- Method signatures and usage

### 🔍 [Part 6: Troubleshooting](06_LIVE_MTMC_TROUBLESHOOTING.md)
- Common issues and solutions
- Camera not starting
- CUDA out of memory
- Cameras out of sync
- No global IDs assigned
- MJPEG stream issues
- Performance tuning guide
- Debug mode

---

## Quick Start

If you're already familiar with the system:

```bash
# 1. Activate environment
conda activate vehicle_mtmc

# 2. Navigate to directory
cd /mnt/mmlab2024nas/vund/.svn/bin/vehicle_mtmc

# 3. Set PYTHONPATH
export PYTHONPATH=$(pwd)

# 4. Run system
python3 mtmc/run_live_mtmc.py --config examples/live_parking.yaml

# 5. View streams
# Open browser: http://localhost:8080/
```

---

## Key Files Reference

| File | Location | Purpose |
|------|----------|---------|
| **Main script** | `mtmc/run_live_mtmc.py` | Live MTMC implementation (475 lines) |
| **Config defaults** | `config/defaults.py` | All default values and schema |
| **Example config** | `config/examples/live_parking.yaml` | Sample live configuration |
| **Camera layout** | `config/examples/parking_camera_layout.txt` | Temporal constraints |
| **Clustering** | `mtmc/mtmc_clustering.py` | Hierarchical clustering algorithm |
| **Tracker** | `mot/tracker.py` | ByteTrack/DeepSORT implementations |
| **Detector** | `detection/load_detector.py` | YOLO loading |
| **ReID** | `reid/feature_extractor.py` | Feature extraction |

---

## System Requirements

**Minimum**:
- 4-core CPU, 8GB RAM
- NVIDIA GPU 4GB VRAM
- Python 3.10
- CUDA 11.0+

**Recommended** (3+ cameras):
- 8-core CPU, 16GB RAM
- NVIDIA GPU 8GB VRAM (RTX 3060+)
- Python 3.10
- CUDA 11.7+

---

## Feature Overview

✅ **Real-time processing** - Process multiple camera streams simultaneously  
✅ **Global ID tracking** - Same vehicle ID across all cameras  
✅ **MJPEG streaming** - View live annotated video in browser  
✅ **Frame synchronization** - VirtualClock keeps cameras in sync  
✅ **Periodic clustering** - MTMC runs every N seconds  
✅ **Configurable** - Extensive YAML configuration  
✅ **GPU accelerated** - ONNX/TensorRT support  
✅ **RTSP support** - Live camera streams or video files  

---

## Workflow Diagram

```
Start
  │
  ├─→ Load Config (Part 3)
  │
  ├─→ Load Models (ReID, YOLO)
  │
  ├─→ Start VirtualClock
  │
  ├─→ Start MJPEG Server (Port 8080)
  │
  ├─→ Create Worker Threads (1 per camera)
  │     │
  │     ├─→ Camera A Worker
  │     │     ├─ Wait for tick
  │     │     ├─ Read frame
  │     │     ├─ Detect (YOLO)
  │     │     ├─ Track (ByteTrack)
  │     │     ├─ Extract features (ReID)
  │     │     ├─ Update aggregator
  │     │     ├─ Get global IDs
  │     │     ├─ Annotate frame
  │     │     └─ Stream MJPEG
  │     │
  │     ├─→ Camera B Worker (same)
  │     └─→ Camera C Worker (same)
  │
  ├─→ LiveMTMCAggregator (background)
  │     ├─ Collect tracks from all cameras
  │     ├─ Run clustering (every N seconds)
  │     └─ Assign global IDs
  │
  └─→ User views streams in browser
        http://localhost:8080/
```

---

## Configuration Example

**Minimal config** (`config/examples/live_parking.yaml`):

```yaml
OUTPUT_DIR: "output/live_parking"

MOT:
  REID_MODEL_OPTS: "models/resnet50_mixstyle/opts.yaml"
  REID_MODEL_CKPT: "models/resnet50_mixstyle/net_19.pth"
  REID_ONNX: "models/resnet50_mixstyle/model.onnx"
  DETECTOR: "yolov8s"
  TRACKER: "bytetrack_iou"

MTMC:
  CAMERA_LAYOUT: 'config/examples/parking_camera_layout.txt'
  MIN_SIM: 0.5

EXPRESS:
  CAMERAS:
    - video: "datasets/parking_a.mp4"
      name: "cam_a"
    - video: "datasets/parking_b.mp4"
      name: "cam_b"
    - video: "datasets/parking_c.mp4"
      name: "cam_c"

LIVE:
  TARGET_FPS: 8
  MJPEG_PORT: 8080
  CLUSTER_INTERVAL: 10.0
```

See **Part 3** for complete configuration reference.

---

## Performance Tips

1. **Lower FPS** for less CPU: `TARGET_FPS: 5`
2. **Use ONNX** for 2-3x speedup: `REID_ONNX: "model.onnx"`
3. **Smaller models** for speed: `DETECTOR: "yolov8n"`
4. **Increase cluster interval** for stability: `CLUSTER_INTERVAL: 15.0`
5. **Reduce batch size** if OOM: `REID_BATCHSIZE: 8`

See **Part 6** for complete tuning guide.

---

## Support

- **GitHub Issues**: https://github.com/regob/vehicle_mtmc/issues
- **Original Paper**: [Multi-Camera Trajectory Matching](https://doi.org/10.1007/s11042-023-17397-0)
- **Documentation**: This tutorial

---

## License

MIT License - See `vehicle_mtmc/LICENSE.md`

---

**Start reading**: [Part 1: Overview and Architecture](01_LIVE_MTMC_OVERVIEW.md)
