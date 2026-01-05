# License Plate Recognition Integration - Summary

## What Was Added

I've integrated license plate recognition (ALPR) into your multi-camera tracking system with the following features:

### 1. **Per-Camera ALPR Configuration**
- Camera A (entrance) now performs license plate OCR on detected vehicles
- Cameras B and C do not run OCR (for performance)
- Plates detected at the entrance are propagated across all cameras via MTMC

### 2. **Key Features**
- ✅ Plates are displayed **on top** of track IDs in video output
- ✅ Plates are detected only at camera A (entrance) to optimize performance
- ✅ Once detected, plates are propagated to the same vehicle in other cameras via MTMC matching
- ✅ Vehicles without plates show only the ID (no "null" displayed)
- ✅ First detected plate is kept (subsequent detections don't override)

### 3. **Files Modified**

**Core Tracking:**
- `mot/tracklet.py` - Added `plate` attribute to Tracklet class
- `mot/tracker.py` - Updated trackers to accept and propagate plate info
- `mot/run_tracker.py` - Integrated ALPR into tracking pipeline

**Multi-Camera:**
- `mtmc/multicam_tracklet.py` - Propagate plates across cameras

**Visualization:**
- `mot/video_output.py` - Display plates above track IDs

**Configuration:**
- `config/defaults.py` - Added `ENABLE_ALPR` config option
- `config/verify_config.py` - Allow `enable_alpr` per camera
- `config/config_tools.py` - Handle ALPR config field
- `config/examples/express_parking.yaml` - Enabled ALPR for camera A

**New File:**
- `mot/plate_recognition.py` - ALPR wrapper class

### 4. **Usage**

Your current config in `express_parking.yaml`:

```yaml
EXPRESS:
  CAMERAS:
    - "video": "datasets/parking_a_30sec.mp4"
      "detector": "yolov8s"
      "tracked_classes": [1, 2, 3, 5, 7]
      "enable_alpr": true  # ← OCR enabled for entrance camera
    - "video": "datasets/parking_b_30sec.mp4"
      "detector": "yolov8s_car_custom.pt"
      "tracked_classes": [0]
    - "video": "datasets/parking_c_30sec.mp4"
      "detector": "yolov8s_car_custom.pt"
      "tracked_classes": [0]
```

### 5. **How It Works**

1. **Camera A Detection**: When a car enters, ALPR detects its license plate
2. **Plate Storage**: Plate text is stored in the tracklet
3. **MTMC Matching**: When MTMC runs, it matches vehicles across cameras using ReID features
4. **Plate Propagation**: The plate from Camera A is copied to the same vehicle in Cameras B & C
5. **Video Output**: All videos show both Track ID and Plate number

### 6. **Installation**

Make sure you have the fast_alpr package installed:

```bash
pip install fast-alpr
```

If not installed, the system will continue to work but plates won't be detected (logged as warning).

### 7. **Run MTMC**

```bash
python3 mtmc/run_express_mtmc.py --config config/examples/express_parking.yaml
```

### 8. **Output**

Check the final videos in:
- `output/parking_mtmc/0_parking_a_30sec/mtmc.mp4`
- `output/parking_mtmc/1_parking_b_30sec/mtmc.mp4`
- `output/parking_mtmc/2_parking_c_30sec/mtmc.mp4`

Each video will show:
```
Plate: ABC123
ID: 5
Color: white
Type: car
```

For vehicles without detected plates, only the ID and attributes are shown.
