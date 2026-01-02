# Smart Parking System 🚗

AI-powered parking management system with real-time object detection and license plate recognition.

## 🏗️ System Architecture

### **Simple Overview: Who Calls Who?**

```
User Browser
    ↓ Opens webpage
┌─────────────────────────────┐
│   FRONTEND (Port 5169)      │  React App
│   - Displays UI             │
│   - Shows video stream      │
└─────────────────────────────┘
    ↓ Makes HTTP requests
    ↓ GET /stream/detect
    ↓ POST /api/plate-detect
┌─────────────────────────────┐
│   BACKEND (Port 8069)       │  FastAPI Server
│   - Runs AI models (YOLO)   │
│   - Processes video frames  │
│   - Stores to Firebase      │
└─────────────────────────────┘
    ↓ Fetches stream
    ↓ GET /stream
┌─────────────────────────────┐
│   ESP32 SERVER (Port 5069)  │  Video Source
│   - Provides MJPEG stream   │
│   - Dev: Video files        │
│   - Prod: Real camera       │
└─────────────────────────────┘
```

### **Component Responsibilities**

#### 1️⃣ **Frontend** (React on port 5169)
**What it does:**
- Shows web interface to user
- Displays video stream using `<img>` tag
- Lets user adjust detection settings
- Makes API calls to backend

**What it DOESN'T do:**
- No AI processing
- No video file handling
- No direct ESP32 connection (goes through backend)

**Example calls:**
```javascript
// Display stream with detection
<img src="http://localhost:8069/stream/detect?conf=0.25" />

// Detect license plate
fetch('http://localhost:8069/api/plate-detect', {
  method: 'POST',
  body: JSON.stringify({ imageData: '...' })
})
```

#### 2️⃣ **Backend** (FastAPI on port 8069)
**What it does:**
- Runs YOLO AI model (with CUDA)
- Processes video frames in real-time
- Adds bounding boxes to detections
- Proxies stream from ESP32 server
- Saves detection results to Firebase

**What it DOESN'T do:**
- No user interface
- No video file storage
- No direct browser interaction

**How it processes a frame:**
```python
1. Frontend requests: GET /stream/detect
2. Backend connects to: http://localhost:5069/stream
3. For each frame:
   a. Read JPEG frame from ESP32
   b. Run YOLO detection (GPU accelerated)
   c. Draw bounding boxes + labels
   d. Send annotated frame to frontend
4. Loop continuously
```

**APIs it provides:**
- `GET /stream` → Raw stream proxy (no AI)
- `GET /stream/detect` → Stream with AI detection
- `POST /api/plate-detect` → Detect license plates
- `POST /api/object-tracking` → Track objects in video
- `GET /health` → Check if backend is alive

#### 3️⃣ **ESP32 Server** (Port 5069)
**What it does:**
- Provides raw video stream (MJPEG format)
- In development: Streams from video files
- In production: Streams from real ESP32-CAM camera

**What it DOESN'T do:**
- No AI processing
- No detection or tracking
- No data storage
- Just streams video

**How to switch modes:**
```bash
# Development (video files)
python start_mock.py --video parking.mp4 --port 5069

# Production (real hardware)
# Flash ESP32-CAM firmware, it runs on port 81
# Update backend: VITE_ESP32_URL=http://192.168.33.122:81
```

---

### **Complete Request Flow Example**

#### **Scenario: User views stream with object detection**

```
┌──────────┐
│  User    │ Opens browser → http://localhost:5169
└────┬─────┘
     │
     ▼
┌──────────────────────────────────────────┐
│  FRONTEND (React)                        │
│  StreamViewerPageESP32.tsx               │
│                                          │
│  <img src="http://localhost:8069/       │
│            stream/detect?conf=0.25" />   │
└────┬─────────────────────────────────────┘
     │ HTTP GET Request
     │ (Browser automatically requests image)
     ▼
┌──────────────────────────────────────────┐
│  BACKEND (FastAPI)                       │
│  main_fastapi.py                         │
│                                          │
│  @app.get("/stream/detect")              │
│  1. Connect to ESP32                     │ ─────┐
│  2. Read frame from ESP32                │      │
│  3. Run YOLO model (GPU)                 │      │
│  4. Draw bounding boxes                  │      │
│  5. Send back to frontend                │      │
│  6. Repeat for next frame                │      │
└────┬─────────────────────────────────────┘      │
     │                                            │
     │ HTTP GET /stream                           │
     │                                            │
     └────────────────────────────────────────────┘
                                                   ▼
                                    ┌──────────────────────────┐
                                    │  ESP32 SERVER            │
                                    │  mock_esp32_server.py    │
                                    │                          │
                                    │  Reads video file        │
                                    │  Sends MJPEG frames      │
                                    └──────────────────────────┘
```

#### **Scenario: User detects license plate**

```
┌──────────┐
│  User    │ Clicks "Detect Plate" button
└────┬─────┘
     │
     ▼
┌──────────────────────────────────────────┐
│  FRONTEND                                │
│  Captures current frame                  │
│  Converts to base64                      │
│  fetch('http://localhost:8069/           │
│        api/plate-detect', {              │
│    body: { imageData: 'base64...' }      │
│  })                                      │
└────┬─────────────────────────────────────┘
     │ HTTP POST
     │ { imageData: "data:image/jpeg;base64,..." }
     ▼
┌──────────────────────────────────────────┐
│  BACKEND                                 │
│  1. Decode base64 image                  │
│  2. Run YOLO (detect vehicles)           │
│  3. Run ALPR (read plate text)           │
│  4. Save to Firebase                     │ ──→ Firebase
│  5. Return results                       │
└────┬─────────────────────────────────────┘
     │ Response
     │ { plates: [{ text: "ABC123", confidence: 0.95 }] }
     ▼
┌──────────────────────────────────────────┐
│  FRONTEND                                │
│  Displays plate number to user           │
└──────────────────────────────────────────┘
```

---

### **Why This Architecture?**

#### **Separation of Concerns**
- **Frontend**: User interface only (React is good at this)
- **Backend**: Heavy AI processing (Python is good at this)
- **ESP32**: Video streaming only (cheap hardware)

#### **Advantages**
1. ✅ **Frontend stays simple** - No AI models to download
2. ✅ **Backend can use GPU** - Fast CUDA processing
3. ✅ **ESP32 is lightweight** - Just streams video
4. ✅ **Easy to scale** - Add more backends for load balancing
5. ✅ **Development friendly** - Can use video files instead of real hardware

#### **Why Backend is the Middleman?**
- **CORS**: Browsers block direct camera connections
- **Processing**: Need server-side GPU for AI
- **Security**: Don't expose ESP32 directly to internet
- **Flexibility**: Can switch between dev/prod streams easily

---

### **Communication Protocols**

| Connection | Protocol | Format | Purpose |
|------------|----------|--------|---------|
| Browser → Frontend | HTTP/HTTPS | HTML/JS/CSS | Load webpage |
| Frontend → Backend | HTTP REST | JSON | API calls, commands |
| Frontend ← Backend | HTTP MJPEG | JPEG frames | Video stream |
| Backend → ESP32 | HTTP | MJPEG | Fetch video |
| Backend → Firebase | HTTPS | JSON | Store data |

---

### **Port Summary**

```
localhost:5169  →  Frontend (React dev server)
localhost:8069  →  Backend (FastAPI + AI)
localhost:5069  →  ESP32 Server (Video source)
```

**Key Point**: Frontend NEVER talks to ESP32 directly. Always goes through Backend.

---

### **Data Flow for Real-Time Detection**

```
┌─────────────┐
│ Video File  │ (parking.mp4)
│ or Camera   │
└──────┬──────┘
       │ 30 FPS
       ▼
┌─────────────────┐
│  ESP32 Server   │  Encodes frames → MJPEG
│  (Port 5069)    │  Sends continuous stream
└──────┬──────────┘
       │ MJPEG Stream (~30 FPS)
       ▼
┌─────────────────────────────────┐
│  Backend (Port 8069)            │
│                                 │
│  For each frame:                │
│  1. Decode JPEG                 │  ← 10ms (CPU)
│  2. Run YOLO detection          │  ← 10ms (GPU) ⚡
│  3. Draw bounding boxes         │  ← 2ms (CPU)
│  4. Encode back to JPEG         │  ← 5ms (CPU)
│  Total: ~27ms = ~37 FPS         │
└──────┬──────────────────────────┘
       │ MJPEG with annotations (~30 FPS)
       ▼
┌─────────────────┐
│  Frontend       │  Browser decodes & displays
│  (Port 5169)    │  User sees annotated video
└─────────────────┘
```

**Note**: GPU processes ~100 FPS but stream is 30 FPS, so detection is real-time with overhead.

---

### **Quick Architecture Check**

To verify everything is connected correctly:

```bash
# 1. Check ESP32 is streaming
curl http://localhost:5069/status
# Expected: {"device":"ESP32-CAM Mock","status":"idle",...}

# 2. Check backend can reach ESP32
curl http://localhost:8069/stream | head -c 1000
# Expected: Binary JPEG data (should show bytes)

# 3. Check frontend can reach backend
curl http://localhost:8069/health
# Expected: {"status":"ok","models_loaded":true,...}

# 4. Check frontend is running
curl http://localhost:5169
# Expected: HTML content
```

If all 4 work → Architecture is correctly set up! ✅

## � Port Configuration

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| **Frontend** | 5169 | http://localhost:5169 | React Vite dev server |
| **Backend** | 8069 | http://localhost:8069 | FastAPI REST API + AI |
| **ESP32 Dev** | 5069 | http://localhost:5069 | Development streaming |
| **ESP32 Prod** | 81 | http://192.168.x.x:81 | Real hardware streaming |

## 📁 Project Structure

```
SmartParking/
├── frontend/              # React + TypeScript frontend
│   ├── src/
│   │   ├── pages/        # Page components
│   │   │   └── StreamViewerPageESP32.tsx  # Main stream viewer
│   │   ├── components/   # Reusable components
│   │   ├── config/       # API configuration
│   │   └── services/     # API services
│   ├── .env             # Environment variables
│   └── package.json
│
├── server/               # FastAPI backend
│   ├── main_fastapi.py  # Main API server (CUDA enabled)
│   ├── services/
│   │   ├── ai_service.py        # YOLO + ALPR (GPU accelerated)
│   │   └── firebase_service.py  # Firebase integration
│   ├── yolov8s_car_custom.pt   # Custom trained model
│   ├── yolov8n.pt              # Default YOLO model
│   └── requirements.txt
│
├── ESP32/                # ESP32-CAM integration
│   ├── mock_esp32_server.py    # Development server
│   ├── esp32_cam_firmware.ino  # Real hardware firmware
│   ├── esp32_client.py         # Python client library
│   ├── start_mock.py           # Quick start script
│   ├── test_esp32_connection.py # Testing utilities
│   ├── stream/                  # Video files (dev)
│   └── HARDWARE_SETUP.md
│
└── docs/                 # Documentation
    ├── QUICK_START_OBJECT_TRACKING.md
    ├── PORT_CONFIGURATION.md
    ├── ENVIRONMENT_VARIABLES.md
    └── ESP32_REFACTOR.md
```

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** (conda environment: `scheduler`)
- **Node.js 18+** 
- **CUDA 11.8+** (for GPU acceleration)
- **NVIDIA GPU** with 4GB+ VRAM (recommended)

### 1. Start ESP32 Streaming Server

```bash
cd ESP32
python start_mock.py --video videos/parking_c.mp4 --port 5069
```

### 2. Start Backend (with CUDA)

```bash
cd server
eval "$(conda shell.bash hook)" && conda activate scheduler
python main_fastapi.py
```

Expected output:
```
🚀 Starting FastAPI SmartParking Server...
📦 Loading AI models...
🔥 Using CUDA device: NVIDIA GeForce RTX 3090
✅ YOLO model loaded on cuda:0
✅ ALPR model loaded
📹 Connecting to ESP32: http://localhost:5069
✅ ESP32 connected
```

### 3. Start Frontend

```bash
cd frontend
npm install  # First time only
npm run dev
```

### 4. Open Browser

Navigate to: **http://localhost:5169**

Select viewing mode:
- 🎯 **Object Detection** - Real-time YOLO detection with bounding boxes
- 📹 **Raw Stream** - Original stream without processing
- ⚡ **Direct Stream** - Bypass backend proxy

## 🎯 Features

### AI-Powered Detection
- ✅ **YOLOv8s Custom Model** - Trained on parking lot dataset (mAP50: 99.49%)
- ✅ **CUDA Acceleration** - 10-30x faster inference on GPU
- ✅ **Real-time Object Detection** - Cars, motorcycles, persons
- ✅ **Object Tracking** - ByteTrack algorithm for consistent IDs
- ✅ **License Plate Recognition** - Fast-ALPR with ONNX runtime

### Streaming Modes
- 🎯 **Object Detection Mode** - Annotated stream with bounding boxes
- 📹 **Raw Stream Mode** - Original video feed
- ⚡ **Direct Stream Mode** - Direct ESP32 connection
- ⚙️ **Adjustable Settings** - Confidence threshold, labels on/off

### Development Features
- 🔄 **Hot Reload** - Frontend and backend auto-reload on changes
- 🎬 **Mock Streaming** - Test without ESP32 hardware
- 📊 **API Documentation** - Auto-generated at `/docs`
- 🔍 **Health Checks** - Monitor service status

## 🎮 API Endpoints

### Streaming
```bash
# Raw stream proxy
GET http://localhost:8069/stream

# Stream with real-time detection
GET http://localhost:8069/stream/detect?conf=0.25&show_labels=true

# Parameters:
#   conf: Confidence threshold (0.1-0.9, default: 0.25)
#   show_labels: Show detection labels (true/false, default: true)
```

### Detection APIs
```bash
# License plate detection
POST http://localhost:8069/api/plate-detect
Body: { "imageData": "data:image/jpeg;base64,..." }

# Object tracking on video
POST http://localhost:8069/api/object-tracking
Body: { 
  "videoData": "data:video/mp4;base64,...",
  "confThreshold": 0.25,
  "iouThreshold": 0.45
}

# ESP32 snapshot
GET http://localhost:8069/api/esp32/snapshot

# ESP32 status
GET http://localhost:8069/api/esp32/status
```

### Health & Testing
```bash
# Backend health check
GET http://localhost:8069/health

# Test ESP32 connection
GET http://localhost:8069/test/esp32

# API documentation (Swagger)
GET http://localhost:8069/docs
```

## ⚙️ Configuration

### Frontend (.env)
```bash
# Backend API
VITE_BACKEND_URL=http://localhost:8069

# ESP32-CAM URL (development or production)
VITE_ESP32_URL=http://localhost:5069

# Firebase (optional)
VITE_FIREBASE_API_KEY=your_key
VITE_FIREBASE_AUTH_DOMAIN=your_domain
VITE_FIREBASE_PROJECT_ID=your_project_id
```

### Backend (environment variables)
```bash
# ESP32 Configuration
USE_MOCK_ESP32=true                          # false for real hardware
MOCK_ESP32_URL=http://localhost:5069         # Development server
ESP32_URL=http://192.168.33.122:81           # Real ESP32-CAM IP

# CUDA Configuration (automatic detection)
# Set CUDA_VISIBLE_DEVICES=0 to select GPU
# Model automatically uses CUDA if available
```

## 🎯 Object Tracking Performance

### Model Specifications
- **Model**: YOLOv8s Custom (parking lot trained)
- **mAP50**: 99.49%
- **Classes**: Car, Motorcycle, Person, Truck
- **Input Size**: 640x640
- **Framework**: Ultralytics YOLO

### Performance Benchmarks

| Hardware | FPS (Detection) | Latency | VRAM Usage |
|----------|----------------|---------|------------|
| NVIDIA RTX 3090 | ~100 FPS | 10ms | 2.5GB |
| NVIDIA RTX 3080 | ~80 FPS | 12ms | 2.5GB |
| NVIDIA GTX 1080 | ~50 FPS | 20ms | 2.0GB |
| CPU (16 cores) | ~8 FPS | 125ms | N/A |

## 🔧 Troubleshooting

### No stream visible
1. Check ESP32 server: `curl http://localhost:5069/status`
2. Check backend: `curl http://localhost:8069/health`
3. Test stream: `curl http://localhost:8069/stream | head -c 1000`
4. Restart services in order: ESP32 → Backend → Frontend

### CUDA not detected
```bash
# Check CUDA availability
python -c "import torch; print(torch.cuda.is_available())"

# Check GPU
nvidia-smi

# Install CUDA-enabled PyTorch
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Slow detection speed
- Verify CUDA is enabled (check backend startup logs)
- Lower confidence threshold
- Use smaller model (yolov8n.pt instead of yolov8s)
- Reduce input resolution

### Port conflicts
```bash
# Check what's using ports
lsof -i :5069  # ESP32
lsof -i :8069  # Backend
lsof -i :5169  # Frontend

# Kill process on port
kill -9 $(lsof -ti :5069)
```

## 📚 Documentation

Detailed guides available in project root:
- **`QUICK_START_OBJECT_TRACKING.md`** - Complete setup guide
- **`PORT_CONFIGURATION.md`** - Port management and troubleshooting
- **`ENVIRONMENT_VARIABLES.md`** - Configuration reference
- **`ESP32/README.md`** - ESP32 integration guide
- **`ESP32/HARDWARE_SETUP.md`** - Hardware wiring and setup
- **`ESP32_REFACTOR.md`** - Architecture overview

## 🔒 Security Notes

- Frontend `.env` variables are **PUBLIC** (embedded in JS bundle)
- Never put secrets in `VITE_*` variables
- Firebase config is safe to expose (protected by Security Rules)
- Backend environment variables are **PRIVATE** (server-only)
- Add `.env` to `.gitignore`

## 🚀 Production Deployment

### With Real ESP32-CAM Hardware

1. **Flash ESP32 firmware** (see `ESP32/HARDWARE_SETUP.md`)
2. **Configure production URLs:**
   ```bash
   # Frontend .env
   VITE_BACKEND_URL=https://api.yourserver.com
   VITE_ESP32_URL=http://192.168.33.122:81
   
   # Backend
   export USE_MOCK_ESP32=false
   export ESP32_URL=http://192.168.33.122:81
   ```
3. **Build frontend:** `npm run build`
4. **Deploy** `frontend/dist/` to web server
5. **Run backend** with production settings

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/YourFeature`
3. Commit changes: `git commit -m 'Add YourFeature'`
4. Push to branch: `git push origin feature/YourFeature`
5. Open Pull Request

## 📄 License

[Your License Here]

## 👥 Team

[Your Team Info]

---

**Tech Stack**: React · TypeScript · Vite · Python · FastAPI · YOLOv8 · PyTorch · CUDA · OpenCV · Firebase · ESP32-CAM