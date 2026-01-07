# Smart Parking System - Project Overview

## 🎯 Project Summary

**Smart Parking System** is an AI-powered parking management solution that provides real-time vehicle detection, license plate recognition, object tracking, and automated parking space monitoring. The system uses computer vision and deep learning to manage parking lots efficiently.

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                           │
│  Frontend (React + TypeScript + Vite) - Port 5169               │
│  - Multi-camera monitoring dashboard                             │
│  - Real-time parking space visualization                         │
│  - Detection history and analytics                               │
│  - Parking space editor for administrators                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓ ↑
                      (REST API + WebSocket)
                              ↓ ↑
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND SERVICES                            │
│  FastAPI Server (Python) - Port 8069                            │
│  ├─ AI Detection Service (YOLO + ByteTrack)                     │
│  ├─ License Plate Recognition (ALPR)                            │
│  ├─ Stream Broadcasting Service                                 │
│  ├─ Firebase Integration Service                                │
│  └─ Parking Monitor Worker (Background Process)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓ ↑
            ┌─────────────────┴──────────────┐
            ↓                                ↓
┌────────────────────────┐      ┌────────────────────────┐
│   VIDEO SOURCES        │      │   DATA STORAGE         │
│  ESP32-CAM Cameras     │      │  Firebase/Firestore    │
│  - Port 5069 (Mock)    │      │  - User data           │
│  - Port 81 (Real HW)   │      │  - Detection history   │
│  - Multiple cameras    │      │  - Parking spaces      │
└────────────────────────┘      │  - Plate records       │
                                └────────────────────────┘
```

## 🎭 Key Features

### 1. **Multi-Camera Monitoring**
- Support for multiple ESP32-CAM cameras
- Real-time video streaming (MJPEG)
- Mock server for development (video file playback)
- Hardware integration for production

### 2. **AI-Powered Detection**
- **Object Detection**: YOLOv8/v11 for vehicle detection
- **License Plate Recognition**: Fast-ALPR for plate reading
- **Object Tracking**: 
  - **Single-Camera (MOT)**: ByteTrack for tracking within one camera
  - **Multi-Camera (MTMC)**: NEW - Global ID assignment across all cameras
- **ReID (Re-Identification)**: ResNet50/MobileNetV4 for cross-camera matching
- **GPU Acceleration**: CUDA support for high performance

### 3. **Parking Space Management**
- Interactive parking space editor
- Draw and define parking spaces on camera feeds
- Automatic occupancy detection (IoU-based matching)
- Real-time occupancy status updates

### 4. **Real-Time Monitoring**
- WebSocket-based live streaming
- Multiple viewers can watch same stream without extra GPU load
- Detection broadcaster system for efficient resource usage
- Real-time parking space visualization with color coding:
  - 🟢 Green: Available spaces
  - 🔴 Red: Occupied spaces
  - 🟡 Yellow: Moving vehicles/Alerts

### 5. **Historical Data & Analytics**
- Detection history logging
- Plate recognition history
- Statistical analysis of parking usage
- Alert system for anomalies

### 6. **User Management**
- Firebase Authentication
- Role-based access control (User/Admin)
- User-specific camera configurations
- Secure data isolation

## 🛠️ Technology Stack

### Frontend
- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite
- **UI Library**: Tailwind CSS + Shadcn/UI
- **State Management**: React Context API
- **Real-time**: Firebase SDK (Firestore listeners)
- **Routing**: React Router v6
- **Canvas**: HTML5 Canvas API for 2D visualization

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **AI/ML**: 
  - Ultralytics YOLO (v8/v11)
  - ByteTrack for single-camera object tracking
  - Fast-ALPR for license plate recognition
  - **NEW: Multi-Camera Tracking (MTMC)** - `vehicle_mtmc/` directory
    - ReID models: ResNet50-IBN, MobileNetV4, EfficientNet-B0
    - Hierarchical clustering for global ID assignment
    - ONNX/TensorRT optimization for speed
- **Computer Vision**: OpenCV (cv2)
- **GPU**: PyTorch with CUDA support
- **Database**: Firebase/Firestore
- **Async**: asyncio, aiohttp
- **Video Processing**: MJPEG streaming

### Hardware/IoT
- **Camera**: ESP32-CAM modules
- **Firmware**: Arduino-based ESP32 firmware
- **Streaming**: MJPEG over HTTP
- **Mock**: Python-based mock server for development

### Infrastructure
- **Python Environment**: Conda (scheduler environment)
- **Package Manager**: npm (frontend), pip (backend)
- **Development**: Local development with hot reload
- **Ports**:
  - Frontend: 5169
  - Backend: 8069
  - ESP32 Mock: 5069
  - ESP32 Hardware: 81

## 📊 System Workflow

### Complete Flow: From Camera to Display

```
1. VIDEO CAPTURE
   ESP32-CAM captures video
   └─> Streams MJPEG frames over HTTP
   
2. BACKEND PROCESSING
   Worker fetches frames periodically
   ├─> YOLOv8 detects vehicles (GPU)
   ├─> ByteTrack assigns tracking IDs
   ├─> Matches detections to parking spaces (IoU)
   └─> Updates occupancy status
   
3. BROADCASTING
   Detection frames broadcasted to viewers
   ├─> Base64 encoded JPEG
   ├─> WebSocket delivery
   └─> Multiple viewers receive same frame (no extra GPU load)
   
4. FRONTEND DISPLAY
   React app renders real-time data
   ├─> Video stream with bounding boxes
   ├─> Parking space overlay
   ├─> Statistics and alerts
   └─> Historical data charts
   
5. DATA PERSISTENCE
   Firebase stores all data
   ├─> Detection logs
   ├─> Parking space definitions
   ├─> Plate recognition results
   └─> User configurations
```

## 🎯 Core Use Cases

### Use Case 1: Parking Space Monitoring
1. Admin defines parking spaces using editor
2. Worker continuously processes camera feeds
3. Vehicles detected and tracked in real-time
4. Occupancy status updated automatically
5. Users view real-time parking availability

### Use Case 2: License Plate Recognition
1. Vehicle enters parking lot
2. Camera captures vehicle image
3. YOLO detects vehicle bounding box
4. ALPR recognizes license plate text
5. Plate stored in database with timestamp
6. Admin can search plate history

### Use Case 3: Multi-Camera Dashboard
1. Admin adds multiple cameras to system
2. Each camera has defined parking spaces
3. Worker monitors all cameras simultaneously
4. Dashboard shows aggregated statistics
5. Users can switch between camera views

### Use Case 4: Detection Viewer
1. User connects to detection stream
2. WebSocket establishes connection
3. Receives annotated frames with:
   - Vehicle bounding boxes
   - Parking space overlays
   - Tracking IDs
   - Confidence scores
4. Multiple users can watch concurrently

## 🔐 Security & Access Control

### Role-Based Access
- **User Role**: 
  - View own camera feeds
  - View parking availability
  - Access personal detection history
  
- **Admin Role**:
  - All user permissions
  - Add/remove cameras
  - Define parking spaces
  - View all detection logs
  - Manage user accounts

### Firebase Security
- Authentication via Firebase Auth
- Firestore security rules enforce access control
- API key exposure is safe (client-side keys)
- Backend uses Admin SDK with service account

## 📈 Performance Characteristics

### Processing Speed
- **Object Detection**: 20-30 FPS (with GPU)
- **Tracking**: ByteTrack adds ~5ms per frame
- **Plate Recognition**: 200-500ms per detection
- **Stream Latency**: ~100-300ms

### Resource Usage
- **GPU Memory**: ~2-4GB VRAM (YOLOv8n-s)
- **CPU**: Minimal when using GPU
- **Network**: ~1-2 Mbps per video stream
- **Storage**: Logs stored in files, metadata in Firebase

### Scalability
- **Cameras**: Supports multiple cameras (tested with 5+)
- **Viewers**: Unlimited concurrent viewers per camera
- **Detection Rate**: Configurable FPS (1-30)
- **Storage**: Firebase can handle millions of documents

## 🚀 Deployment Options

### Development Mode
- Mock ESP32 server (video files)
- Local Firebase emulator (optional)
- Hot reload for frontend/backend
- Debug logging enabled

### Production Mode
- Real ESP32-CAM hardware
- Firebase production instance
- HTTPS/WSS for security
- Performance optimizations enabled
- Logging to files

## 📝 Documentation Structure

The project includes extensive documentation:
- **README.md**: Main project documentation
- **docs/**: Comprehensive guides
  - Architecture diagrams
  - Integration guides
  - API documentation
  - Performance tuning
  - Worker monitoring
  - Troubleshooting
- **ESP32/**: Hardware setup guides
- **frontend/**: UI component documentation
- **server/**: Backend API documentation

## 🎓 Learning Curve

### For Users
- **Easy**: Basic monitoring and viewing
- **Moderate**: Camera configuration
- **Advanced**: Parking space editing

### For Developers
- **Frontend**: React + TypeScript knowledge required
- **Backend**: Python, FastAPI, async programming
- **AI/ML**: Understanding of YOLO, object detection concepts
- **Hardware**: ESP32 programming (for hardware integration)

## 🔄 Development Workflow

1. **Setup Environment**: Install dependencies (Conda, npm)
2. **Start Mock ESP32**: Provide video source
3. **Start Backend**: FastAPI server with AI models
4. **Start Worker**: Background monitoring process
5. **Start Frontend**: React development server
6. **Test Features**: Use browser to interact
7. **Monitor Logs**: Check console output for issues
8. **Deploy**: Move to production with real hardware

## 🎨 Project Highlights

### What Makes This Project Special?
- ✅ **Modular Architecture**: Clean separation of concerns
- ✅ **Real-time Processing**: WebSocket streaming with low latency
- ✅ **GPU Optimization**: Efficient use of CUDA for AI inference
- ✅ **Scalable Broadcasting**: One detection → many viewers
- ✅ **Professional UI**: Modern React with Tailwind CSS
- ✅ **Comprehensive Docs**: Well-documented codebase
- ✅ **Development Tools**: Mock servers for testing
- ✅ **Production Ready**: Supports real hardware integration

## 🎯 Project Goals

### Primary Objectives
1. Automated parking space monitoring
2. Real-time vehicle detection and tracking
3. License plate recognition
4. Multi-camera support
5. User-friendly web interface

### Secondary Objectives
1. Historical data analysis
2. Alert system for anomalies
3. Performance optimization
4. Scalability for large deployments
5. Easy hardware integration

## 📊 Current Status

The project is **production-ready** with:
- ✅ Core features implemented
- ✅ Multi-camera support working
- ✅ Real-time detection and tracking
- ✅ Web interface complete
- ✅ Hardware integration tested
- ✅ Documentation comprehensive
- ⚠️ Some features marked as "future enhancements"

## 🔮 Future Enhancements

Mentioned in documentation:
- Vehicle classification (car vs motorcycle vs truck)
- Advanced analytics dashboard
- Mobile app
- Email notifications
- Integration with payment systems
- Cloud deployment options
- Multi-language support
