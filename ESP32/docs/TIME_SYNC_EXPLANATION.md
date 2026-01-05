# Time Synchronization in Mock ESP32 Server

## Problem
When starting multiple camera streams at different times, each camera shows different timestamps even though they should represent the same scene.

## Solution
All videos are synchronized to a **global timeline** starting at Unix epoch 0 (1970-01-01 00:00:00).

## How It Works

### Calculation
```
current_time = time.time()  # Current Unix timestamp (e.g., 1736025600)
video_duration = total_frames / fps  # Video length in seconds (e.g., 60s)
elapsed_time = current_time % video_duration  # Position in loop (e.g., 23.456s)
frame_index = int(elapsed_time * fps)  # Which frame to show
```

### Example
**Scenario:** Two cameras with different videos
- Camera A: 60-second video, 30fps (1800 frames)
- Camera B: 45-second video, 30fps (1350 frames)
- Current Unix time: 1736025623.456 seconds

**Calculation for Camera A:**
```
elapsed_time = 1736025623.456 % 60 = 23.456s
frame_index = 23.456 * 30 = 703
Display: "Time: 00:00:23.456"
```

**Calculation for Camera B:**
```
elapsed_time = 1736025623.456 % 45 = 23.456s
frame_index = 23.456 * 30 = 703
Display: "Time: 00:00:23.456"
```

**Result:** Both cameras show **"Time: 00:00:23.456"** even though:
- Camera A is at frame 703 of its 1800-frame video
- Camera B is at frame 703 of its 1350-frame video
- They were started at different times
- They represent different angles of the same scene at the same moment

## Benefits

✅ **Perfect synchronization** - All cameras show the same timestamp
✅ **No drift** - Sync is maintained indefinitely
✅ **Start anytime** - Cameras can be started/stopped at any time
✅ **Deterministic** - Same timestamp always shows the same frame
✅ **Loop seamlessly** - Videos loop perfectly when duration is reached

## Visual Example

```
Real World Time:  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━▶
                  10:00:00          10:00:20          10:00:40

Camera A Started: ┌─────────────────────────────────────▶
                  │  @ 10:00:00
                  │  Shows: 00:00:00 → 00:00:20 → 00:00:40
                  
Camera B Started:           ┌─────────────────────────▶
                            │  @ 10:00:10
                            │  Shows: 00:00:10 → 00:00:30

Synchronized:     📹 @ 10:00:20 = "Time: 00:00:20.000" (BOTH)
                  📹 @ 10:00:35 = "Time: 00:00:35.000" (BOTH)
```

## Frame ID Overlay

When `SHOW_FRAME_ID = True`, each frame displays:
- **Frame:** The actual frame number in that specific video
- **Time:** The synchronized timestamp (same across all cameras)

This helps verify synchronization is working correctly.

## Technical Notes

- Videos loop when they reach their duration
- Frame seeking uses `cv2.CAP_PROP_POS_FRAMES` for accuracy
- Each camera can use different video files (different angles of same scene)
- FPS can be adjusted per stream without breaking synchronization
- The synchronized time resets at each video's duration (modulo operation)

## Testing Synchronization

1. Start Camera A: `python start_mock.py --port 5070 --video videos/parking_a.mp4`
2. Wait 10 seconds
3. Start Camera B: `python start_mock.py --port 5069 --video videos/parking_b.mp4`
4. Both cameras should show the **same timestamp** in the overlay
5. The frame numbers will be different, but timestamps match

## Configuration

In `mock_esp32_server.py`:
```python
SHOW_FRAME_ID = True  # Enable/disable frame overlay
```

Set to `False` in production to remove the debugging overlay.
