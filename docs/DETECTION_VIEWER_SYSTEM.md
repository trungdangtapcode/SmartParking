# GPU-Efficient Detection Viewer System

## Overview
Created a scalable detection viewing system where **multiple users can watch the same worker detection stream** without additional GPU processing. The worker processes frames once on GPU, then broadcasts to unlimited viewers.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        SINGLE GPU                             │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Worker (parking_monitor_worker.py)                    │  │
│  │  • Fetches frames from camera                          │  │
│  │  • Runs YOLO detection (GPU)                           │  │
│  │  • Matches to parking spaces                           │  │
│  │  • Draws annotations (boxes, labels)                   │  │
│  │  • Broadcasts to viewers                               │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │   Broadcaster   │ (detection_broadcaster.py)
                    │  Manages viewers │
                    └─────────────────┘
                              ↓
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
   [Viewer 1]           [Viewer 2]           [Viewer N]
   (WebSocket)          (WebSocket)          (WebSocket)
```

**Key Benefits:**
- ✅ **Single GPU process** - Worker runs detection once
- ✅ **Unlimited viewers** - Broadcast to any number of users
- ✅ **Real-time streaming** - WebSocket-based live frames
- ✅ **No extra load** - Viewers don't trigger detection
- ✅ **Parking space overlay** - Shows occupied/free spaces
- ✅ **Vehicle detection boxes** - Live bounding boxes with confidence

## Backend Components

### 1. Detection Broadcaster Service
**File:** `server/services/detection_broadcaster.py`

Manages broadcasting of detection frames to multiple WebSocket clients.

**Key Methods:**
```python
class DetectionBroadcaster:
    async def register_viewer(camera_id, websocket)
        # Add viewer to camera's viewer list
    
    async def unregister_viewer(camera_id, websocket)
        # Remove viewer, cleanup if last viewer
    
    async def broadcast_frame(camera_id, frame_base64, metadata)
        # Send frame to all viewers of this camera
    
    def get_viewer_count(camera_id) -> int
        # Get number of active viewers
```

**Features:**
- Stores latest frame for immediate delivery to new viewers
- Auto-cleanup disconnected viewers
- Thread-safe with asyncio locks
- Per-camera viewer management

### 2. Worker Frame Broadcasting
**File:** `server/parking_monitor_worker.py`

**Modified `process_camera()` method:**
```python
# After detection and matching:
1. Draw annotations on frame (parking spaces + vehicles)
2. Check if anyone is watching (viewer_count > 0)
3. If yes: Encode to JPEG + broadcast
4. If no: Skip encoding (save CPU)
```

**New Methods:**
- `draw_detections_on_frame()` - Annotate frame with:
  - Parking space rectangles (Green=Free, Red=Occupied)
  - Vehicle bounding boxes (Blue with confidence)
  - Labels for spaces and vehicles
- `broadcast_frame_to_viewers()` - Encode and broadcast to viewers

**Optimization:**
- Only encodes frames if viewers are connected
- Uses JPEG quality 85 (good balance of quality/bandwidth)
- Async broadcast to prevent blocking worker

### 3. Viewer WebSocket Endpoint
**File:** `server/routers/detection_viewer.py`

**Endpoint:** `ws://localhost:8069/ws/viewer/detection?camera_id=<id>&user_id=<uid>`

**Flow:**
1. Accept WebSocket connection
2. Register viewer with broadcaster
3. Send immediate info message with viewer count
4. Keep connection alive
5. Broadcaster sends frames asynchronously
6. On disconnect: unregister and cleanup

**Messages sent to client:**
```json
{"type": "info", "message": "Connected...", "viewer_count": 3}
{"type": "frame", "data": "<base64_jpeg>", "metadata": {...}}
{"type": "error", "message": "..."}
```

**Stats Endpoint:** `GET /viewer/stats`
Returns active cameras and viewer counts

### 4. Main App Integration
**File:** `server/main_fastapi.py`

Added router import and registration:
```python
from routers import detection_viewer
app.include_router(detection_viewer.router)
```

## Frontend Components

### Detection Viewer Page
**File:** `frontend/src/pages/DetectionViewerPage.tsx`

**Features:**
- **Parking Lot Selector** - Choose which parking lot to monitor
- **Camera Grid** - Shows all cameras in selected lot
- **Worker Status Badge** - "Worker ON" / "Worker OFF"
- **Watch Button** - Only enabled if worker is ON
- **Streaming Modal** - Full-screen detection viewer
- **Canvas Display** - WebSocket frames drawn in real-time
- **Metadata Footer** - Shows:
  - Vehicle count
  - Occupied spaces
  - Total spaces
  - Last update timestamp
- **Auto-reconnect** - Reconnects if connection drops

**UI Flow:**
```
1. User selects parking lot
   ↓
2. Grid shows cameras with worker status
   ↓
3. User clicks "▶️ Watch Live Detection" (if worker ON)
   ↓
4. Modal opens with canvas
   ↓
5. WebSocket connects to /ws/viewer/detection
   ↓
6. Frames stream to canvas in real-time
   ↓
7. User sees annotated detections live
   ↓
8. Close button or ESC to stop
```

**State Management:**
```typescript
const [selectedLotId, setSelectedLotId] = useState<string>('');
const [cameras, setCameras] = useState<ESP32Config[]>([]);
const [selectedCamera, setSelectedCamera] = useState<ESP32Config | null>(null);
const [isStreaming, setIsStreaming] = useState(false);
const [streamMetadata, setStreamMetadata] = useState<any>(null);
const [connectionStatus, setConnectionStatus] = useState<string>('disconnected');
```

**WebSocket Handling:**
```typescript
ws.onopen = () => setConnectionStatus('connected');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'frame') {
    // Draw to canvas
    const img = new Image();
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
    };
    img.src = `data:image/jpeg;base64,${msg.data}`;
    setStreamMetadata(msg.metadata);
  }
};
ws.onerror = () => setConnectionStatus('error');
ws.onclose = () => {
  setConnectionStatus('disconnected');
  // Auto-reconnect after 3s
};
```

### App Router Integration
**File:** `frontend/src/App.tsx`

Added route and navigation:
```tsx
import DetectionViewerPage from './pages/DetectionViewerPage';

// Route (available to all authenticated users)
<Route 
  path="/detection-viewer" 
  element={
    <ProtectedRoute>
      <DetectionViewerPage />
    </ProtectedRoute>
  } 
/>

// Sidebar navigation
<NavLink to="/detection-viewer">
  <span>📺</span>
  <span>Live Detection</span>
</NavLink>
```

## Data Flow

### Worker Processing (Every 10 seconds)
```
1. Worker fetches frame from camera
   ↓
2. Decodes frame with OpenCV
   ↓
3. Runs YOLO detection (GPU) → [detections]
   ↓
4. Matches detections to parking spaces → [occupancy]
   ↓
5. Updates Firebase with occupancy status
   ↓
6. Checks viewer count
   ↓
7. If viewers > 0:
   - Draws parking space rectangles
   - Draws vehicle bounding boxes
   - Encodes to JPEG base64
   - Broadcasts to all viewers
   ↓
8. If viewers == 0:
   - Skips annotation/encoding (saves CPU)
```

### Viewer Connection
```
1. User opens DetectionViewerPage
   ↓
2. Selects parking lot → loads cameras
   ↓
3. Clicks "Watch Live" on camera with worker ON
   ↓
4. Modal opens, WebSocket connects
   ↓
5. Broadcaster registers viewer
   ↓
6. Sends latest frame immediately (if available)
   ↓
7. Worker broadcasts new frames as they're processed
   ↓
8. Canvas updates in real-time
```

## Message Format

### Frame Message (Worker → Viewer)
```json
{
  "type": "frame",
  "data": "/9j/4AAQSkZJRgABAQEA...", // Base64 JPEG
  "metadata": {
    "vehicle_count": 15,
    "occupied_spaces": 12,
    "total_spaces": 26,
    "timestamp": "2026-01-05T08:04:17.123Z"
  }
}
```

### Info Message (Server → Viewer on connect)
```json
{
  "type": "info",
  "message": "Connected to camera cam123. Viewers: 3",
  "camera_id": "cam123",
  "viewer_count": 3
}
```

### Error Message
```json
{
  "type": "error",
  "message": "Worker not active for this camera"
}
```

## Performance Optimizations

### 1. Conditional Encoding
```python
viewer_count = broadcaster.get_viewer_count(camera_id)
if viewer_count == 0:
    return  # Skip encoding, no one is watching
```

### 2. Frame Caching
Latest frame stored in broadcaster for instant delivery to new viewers:
```python
self._latest_frames[camera_id] = frame_base64
# New viewers get this immediately on connect
```

### 3. Async Broadcasting
Non-blocking frame distribution:
```python
tasks = [ws.send_json(message) for ws in viewers]
await asyncio.gather(*tasks, return_exceptions=True)
```

### 4. Disconnected Viewer Cleanup
```python
# Remove dead connections during broadcast
for ws in disconnected:
    self._viewers[camera_id].discard(ws)
```

## Scalability

**Single Camera:**
- Worker: 1 GPU process
- Viewers: N users (unlimited)
- GPU load: Same as 1 viewer
- Network bandwidth: N × frame_size

**Multiple Cameras:**
- Worker processes cameras sequentially
- Each camera can have unlimited viewers
- Total GPU load: Number of cameras (not viewers)

**Example: 3 cameras, 100 viewers**
```
Camera A: 40 viewers → 1 detection process
Camera B: 35 viewers → 1 detection process  
Camera C: 25 viewers → 1 detection process
Total GPU processes: 3 (not 100!)
```

## Configuration

### Worker Settings
```python
# In parking_monitor_worker.py
check_interval = 10  # Process every 10 seconds
```

### Broadcast Quality
```python
# In broadcast_frame_to_viewers()
cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
```

### WebSocket Auto-Reconnect
```typescript
// In DetectionViewerPage.tsx
setTimeout(() => connectWebSocket(camera), 3000);
```

## Testing

### 1. Start Worker
```bash
cd server
python parking_monitor_worker.py --interval 10
```

### 2. Start Backend
```bash
cd server
python main_fastapi.py
```

### 3. Start Frontend
```bash
cd frontend
npm run dev
```

### 4. Test Viewing
1. Navigate to "📺 Live Detection" in sidebar
2. Select a parking lot
3. Ensure worker is ON for a camera
4. Click "▶️ Watch Live Detection"
5. Verify:
   - ✅ Canvas shows annotated stream
   - ✅ Parking spaces drawn (green/red)
   - ✅ Vehicle boxes visible
   - ✅ Metadata updates
   - ✅ Connection status indicator

### 5. Test Multiple Viewers
1. Open in multiple browser tabs/windows
2. All should see same stream
3. Check worker logs: Should show viewer count
4. Close tabs: Viewer count should decrease

### 6. Test Worker Toggle
1. Turn worker OFF in Worker Monitor page
2. "Watch Live" button should be disabled
3. Existing streams should disconnect

## Troubleshooting

### No frames appearing
- Check worker is running and processing camera
- Verify worker has loaded parking spaces
- Check browser console for WebSocket errors
- Ensure camera worker is enabled

### Connection keeps dropping
- Check network stability
- Verify backend server is running
- Look for errors in worker logs
- Check firewall settings

### High CPU usage
- Reduce JPEG quality (lower than 85)
- Increase worker check interval
- Reduce number of concurrent viewers per camera

### Frames delayed
- Check worker processing time
- Verify network bandwidth
- Consider reducing frame resolution

## Future Enhancements

- [ ] Recording capability (save streams)
- [ ] Snapshot capture button
- [ ] Multi-camera grid view (watch 4-9 cameras simultaneously)
- [ ] Playback of recorded sessions
- [ ] Alert notifications on canvas
- [ ] Adjustable quality settings in UI
- [ ] Mobile-optimized viewer
- [ ] Picture-in-picture mode
- [ ] Zoom and pan controls
