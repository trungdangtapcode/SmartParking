# Unified Parking Space System - Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SMART PARKING SYSTEM                              │
│                     (Unified Parking Space Format)                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│               │          │               │          │               │
│ LiveDetection │          │ ParkingSpace  │          │   Background  │
│   (AI Auto)   │          │    Editor     │          │    Worker     │
│               │          │  (Manual)     │          │  (Monitor)    │
└───────┬───────┘          └───────┬───────┘          └───────┬───────┘
        │                          │                          │
        │ Saves                    │ Saves                    │ Reads
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │      FIREBASE FIRESTORE      │
                    │                              │
                    │  parkingSpaceDefinitions     │
                    │  (Normalized Coordinates)    │
                    │                              │
                    │  Format: 0-1 range           │
                    │  Resolution Independent      │
                    └──────────────┬───────────────┘
                                   │
                                   │ Updates
                                   ▼
                    ┌──────────────────────────────┐
                    │      FIREBASE FIRESTORE      │
                    │                              │
                    │      parkingSpaces           │
                    │   (Runtime Occupancy)        │
                    │                              │
                    │  Updated by Worker           │
                    │  Read by Dashboard           │
                    └──────────────────────────────┘
```

## Data Flow

### 1. AI Detection Flow (LiveDetection)

```
User Action                    System Processing
───────────                    ─────────────────

1. Select Parking Lot     →    Load parking lots from Firebase
   (Dropdown)                   GET parkingLots WHERE ownerId = user.uid

2. Select Camera          →    Load ESP32 configs from Firebase
   (Dropdown)                   GET esp32_configs WHERE userId = user.uid

3. Upload Image           →    Load image into browser
   (File/Camera)               Extract dimensions (width x height)

4. Click "Detect"         →    Send to AI Service
                               YOLO model detects parking spaces
                               Returns: [bbox: [x, y, w, h], confidence]

5. Review Results         →    Display boxes on canvas
                               Show confidence scores
                               Allow manual adjustments

6. Click "Save"           →    Convert to normalized format:
                               {
                                 id: "CAM001_space_123_0",
                                 parkingId: "PARKING_A",
                                 cameraId: "CAM001",
                                 name: "P1",
                                 x: bbox[0] / imgWidth,      ← Normalize!
                                 y: bbox[1] / imgHeight,     ← Normalize!
                                 width: bbox[2] / imgWidth,  ← Normalize!
                                 height: bbox[3] / imgHeight,← Normalize!
                                 createdBy: user.uid
                               }
                               
                               Save to parkingSpaceDefinitions
                               BATCH_WRITE parkingSpaceDefinitions
                               
                               ✅ Success message with link to Editor
```

### 2. Manual Editing Flow (ParkingSpaceEditor)

```
User Action                    System Processing
───────────                    ─────────────────

1. Select Parking Lot     →    Load parking lots from Firebase
   (Dropdown)                   GET parkingLots WHERE ownerId = user.uid

2. Select Camera          →    Load ESP32 configs + existing spaces
                               GET esp32_configs WHERE userId = user.uid
                               GET parkingSpaceDefinitions 
                                   WHERE cameraId = selected

3. View Canvas            →    Load camera MJPEG stream
                               Draw existing spaces (scaled):
                               x_pixel = space.x * stream_width
                               y_pixel = space.y * stream_height

4. Edit Spaces            →    User actions:
   - Drag                      • Move: Update x, y (keep normalized)
   - Resize                    • Resize: Update width, height
   - Rename                    • Rename: Update name field
   - Delete                    • Delete: Remove from array
   - Add new                   • Add: Draw new box, convert to normalized

5. Click "Save"           →    Batch save all spaces
                               UPDATE parkingSpaceDefinitions
                               SET spaces = updated_spaces
                               WHERE cameraId = selected
                               
                               ✅ Success message
```

### 3. Background Monitoring Flow (Worker)

```
Worker Process                 System Processing
──────────────                 ─────────────────

1. Start Worker           →    Load configuration
   python worker.py            ENV: ENABLE_PARKING_MONITOR=true
                                    MONITOR_CHECK_INTERVAL=5

2. Query Active Cameras   →    Query Firebase for enabled cameras
                               GET parkingLots WHERE status='active'
                               FOR EACH lot.cameras:
                                 GET esp32_configs WHERE id = camera
                                 IF workerEnabled = true:
                                   Add to processing queue

3. For Each Camera        →    Processing pipeline:
                               
   a) Fetch Frame              HTTP GET {camera_url}/capture
                               Returns: JPEG bytes
   
   b) Decode Image             OpenCV: cv2.imdecode(frame_bytes)
                               Get dimensions: frame.shape = [H, W]
   
   c) Run YOLO                 model.predict(frame)
                               Returns: [{bbox: [x,y,w,h], class, conf}]
   
   d) Normalize Coords         detections_norm = [
                                 {
                                   x: det.x / frame_width,
                                   y: det.y / frame_height,
                                   width: det.w / frame_width,
                                   height: det.h / frame_height
                                 }
                               ]
   
   e) Load Space Defs          GET parkingSpaceDefinitions
                               WHERE cameraId = camera.id
                               Already in normalized format!
   
   f) Match IoU                FOR detection IN detections_norm:
                                 FOR space IN spaces:
                                   iou = calculate_iou(detection, space)
                                   IF iou > 0.5:
                                     MATCH found
   
   g) Update Occupancy         UPDATE parkingSpaces
                               SET occupied = true/false
                                   lastChecked = now()
                                   vehicleDetected = {...}
                               WHERE spaceId = space.id

4. Sleep & Repeat         →    await asyncio.sleep(CHECK_INTERVAL)
                               GOTO step 2
```

## Coordinate System

### Normalized Coordinates (0-1 Range)

```
Image/Frame:               Normalized Space:
┌───────────────┐         ┌───────────────┐
│ 0,0           │ 1920px  │ 0,0           │ 1.0
│               │         │               │
│    ┌─────┐    │         │    ┌─────┐    │
│    │Space│    │         │    │ x,y │    │ 
│    │ P1  │    │  →      │    │0.5, │    │
│    └─────┘    │         │    │0.3  │    │
│               │         │    └─────┘    │
│               │ 1080px  │               │ 1.0
└───────────────┘         └───────────────┘

Space Coordinates:
Pixel:       [960,  324,  150, 200]
             [x,    y,    w,   h  ]

Normalized:  [0.5,  0.3,  0.078, 0.185]
             [x/W,  y/H,  w/W,   h/H  ]

Benefits:
✅ Works with 640x480 camera
✅ Works with 1920x1080 camera
✅ Works with any resolution
✅ Smaller database storage
```

## Database Schema

### Collection: `parkingSpaceDefinitions`

```
Document ID: {cameraId}_space_{timestamp}_{index}

{
  "id": "ESP32_001_space_1704470400000_0",
  "parkingId": "PARKING_A",
  "cameraId": "ESP32_001",
  "name": "P1",
  
  // Normalized coordinates (0-1 range)
  "x": 0.15,        // 15% from left edge
  "y": 0.20,        // 20% from top edge
  "width": 0.12,    // 12% of image width
  "height": 0.18,   // 18% of image height
  
  "createdBy": "user_abc123",
  "createdAt": Timestamp(2024-01-05 10:00:00),
  "updatedAt": Timestamp(2024-01-05 10:00:00)
}

Indexes:
- cameraId (for quick lookup)
- parkingId (for parking lot queries)
- createdBy (for user queries)
```

### Collection: `parkingSpaces` (Runtime State)

```
Document ID: {parkingId}_{cameraId}_{spaceId}

{
  "parkingId": "PARKING_A",
  "cameraId": "ESP32_001",
  "spaceId": "ESP32_001_space_1704470400000_0",
  "spaceName": "P1",
  
  // Occupancy status
  "occupied": true,
  "lastChecked": Timestamp(2024-01-05 10:05:00),
  
  // Vehicle detection (if occupied)
  "vehicleDetected": {
    "bbox": [0.15, 0.20, 0.12, 0.18],  // Normalized
    "confidence": 0.92,
    "class": "car"
  }
}

Indexes:
- parkingId (for dashboard queries)
- occupied (for available space queries)
```

## Component Interaction

```
┌──────────────────────────────────────────────────────────────┐
│                       USER INTERFACE                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  LiveDetection Page          ParkingSpaceEditor Page         │
│  ┌────────────────┐          ┌────────────────┐             │
│  │                │          │                │             │
│  │  [Parking ▼]   │          │  [Parking ▼]   │             │
│  │  [Camera  ▼]   │          │  [Camera  ▼]   │             │
│  │                │          │                │             │
│  │  [Upload IMG]  │          │  [Live Stream] │             │
│  │                │          │                │             │
│  │  [🔍 Detect]  │────┐    │  [Draw Canvas] │             │
│  │                │    │    │                │             │
│  │  [💾 Save]    │────┼───→│  [💾 Save]    │             │
│  │                │    │    │                │             │
│  └────────────────┘    │    └────────────────┘             │
│                        │                                     │
└────────────────────────┼─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    FIREBASE LAYER                             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  parkingSpaceDefinitions (Source of Truth)                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │ Space P1: {x:0.15, y:0.20, w:0.12, h:0.18}        │     │
│  │ Space P2: {x:0.30, y:0.20, w:0.12, h:0.18}        │     │
│  │ Space P3: {x:0.45, y:0.20, w:0.12, h:0.18}        │     │
│  └────────────────────────────────────────────────────┘     │
│                        ▲ Write            │ Read             │
│                        │                  ▼                  │
│  ┌─────────────────────┴──────────────────────────────┐     │
│  │                                                     │     │
│  │  Frontend Services:                                │     │
│  │  • batchSaveParkingSpaces()    ← Save             │     │
│  │  • getParkingSpacesByCamera()  ← Load             │     │
│  │  • deleteParkingSpace()        ← Delete           │     │
│  │                                                     │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            │ Read
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    BACKEND WORKER                             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  parking_monitor_worker.py                                   │
│  ┌────────────────────────────────────────────────────┐     │
│  │                                                     │     │
│  │  1. Load spaces from parkingSpaceDefinitions      │     │
│  │  2. Fetch frame from camera                        │     │
│  │  3. Run YOLO detection                             │     │
│  │  4. Match detections to spaces (IoU)               │     │
│  │  5. Update parkingSpaces collection                │     │
│  │                                                     │     │
│  │  Loop every 5 seconds...                           │     │
│  │                                                     │     │
│  └────────────────────────────────────────────────────┘     │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

## File Structure

```
project/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── LiveDetection.tsx         ← AI detection (UPDATED)
│   │   ├── pages/
│   │   │   └── ParkingSpaceEditorPage.tsx ← Manual editing (No change)
│   │   ├── services/
│   │   │   ├── parkingSpaceService.ts    ← Unified CRUD
│   │   │   ├── esp32ConfigService.ts     ← Camera configs
│   │   │   └── parkingLotService.ts      ← Parking lots
│   │   └── types/
│   │       └── parkingLot.types.ts       ← Type definitions
│   
├── server/
│   ├── parking_monitor_worker.py         ← Background worker
│   └── services/
│       └── parking_space_service.py      ← Backend logic
│
└── docs/
    ├── UNIFIED_PARKING_SPACES.md         ← Complete guide (NEW)
    ├── UNIFIED_PARKING_SPACES_SUMMARY.md ← Quick summary (NEW)
    ├── PARKING_SPACE_EDITOR.md           ← Editor guide
    ├── PARKING_MONITOR_WORKER.md         ← Worker guide
    └── WORKER_CONTROL.md                 ← Worker control
```

## Key Algorithms

### IoU (Intersection over Union) Matching

```python
def calculate_iou(box1: Dict, box2: Dict) -> float:
    """
    Calculate IoU between two normalized boxes (0-1 range)
    
    Args:
        box1: {x, y, width, height}  # Normalized 0-1
        box2: {x, y, width, height}  # Normalized 0-1
    
    Returns:
        float: IoU score (0-1)
    """
    # Get box coordinates
    x1_min = box1['x']
    y1_min = box1['y']
    x1_max = box1['x'] + box1['width']
    y1_max = box1['y'] + box1['height']
    
    x2_min = box2['x']
    y2_min = box2['y']
    x2_max = box2['x'] + box2['width']
    y2_max = box2['y'] + box2['height']
    
    # Calculate intersection
    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)
    
    inter_width = max(0, inter_x_max - inter_x_min)
    inter_height = max(0, inter_y_max - inter_y_min)
    inter_area = inter_width * inter_height
    
    # Calculate union
    box1_area = box1['width'] * box1['height']
    box2_area = box2['width'] * box2['height']
    union_area = box1_area + box2_area - inter_area
    
    # Calculate IoU
    iou = inter_area / union_area if union_area > 0 else 0
    
    return iou

# Usage in matching
def match_detections_to_spaces(detections, spaces):
    matches = []
    
    for detection in detections:
        best_match = None
        best_iou = 0.5  # Threshold
        
        for space in spaces:
            iou = calculate_iou(detection, space)
            if iou > best_iou:
                best_iou = iou
                best_match = space
        
        if best_match:
            matches.append((detection, best_match, best_iou))
    
    return matches
```

## Summary

This unified system provides:

✅ **Single Source of Truth**: `parkingSpaceDefinitions` collection  
✅ **Resolution Independent**: Normalized coordinates (0-1)  
✅ **Seamless Workflow**: AI → Manual → Monitor  
✅ **User Friendly**: Dropdown selection, no typing  
✅ **Developer Friendly**: One format everywhere  
✅ **Production Ready**: Worker reads same data  

All components now work together harmoniously! 🎉
