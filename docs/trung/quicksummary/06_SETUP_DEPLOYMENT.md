# Smart Parking System - Setup & Deployment Guide

## 🚀 Quick Start Guide

### Prerequisites

**Hardware Requirements**:
- CPU: Modern multi-core processor (Intel i5/Ryzen 5 or better)
- RAM: 8GB minimum, 16GB recommended
- GPU: NVIDIA GPU with CUDA support (RTX 2060 or better recommended)
  - Optional: Can run on CPU but much slower
- Storage: 10GB free space
- Network: Stable internet connection

**Software Requirements**:
- Python 3.10+
- Node.js 18+ and npm
- Conda (Miniconda or Anaconda)
- Git
- CUDA Toolkit 11.8+ (for GPU support)

**Optional**:
- ESP32-CAM hardware (for production)
- Arduino IDE (for ESP32 firmware)

---

## 📦 Installation Steps

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd SmartParking
```

### Step 2: Backend Setup

#### 2.1: Create Conda Environment

```bash
cd server

# Create environment from yml file
conda env create -f environment.yml

# Activate environment
conda activate scheduler

# Verify installation
python --version  # Should be 3.10+
```

#### 2.2: Install Python Dependencies

```bash
# Install requirements
pip install -r requirements.txt

# Verify CUDA (if using GPU)
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

**Expected output with GPU**:
```
CUDA available: True
```

#### 2.3: Download AI Models

Models are automatically downloaded on first run, but you can pre-download:

```bash
# YOLO models (auto-downloaded)
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Optional: Custom trained model
# Place yolov8s_car_custom.pt in server/ directory
```

#### 2.4: Configure Firebase

**Option A: Use Existing Firebase Project**
1. Download service account key from Firebase Console
2. Save as `firebase_credentials.json` in `server/` directory

**Option B: Create New Firebase Project**
```bash
1. Go to https://console.firebase.google.com/
2. Create new project
3. Enable Firestore Database
4. Create service account key
5. Save as server/firebase_credentials.json
```

**File structure**:
```
server/
├── firebase_credentials.json    # Service account key
└── .env                         # Environment variables
```

#### 2.5: Configure Environment Variables

Create `server/.env` file:
```bash
# ESP32 Configuration
ESP32_URL=http://localhost:5069

# Firebase (optional, if not using credentials file)
# FIREBASE_PROJECT_ID=your-project-id

# Worker Configuration
MONITOR_CHECK_INTERVAL=0.1    # 10 FPS
ENABLE_LOGGING=true
USE_TRACKING=true
```

### Step 3: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
```

Edit `frontend/.env`:
```bash
# Firebase Client Configuration
VITE_FIREBASE_API_KEY=your-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abcdef

# Backend API
VITE_API_BASE_URL=http://localhost:8069
```

### Step 4: ESP32 Mock Server (Development)

```bash
cd ESP32

# Place test videos in stream/ folder
mkdir -p stream
# Copy some .mp4 files to stream/

# Start mock server
python start_mock.py --video stream/parking_c.mp4 --port 5069
```

---

## 🏃 Running the System

### Development Mode (3 Terminals)

**Terminal 1: Backend Server**
```bash
cd server
conda activate scheduler
python main_fastapi.py
```

Expected output:
```
🚀 Starting FastAPI SmartParking Server...
📦 Loading AI models...
🚀 CUDA available: NVIDIA GeForce RTX 3080
✅ AI models loaded successfully
🔥 Initializing Firebase Admin SDK...
✅ Firebase initialized
📹 Connecting to ESP32: http://localhost:5069
✅ ESP32 connected
INFO:     Uvicorn running on http://0.0.0.0:8069
```

**Terminal 2: Worker Process**
```bash
cd server
conda activate scheduler
python parking_monitor_worker.py --fps 10
```

Expected output:
```
🚀 Starting parking monitor worker...
⏱️  Target FPS: 10 FPS per camera
📦 Loading AI models...
✅ Models loaded successfully
🎯 ByteTrack tracking ENABLED
Found worker-enabled camera: Parking Lot A Main (cam_001)
✅ Loaded 45 parking spaces for camera cam_001
Processing camera: Parking Lot A Main (cam_001)
🚗 Detected 12 vehicles in camera cam_001
```

**Terminal 3: Frontend**
```bash
cd frontend
npm run dev
```

Expected output:
```
  VITE v5.0.0  ready in 300 ms

  ➜  Local:   http://localhost:5169/
  ➜  Network: http://192.168.1.100:5169/
```

### Production Mode

For production deployment, see detailed guides:
- Backend: Use Gunicorn/Uvicorn with supervisor
- Frontend: Build and serve with Nginx
- Worker: Run as systemd service

---

## 🔧 Configuration Guide

### Worker Configuration

Edit `server/config/tracking_config.yaml`:

```yaml
# High Performance (Fast)
performance:
  fps: 20                # Process 20 frames/sec
  imgsz: 320            # Smaller image size
  skip_frames: 1        # Skip every other frame
  
detection:
  conf_threshold: 0.15  # Lower confidence
  
# High Accuracy (Slower)
performance:
  fps: 5                # Process 5 frames/sec
  imgsz: 1280           # Larger image size
  skip_frames: 0        # Don't skip frames
  
detection:
  conf_threshold: 0.4   # Higher confidence
```

### Camera Configuration

In Firebase Console → Firestore → `cameras` collection:

```javascript
{
  id: "cam_001",
  name: "Parking Lot A Main Entrance",
  parkingLotId: "lot_a",
  streamUrl: "http://192.168.1.100:81/stream",
  enabled: true,
  workerEnabled: true,  // Enable worker monitoring
  userId: "admin_uid",
  settings: {
    fps: 10,
    resolution: "640x480"
  }
}
```

### Parking Space Configuration

Use the Parking Space Editor:
1. Navigate to http://localhost:5169/parking-spaces
2. Select parking lot and camera
3. Draw spaces on canvas
4. Save to Firebase

Spaces are stored with normalized coordinates:
```javascript
{
  id: "space_001",
  cameraId: "cam_001",
  name: "A1",
  x: 0.1,      // 10% from left
  y: 0.2,      // 20% from top
  width: 0.15, // 15% of frame width
  height: 0.2, // 20% of frame height
  occupied: false
}
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. CUDA Not Available

**Problem**: `CUDA available: False`

**Solutions**:
```bash
# Check NVIDIA driver
nvidia-smi

# Verify PyTorch CUDA version
python -c "import torch; print(torch.version.cuda)"

# Reinstall PyTorch with CUDA
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

#### 2. Firebase Connection Failed

**Problem**: `❌ Firebase initialization failed`

**Solutions**:
```bash
# Verify credentials file exists
ls -la server/firebase_credentials.json

# Check file permissions
chmod 600 server/firebase_credentials.json

# Verify file format (should be valid JSON)
python -c "import json; json.load(open('server/firebase_credentials.json'))"

# Check Firebase project ID matches
```

#### 3. ESP32 Connection Failed

**Problem**: `⚠️  ESP32 not connected`

**Solutions**:
```bash
# Start mock server
cd ESP32
python start_mock.py --port 5069

# Test connection
curl http://localhost:5069/stream

# Check firewall
sudo ufw allow 5069
```

#### 4. Worker Not Detecting Cameras

**Problem**: `⚠️ No active cameras found. Waiting...`

**Solutions**:
1. Check Firebase camera configuration
2. Ensure `workerEnabled: true` is set
3. Verify camera `enabled: true`
4. Check worker has Firebase access

```python
# Test Firebase connection
python -c "
from services.firebase_service import FirebaseService
fs = FirebaseService()
cameras = fs.db.collection('cameras').where('workerEnabled', '==', True).stream()
print(f'Found {len(list(cameras))} cameras')
"
```

#### 5. Frontend Build Errors

**Problem**: npm build fails

**Solutions**:
```bash
# Clear cache
rm -rf node_modules package-lock.json
npm cache clean --force

# Reinstall
npm install

# Check Node version
node --version  # Should be 18+

# Update npm
npm install -g npm@latest
```

#### 6. Port Already in Use

**Problem**: `Port 8069 already in use`

**Solutions**:
```bash
# Linux/Mac
lsof -i :8069
kill -9 <PID>

# Windows
netstat -ano | findstr :8069
taskkill /PID <PID> /F

# Or use different port
uvicorn main_fastapi:app --port 8070
```

---

## 📊 Performance Tuning

### GPU Optimization

```python
# server/services/ai_service.py

# Batch processing (if processing multiple cameras)
results = self.yolo_model.predict(
    frames,  # List of frames
    batch=4  # Process 4 at once
)

# Use smaller model for speed
model = YOLO('yolov8n.pt')  # Nano (fastest)
model = YOLO('yolov8s.pt')  # Small (balanced)
model = YOLO('yolov8m.pt')  # Medium (accurate)

# Adjust image size
results = model.predict(
    frame,
    imgsz=320   # Fast
    imgsz=640   # Balanced (default)
    imgsz=1280  # Accurate
)
```

### Worker Optimization

```bash
# High FPS (20 FPS per camera)
python parking_monitor_worker.py --fps 20

# Arguments:
#   --fps: Target frames per second
#   --no-firebase: Disable Firebase writes (faster)
#   --no-logging: Disable file logging
#   --no-tracking: Disable ByteTrack (faster but less accurate)

# Example: Maximum speed
python parking_monitor_worker.py --fps 30 --no-firebase --no-tracking
```

### Network Optimization

```bash
# Reduce video quality (ESP32 mock)
python start_mock.py --quality 50  # JPEG quality 0-100

# Reduce frame rate (ESP32 mock)
python start_mock.py --fps 15  # 15 FPS instead of 30
```

---

## 🔐 Security Setup

### Firebase Security Rules

Update Firestore security rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Helper functions
    function isAuthenticated() {
      return request.auth != null;
    }
    
    function isAdmin() {
      return isAuthenticated() && 
             get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == "admin";
    }
    
    // Users collection
    match /users/{userId} {
      allow read: if isAuthenticated() && request.auth.uid == userId;
      allow write: if isAuthenticated() && request.auth.uid == userId;
    }
    
    // Cameras
    match /cameras/{cameraId} {
      allow read: if isAuthenticated();
      allow write: if isAdmin() || 
                     (isAuthenticated() && 
                      resource.data.userId == request.auth.uid);
    }
    
    // Parking spaces
    match /parkingSpaceDefinitions/{spaceId} {
      allow read: if isAuthenticated();
      allow write: if isAdmin();
    }
    
    // Detection history
    match /detections/{detectionId} {
      allow read: if isAuthenticated();
      allow write: if false; // Only backend writes
    }
    
    // Plate history
    match /plateHistory/{plateId} {
      allow read: if isAuthenticated();
      allow write: if false; // Only backend writes
    }
  }
}
```

### Backend API Security

Add authentication middleware (optional):

```python
# server/middleware/auth.py
from fastapi import Header, HTTPException
import firebase_admin.auth as auth

async def verify_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "Missing authorization header")
    
    try:
        token = authorization.replace("Bearer ", "")
        decoded = auth.verify_id_token(token)
        return decoded
    except:
        raise HTTPException(401, "Invalid token")

# Use in routes
@router.get("/api/protected")
async def protected_route(user = Depends(verify_token)):
    return {"user_id": user['uid']}
```

---

## 📚 Additional Resources

### Documentation Files

- `README.md` - Main project documentation
- `docs/FIREBASE_ARCHITECTURE.md` - Firebase integration guide
- `docs/BYTETRACK_INTEGRATION.md` - Tracking system guide
- `docs/WORKER_MONITORING_GUIDE.md` - Worker setup and monitoring
- `docs/PARKING_SPACE_EDITOR.md` - Parking space editor guide
- `docs/DETECTION_VIEWER_SYSTEM.md` - Detection viewer architecture
- `ESP32/README.md` - ESP32 hardware integration

### Useful Commands

```bash
# Backend
python main_fastapi.py                    # Start backend
python parking_monitor_worker.py          # Start worker
python -c "import torch; print(torch.cuda.is_available())"  # Test CUDA

# Frontend
npm run dev                               # Development server
npm run build                             # Production build
npm run preview                           # Preview build

# ESP32
python ESP32/start_mock.py                # Start mock server
python ESP32/test_esp32_connection.py     # Test connection

# Database
# Access Firestore: https://console.firebase.google.com/
```

### Development Tips

1. **Use Mock ESP32**: Faster iteration without hardware
2. **Lower FPS**: Start with 5 FPS for easier debugging
3. **Disable Firebase Writes**: Faster worker for testing
4. **Enable Debug Logging**: More verbose output
5. **Use Small Model**: YOLOv8n for faster inference

### Testing Checklist

- [ ] Backend starts without errors
- [ ] AI models load successfully
- [ ] Firebase connects
- [ ] ESP32 mock server running
- [ ] Worker detects cameras
- [ ] Frontend loads
- [ ] Can login/register
- [ ] Can view detection stream
- [ ] Can draw parking spaces
- [ ] Detections match to spaces
- [ ] WebSocket updates work

---

## 🎓 Next Steps

After successful setup:

1. **Create Admin Account**: Register and set role to "admin" in Firestore
2. **Add Parking Lot**: Go to `/parking-management` and create lot
3. **Add Cameras**: Configure camera streams
4. **Define Spaces**: Use parking space editor
5. **Enable Worker**: Set `workerEnabled: true` for cameras
6. **Monitor**: View worker dashboard at `/worker-monitor`

For production deployment:
- Set up HTTPS/WSS
- Configure reverse proxy (Nginx)
- Set up systemd services
- Configure automated backups
- Set up monitoring/alerting

Enjoy your Smart Parking System! 🚗🅿️
