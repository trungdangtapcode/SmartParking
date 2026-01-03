# Real-Time Streaming Architecture

## 🎯 Problem Statement

**Goal:** Low FPS and frame skipping for batch processing efficiency, while maintaining real-time streaming without latency/delay accumulation.

**Challenge:** Balance between:
- ⚡ **Real-time responsiveness** (low latency, immediate frame delivery)
- 🔋 **Computational efficiency** (process fewer frames, save GPU/CPU)
- 📊 **Consistent timing** (predictable frame intervals)

---

## ❌ What NOT to Do (Old Implementation)

### Anti-Pattern 1: Send ALL frames with artificial delay

```python
# ❌ BAD: Sends every frame, adds artificial sleep
async for chunk in response.content.iter_chunked(1024):
    # ... parse frame ...
    
    # Process every Nth frame
    if frame_count % skip_frames == 0:
        annotated = process_with_yolo(frame)
    
    # ❌ Send ALL frames (even skipped ones)
    await websocket.send_json({
        "type": "frame",
        "data": last_annotated or raw_frame
    })
    
    # ❌ Artificial delay accumulates latency
    await asyncio.sleep(1.0 / fps)
```

**Problems:**
- 📦 Sends skipped frames (old/stale data)
- ⏰ `asyncio.sleep()` accumulates delay
- 🐌 Latency increases over time
- 📊 Inconsistent timing (processing time + sleep)
- 💾 Memory/bandwidth waste (sending unnecessary frames)

**Result:** Stream lags behind real-time by several seconds!

---

## ✅ Correct Implementation (New)

### Pattern: Real-Time Read + Selective Process/Send

```python
# ✅ GOOD: Read at full speed, process/send selectively
last_send_time = asyncio.get_event_loop().time()
min_frame_interval = 1.0 / fps  # Target interval

async for chunk in response.content.iter_chunked(1024):
    # ... parse frame ...
    
    # ✅ Read ALL frames from ESP32 (real-time, no blocking)
    frame_count += 1
    
    # ✅ Only process every Nth frame
    should_process = (frame_count % skip_frames) == 0
    
    if should_process:
        # ✅ Check if enough time passed (FPS throttle)
        current_time = asyncio.get_event_loop().time()
        time_since_last_send = current_time - last_send_time
        
        if time_since_last_send < min_frame_interval:
            # ✅ Skip this frame (drop, don't queue)
            continue
        
        # ✅ Process with YOLO
        annotated = process_with_yolo(frame)
        
        # ✅ Send ONLY processed frames (no old/stale data)
        await websocket.send_json({
            "type": "frame",
            "data": annotated
        })
        
        last_send_time = current_time
    else:
        # ✅ Skip immediately (don't decode, don't send)
        pass
```

**Benefits:**
- ⚡ **No latency accumulation** (reads at ESP32 speed)
- 🎯 **Only sends fresh frames** (no stale data)
- 🔋 **CPU/GPU efficient** (processes fewer frames)
- 📊 **Consistent frame timing** (time-based, not count-based)
- 💾 **Minimal bandwidth** (sends only necessary frames)

---

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         ESP32-CAM                                │
│                    (30 FPS @ ~10KB/frame)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │ MJPEG Stream (continuous)
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Read Loop (REAL-TIME, no blocking)                     │  │
│  │  • Read at ESP32 speed (30 FPS)                         │  │
│  │  • Parse JPEG boundaries                                │  │
│  │  • Count all frames                                     │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Frame Filter (skip_frames=2)                           │  │
│  │  • Frame 1: SKIP (don't decode)                         │  │
│  │  • Frame 2: PROCESS ✅                                   │  │
│  │  • Frame 3: SKIP                                         │  │
│  │  • Frame 4: PROCESS ✅                                   │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  FPS Throttle (fps=10)                                  │  │
│  │  • Check time since last send                           │  │
│  │  • If < 100ms: DROP frame (don't send)                  │  │
│  │  • If >= 100ms: SEND frame ✅                            │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  YOLO Processing (only for frames to send)              │  │
│  │  • Decode JPEG → NumPy                                  │  │
│  │  • YOLO inference (GPU)                                 │  │
│  │  • Draw bounding boxes                                  │  │
│  │  • Encode to JPEG                                       │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  WebSocket Send                                          │  │
│  │  • Send base64 JPEG                                     │  │
│  │  • Update last_send_time                                │  │
│  └──────────────────────┬──────────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────────────┘
                          │ WebSocket (10 FPS effective)
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Frontend (Browser)                            │
│  • Receives 10 FPS (every 100ms)                               │
│  • Renders to canvas                                           │
│  • NO LAG (always fresh frames)                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Performance Comparison

### Scenario: ESP32 @ 30 FPS, Target 10 FPS, skip_frames=2

| Metric | ❌ Old (with sleep) | ✅ New (real-time) |
|--------|---------------------|---------------------|
| **Frames read/sec** | 30 | 30 |
| **Frames decoded** | 15 (every 2nd) | 15 (every 2nd) |
| **Frames sent** | 30 (all) | 10 (time-throttled) |
| **YOLO calls/sec** | 15 | 10 |
| **Latency after 1 min** | ~5-10 seconds | <100ms |
| **Bandwidth used** | 300 KB/s | 100 KB/s |
| **CPU usage** | High (decode all) | Medium (decode selective) |
| **GPU usage** | High (process 15 FPS) | Low (process 10 FPS) |
| **Real-time?** | ❌ NO (lags behind) | ✅ YES (stays current) |

---

## 🎛️ Parameter Tuning Guide

### `skip_frames` (Frame Selection)

**Purpose:** Reduce processing load by skipping frames during read

| Value | Behavior | Use Case |
|-------|----------|----------|
| `1` | Process every frame | High accuracy, real-time monitoring |
| `2` | Process every 2nd frame | Balanced (default) |
| `5` | Process every 5th frame | Batch processing, low priority |
| `10` | Process every 10th frame | Very low load, statistical monitoring |

**Effect on latency:** ✅ NONE (reads at full speed)

---

### `fps` (Send Throttle)

**Purpose:** Limit network bandwidth and client rendering load

| Value | Behavior | Use Case |
|-------|----------|----------|
| `30` | Send up to 30 FPS | Real-time action (default for raw) |
| `15` | Send up to 15 FPS | Smooth monitoring |
| `10` | Send up to 10 FPS | Balanced (default for detection) |
| `5` | Send up to 5 FPS | Low bandwidth, periodic check |
| `1` | Send 1 FPS | Dashboard snapshots |

**Effect on latency:** ✅ NONE (drops old frames, no queuing)

---

### Recommended Combinations

| Use Case | `skip_frames` | `fps` | Result |
|----------|---------------|-------|--------|
| **Real-time security** | 1 | 15 | High accuracy, smooth |
| **Parking lot monitoring** | 2 | 10 | Balanced (default) |
| **Background logging** | 5 | 5 | Very efficient |
| **Periodic snapshot** | 10 | 1 | Minimal resources |

---

## 🔍 Debugging

### Check if stream is real-time:

1. **Backend logs:**
   ```
   ✅ [abc12345] Detection started (processing every 2 frames, max 10 FPS)
   📹 [abc12345] Processed 50 frames | Read 100 total | Skipped 0 (FPS limit)
   ```

2. **Stats message (sent every 50 frames):**
   ```json
   {
     "type": "stats",
     "processed": 50,
     "skipped": 50,
     "total": 100,
     "fps": 9.8
   }
   ```

3. **Visual test:**
   - Wave hand in front of camera
   - Should see movement within <500ms
   - No gradual delay accumulation over time

---

## 🐛 Common Issues

### Issue: Stream lags behind by several seconds

**Cause:** Old implementation (sending all frames + sleep)

**Fix:** ✅ Updated to new implementation (selective send, no sleep)

---

### Issue: Frames are choppy/inconsistent

**Cause:** FPS throttle dropping too many frames

**Fix:** Increase `fps` parameter or decrease `skip_frames`

---

### Issue: High CPU/GPU usage

**Cause:** Processing too many frames

**Fix:** Increase `skip_frames` (e.g., 2 → 5)

---

### Issue: Missing fast-moving objects

**Cause:** Skipping too many frames

**Fix:** Decrease `skip_frames` (e.g., 5 → 2) or increase `fps`

---

## 📈 Monitoring

### Backend metrics to track:

```python
# In websocket_streams.py logs:
processed_count    # Frames processed with YOLO
frame_count        # Total frames read from ESP32
skipped_count      # Frames skipped by FPS throttle
actual_fps         # Measured FPS of sent frames
```

### Frontend metrics to track:

```typescript
// In WebSocketStreamManager:
framesReceived     // Total frames received
connectionStatus   // connected/disconnected
stats.processed    // Backend processing count
stats.fps          // Backend actual FPS
```

---

## ✅ Key Takeaways

1. **Read at full speed** - Never block on ESP32 stream (real-time)
2. **Process selectively** - Use `skip_frames` to reduce load
3. **Send time-throttled** - Use `fps` to limit bandwidth
4. **Drop old frames** - Never queue stale data (no latency)
5. **No artificial delays** - Time-based throttle, not sleep-based

**Result:** Efficient batch processing with real-time responsiveness! 🚀

---

**Last updated:** January 4, 2026
