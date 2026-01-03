# SmartParking Backend Requirements

## ✅ Single Source of Truth

**Use only:** `requirements.txt`

This file contains ALL dependencies needed for the SmartParking backend with GPU support.

## 📦 What's Included

### Web Framework
- FastAPI (REST API)
- Uvicorn (ASGI server)
- aiohttp (ESP32 proxy)
- WebSockets support

### AI/Computer Vision
- YOLOv8 (object detection)
- ByteTrack (object tracking, built into ultralytics)
- fast-alpr (license plate recognition)
- OpenCV (image processing)

### GPU Support
- PyTorch with CUDA
- TorchVision
- Automatically uses GPU if available

### Backend Services
- Firebase Admin SDK
- python-dotenv (environment variables)

## 🚀 Installation

### Step 1: Activate Environment
```bash
conda activate scheduler
```

### Step 2: Install Requirements
```bash
cd server
pip install -r requirements.txt
```

### Step 3: Verify Installation
```bash
python verify_requirements.py
```

Expected output:
```
✅ All requirements installed with GPU support!
   GPU available: NVIDIA GeForce RTX 3090
   CUDA version: 12.1
```

## 🎮 GPU Requirements

For GPU acceleration, you need:

1. **NVIDIA GPU** (GTX 1060 or better)
2. **NVIDIA Drivers** (latest)
3. **CUDA Toolkit** (11.8 or 12.1)
4. **cuDNN** (compatible with CUDA version)

### Check GPU Status
```bash
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

### Expected Output
```
CUDA available: True
```

## 🔧 Troubleshooting

### Issue: "No module named 'fastapi'"
**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: "CUDA not available"
**Solution:**
1. Check NVIDIA drivers: `nvidia-smi`
2. Install CUDA toolkit
3. Reinstall PyTorch: `pip install torch torchvision --force-reinstall`

### Issue: "ImportError: DLL load failed" (Windows)
**Solution:**
1. Install Visual C++ Redistributable
2. Download: https://aka.ms/vs/17/release/vc_redist.x64.exe

### Issue: Package conflicts
**Solution:**
```bash
# Remove all packages
pip freeze | xargs pip uninstall -y

# Clean install
pip install -r requirements.txt
```

## 📝 Version Compatibility

| Package | Version | Notes |
|---------|---------|-------|
| Python | 3.10+ | Required |
| FastAPI | >=0.104.1 | Latest stable |
| PyTorch | >=2.0.0 | Auto-detects CUDA |
| Ultralytics | >=8.0.0 | Includes YOLOv8 + ByteTrack |
| OpenCV | >=4.8.0 | Latest |
| NumPy | >=2.0.0, <2.3.0 | Compatible range |

## ⚠️ Important Notes

1. **Do NOT use `requirements_fastapi.txt`** - it has been removed
2. **Only use `requirements.txt`** for all installations
3. **GPU support is automatic** - PyTorch will detect CUDA if available
4. **No manual CUDA installation needed** - pip handles it

## 🧪 Testing

After installation, test the backend:

```bash
# Start backend
python main_fastapi.py

# Expected output:
# 🚀 Starting FastAPI SmartParking Server...
# 📦 Loading AI models...
# 🎮 Using device: cuda
# ✅ AI models loaded successfully
# ✅ Firebase initialized
# ✅ ESP32 connected: http://localhost:5069
```

## 📚 Related Files

- `requirements.txt` - **USE THIS** (single source of truth)
- `environment.yml` - Conda environment (alternative)
- `verify_requirements.py` - Verification script

## 🔄 Updates

When adding new dependencies:

1. Add to `requirements.txt` only
2. Test installation in clean environment
3. Update this README if needed
4. Commit changes

## 💡 Tips

- Use virtual environment (conda or venv)
- Keep dependencies minimal
- Pin major versions only (allow minor updates)
- Test on both GPU and CPU systems
- Document any special requirements

---

**Last Updated:** January 3, 2026
**Maintainer:** SmartParking Team
