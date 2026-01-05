# Worker Live Detection Stream Feature

## Overview
Added real-time detection stream viewing capability to the Worker Monitor dashboard. When a worker is enabled for a camera, admins can now view the live annotated detection stream to see exactly what the worker is processing.

## Implementation

### Backend Changes

#### `server/routers/websocket_streams.py`
Added `camera_url` parameter to `/ws/stream/detect` endpoint:

```python
@router.websocket("/stream/detect")
async def ws_detection_stream(
    websocket: WebSocket,
    user_id: Optional[str] = None,
    camera_url: Optional[str] = None,  # NEW PARAMETER
    conf: float = 0.25,
    show_labels: bool = True,
    fps: int = 10,
    skip_frames: int = 2
):
```

**Priority for camera selection:**
1. `camera_url` parameter (direct URL) - **HIGHEST PRIORITY**
2. `user_id` lookup in Firebase config
3. Default `ESP32_URL` - **LOWEST PRIORITY**

This allows the frontend to directly specify which camera to stream from without relying on user configs.

### Frontend Changes

#### `frontend/src/pages/WorkerMonitorPage.tsx`

**New State Variables:**
```typescript
const [showDetectionStream, setShowDetectionStream] = useState(false);
const [streamingCameraId, setStreamingCameraId] = useState<string | null>(null);
const streamCanvasRef = useRef<HTMLCanvasElement>(null);
const streamWsRef = useRef<WebSocket | null>(null);
```

**New Functions:**
- `handleViewDetectionStream(cameraId)` - Opens modal and starts stream
- `startDetectionStream(camera)` - Connects WebSocket and handles frame rendering
- `handleCloseDetectionStream()` - Closes WebSocket and modal
- `addNewLog(log)` - Helper to add log entries

**New UI Components:**
1. **"📹 View Live" Button** - Only visible when `workerEnabled === true`
   ```tsx
   {camera.workerEnabled && (
     <button onClick={() => handleViewDetectionStream(camera.id)}>
       📹 View Live
     </button>
   )}
   ```

2. **Detection Stream Modal** - Full-screen overlay with canvas
   - Shows camera name in header
   - Canvas displays real-time annotated frames
   - Close button and ESC key support
   - Auto-resizes canvas to match incoming frame dimensions

**WebSocket Connection:**
```typescript
const encodedCameraUrl = encodeURIComponent(camera.ipAddress);
const wsUrl = `ws://localhost:8069/ws/stream/detect?camera_url=${encodedCameraUrl}&conf=0.25&fps=10&skip_frames=2`;
```

**Frame Rendering:**
```typescript
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'frame') {
    const img = new Image();
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
    };
    img.src = `data:image/jpeg;base64,${msg.data}`;
  }
};
```

**Lifecycle Management:**
- ESC key closes modal
- WebSocket cleanup on component unmount
- Logs stream open/close events

## Usage Flow

1. **Admin enables worker** for a camera (toggle ON)
2. **"📹 View Live" button appears** next to the toggle
3. **Admin clicks "View Live"**
4. **Modal opens** with canvas
5. **WebSocket connects** to backend using camera IP
6. **Backend fetches frames** from camera's `/stream` endpoint
7. **Backend processes frames** with YOLO detection
8. **Backend sends annotated frames** to frontend as base64 JPEG
9. **Frontend displays frames** on canvas in real-time
10. **Admin sees live detection** with bounding boxes and labels
11. **Admin closes modal** (button or ESC key)
12. **WebSocket disconnects** and cleanup occurs

## Configuration

**WebSocket Parameters:**
- `camera_url`: Camera IP address (e.g., `http://192.168.1.100`)
- `conf`: Detection confidence threshold (default: 0.25)
- `fps`: Target frames per second (default: 10)
- `skip_frames`: Process every Nth frame (default: 2)

**Adjustable Settings:**
To change detection sensitivity or performance, modify the WebSocket URL:
```typescript
const wsUrl = `ws://localhost:8069/ws/stream/detect?camera_url=${encodedCameraUrl}&conf=0.5&fps=15&skip_frames=1`;
```

## Benefits

1. **Visual Confirmation** - Admin can verify worker is functioning correctly
2. **Debugging Aid** - See exactly what the worker detects
3. **Quality Assurance** - Ensure detection accuracy before relying on worker
4. **Real-time Monitoring** - Watch live parking space occupancy changes
5. **No Separate Tool** - Integrated into existing worker dashboard

## Technical Details

**WebSocket Message Types:**
- `{"type": "frame", "data": "<base64_jpeg>"}` - Annotated video frame
- `{"type": "stats", "processed": 100, "skipped": 50, "fps": 9.8}` - Performance stats
- `{"type": "error", "message": "..."}` - Error messages

**Canvas Rendering:**
- Automatically adjusts to frame dimensions
- Uses 2D canvas context for optimal performance
- Handles base64 JPEG decoding natively

**Error Handling:**
- WebSocket connection errors logged
- Failed frame fetch handled gracefully
- Modal can be closed at any time
- Worker must be enabled to view stream

## Dependencies

**Backend:**
- FastAPI WebSocket support
- OpenCV for frame processing
- YOLO model for detection
- aiohttp for camera stream fetching

**Frontend:**
- React hooks (useState, useEffect, useRef)
- Canvas API for rendering
- WebSocket API for streaming
- Tailwind CSS for styling

## Future Enhancements

Potential improvements:
- [ ] Stream recording capability
- [ ] Snapshot capture button
- [ ] Detection statistics overlay
- [ ] Multi-camera simultaneous viewing
- [ ] Adjustable detection parameters in UI
- [ ] Stream quality/bandwidth controls
- [ ] Detection zone overlay on stream
- [ ] Vehicle count display on stream
