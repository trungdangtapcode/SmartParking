# Smart Parking System - Technical Deep Dive

## 🧠 AI & Computer Vision Implementation

### YOLO Object Detection

**Model Architecture**: YOLOv8 (You Only Look Once version 8)

**Why YOLO?**
- ✅ Real-time performance (30+ FPS on GPU)
- ✅ Single-stage detector (faster than R-CNN)
- ✅ High accuracy (mAP 45%+)
- ✅ Easy to fine-tune
- ✅ Excellent community support

**Model Variants**:
```python
# Available models (trade-off: speed vs accuracy)
yolov8n.pt  # Nano:   3.2M params, 80 FPS, 37.3 mAP
yolov8s.pt  # Small:  11.2M params, 60 FPS, 44.9 mAP
yolov8m.pt  # Medium: 25.9M params, 40 FPS, 50.2 mAP
yolov8l.pt  # Large:  43.7M params, 25 FPS, 52.9 mAP
yolov8x.pt  # XLarge: 68.2M params, 15 FPS, 53.9 mAP
```

**Detection Pipeline**:
```python
# 1. Preprocessing
frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
resized = cv2.resize(frame_rgb, (640, 640))  # YOLO input size
normalized = resized / 255.0  # Normalize to [0, 1]

# 2. Inference (automatic in ultralytics)
results = model.predict(
    frame,
    conf=0.25,      # Confidence threshold
    iou=0.45,       # NMS IoU threshold
    classes=[2, 5, 7],  # car, bus, truck
    device='cuda',
    verbose=False
)

# 3. Post-processing (Non-Maximum Suppression)
# - Remove overlapping boxes (IoU > 0.45)
# - Keep only high confidence (> 0.25)
# - Return filtered detections

# 4. Output format
for detection in results[0].boxes:
    x1, y1, x2, y2 = detection.xyxy[0]  # Bounding box
    confidence = detection.conf[0]       # Confidence score
    class_id = detection.cls[0]          # Class ID
    class_name = model.names[class_id]   # Class name
```

**Custom Training** (if using yolov8s_car_custom.pt):
```python
# Training was done on custom dataset
# - Annotated parking lot images
# - Focus on cars, motorcycles
# - Various lighting conditions
# - Different camera angles

# Results: Better accuracy for parking scenarios
# - General YOLO: 45% mAP
# - Custom model: 60-70% mAP (parking lots)
```

### ByteTrack Multi-Object Tracking

**Algorithm Overview**:
1. **Detection**: Get all detections from YOLO
2. **Association**: Match detections to existing tracks
3. **Update**: Update track positions
4. **Management**: Handle new tracks, lost tracks

**Two-Stage Matching**:

**Stage 1: High Confidence Matching**
```python
# Match high confidence detections (> 0.6) to tracks
# using IoU (Intersection over Union)

for detection in high_conf_detections:
    for track in active_tracks:
        iou = calculate_iou(detection.bbox, track.bbox)
        if iou > 0.8:  # High threshold
            track.update(detection)
            matched_tracks.add(track)
            break
```

**Stage 2: Low Confidence Matching**
```python
# Match low confidence detections (0.1-0.6) to unmatched tracks
# Recover from occlusions, temporary losses

for detection in low_conf_detections:
    for track in unmatched_tracks:
        iou = calculate_iou(detection.bbox, track.bbox)
        if iou > 0.5:  # Lower threshold
            track.update(detection)
            recovered_tracks.add(track)
            break
```

**Track Management**:
```python
# New tracks
for detection in unmatched_detections:
    if detection.conf > 0.7:  # High confidence
        new_track = Track(next_id, detection)
        active_tracks.append(new_track)
        next_id += 1

# Lost tracks
for track in active_tracks:
    if not track.updated_this_frame:
        track.lost_frames += 1
        
        if track.lost_frames > 30:  # Buffer
            active_tracks.remove(track)
```

**Benefits Over Detection-Only**:
- ✅ Persistent IDs across frames
- ✅ Handle occlusions
- ✅ Reduce false positives
- ✅ Enable trajectory analysis
- ✅ Count unique vehicles

**Performance**:
- Adds ~5ms per frame
- Tracks 100+ objects simultaneously
- Handles 30 FPS video smoothly

### License Plate Recognition (ALPR)

**Two-Model Pipeline**:

**Model 1: Plate Detection**
- Base: YOLO v9 Tiny
- Specialized for license plates
- Input: Vehicle crop (from YOLO detection)
- Output: Plate bounding box

**Model 2: OCR**
- Base: Mobile ViT v2
- Optimized for plate text
- Input: Plate crop
- Output: Text + confidence

**Full Pipeline**:
```python
async def detect_license_plates(frame):
    # 1. Detect vehicles
    vehicles = yolo.predict(frame, classes=[2])  # Cars only
    
    plates = []
    for vehicle in vehicles:
        # 2. Crop vehicle region
        x1, y1, x2, y2 = vehicle.bbox
        vehicle_crop = frame[y1:y2, x1:x2]
        
        # 3. Detect plate in vehicle
        plate_results = alpr.predict(vehicle_crop)
        
        for plate in plate_results:
            # 4. Extract plate text
            plate_text = plate['text']
            confidence = plate['confidence']
            
            # 5. Validate format (optional)
            if is_valid_plate_format(plate_text):
                plates.append({
                    'text': plate_text,
                    'confidence': confidence,
                    'vehicle_bbox': vehicle.bbox,
                    'plate_bbox': plate['bbox']
                })
    
    return plates

def is_valid_plate_format(text):
    # Example: Vietnamese plate format
    # 30A-12345, 51B-67890, etc.
    import re
    pattern = r'^\d{2}[A-Z]-\d{5}$'
    return re.match(pattern, text) is not None
```

**Challenges & Solutions**:

**Challenge 1: Low Resolution**
- Solution: Upscale plate region before OCR
```python
plate_crop = cv2.resize(plate_crop, None, fx=2, fy=2, 
                       interpolation=cv2.INTER_CUBIC)
```

**Challenge 2: Poor Lighting**
- Solution: Enhance contrast
```python
from skimage import exposure
enhanced = exposure.equalize_adapthist(plate_crop)
```

**Challenge 3: Motion Blur**
- Solution: Use multiple frames, vote on result
```python
plate_votes = {}
for frame in frames:
    plate_text = detect_plate(frame)
    plate_votes[plate_text] = plate_votes.get(plate_text, 0) + 1

final_plate = max(plate_votes, key=plate_votes.get)
```

### Parking Space Occupancy Detection

**IoU-Based Matching**:

**Intersection over Union (IoU)**:
```python
def calculate_iou(box1, box2):
    """
    box1, box2: {x1, y1, x2, y2}
    Returns: IoU score (0-1)
    """
    # Calculate intersection rectangle
    x1 = max(box1['x1'], box2['x1'])
    y1 = max(box1['y1'], box2['y1'])
    x2 = min(box1['x2'], box2['x2'])
    y2 = min(box1['y2'], box2['y2'])
    
    # Calculate intersection area
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    
    # Calculate union area
    area1 = (box1['x2'] - box1['x1']) * (box1['y2'] - box1['y1'])
    area2 = (box2['x2'] - box2['x1']) * (box2['y2'] - box2['y1'])
    union = area1 + area2 - intersection
    
    # Calculate IoU
    if union == 0:
        return 0.0
    
    iou = intersection / union
    return iou
```

**Visual Example**:
```
Detection Box (Vehicle):
┌─────────────┐
│             │
│   Vehicle   │
│             │
└─────────────┘

Parking Space:
    ┌───────────────┐
    │               │
    │  Parking A1   │
    │               │
    └───────────────┘

Overlap:
    ┌─────────┐
    │░░░░░░░░░│  ← Intersection
    └─────────┘

IoU = Intersection / Union
    = (overlap area) / (total combined area)
    = 0.45  (45% overlap)

If IoU > 0.3:  Space is OCCUPIED
If IoU ≤ 0.3:  Space is EMPTY
```

**Matching Algorithm**:
```python
def match_detections_to_spaces(detections, spaces):
    occupied_spaces = []
    
    for detection in detections:
        best_space = None
        best_iou = 0.3  # Threshold
        
        # Find best matching space
        for space in spaces:
            iou = calculate_iou(detection.bbox, space.bbox)
            
            if iou > best_iou:
                best_iou = iou
                best_space = space
        
        if best_space:
            occupied_spaces.append(best_space)
    
    # Determine empty spaces
    empty_spaces = [
        space for space in spaces
        if space not in occupied_spaces
    ]
    
    return {
        'occupied': occupied_spaces,
        'empty': empty_spaces
    }
```

**Why IoU > 0.3?**
- Too low (0.1): False positives (nearby vehicles)
- Too high (0.7): False negatives (partial overlap)
- 0.3-0.4: Good balance for parking scenarios

---

## 🔄 Real-Time Streaming Architecture

### MJPEG Streaming

**Why MJPEG?**
- ✅ Simple protocol
- ✅ HTTP-based (no special server)
- ✅ Works in browsers with `<img>` tag
- ✅ Frame-by-frame processing
- ❌ Higher bandwidth than H.264

**MJPEG Format**:
```
--frame\r\n
Content-Type: image/jpeg\r\n\r\n
<JPEG_BYTES>
\r\n
--frame\r\n
Content-Type: image/jpeg\r\n\r\n
<JPEG_BYTES>
\r\n
...
```

**Server Implementation**:
```python
async def stream_mjpeg():
    """Generator function for MJPEG stream"""
    async with aiohttp.ClientSession() as session:
        async with session.get(ESP32_URL) as response:
            async for chunk in response.content.iter_any():
                # Parse MJPEG chunk
                if b'--frame' in chunk:
                    # Extract JPEG data
                    jpeg_data = extract_jpeg(chunk)
                    
                    # Yield frame
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' +
                        jpeg_data +
                        b'\r\n'
                    )

# Use in FastAPI
@app.get("/stream")
async def get_stream():
    return StreamingResponse(
        stream_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
```

**Client Implementation (Browser)**:
```html
<!-- Simple image tag -->
<img src="http://localhost:8069/stream" />

<!-- With error handling -->
<img 
  src="http://localhost:8069/stream"
  onerror="this.src='error.jpg'"
/>
```

### WebSocket Streaming

**Why WebSocket for Detection?**
- ✅ Bi-directional communication
- ✅ Lower latency than HTTP
- ✅ Can send metadata with frames
- ✅ Connection state management
- ✅ Efficient for many viewers

**Protocol Design**:
```typescript
// Client → Server (connection)
{
  type: "connect",
  camera_id: "cam_001",
  user_id: "user123"
}

// Server → Client (frame)
{
  type: "frame",
  camera_id: "cam_001",
  frame: "base64_encoded_jpeg",
  metadata: {
    detected_count: 5,
    occupied_spaces: 3,
    total_spaces: 10,
    timestamp: "2026-01-07T10:30:00Z",
    fps: 10
  }
}

// Server → Client (error)
{
  type: "error",
  message: "Camera offline"
}

// Client → Server (disconnect)
{
  type: "disconnect"
}
```

**Server Implementation**:
```python
@router.websocket("/ws/viewer/detection")
async def detection_viewer_websocket(
    websocket: WebSocket,
    camera_id: str,
    user_id: str
):
    await websocket.accept()
    
    # Register viewer
    await detection_broadcaster.register_viewer(camera_id, websocket)
    
    try:
        # Keep connection alive
        while True:
            # Wait for messages (ping/pong)
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        # Client disconnected
        await detection_broadcaster.unregister_viewer(camera_id, websocket)
```

**Client Implementation**:
```typescript
const ws = new WebSocket(
  `ws://localhost:8069/ws/viewer/detection?camera_id=cam1&user_id=uid`
);

ws.onopen = () => {
  console.log('Connected');
  
  // Send ping every 30s to keep alive
  setInterval(() => {
    ws.send('ping');
  }, 30000);
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'frame') {
    // Update image
    imgElement.src = `data:image/jpeg;base64,${data.frame}`;
    
    // Update stats
    statsElement.textContent = 
      `Detected: ${data.metadata.detected_count}`;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected');
  // Attempt reconnection
  setTimeout(connectWebSocket, 5000);
};
```

### Broadcast Architecture

**Single Source, Multiple Viewers**:

```python
class DetectionBroadcaster:
    def __init__(self):
        # Store viewers per camera
        self.viewers: Dict[str, Set[WebSocket]] = {}
        
        # Store latest frame per camera
        self.latest_frames: Dict[str, Dict] = {}
        
        # Locks for thread safety
        self.locks: Dict[str, asyncio.Lock] = {}
    
    async def broadcast_frame(self, camera_id, frame_base64, metadata):
        """Broadcast frame to all viewers of this camera"""
        
        if camera_id not in self.viewers:
            return  # No viewers, skip encoding
        
        # Prepare message
        message = {
            "type": "frame",
            "camera_id": camera_id,
            "frame": frame_base64,
            "metadata": metadata
        }
        
        # Store as latest frame
        self.latest_frames[camera_id] = message
        
        # Send to all viewers
        async with self.locks[camera_id]:
            disconnected = []
            
            for websocket in self.viewers[camera_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    # Mark for removal
                    disconnected.append(websocket)
            
            # Remove disconnected viewers
            for ws in disconnected:
                self.viewers[camera_id].discard(ws)
```

**Benefits**:
1. **GPU Efficiency**: Detection runs once
2. **CPU Efficiency**: JPEG encoding once
3. **Scalable**: Add viewers without extra cost
4. **Memory Efficient**: Single frame buffer

**Performance Comparison**:
```
Individual Processing (Old):
1 viewer:  1 detection + 1 encoding = 50ms
2 viewers: 2 detections + 2 encodings = 100ms
5 viewers: 5 detections + 5 encodings = 250ms

Broadcast Architecture (New):
1 viewer:  1 detection + 1 encoding + 1 send = 51ms
2 viewers: 1 detection + 1 encoding + 2 sends = 52ms
5 viewers: 1 detection + 1 encoding + 5 sends = 54ms

Improvement: 5x reduction in processing time!
```

---

## 🗄️ Database Design & Optimization

### Firebase/Firestore Schema Design

**Why NoSQL?**
- ✅ Flexible schema
- ✅ Real-time updates
- ✅ Scalable
- ✅ Easy integration
- ❌ No complex joins
- ❌ Limited query capabilities

**Normalized vs Denormalized**:

**Normalized (SQL-style)**:
```javascript
// vehicles
{ id, plate }

// detections
{ id, vehicle_id, timestamp }

// Query requires join
```

**Denormalized (Firestore-style)**:
```javascript
// detections (includes vehicle data)
{
  id: "det_001",
  vehiclePlate: "30A-12345",  // Denormalized
  cameraId: "cam_001",
  timestamp: Timestamp,
  detectionData: {...}
}

// Benefits: Single query, no joins
// Tradeoff: Data duplication
```

**Indexing Strategy**:
```javascript
// Firestore automatically indexes:
- Document ID
- Each top-level field

// Composite indexes needed for:
// Query: Get detections by camera AND date range
{
  collectionGroup: "detections",
  fields: [
    { fieldPath: "cameraId", order: "ASCENDING" },
    { fieldPath: "timestamp", order: "DESCENDING" }
  ]
}

// Create in Firebase Console → Firestore → Indexes
```

**Query Optimization**:
```typescript
// ❌ Bad: Fetch all, filter in code
const allDetections = await getDocs(collection(db, 'detections'));
const filtered = allDetections.filter(d => d.cameraId === 'cam1');

// ✅ Good: Filter in query
const q = query(
  collection(db, 'detections'),
  where('cameraId', '==', 'cam1'),
  orderBy('timestamp', 'desc'),
  limit(50)
);
const snapshot = await getDocs(q);

// ✅ Better: Use real-time listener
const unsubscribe = onSnapshot(q, (snapshot) => {
  const detections = snapshot.docs.map(doc => doc.data());
  updateUI(detections);
});
```

**Pagination**:
```typescript
// Initial query
const firstQuery = query(
  collection(db, 'detections'),
  orderBy('timestamp', 'desc'),
  limit(25)
);
const firstPage = await getDocs(firstQuery);

// Next page
const lastDoc = firstPage.docs[firstPage.docs.length - 1];
const nextQuery = query(
  collection(db, 'detections'),
  orderBy('timestamp', 'desc'),
  startAfter(lastDoc),
  limit(25)
);
const nextPage = await getDocs(nextQuery);
```

### Caching Strategy

**Three-Level Cache**:

**Level 1: In-Memory (Worker)**
```python
class ParkingMonitorWorker:
    def __init__(self):
        # Cache parking spaces in memory
        self.camera_spaces_cache: Dict[str, List[Dict]] = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_cache_refresh = 0
    
    async def get_parking_spaces(self, camera_id):
        now = time.time()
        
        # Check cache
        if camera_id in self.camera_spaces_cache:
            if now - self.last_cache_refresh < self.cache_ttl:
                return self.camera_spaces_cache[camera_id]
        
        # Cache miss - fetch from Firebase
        spaces = await self.firebase.get_parking_spaces(camera_id)
        self.camera_spaces_cache[camera_id] = spaces
        self.last_cache_refresh = now
        
        return spaces
```

**Level 2: Redis (if using)**
```python
import redis

redis_client = redis.Redis(host='localhost', port=6379)

def get_with_cache(key, fetch_fn, ttl=300):
    # Try cache first
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    
    # Fetch from source
    data = fetch_fn()
    
    # Store in cache
    redis_client.setex(
        key,
        ttl,
        json.dumps(data)
    )
    
    return data

# Usage
spaces = get_with_cache(
    f"parking_spaces:{camera_id}",
    lambda: firebase.get_parking_spaces(camera_id),
    ttl=300
)
```

**Level 3: Browser (Frontend)**
```typescript
// React Query for caching
import { useQuery } from 'react-query';

function useParkingSpaces(cameraId: string) {
  return useQuery(
    ['parking-spaces', cameraId],
    () => apiService.getParkingSpaces(cameraId),
    {
      staleTime: 5 * 60 * 1000,  // 5 minutes
      cacheTime: 10 * 60 * 1000,  // 10 minutes
      refetchOnWindowFocus: false
    }
  );
}
```

---

## ⚡ Performance Metrics

### Latency Breakdown

**End-to-End Latency** (Camera → Display):
```
1. Camera Capture:        ~33ms (30 FPS)
2. Network Transfer:      ~10-50ms (ESP32 → Backend)
3. YOLO Detection:        ~20-40ms (GPU)
4. ByteTrack:            ~5ms
5. Space Matching:        ~2ms
6. Frame Encoding:        ~5-10ms (JPEG)
7. WebSocket Send:        ~1-5ms
8. Network Transfer:      ~10-50ms (Backend → Client)
9. Browser Decode:        ~5ms

Total: ~100-200ms (acceptable for real-time)
```

**Optimization Targets**:
- Detection: < 50ms (GPU)
- End-to-end: < 200ms
- Throughput: > 10 FPS per camera

### Resource Usage

**GPU Memory** (NVIDIA RTX 3080, 10GB VRAM):
```
YOLO v8n:     ~1.5 GB
YOLO v8s:     ~2.5 GB
YOLO v8m:     ~4.5 GB
ByteTrack:    ~0.5 GB
ALPR:         ~1.0 GB

Total (v8s):  ~4 GB
Remaining:    ~6 GB (for multiple models/batches)
```

**CPU Usage**:
```
With GPU:     5-15% (mainly I/O)
Without GPU:  80-100% (inference on CPU)
```

**Network Bandwidth**:
```
MJPEG Stream (640x480, 30 FPS):
- Quality 50:   ~0.5 Mbps
- Quality 75:   ~1.0 Mbps
- Quality 95:   ~2.0 Mbps

WebSocket (Base64 JPEG, 10 FPS):
- Per viewer:   ~0.3 Mbps
- 10 viewers:   ~3.0 Mbps (manageable)
```

This deep dive provides a comprehensive understanding of the technical implementation and optimization strategies used in the Smart Parking System.
