# ESP32 Mock Server - Frame Index Debug Feature

## 🔍 Purpose

Added frame index overlay to help debug stream synchronization issues between `/stream` (raw) and `/stream/detect` (with detection).

## ⚙️ Configuration

In `mock_esp32_server.py`, line ~32:

```python
# 🔍 DEBUG: Show frame index overlay on video
SHOW_FRAME_ID = True  # Set to False to disable frame index overlay
```

## 📹 What It Does

When `SHOW_FRAME_ID = True`:
- Shows "Frame: X" in green text at top-left corner of every frame
- Frame counter increments for each frame sent
- Resets to 0 when video loops
- Semi-transparent black background for better readability

**Visual:**
```
┌─────────────────┐
│ Frame: 123      │  ← Green text on semi-transparent black background
│                 │
│                 │
│   [Video]       │
│                 │
└─────────────────┘
```

## 🧪 How to Use for Debugging

### Test 1: Verify Real-Time Sync

1. **Start ESP32 mock server:**
   ```bash
   cd ESP32
   python start_mock.py --port 5069
   ```

2. **Open both streams side-by-side:**
   - Left: `http://localhost:8069/stream` (raw)
   - Right: `http://localhost:8069/stream/detect` (detection)

3. **Watch frame numbers:**
   - **Expected:** Both streams show approximately the same frame number (±2-3 frames)
   - **Good:** Raw stream shows frame 150, detection shows frame 148
   - **Bad:** Raw stream shows frame 150, detection shows frame 50 (100 frames behind!)

### Test 2: Verify Frame Skipping

With `skip_frames=2` (process every 2nd frame):

```
Raw stream:   Frame 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20
Detection:    Frame 10,     12,     14,     16,     18,     20
                     ✓      ✓      ✓      ✓      ✓      ✓
```

**Expected:** Detection stream shows every Nth frame from raw stream

### Test 3: Verify FPS Throttling

With `fps=10` (target 10 FPS, ESP32 sends 30 FPS):

```
Time:     0.0s  0.1s  0.2s  0.3s  0.4s  0.5s
Raw:      F1    F4    F7    F10   F13   F16    (all frames)
Detect:   F1    F4    F7    F10   F13   F16    (every ~3rd frame)
          ✓     ✓     ✓     ✓     ✓     ✓
```

**Expected:** Detection stream shows frames at correct time intervals (every 100ms for 10 FPS)

## 📊 Interpreting Results

### ✅ Good (Synchronized)

```
[12:34:56.000] Raw stream:       Frame 150
[12:34:56.050] Detection stream: Frame 148
```
**Analysis:** Only 2 frames behind → Synchronized ✅

### ⚠️ Warning (Slightly Behind)

```
[12:34:56.000] Raw stream:       Frame 150
[12:34:56.200] Detection stream: Frame 135
```
**Analysis:** 15 frames behind → Processing slightly slow, but catching up

### 🔴 Bad (Severely Lagging)

```
[12:34:56.000] Raw stream:       Frame 150
[12:34:56.000] Detection stream: Frame 50
```
**Analysis:** 100 frames behind (3+ seconds) → Not real-time!

**Solution:** Increase `skip_frames` or reduce `fps`

## 🎛️ API Usage

### Streaming endpoint:
```
GET http://localhost:5069/stream
```
- Shows frame index on all frames
- Controlled by `SHOW_FRAME_ID` constant

### Capture endpoint:
```
GET http://localhost:5069/capture?show_frame_id=true
GET http://localhost:5069/capture?show_frame_id=false
```
- Optional query parameter to override `SHOW_FRAME_ID`

## 🔧 Disable Frame Index

To disable the frame index overlay:

```python
# In mock_esp32_server.py
SHOW_FRAME_ID = False  # No overlay
```

Or for single capture:
```
http://localhost:5069/capture?show_frame_id=false
```

## 📝 Implementation Details

**Overlay rendering:**
```python
# Semi-transparent black background
overlay = frame.copy()
cv2.rectangle(overlay, (5, 5), (200, 50), (0, 0, 0), -1)
cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

# Green text
cv2.putText(frame, f"Frame: {frame_idx}", 
            (10, 35), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.8, 
            (0, 255, 0),  # Green
            2, 
            cv2.LINE_AA)
```

**Frame counter:**
- Increments on each frame sent
- Resets to 0 when video loops
- Persistent across requests (global counter per video stream)

## 🚀 Quick Start

1. **Enable frame index:**
   ```python
   SHOW_FRAME_ID = True  # Already default
   ```

2. **Start server:**
   ```bash
   cd ESP32
   python start_mock.py --port 5069
   ```

3. **Open streams and compare frame numbers!**

## ✅ Success Criteria

After fixing real-time streaming:

| Metric | Expected Value |
|--------|---------------|
| Frame difference | <5 frames |
| Time lag | <200ms |
| Buffer growth | None (stays small) |
| Frame numbers | Increasing together |

---

**Now you can visually verify that your streams are synchronized! 🎉**
