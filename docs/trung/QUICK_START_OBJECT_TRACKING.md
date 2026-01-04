# 🎯 Quick Start: Object Tracking with ESP32

Complete guide to run SmartParking with real-time object detection and tracking.

## 📋 System Ports

| Service | Port | URL |
|---------|------|-----|
| Frontend | 5169 | http://localhost:5169 |
| Backend (FastAPI) | 8069 | http://localhost:8069 |
| Mock ESP32 | 5069 | http://localhost:5069 |
| Real ESP32 | 81 | http://192.168.33.122:81 |

## 🚀 Quick Start (3 Steps)

### Step 0: Configure Environment Variables (First Time Only)

The frontend uses environment variables for URLs. Check `frontend/.env`:

```bash
# Backend API URLs
VITE_BACKEND_URL=http://localhost:8069
VITE_ESP32_DIRECT_URL=http://192.168.33.122:81
VITE_MOCK_ESP32_URL=http://localhost:5069
```

**To customize:** Edit `frontend/.env` with your values, then restart frontend.

---

### Step 1: Start Mock ESP32 Server

```bash
cd ESP32
python start_mock.py --video videos/parking_c.mp4 --port 5069
```

**Leave this terminal running!**

---

### Step 2: Start Backend (FastAPI)

Open **new terminal**:

```bash
cd server
eval "$(conda shell.bash hook)" && conda activate scheduler
python main_fastapi.py
```

**Leave this terminal running!**

Expected output:
```
🚀 Starting FastAPI SmartParking Server...
📦 Loading AI models...
✅ AI models loaded successfully
📹 Connecting to ESP32: http://localhost:5069 (Mock)
✅ ESP32 connected: http://localhost:5069
```

---

### Step 3: Start Frontend

Open **new terminal**:

```bash
cd frontend
npm run dev
```

**Leave this terminal running!**

Then open browser: **http://localhost:5169**

---

## 🎯 Using Object Detection

1. **Navigate to ESP32 Stream Page** in the frontend
2. **Select "Object Tracking" mode** (🎯 button)
3. **Adjust settings:**
   - **Confidence Threshold**: Lower = more detections, Higher = more accurate
   - **Show Labels**: Toggle detection labels on/off
4. **Watch the stream** with real-time YOLO object detection!

### Available Modes

| Mode | Description | URL |
|------|-------------|-----|
| 🎯 Object Tracking | Real-time YOLO detection | http://localhost:8069/stream/detect |
| 📹 Raw Stream | No detection (faster) | http://localhost:8069/stream |
| ⚡ Direct ESP32 | Bypass backend | http://192.168.33.122:81/stream |
| 🎬 Mock Server | Direct to mock | http://localhost:5069/stream |

## 🔧 Troubleshooting

### Backend can't connect to Mock ESP32

**Error:** `Cannot connect to ESP32 at http://localhost:5069`

**Solution:** Make sure Mock ESP32 server is running:
```bash
cd ESP32
python start_mock.py --video videos/parking_c.mp4 --port 5069
```

### Frontend shows white screen

**Solution:** Check all services are running and ports are correct:
```bash
# Check backend
curl http://localhost:8069/health

# Check mock ESP32
curl http://localhost:5069/status

# Check frontend
curl http://localhost:5169
```

### No video in Mock ESP32

**Error:** `Default video not found: test_video.mp4`

**Solution:** Place video files in `ESP32/stream/` or use `--video` argument:
```bash
python start_mock.py --video videos/parking_c.mp4 --port 5069
```

### Detection stream is slow

**Solutions:**
1. Lower the confidence threshold (faster processing)
2. Use "Raw Stream" mode (no detection)
3. Check CPU usage - YOLO is computationally intensive

### YOLO model not loading

**Error:** `Failed to load YOLO model`

**Solution:** Verify models exist:
```bash
cd server
ls -lh yolov8*.pt

# Should see:
# yolov8n.pt (default)
# yolov8s_car_custom.pt (custom)
```

## 📊 Detection API Endpoints

### Stream Endpoints
```bash
# Raw stream (no detection)
curl http://localhost:8069/stream

# With object detection
curl "http://localhost:8069/stream/detect?conf=0.25&show_labels=true"
```

### Single Frame Detection
```bash
# Capture snapshot
curl http://localhost:8069/api/esp32/snapshot

# Get ESP32 status
curl http://localhost:8069/api/esp32/status
```

### Video Upload Detection
```bash
# Upload video for tracking
curl -X POST http://localhost:8069/api/object-tracking \
  -H "Content-Type: application/json" \
  -d '{"videoData": "data:video/mp4;base64,...", "confThreshold": 0.25}'
```

## 🎬 Using Real ESP32-CAM

### Setup Real Hardware

1. **Flash ESP32-CAM firmware:**
   ```bash
   # See ESP32/HARDWARE_SETUP.md for complete guide
   ```

2. **Configure backend for real ESP32:**
   ```bash
   cd server
   export USE_MOCK_ESP32=false
   export ESP32_URL=http://192.168.33.122:81
   python main_fastapi.py
   ```

3. **Test connection:**
   ```bash
   python ESP32/test_esp32_connection.py --url http://192.168.33.122:81
   ```

## 📝 Environment Variables

### Frontend Configuration (`frontend/.env`)

```bash
# Backend API URLs
VITE_BACKEND_URL=http://localhost:8069
VITE_ESP32_DIRECT_URL=http://192.168.33.122:81  # Update with your ESP32 IP
VITE_MOCK_ESP32_URL=http://localhost:5069

# Firebase Configuration
VITE_FIREBASE_API_KEY=your_key
VITE_FIREBASE_AUTH_DOMAIN=your_domain
# ... etc
```

### Backend Configuration (`server/.env`)

Configure in `server/.env` or export before running:

```bash
# Use Mock or Real ESP32
export USE_MOCK_ESP32=true          # or false for real hardware

# ESP32 URLs
export MOCK_ESP32_URL=http://localhost:5069
export ESP32_URL=http://192.168.33.122:81
```

**Note:** After changing `.env` files, restart the respective services.

## 🎯 Complete Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (5169)                      │
│              React + Vite + TypeScript                  │
└───────────────────┬─────────────────────────────────────┘
                    │ HTTP
                    ▼
┌─────────────────────────────────────────────────────────┐
│               Backend FastAPI (8069)                    │
│         • /stream → Raw MJPEG proxy                     │
│         • /stream/detect → YOLO detection               │
│         • /api/object-tracking → Video analysis         │
└───────────────────┬─────────────────────────────────────┘
                    │
        ┌───────────┴────────────┐
        │                        │
        ▼                        ▼
┌──────────────┐      ┌──────────────────┐
│ Mock ESP32   │      │ Real ESP32-CAM   │
│    (5069)    │      │      (81)        │
│ Dev/Testing  │      │   Production     │
└──────────────┘      └──────────────────┘
```

## 🎓 Next Steps

1. **Test with different videos:**
   ```bash
   python start_mock.py --list-videos
   python start_mock.py --video YOUR_VIDEO.mp4 --port 5069
   ```

2. **Adjust detection parameters:**
   - Confidence threshold: 0.1 (more) to 0.9 (fewer)
   - Toggle labels on/off
   - Try different YOLO models

3. **Switch to real hardware:**
   - Flash ESP32-CAM (see ESP32/HARDWARE_SETUP.md)
   - Configure WiFi
   - Update backend environment variables

4. **Enable Firebase:**
   - Configure Firebase Authentication
   - Detection results will be saved automatically

---

**Need help?** Check:
- `ESP32/README.md` - ESP32 setup guide
- `ESP32/HARDWARE_SETUP.md` - Hardware wiring
- `server/README.md` - Backend API docs
- API Docs: http://localhost:8069/docs
