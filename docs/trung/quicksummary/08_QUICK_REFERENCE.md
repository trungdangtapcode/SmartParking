# Smart Parking System - Quick Reference Guide

## 📋 Project at a Glance

### What is This Project?

A **complete AI-powered parking management system** that uses computer vision to:
- Monitor multiple parking cameras in real-time
- Detect and track vehicles automatically
- Recognize license plates
- Manage parking space occupancy
- Provide web-based dashboard for monitoring

### Tech Stack Summary

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS |
| **Backend** | FastAPI (Python), AsyncIO, Uvicorn |
| **AI/ML** | YOLOv8, ByteTrack, Fast-ALPR, PyTorch, CUDA |
| **Database** | Firebase/Firestore (NoSQL) |
| **Streaming** | MJPEG, WebSocket, HTTP |
| **Hardware** | ESP32-CAM (IoT Camera) |
| **Environment** | Conda, npm |

### Key Numbers

- **19** Frontend pages
- **12** API router modules
- **7** Core services
- **651** lines in AI service
- **898** lines in worker process
- **10-30** FPS processing speed
- **100-200ms** end-to-end latency

---

## 🗺️ System Map

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACES                          │
│  - Detection Viewer   - Worker Monitor   - Space Editor    │
│  - History Pages      - Analytics        - Admin Dashboard │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND SERVICES                         │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐       │
│  │  FastAPI    │  │   Worker    │  │   Firebase   │       │
│  │  Server     │  │   Process   │  │   Service    │       │
│  └─────────────┘  └─────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                    AI PROCESSING                            │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐ │
│  │  YOLO    │  │ ByteTrack │  │   ALPR   │  │   IoU    │ │
│  │Detection │  │ Tracking  │  │  Plates  │  │ Matching │ │
│  └──────────┘  └───────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                  VIDEO SOURCES & DATA                       │
│  ESP32-CAM Cameras (Real/Mock)  +  Firestore Database      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start Commands

### First-Time Setup

```bash
# 1. Clone repository
git clone <repo-url> && cd SmartParking

# 2. Backend setup
cd server
conda env create -f environment.yml
conda activate scheduler
pip install -r requirements.txt

# 3. Frontend setup
cd ../frontend
npm install

# 4. Configure Firebase
# - Download firebase_credentials.json
# - Place in server/ directory
# - Update frontend/.env with Firebase config

# 5. Start ESP32 mock (development)
cd ../ESP32
python start_mock.py --port 5069
```

### Running the System (3 Terminals)

```bash
# Terminal 1: Backend
cd server && conda activate scheduler
python main_fastapi.py
# → http://localhost:8069

# Terminal 2: Worker
cd server && conda activate scheduler
python parking_monitor_worker.py --fps 10

# Terminal 3: Frontend
cd frontend
npm run dev
# → http://localhost:5169
```

### Quick Tests

```bash
# Test CUDA
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"

# Test ESP32 connection
curl http://localhost:5069/stream

# Test backend health
curl http://localhost:8069/health

# Test frontend
curl http://localhost:5169
```

---

## 📁 Important Files Reference

### Configuration Files

```
server/
├── .env                           # Backend environment vars
├── environment.yml                # Conda environment
├── requirements.txt               # Python packages
├── firebase_credentials.json      # Firebase admin key
└── config/
    └── tracking_config.yaml       # ByteTrack settings

frontend/
└── .env                           # Frontend environment vars
    VITE_FIREBASE_API_KEY=...
    VITE_API_BASE_URL=...

ESP32/
├── config_template.h              # Hardware config
└── esp32_cam_firmware.ino         # Firmware code
```

### Core Source Files

```
server/
├── main_fastapi.py                # Application entry
├── parking_monitor_worker.py      # Worker process
├── services/
│   ├── ai_service.py              # AI models
│   ├── firebase_service.py        # Database
│   └── parking_space_service.py   # Parking logic
└── routers/
    ├── streams.py                 # Video streaming
    └── detection_viewer.py        # WebSocket viewer

frontend/src/
├── App.tsx                        # Main app + routing
├── pages/
│   ├── DetectionViewerPage.tsx   # Live viewer
│   ├── ParkingSpaceEditorPage.tsx# Space editor
│   └── WorkerMonitorPage.tsx     # Worker dashboard
└── services/
    ├── apiService.ts              # Backend API
    └── parkingSpaceService.ts     # Parking spaces
```

---

## 🔌 API Quick Reference

### REST Endpoints

```bash
# Health & Status
GET  /health                       # System health check
GET  /debug/streams                # Active connections

# Video Streaming
GET  /stream                       # Raw MJPEG stream
GET  /stream/detect                # Stream with detection
GET  /stream/proxy                 # Direct proxy

# AI Processing
POST /api/plate-detect             # Detect license plates
POST /api/object-tracking          # Track objects

# Data Access
GET  /api/firebase/history         # Detection history
GET  /api/firebase/plates          # Plate history

# Worker
GET  /api/worker/stats             # Worker statistics
GET  /stream/worker-detection      # Worker stream
```

### WebSocket Endpoints

```bash
# Detection Viewer
ws://localhost:8069/ws/viewer/detection?camera_id=cam1&user_id=uid

# Regular Stream
ws://localhost:8069/ws/stream?camera_id=cam1
```

---

## 🎯 Common Tasks

### Add New Camera

1. **In Firebase Console**:
   - Go to Firestore → `cameras` collection
   - Add document:
   ```json
   {
     "id": "cam_003",
     "name": "Parking Lot C",
     "streamUrl": "http://192.168.1.103:81/stream",
     "enabled": true,
     "workerEnabled": true,
     "parkingLotId": "lot_c"
   }
   ```

2. **Define Parking Spaces**:
   - Go to http://localhost:5169/parking-spaces
   - Select camera
   - Draw spaces
   - Save

### Change Detection Settings

Edit `server/config/tracking_config.yaml`:
```yaml
detection:
  conf_threshold: 0.25    # Lower = more detections
  iou_threshold: 0.45     # Higher = fewer duplicates

performance:
  fps: 10                 # Target FPS
  imgsz: 640             # Image size (320/640/1280)
```

### Enable/Disable Worker

```bash
# Start worker
python parking_monitor_worker.py --fps 10

# High performance
python parking_monitor_worker.py --fps 20 --no-firebase

# Stop worker
# Press Ctrl+C in worker terminal
```

### View Logs

```bash
# Worker logs (console output)
# Just read terminal where worker is running

# Detection logs (files)
ls -la server/logs/
cat server/logs/detections_20260107_*.log

# Backend logs
# Read terminal where main_fastapi.py is running
```

---

## 🐛 Troubleshooting Quick Fixes

### Problem: No GPU detected
```bash
# Check CUDA
nvidia-smi

# Reinstall PyTorch with CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Problem: Firebase connection failed
```bash
# Verify file exists
ls -la server/firebase_credentials.json

# Check JSON validity
python -c "import json; json.load(open('server/firebase_credentials.json'))"
```

### Problem: Worker not detecting cameras
```bash
# Check Firebase for cameras with workerEnabled=true
# In Firebase Console: Firestore → cameras
# Ensure at least one camera has workerEnabled: true
```

### Problem: Port already in use
```bash
# Linux/Mac
lsof -i :8069
kill -9 <PID>

# Windows
netstat -ano | findstr :8069
taskkill /PID <PID> /F
```

### Problem: Frontend build errors
```bash
# Clear and reinstall
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

---

## 📊 Performance Tuning

### For Maximum Speed
```yaml
# config/tracking_config.yaml
performance:
  fps: 30
  imgsz: 320
  skip_frames: 1

detection:
  conf_threshold: 0.15

# Worker command
python parking_monitor_worker.py --fps 30 --no-firebase --no-logging
```

### For Maximum Accuracy
```yaml
# config/tracking_config.yaml
performance:
  fps: 5
  imgsz: 1280
  skip_frames: 0

detection:
  conf_threshold: 0.4

bytetrack:
  track_high_thresh: 0.7
  new_track_thresh: 0.8
```

### For Balanced Performance (Recommended)
```yaml
# config/tracking_config.yaml (default)
performance:
  fps: 10
  imgsz: 640

detection:
  conf_threshold: 0.25
```

---

## 🔐 Security Checklist

- [ ] Firebase service account key secured (chmod 600)
- [ ] Frontend .env not committed to git (.gitignore)
- [ ] Firestore security rules configured
- [ ] API authentication enabled (optional)
- [ ] HTTPS/WSS in production
- [ ] Admin users properly configured

---

## 📖 Documentation Index

| Document | Description |
|----------|-------------|
| `README.md` | Main project documentation |
| `01_PROJECT_OVERVIEW.md` | High-level system overview |
| `02_ARCHITECTURE_DETAILS.md` | Architecture deep dive |
| `03_FRONTEND_ARCHITECTURE.md` | Frontend implementation |
| `04_BACKEND_ARCHITECTURE.md` | Backend implementation |
| `05_KEY_FEATURES_WORKFLOWS.md` | Feature documentation |
| `06_SETUP_DEPLOYMENT.md` | Setup and deployment |
| `07_TECHNICAL_DEEP_DIVE.md` | Technical details |
| `08_QUICK_REFERENCE.md` | This file |

### Additional Docs

```
docs/
├── FIREBASE_ARCHITECTURE.md       # Firebase integration
├── BYTETRACK_INTEGRATION.md       # Tracking system
├── PARKING_SPACE_EDITOR.md        # Space editor guide
├── WORKER_MONITORING_GUIDE.md     # Worker setup
├── DETECTION_VIEWER_SYSTEM.md     # Detection viewer
└── PERFORMANCE_TUNING.md          # Optimization tips

ESP32/
└── README.md                       # Hardware setup

server/
├── MODULAR_ARCHITECTURE.md         # Backend structure
└── FASTAPI_SETUP.md                # FastAPI guide
```

---

## 💡 Tips & Best Practices

### Development Tips

1. **Use Mock ESP32**: Faster iteration, no hardware needed
2. **Start with Low FPS**: Easier debugging at 5 FPS
3. **Disable Firebase Writes**: Speed up testing
4. **Use Small YOLO Model**: YOLOv8n for development
5. **Check GPU Usage**: `nvidia-smi` to monitor

### Production Tips

1. **Use Real ESP32-CAM**: Better image quality
2. **Optimize FPS**: Balance speed vs accuracy
3. **Enable Firebase**: For data persistence
4. **Use Custom Model**: Better accuracy for parking lots
5. **Monitor Resources**: CPU, GPU, Memory, Network

### Debugging Tips

1. **Check Logs First**: Console output has most info
2. **Test Components Separately**: Backend, frontend, worker
3. **Use Health Endpoint**: `/health` for system status
4. **Verify GPU**: CUDA must be available for speed
5. **Check Firestore**: Verify data in Firebase Console

---

## 🎓 Learning Resources

### To Understand This Project

1. **FastAPI**: https://fastapi.tiangolo.com/
2. **React**: https://react.dev/
3. **YOLO**: https://docs.ultralytics.com/
4. **Firebase**: https://firebase.google.com/docs
5. **ByteTrack**: https://github.com/ifzhang/ByteTrack

### To Extend This Project

1. **YOLO Fine-tuning**: Train on custom parking data
2. **WebSocket**: Real-time communication patterns
3. **Computer Vision**: OpenCV documentation
4. **NoSQL Design**: Firebase best practices
5. **React Context**: State management patterns

---

## 🚀 Next Steps After Setup

### For Users
1. Login/Register account
2. View detection viewer
3. Check parking availability
4. View history and analytics

### For Admins
1. Create parking lots
2. Add cameras
3. Define parking spaces
4. Monitor worker dashboard
5. Review alerts and statistics

### For Developers
1. Read architecture docs
2. Explore codebase
3. Try modifications
4. Add new features
5. Optimize performance

---

## 📞 Quick Help

### Get System Status
```bash
# Backend health
curl http://localhost:8069/health

# Active streams
curl http://localhost:8069/debug/streams

# Worker stats (if API exposed)
curl http://localhost:8069/api/worker/stats
```

### Check Versions
```bash
python --version       # Should be 3.10+
node --version         # Should be 18+
npm --version
conda --version
```

### Restart Everything
```bash
# Stop all (Ctrl+C in each terminal)
# Then restart in order:

# 1. ESP32 mock
cd ESP32 && python start_mock.py --port 5069

# 2. Backend
cd server && conda activate scheduler && python main_fastapi.py

# 3. Worker
cd server && conda activate scheduler && python parking_monitor_worker.py

# 4. Frontend
cd frontend && npm run dev
```

---

## 🎉 Success Indicators

System is working correctly when:
- ✅ Backend shows "✅ AI models loaded successfully"
- ✅ Worker shows "Processing camera: ..." with detections
- ✅ Frontend loads without errors
- ✅ Detection viewer shows live annotated stream
- ✅ Parking spaces update in real-time
- ✅ GPU usage visible in `nvidia-smi`
- ✅ No errors in any terminal

---

This quick reference guide provides fast access to the most commonly needed information for the Smart Parking System. Keep it handy!
