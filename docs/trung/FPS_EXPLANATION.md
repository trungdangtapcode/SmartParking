# FPS Setting: Lower FPS ≠ Slower Video Speed

## ❌ Wrong Understanding

**Misconception:** "Lower FPS means slower video playback"

Example: If ESP32 sends 30 FPS and I set `fps=10`, the video plays at 1/3 speed (slow motion).

## ✅ Correct Understanding

**Reality:** "Lower FPS means dropping frames while maintaining real-time speed"

Example: If ESP32 sends 30 FPS and I set `fps=10`, we send every 3rd frame at the same timestamps (real-time).

---

## 🎯 What FPS Parameter Actually Does

### `fps=10` means:

"Send a MAXIMUM of 10 frames per second to the client, but **always show the LATEST frame**"

- ESP32 sends 30 FPS (one frame every 33ms)
- Backend processes and sends 10 FPS (one frame every 100ms)
- **The 10 FPS you see are from timestamps 0s, 0.1s, 0.2s, 0.3s... (REAL-TIME)**
- NOT from frames 1, 2, 3, 4... (which would be slow motion)

---

## 📊 Comparison

### Scenario: ESP32 @ 30 FPS, Target `fps=10`

| Time | ESP32 Sends | Backend Processes | Backend Sends | What Client Sees |
|------|-------------|-------------------|---------------|------------------|
| 0.00s | Frame 1 | ✅ | ✅ | Frame 1 @ 0.00s ✅ |
| 0.03s | Frame 2 | ❌ Skip | ❌ | - |
| 0.06s | Frame 3 | ❌ Skip | ❌ | - |
| 0.10s | Frame 4 | ✅ | ✅ | Frame 4 @ 0.10s ✅ |
| 0.13s | Frame 5 | ❌ Skip | ❌ | - |
| 0.16s | Frame 6 | ❌ Skip | ❌ | - |
| 0.20s | Frame 7 | ✅ | ✅ | Frame 7 @ 0.20s ✅ |

**Result:** Video plays at **normal speed** (real-time), but **smoother** because fewer frames = less bandwidth/processing.

---

## 🔥 The WRONG Logic (Previous Implementation)

```python
# ❌ WRONG: This slows down video playback!
if time_since_last_send < min_frame_interval:
    continue  # Wait for more time to pass before processing next frame
```

**Problem:** We wait until enough time passes, which means we're not draining the buffer fast enough. Frames accumulate, and we play old frames → **video lags behind real-time**.

**Effect:**
- At 5 seconds real-time, video shows 2 seconds worth of content
- Video plays in "slow motion" because we're behind

---

## ✅ The CORRECT Logic (New Implementation)

```python
# ✅ CORRECT: Always read/process, only send at target FPS
async for chunk in response.content.iter_chunked(1024):
    # 1. ALWAYS read frames from ESP32 (real-time, 30 FPS)
    frame = extract_frame_from_chunk(chunk)
    frame_count += 1
    
    # 2. Process every Nth frame (skip_frames)
    if frame_count % skip_frames == 0:
        annotated = process_with_yolo(frame)
        latest_frame_data = annotated
        processed_count += 1
        
        # 3. Send ONLY if enough time passed (FPS throttle)
        if time_since_last_send >= 1.0/fps:
            await websocket.send(latest_frame_data)
            last_send_time = current_time
        # If not enough time, SKIP SENDING but keep processing
        # This ensures we're always working on the LATEST frame
```

**Key differences:**

| Aspect | ❌ Wrong | ✅ Correct |
|--------|---------|-----------|
| **Reading** | Blocked by time wait | Always reads at ESP32 speed |
| **Processing** | Waits for time interval | Processes latest frame |
| **Sending** | Sends when time passed | Sends latest frame when time passed |
| **Buffer** | Grows (old frames) | Stays small (latest frames) |
| **Video speed** | Slow motion | Real-time ✅ |

---

## 🎬 Real-World Example

### Imagine a security camera:

**ESP32:** Sends 30 FPS (every 33ms)
**Target:** `fps=10`, `skip_frames=3`

#### Timeline (first 300ms):

| Real Time | ESP32 Frame | Read? | Process? | Send? | Client Sees |
|-----------|-------------|-------|----------|-------|-------------|
| 0ms | #1 | ✅ | ✅ (every 3rd) | ✅ (t=0ms) | Frame #1 @ 0ms |
| 33ms | #2 | ✅ | ❌ skip | ❌ | - |
| 66ms | #3 | ✅ | ❌ skip | ❌ | - |
| 100ms | #4 | ✅ | ✅ (every 3rd) | ✅ (t>=100ms) | Frame #4 @ 100ms |
| 133ms | #5 | ✅ | ❌ skip | ❌ | - |
| 166ms | #6 | ✅ | ❌ skip | ❌ | - |
| 200ms | #7 | ✅ | ✅ (every 3rd) | ✅ (t>=200ms) | Frame #7 @ 200ms |
| 233ms | #8 | ✅ | ❌ skip | ❌ | - |
| 266ms | #9 | ✅ | ❌ skip | ❌ | - |
| 300ms | #10 | ✅ | ✅ (every 3rd) | ✅ (t>=300ms) | Frame #10 @ 300ms |

**Client playback:** Shows frames #1, #4, #7, #10 at timestamps 0, 100, 200, 300ms → **Real-time!**

---

## 🔍 How to Verify It's Working Correctly

### Test 1: Timestamp Check

Add real-time clock to both streams:

```python
# Add timestamp overlay
cv2.putText(frame, datetime.now().strftime("%H:%M:%S.%f")[:-3], 
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
```

**Expected:** Both `/stream` and `/stream/detect` show the SAME timestamp (±100ms)

### Test 2: Motion Test

Wave hand in front of camera:

**Expected:**
- `/stream` shows wave immediately
- `/stream/detect` shows wave at the same time (not 3 seconds later)
- Both are synchronized

### Test 3: Check Logs

Backend logs should show:

```
📹 Processed 50 frames | Read 150 total | Actual FPS: 9.8 | 
   Process time: 35ms | Buffer: 8192 bytes
```

**Good indicators:**
- ✅ Read count = 3× processed count (with `skip_frames=3`)
- ✅ Actual FPS ≈ target FPS
- ✅ Buffer size small (<50KB)
- ✅ Process time reasonable

---

## 🎯 Summary

### What `fps` Parameter Does:

| Parameter | Actual Meaning | NOT This |
|-----------|---------------|----------|
| `fps=30` | Send up to 30 frames/sec (real-time) | Play video at 30 FPS speed |
| `fps=10` | Send up to 10 frames/sec (real-time, skip 20) | Play video at 1/3 speed |
| `fps=5` | Send up to 5 frames/sec (real-time, skip 25) | Play video at 1/6 speed |
| `fps=1` | Send 1 frame/sec (real-time, skip 29) | Play video at 1/30 speed |

### Key Concept:

**Lower FPS = Fewer frames sent, NOT slower playback speed**

Think of it like a photo sequence:
- 30 FPS = Take photo every 33ms, show all 30 photos
- 10 FPS = Take photo every 33ms, show only 10 photos (every 100ms worth)
- Both show the SAME real-world timeline, just different smoothness

---

## 🚀 The Correct Implementation

```python
# Real-time video streaming with FPS throttle
latest_frame_data = None
last_send_time = 0
min_frame_interval = 1.0 / fps

while True:
    # ALWAYS read at ESP32 speed (don't block!)
    frame = read_from_esp32()
    
    # Process selectively (reduce CPU/GPU load)
    if should_process(frame):
        annotated = yolo(frame)
        latest_frame_data = annotated
    
    # Send at target FPS (bandwidth control)
    if time.now() - last_send_time >= min_frame_interval:
        if latest_frame_data:
            send(latest_frame_data)  # Always send LATEST, not old
            last_send_time = time.now()
```

**This ensures:**
1. ✅ Always reading latest frames from ESP32 (no buffer buildup)
2. ✅ Processing selectively (efficient)
3. ✅ Sending at target FPS (bandwidth control)
4. ✅ **Always showing real-time content (not slow motion)**

---

**Test the updated code - the video should now play at normal speed, just with fewer frames per second!**
