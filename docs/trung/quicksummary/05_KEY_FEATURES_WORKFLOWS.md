# Smart Parking System - Key Features & Workflows

## 🎯 Core Features

### 1. Multi-Camera Parking Monitoring

**Description**: Monitor multiple parking cameras simultaneously with real-time detection and tracking.

**Key Components**:
- Worker process monitors all active cameras
- Each camera has independent detection pipeline
- Aggregated statistics across all cameras
- Per-camera configuration (FPS, resolution, etc.)

**Workflow**:
```
1. Admin enables cameras in Firebase
   └─> Set workerEnabled: true for cameras
   
2. Worker discovers active cameras
   └─> Queries Firebase for workerEnabled cameras
   └─> Starts monitoring each camera
   
3. For each camera (parallel processing):
   ├─> Fetch frame from ESP32/video source
   ├─> Run YOLO detection (GPU)
   ├─> Apply ByteTrack tracking
   ├─> Match detections to parking spaces
   ├─> Draw annotations
   ├─> Broadcast to viewers
   └─> Log results
   
4. Users view streams
   └─> WebSocket connection
   └─> Real-time annotated frames
   └─> Per-camera statistics
```

**Technical Details**:
```python
# Worker processes cameras concurrently
async def monitor_all_cameras():
    cameras = await get_active_cameras()
    
    # Process all cameras in parallel
    tasks = [
        process_camera(camera)
        for camera in cameras
    ]
    
    await asyncio.gather(*tasks, return_exceptions=True)
```

---

### 2. Parking Space Editor

**Description**: Interactive tool for defining parking spaces on camera feeds.

**User Interface**:
- Canvas overlay on live camera feed
- Draw mode: Click and drag to create rectangles
- Edit mode: Drag to move, resize with corner handles
- Space naming and metadata
- Batch operations (save all, clear all)

**Data Structure**:
```typescript
interface ParkingSpaceDefinition {
  id: string;
  parkingLotId: string;
  cameraId: string;
  name: string;
  // Normalized coordinates (0-1)
  x: number;
  y: number;
  width: number;
  height: number;
  occupied: boolean;
  lastUpdated: timestamp;
}
```

**Workflow**:
```
1. Admin navigates to /parking-spaces
   
2. Select parking lot and camera
   └─> Load live camera feed
   
3. Draw parking spaces
   ├─> Click and drag on canvas
   ├─> Rectangle appears with normalized coordinates
   ├─> Name the space (e.g., "A1", "B5")
   └─> Repeat for all spaces
   
4. Save to Firebase
   └─> Batch save all spaces
   └─> Store in parkingSpaceDefinitions collection
   
5. Worker uses spaces for detection
   └─> Load spaces from cache
   └─> Match vehicles to spaces (IoU)
   └─> Update occupancy status
```

**Why Normalized Coordinates?**
- Frame size independent (works with any resolution)
- Easy to scale for different displays
- Consistent across different video sources

**IoU Matching Logic**:
```python
def match_vehicle_to_space(vehicle_bbox, space_bbox):
    """
    Check if vehicle overlaps with parking space
    using Intersection over Union (IoU)
    """
    iou = calculate_iou(vehicle_bbox, space_bbox)
    
    if iou > 0.3:  # 30% overlap threshold
        return "OCCUPIED"
    else:
        return "EMPTY"
```

---

### 3. Real-Time Detection Viewer

**Description**: Live view of AI detection results with WebSocket streaming.

**Architecture**:
```
┌──────────────┐
│   Worker     │ Runs detection once
│   (GPU)      │
└──────┬───────┘
       │
       ↓
┌──────────────────┐
│ DetectionBroad-  │ Manages viewers
│ caster Service   │
└──────┬───────────┘
       │
       ├─────────┬─────────┬─────────┐
       ↓         ↓         ↓         ↓
   [View1]   [View2]   [View3]   [ViewN]
   
Benefits:
✅ Single detection → Unlimited viewers
✅ No extra GPU load
✅ Real-time streaming
✅ Efficient resource usage
```

**WebSocket Protocol**:
```typescript
// Connect to detection stream
const ws = new WebSocket(
  `ws://localhost:8069/ws/viewer/detection?camera_id=cam1&user_id=uid`
);

// Receive frames
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  /*
  {
    type: "frame",
    camera_id: "cam1",
    frame: "base64_encoded_jpeg",
    metadata: {
      detected_count: 5,
      occupied_spaces: 3,
      total_spaces: 10,
      timestamp: "2026-01-07T10:30:00Z"
    }
  }
  */
};
```

**Frontend Display**:
```tsx
function DetectionViewer({ cameraId }: Props) {
  const [frame, setFrame] = useState<string | null>(null);
  const [stats, setStats] = useState(null);
  
  useEffect(() => {
    const ws = new WebSocket(`ws://...?camera_id=${cameraId}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setFrame(data.frame);
      setStats(data.metadata);
    };
    
    return () => ws.close();
  }, [cameraId]);
  
  return (
    <div>
      <img src={`data:image/jpeg;base64,${frame}`} />
      <div>Detected: {stats?.detected_count} vehicles</div>
      <div>Occupied: {stats?.occupied_spaces}/{stats?.total_spaces}</div>
    </div>
  );
}
```

---

### 4. ByteTrack Multi-Object Tracking

**Description**: Persistent tracking of vehicles across frames with unique IDs.

**How ByteTrack Works**:
1. **Detection**: YOLO detects vehicles in each frame
2. **Tracking**: ByteTrack matches detections across frames
3. **ID Assignment**: Each vehicle gets unique track ID
4. **Trajectory**: Track history stored (last 30 points)
5. **Visualization**: Draw tracking trails on video

**Benefits**:
- ✅ Consistent vehicle identification
- ✅ Count vehicles entering/exiting
- ✅ Track parking duration
- ✅ Analyze movement patterns
- ✅ Better than detection-only (reduces false positives)

**Configuration**:
```yaml
bytetrack:
  track_high_thresh: 0.6      # High confidence detections
  track_low_thresh: 0.1       # Low confidence detections
  new_track_thresh: 0.7       # Threshold for new tracks
  track_buffer: 30            # Keep lost tracks for 30 frames
  match_thresh: 0.8           # Matching threshold

visualization:
  draw_trails: true           # Show movement trails
  trail_length: 30            # 30 points in trail
  draw_labels: true           # Show track IDs
```

**Example Output**:
```
Frame 1: Detected car at (100, 100) → Assigned track_id=1
Frame 2: Detected car at (105, 102) → Matched to track_id=1
Frame 3: Detected car at (110, 104) → Matched to track_id=1
Frame 4: Car leaves frame → track_id=1 buffered for 30 frames
Frame 5-34: If car reappears, still track_id=1
Frame 35: track_id=1 deleted if not seen
```

**API Usage**:
```python
# Enable tracking in detection
detections = await ai_service.detect_objects(
    frame,
    use_tracking=True  # Enable ByteTrack
)

# Each detection now has track_id
for det in detections:
    print(f"Track ID: {det['track_id']}")
    print(f"Class: {det['class_name']}")
    print(f"Confidence: {det['confidence']}")
```

---

### 5. License Plate Recognition (ALPR)

**Description**: Automatic license plate detection and text recognition.

**Two-Stage Pipeline**:

**Stage 1: Plate Detection**
- Model: YOLO v9 tiny (specialized for plates)
- Input: Full vehicle image
- Output: Bounding box of license plate

**Stage 2: OCR (Text Recognition)**
- Model: Mobile ViT v2 (optimized for plates)
- Input: Cropped plate image
- Output: Plate text + confidence

**Workflow**:
```
1. User captures frame or uploads image
   └─> Frontend: POST /api/plate-detect
   
2. Backend processes image
   ├─> Detect vehicles (YOLO)
   ├─> For each vehicle:
   │   ├─> Crop vehicle region
   │   ├─> Detect plate location
   │   ├─> Crop plate region
   │   ├─> Run OCR
   │   └─> Return plate text
   └─> Save to Firebase
   
3. Frontend displays results
   └─> Show plate text
   └─> Show confidence score
   └─> Store in plate history
```

**API Endpoint**:
```python
@router.post("/api/plate-detect")
async def detect_license_plate(
    image_data: str  # Base64 encoded image
) -> Dict[str, Any]:
    """
    Detect and recognize license plates
    
    Returns:
    {
      "success": true,
      "plates": [
        {
          "text": "30A-12345",
          "confidence": 0.95,
          "bbox": {"x": 100, "y": 50, "w": 150, "h": 50}
        }
      ],
      "vehicle_count": 3,
      "timestamp": "2026-01-07T10:30:00Z"
    }
    """
```

**Use Cases**:
- Entry/exit logging
- Parking validation (authorized vehicles)
- Security alerts (unauthorized vehicles)
- Billing integration
- Historical search

---

### 6. Worker Monitor Dashboard

**Description**: Admin dashboard for monitoring worker status and performance.

**Dashboard Sections**:

**1. Live Detection Streams**
- Grid view of all active cameras
- Real-time annotated video
- Per-camera statistics

**2. Detection & Tracking Stats**
```
┌─────────────────────────────────────┐
│  Total Vehicles Detected: 42        │
│  Total Parking Spaces: 150          │
│                                     │
│  Camera Breakdown:                  │
│  ├─ Cam 1: 15 vehicles, 45 spaces  │
│  │   • Occupied: 12                │
│  │   • Available: 33               │
│  ├─ Cam 2: 12 vehicles, 50 spaces  │
│  └─ Cam 3: 15 vehicles, 55 spaces  │
└─────────────────────────────────────┘
```

**3. ByteTrack Configuration**
- Current tracking parameters
- Performance settings
- FPS and image size
- Device (CUDA/CPU)

**4. System Information**
```
┌─────────────────────────────────────┐
│  GPU Acceleration: ✅ ENABLED       │
│  Device: NVIDIA RTX 3080            │
│  VRAM: 10 GB                        │
│                                     │
│  AI Models:                         │
│  • YOLO v8: ✅ Loaded               │
│  • ByteTrack: ✅ Active             │
│  • Fast-ALPR: ✅ Ready              │
│                                     │
│  Backend Services:                  │
│  • FastAPI: ✅ Running              │
│  • Worker: ✅ Active                │
│  • Firebase: ✅ Connected           │
└─────────────────────────────────────┘
```

**Real-Time Updates**:
- WebSocket connection for live stats
- Auto-refresh detection counts
- Connection status indicators

---

### 7. Detection History & Analytics

**Description**: Historical data storage and analysis.

**Data Storage**:
```
Firebase Collections:
├─ detections/           # All detection events
├─ plateHistory/         # Plate recognition records
├─ alerts/              # System alerts
└─ workerStatus/        # Worker monitoring data
```

**Query Examples**:
```typescript
// Get detection history
const history = await apiService.getDetectionHistory({
  camera_id: "cam1",
  start_date: "2026-01-01",
  end_date: "2026-01-07",
  limit: 100
});

// Search plate history
const plates = await apiService.searchPlates({
  plate_text: "30A",  // Partial match
  date_range: ["2026-01-01", "2026-01-07"]
});

// Get statistics
const stats = await apiService.getParkingStats({
  camera_id: "cam1",
  period: "week"
});
```

**Analytics Features**:
- Occupancy trends over time
- Peak hours analysis
- Average parking duration
- Vehicle type distribution
- Plate frequency analysis

**Visualization**:
- Line charts for trends
- Bar charts for comparisons
- Pie charts for distributions
- Heatmaps for occupancy patterns

---

### 8. ESP32-CAM Integration

**Description**: Support for ESP32-CAM hardware cameras.

**Hardware Setup**:
```
ESP32-CAM Module
├─ Camera: OV2640 (2MP)
├─ WiFi: 2.4GHz 802.11 b/g/n
├─ Power: 5V via USB or external
└─ Streaming: MJPEG over HTTP
```

**Firmware Features**:
- Auto-connect to WiFi
- MJPEG streaming server
- Configurable resolution
- Frame rate control
- LED control

**Development vs Production**:

**Development (Mock Server)**:
```bash
# Start mock ESP32 server
python ESP32/start_mock.py --video parking.mp4 --port 5069

# Benefits:
✅ No hardware needed
✅ Use video files for testing
✅ Reproducible testing
✅ Faster development
```

**Production (Real Hardware)**:
```bash
# Flash firmware to ESP32-CAM
1. Open Arduino IDE
2. Load ESP32/esp32_cam_firmware.ino
3. Configure WiFi credentials
4. Upload to board

# Update backend to use real ESP32
export ESP32_URL=http://192.168.1.100:81
```

**Stream Endpoints**:
```
Mock Server:
GET http://localhost:5069/stream     # MJPEG stream
GET http://localhost:5069/capture    # Single frame

Real ESP32:
GET http://192.168.1.100:81/stream   # MJPEG stream
GET http://192.168.1.100:81/capture  # Single frame
```

---

### 9. Alert System

**Description**: Automated alerts for parking anomalies.

**Alert Types**:

**1. Wrong Parking**
- Vehicle not in designated space
- IoU < threshold with any space
- Severity: Medium

**2. Unregistered Vehicle**
- License plate not in database
- Plate not found in Firebase
- Severity: High

**3. Overstay**
- Parking duration > limit
- Time in space > threshold
- Severity: Low to Medium

**4. Parking Lot Full**
- Occupancy > 95%
- No available spaces
- Severity: Low

**Alert Workflow**:
```
1. Worker detects anomaly
   └─> Check conditions
   
2. Create alert
   └─> Save to Firebase alerts collection
   
3. Notify users
   └─> Real-time listener triggers UI update
   └─> Optional: Email notification (future)
   
4. Admin reviews alert
   └─> Mark as resolved
   └─> Update alert status
```

**Alert Data Structure**:
```typescript
interface Alert {
  id: string;
  type: 'wrong_parking' | 'unregistered' | 'overstay' | 'lot_full';
  severity: 'low' | 'medium' | 'high';
  cameraId: string;
  vehicleId?: string;
  plateText?: string;
  message: string;
  timestamp: Date;
  resolved: boolean;
  resolvedBy?: string;
  resolvedAt?: Date;
}
```

---

### 10. User Management & Authentication

**Description**: Secure user authentication with role-based access.

**Authentication Flow**:
```
1. User Registration
   ├─> Frontend: Firebase Auth signup
   ├─> Create user in Firebase Auth
   ├─> Store user profile in Firestore
   └─> Set default role: "user"
   
2. User Login
   ├─> Frontend: Firebase Auth signin
   ├─> Receive JWT token
   ├─> Fetch user role from Firestore
   └─> Store in AuthContext
   
3. Protected Routes
   ├─> Check if user is authenticated
   ├─> Check if user has required role
   └─> Allow/deny access
```

**Role-Based Access Control**:

**User Role**:
- ✅ View own cameras
- ✅ View parking availability
- ✅ View detection history (own cameras)
- ❌ Cannot edit parking spaces
- ❌ Cannot view all cameras
- ❌ Cannot access admin features

**Admin Role**:
- ✅ All user permissions
- ✅ Add/edit/delete cameras
- ✅ Define parking spaces
- ✅ View all detection data
- ✅ Manage alerts
- ✅ Access worker dashboard

**Security Implementation**:
```typescript
// Frontend: Protected Route
<ProtectedRoute requireAdmin>
  <ParkingSpaceEditorPage />
</ProtectedRoute>

// Firestore Security Rules
match /parkingSpaceDefinitions/{spaceId} {
  allow read: if request.auth != null;
  allow write: if request.auth.token.role == "admin";
}
```

---

## 🔄 Complete System Workflows

### Workflow 1: Setup New Parking Lot

```
1. Admin creates parking lot
   └─> Go to /parking-management
   └─> Add new parking lot
   └─> Enter name, location, capacity
   
2. Add cameras to parking lot
   └─> Add camera configurations
   └─> Set stream URLs
   └─> Enable cameras
   
3. Define parking spaces
   └─> Go to /parking-spaces
   └─> Select parking lot & camera
   └─> Draw parking space rectangles
   └─> Name each space
   └─> Save to Firebase
   
4. Enable worker monitoring
   └─> Set workerEnabled: true for cameras
   └─> Worker automatically starts monitoring
   
5. Users can now view
   └─> Real-time occupancy
   └─> Detection streams
   └─> Historical data
```

### Workflow 2: Daily Operations

```
1. Worker continuously monitors (24/7)
   ├─> Fetch frames from all cameras
   ├─> Run AI detection
   ├─> Update parking space status
   └─> Broadcast to viewers
   
2. Users view real-time status
   ├─> Open detection viewer
   ├─> Select camera
   └─> Watch live annotated stream
   
3. Vehicles enter/exit
   ├─> Worker detects change
   ├─> Updates occupancy status
   ├─> Logs event to history
   └─> Triggers alerts if needed
   
4. Admin monitors dashboard
   ├─> View all cameras
   ├─> Check system health
   ├─> Review alerts
   └─> Analyze statistics
```

### Workflow 3: License Plate Search

```
1. Admin searches for plate
   └─> Go to /plate-history
   └─> Enter plate number (partial match OK)
   
2. System queries Firebase
   └─> Search plateHistory collection
   └─> Filter by plate text
   └─> Return matching records
   
3. Display results
   ├─> List of all occurrences
   ├─> Timestamps
   ├─> Camera locations
   └─> Vehicle images (if available)
   
4. Export data
   └─> Download CSV
   └─> Include all details
```

These features work together to provide a comprehensive parking management solution with real-time monitoring, historical analysis, and intelligent automation.
