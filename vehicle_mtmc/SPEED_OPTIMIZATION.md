# Speed Optimization Guide

## ONNX Runtime Acceleration (2-3x faster ReID)

### 1. Install ONNX Runtime GPU
```bash
conda activate vehicle_mtmc
pip install onnxruntime-gpu onnx
```

### 2. Export MobileNetV4 to ONNX
```bash
python3 reid/onnx_exporter.py \
  --opts models/mobilenetv4_small/opts.yaml \
  --checkpoint null \
  --output models/mobilenetv4_small/model.onnx
```

### 3. Enable ONNX in config
Edit `config/examples/express_parking.yaml`:
```yaml
MOT:
  REID_ONNX: "models/mobilenetv4_small/model.onnx"  # Add this line
  REID_MODEL_OPTS: "models/mobilenetv4_small/opts.yaml"
  REID_FP16: true
  REID_BATCHSIZE: 32
```

### 4. Run with ONNX
```bash
bash ./run.sh
```

---

## YOLOv8 TensorRT (for detection acceleration)

### 1. Export YOLO to TensorRT
```bash
conda activate vehicle_mtmc
python3 -c "
from ultralytics import YOLO
model = YOLO('yolov8s_car_custom.pt')
model.export(format='engine', half=True)  # Creates .engine file
"
```

### 2. Use TensorRT engine
Edit config:
```yaml
MOT:
  DETECTOR: "yolov8s_car_custom.engine"  # Use .engine instead of .pt
```

---

## Current Optimizations (Already Applied)

✓ **MobileNetV4** - Smallest model (2M params)  
✓ **FP16** - Half precision inference  
✓ **Batch size 32** - Better GPU utilization  
✓ **ByteTrack IOU** - Fast tracker without deep ReID  
✓ **No attributes** - Disabled color/type classification  

---

## Expected Speedups

| Optimization | Speedup |
|-------------|---------|
| MobileNetV4 vs ResNet50 | 3-5x |
| ONNX Runtime | 2-3x |
| FP16 | 1.5-2x |
| YOLO TensorRT | 2-3x |
| **Combined** | **10-30x total** |

---

## Troubleshooting

**ONNX export fails:**
```bash
pip install --upgrade torch onnx onnxruntime-gpu
```

**TensorRT not available:**
- TensorRT requires NVIDIA GPU with CUDA
- Install from: https://developer.nvidia.com/tensorrt

**Out of memory:**
- Reduce `REID_BATCHSIZE` to 16 or 8
- Use `REID_FP16: true`
