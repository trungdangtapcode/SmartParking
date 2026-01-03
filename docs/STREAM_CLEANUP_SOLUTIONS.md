# Stream Performance & Cleanup Issues - Solutions

## Problem: Backend continues processing after tab closed

### Root Causes:
1. **TCP Connection Lingering**: Browser closes tab but TCP connection stays open (TIME_WAIT)
2. **Async Generator Not Cancelling**: Python generators don't immediately stop
3. **Heavy YOLO Processing**: Each frame takes 30-50ms to process
4. **No Frame Skipping**: Processing every single frame even when client is slow

---

## Solutions Implemented

### 1. Multiple Disconnect Detection Points ✅

Added disconnect checks at 3 strategic points:

```python
# Before reading chunk
if await request.is_disconnected():
    print("🔌 Client disconnected")
    break

# Before processing frame
if await request.is_disconnected():
    return

# During yield (exception handling)
try:
    yield frame_data
except Exception:
    print("🔌 Client disconnected during yield")
    return
```

### 2. Reduced Logging Overhead ✅

Changed from logging every 30 frames to every 100 frames:
```python
if frame_count == 1:
    print("✅ Detection stream started")
elif frame_count % 100 == 0:  # Was: % 30
    print(f"📹 Processed {frame_count} frames")
```

### 3. Frontend Cleanup ✅

Added `beforeunload` handler and component unmount cleanup:
```typescript
useEffect(() => {
  const handleBeforeUnload = () => {
    setStreamKey(prev => prev + 1); // Force new connection
  };
  
  window.addEventListener('beforeunload', handleBeforeUnload);
  
  return () => {
    window.removeEventListener('beforeunload', handleBeforeUnload);
    setStreamKey(prev => prev + 1); // Cleanup on unmount
  };
}, []);
```

### 4. Exception Handling in Yield ✅

Catches when client disconnects during frame transmission:
```python
try:
    yield (b'--frame\r\n'
           b'Content-Type: image/jpeg\r\n\r\n' +
           jpeg_encoded.tobytes() + b'\r\n')
except Exception as yield_error:
    print("🔌 Client disconnected during yield")
    return
```

---

## Additional Optimizations Recommended

### 5. Add Frame Skipping for Detection Stream

Skip frames when processing is too slow:

```python
# In stream_with_detection()
frame_count = 0
process_count = 0
PROCESS_EVERY_N_FRAMES = 2  # Only process every 2nd frame

if frame is not None:
    frame_count += 1
    
    # Skip frames if processing can't keep up
    if frame_count % PROCESS_EVERY_N_FRAMES != 0:
        # Just proxy the frame without detection
        _, jpeg_encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    else:
        # Run YOLO detection
        process_count += 1
        results = ai_service.yolo_model(...)
        # ... annotate frame ...
```

### 6. Add Adaptive Quality

Reduce JPEG quality when under load:

```python
# Detect if we're falling behind
if buffer_size > 10 * 1024 * 1024:  # 10MB buffer
    jpeg_quality = 70  # Lower quality
else:
    jpeg_quality = 85  # Normal quality

_, jpeg_encoded = cv2.imencode('.jpg', annotated_frame, 
                               [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
```

### 7. Add Connection Timeout

Force disconnect after inactivity:

```python
import asyncio
from datetime import datetime

last_yield_time = datetime.now()
TIMEOUT_SECONDS = 5

async for chunk in response.content.iter_chunked(1024):
    if await request.is_disconnected():
        break
    
    # Check timeout
    if (datetime.now() - last_yield_time).seconds > TIMEOUT_SECONDS:
        print("⏱️ Stream timeout - client not receiving data")
        break
    
    buffer += chunk
    # ... process frame ...
    
    # Update last yield time after successful yield
    last_yield_time = datetime.now()
```

### 8. Use Connection Pool Limits

Limit concurrent streams in main_fastapi.py startup:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing code ...
    
    # Limit concurrent connections
    app.state.active_streams = 0
    app.state.max_streams = 5  # Max 5 concurrent streams
    
    yield
    
    # Cleanup
    print(f"🛑 Shutting down ({app.state.active_streams} active streams)")
```

Then in stream endpoint:

```python
@app.get("/stream/detect")
async def stream_with_detection(...):
    # Check stream limit
    if app.state.active_streams >= app.state.max_streams:
        raise HTTPException(503, "Too many active streams. Please try again.")
    
    app.state.active_streams += 1
    
    try:
        async def generate_detected_stream():
            # ... stream logic ...
        
        return StreamingResponse(generate_detected_stream(), ...)
    finally:
        app.state.active_streams -= 1
```

---

## Testing & Monitoring

### Monitor Resource Usage:

```bash
# Terminal 1: Run server
cd server
python main_fastapi.py

# Terminal 2: Monitor resources
cd server
python monitor_streams.py
```

### Test Disconnect Behavior:

1. Open stream in browser
2. Wait for "✅ Detection stream started" log
3. Close browser tab
4. Should see "🔌 Client disconnected" within 1-2 seconds
5. Check logs stop incrementing frame count

### Check for Zombie Streams:

```bash
# Check active Python processes
ps aux | grep main_fastapi

# Check network connections
lsof -i :8069 | grep ESTABLISHED

# Monitor CPU usage
top -p $(pgrep -f main_fastapi)
```

### Expected Behavior After Fix:

- ✅ Stream stops within 1-2 seconds of tab close
- ✅ CPU drops to ~10% when no active streams
- ✅ Memory stable, no leaks
- ✅ Log shows disconnect message
- ✅ Frame count stops incrementing
- ✅ SSH remains responsive

### If Still Laggy:

1. **Reduce YOLO processing**:
   ```python
   # Lower confidence threshold reduces false positives
   conf = 0.5  # Instead of 0.25
   
   # Use smaller model
   # Replace yolov8n.pt with yolov8n.pt (already smallest)
   # Or reduce input resolution
   ```

2. **Add frame skipping**:
   ```python
   PROCESS_EVERY_N_FRAMES = 3  # Process only 1 out of 3 frames
   ```

3. **Reduce image resolution**:
   ```python
   # Resize frame before detection
   frame = cv2.resize(frame, (640, 480))  # Smaller resolution
   ```

4. **Limit FPS**:
   ```python
   import asyncio
   
   async for chunk in response.content.iter_chunked(1024):
       # ... process frame ...
       
       # Limit to 15 FPS (instead of 30)
       await asyncio.sleep(1/15)
   ```

---

## Quick Fixes for Immediate Relief

### If System is Currently Laggy:

```bash
# Kill all Python processes (will restart automatically)
pkill -9 -f main_fastapi

# Or restart server gracefully
cd server
python main_fastapi.py
```

### Emergency Cleanup:

```bash
# Find and kill hanging processes
ps aux | grep python | grep main_fastapi
kill -9 <PID>

# Clear any stuck ports
sudo lsof -ti:8069 | xargs sudo kill -9

# Restart fresh
cd server
python main_fastapi.py
```

---

## Configuration Tweaks

### Lower Detection Settings for Better Performance:

In frontend detection settings:
- Confidence Threshold: **0.5** (instead of 0.25)
- This reduces false positives and processing overhead

### Optimize YOLO Settings:

```python
# In ai_service.py or main_fastapi.py
results = ai_service.yolo_model(
    frame,
    conf=0.5,         # Higher = fewer detections
    iou=0.5,          # Higher = fewer overlapping boxes
    max_det=50,       # Limit max detections per frame
    device=ai_service.device,
    verbose=False,
    half=True         # Use FP16 on GPU (2x faster)
)
```

---

## Summary of Changes

Files Modified:
- ✅ `server/main_fastapi.py` - Added disconnect detection, reduced logging
- ✅ `frontend/src/pages/StreamViewerPageESP32.tsx` - Added cleanup handlers
- ✅ `server/monitor_streams.py` - New monitoring utility

Key Improvements:
- 🔌 3-point disconnect detection
- 📉 Reduced logging overhead (30 → 100 frames)
- 🧹 Frontend cleanup on unmount/tab close
- 🛡️ Exception handling in yield
- 📊 Monitoring utility for debugging

Next Steps (if still having issues):
1. Implement frame skipping
2. Add adaptive quality
3. Reduce YOLO confidence threshold
4. Limit concurrent streams
5. Add connection timeout
