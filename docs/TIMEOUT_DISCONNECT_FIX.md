# Timeout-Based Disconnect Detection Fix

## Problem
Streams continued running indefinitely even after client closed the browser tab because FastAPI's `request.is_disconnected()` does NOT reliably detect disconnected clients in streaming responses.

### Symptoms
```
📹 Processed 150 frames (skipped 600)
📹 Processed 500 frames (skipped 2000)  # Different zombie stream
📹 Processed 550 frames (skipped 2200)  # Different zombie stream
📹 Processed 600 frames (skipped 2400)  # Different zombie stream
```

Multiple streams kept processing frames despite closed tabs, causing:
- High CPU usage (multiple YOLO models running)
- System lag and SSH disconnections
- Wasted resources on streams nobody is watching

## Root Cause
FastAPI's `await request.is_disconnected()` returns False even when:
- Browser tab is closed
- User navigates away
- Network connection is lost
- Frontend unmounts the component

This happens because:
1. TCP connection might stay in TIME_WAIT state
2. HTTP keep-alive prevents immediate detection
3. No actual data transmission failure occurs (ESP32 keeps sending)
4. The check doesn't verify if client is consuming yielded data

## Solution: Timeout-Based Detection

### Implementation
Added timeout tracking that detects when client stops consuming frames:

```python
async def generate_detected_stream():
    last_yield_time = time.time()  # Track last successful yield
    YIELD_TIMEOUT = 5.0  # If no successful yield in 5 seconds, assume disconnected
    
    async for chunk in response.content.iter_chunked(1024):
        # Check timeout - if we haven't successfully yielded in N seconds, client is gone
        if time.time() - last_yield_time > YIELD_TIMEOUT:
            print(f"⏱️ Yield timeout ({YIELD_TIMEOUT}s) - client stopped consuming. Processed {processed_count} frames")
            return
        
        # ... process frame ...
        
        try:
            yield frame_data
            last_yield_time = time.time()  # Reset timeout after successful yield
        except (Exception, GeneratorExit, StopAsyncIteration) as e:
            print(f"🔌 Client disconnected during yield: {type(e).__name__}")
            return
```

### How It Works
1. **Track last successful yield**: `last_yield_time = time.time()`
2. **Check timeout before processing**: If `time.time() - last_yield_time > 5.0`, stop
3. **Reset timeout after yield**: `last_yield_time = time.time()` after successful yield
4. **Catch generator exceptions**: `GeneratorExit`, `StopAsyncIteration`

### Timeout Value
- **5 seconds**: Balance between quick cleanup and avoiding false positives
- Accounts for:
  - Network delays
  - Frame processing time
  - FPS limiting delays
- Can be adjusted if needed:
  - Lower (3s): Faster cleanup, risk of false positives on slow networks
  - Higher (10s): More tolerant, slower to detect disconnects

## Applied To
1. **`/stream/raw`** - Raw ESP32 stream proxy
2. **`/stream/detect`** - Detection stream with YOLO

Both endpoints now have:
- ✅ Timeout-based disconnect detection
- ✅ Exception handling for generator exits
- ✅ Proper cleanup logging

## Expected Behavior

### Before Fix
```
# User closes tab
[Backend continues indefinitely]
📹 Processed 100 frames (skipped 400)
📹 Processed 150 frames (skipped 600)
📹 Processed 200 frames (skipped 800)
...
[Never stops until server restart]
```

### After Fix
```
# User closes tab
[Backend detects within 5 seconds]
⏱️ Yield timeout (5.0s) - client stopped consuming. Processed 47 frames
[Stream stops, resources freed]
```

## Testing

### Test Scenario 1: Normal Disconnect
1. Start backend: `conda activate scheduler && cd server && python main_fastapi.py`
2. Open frontend: Navigate to Stream Viewer page
3. Start stream (raw or YOLO mode)
4. Wait for "✅ Detection started" message
5. **Close browser tab**
6. **Expected**: Within 5 seconds, see "⏱️ Yield timeout" message in backend
7. **Expected**: Frame count stops incrementing
8. **Expected**: CPU usage drops

### Test Scenario 2: Mode Switching
1. Start stream in raw mode
2. Switch to YOLO mode
3. **Expected**: Old stream terminates with timeout
4. **Expected**: New stream starts fresh
5. **Expected**: Only ONE stream running at a time

### Test Scenario 3: Multiple Tabs
1. Open 3 tabs with streams
2. Close all 3 tabs quickly
3. **Expected**: All 3 streams timeout within 5-10 seconds
4. **Expected**: No zombie streams remain
5. **Expected**: Backend CPU returns to idle

## Monitoring

Check for zombie streams:
```bash
# Watch backend logs
tail -f logs.txt | grep "Processed"

# Should see timeouts after tab closes:
tail -f logs.txt | grep "timeout"

# Monitor system resources
python monitor_streams.py
```

## Performance Impact
- **Minimal overhead**: Simple time comparison
- **No additional threads**: Uses existing async loop
- **Fast cleanup**: 5 second max delay
- **Works with existing optimizations**: Frame skipping, FPS limiting, etc.

## Fallback Detection
Still keeps `request.is_disconnected()` checks as additional safety:
```python
if await request.is_disconnected():
    print(f"🔌 Client disconnected")
    return
```

This provides multiple layers of disconnect detection:
1. Primary: Timeout-based (reliable)
2. Secondary: `request.is_disconnected()` (when it works)
3. Tertiary: Exception handling (last resort)

## Related Files
- `server/main_fastapi.py` - Main implementation
- `frontend/src/pages/StreamViewerPageESP32.tsx` - Client side
- `docs/STREAM_CLEANUP_SOLUTIONS.md` - Previous attempt
- `docs/PERFORMANCE_TUNING.md` - Performance optimizations

## Date
2024-01-XX - Implemented timeout-based disconnect detection to fix zombie stream issue
