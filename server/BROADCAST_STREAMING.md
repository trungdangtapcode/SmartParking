# Broadcast Streaming (YouTube Live Mode)

## 🎯 Overview

**Problem**: Previously, each client had their own independent stream. When 2 people watched the same camera, they saw different frames at different times.

**Solution**: Broadcast model - ONE source reads from ESP32, ALL clients see the same frame simultaneously (like YouTube Live).

## 🎥 How It Works

```
┌──────────────┐
│   ESP32-CAM  │  ← Single video source
└──────┬───────┘
       │ 30 FPS
       ▼
┌──────────────────┐
│   Broadcaster    │  ← Single reader thread
│  (Frame: 1234)   │
└───┬──────┬───────┘
    │      │
    │      └─────────┐
    ▼      ▼         ▼
┌────────┬────────┬────────┐
│Client 1│Client 2│Client 3│  ← All see Frame 1234
└────────┴────────┴────────┘
```

### Before (❌ Independent Streams):
```
ESP32 ────┬───► Client 1 (Frame 482)
          ├───► Client 2 (Frame 559)
          └───► Client 3 (Frame 391)
```
**Problem**: Different frame IDs, not synchronized

### After (✅ Broadcast):
```
ESP32 ───► Broadcaster ────┬───► Client 1 (Frame 1781)
                            ├───► Client 2 (Frame 1781)
                            └───► Client 3 (Frame 1781)
```
**Result**: Same frame ID, perfectly synchronized!

## 📊 Architecture

### Components

1. **StreamBroadcaster** (`services/stream_broadcaster.py`)
   - Single reader thread per ESP32
   - Reads frames at full speed (30 FPS)
   - Broadcasts to all subscribers
   - Handles client connect/disconnect

2. **BroadcastManager** (`services/stream_broadcaster.py`)
   - Manages multiple broadcasters (one per ESP32)
   - Ensures only ONE broadcaster per source
   - Cleanup inactive broadcasters

3. **Updated Endpoints** (`routers/streams.py`)
   - `/stream` - Raw broadcast stream
   - `/stream/detect` - Detection broadcast stream (TODO)

### Data Flow

```python
# 1. Client connects
client_id = "abc123"
queue = await broadcaster.subscribe_raw()

# 2. Broadcaster reads from ESP32 (single thread)
while True:
    frame = read_from_esp32()  # Frame 1234
    current_frame = frame
    
    # 3. Broadcast to ALL subscribers
    for subscriber_queue in all_queues:
        subscriber_queue.put(frame)  # Everyone gets Frame 1234

# 4. Client receives frame
frame = await queue.get()  # Frame 1234
send_to_browser(frame)

# 5. Client disconnects
broadcaster.unsubscribe(queue)
```

## 🚀 Usage

### Raw Stream (Synchronized)

```html
<!-- Client 1 -->
<img src="http://localhost:8069/stream" />

<!-- Client 2 -->
<img src="http://localhost:8069/stream" />

<!-- Both see Frame 1781 at the same time ✅ -->
```

### With Frame Index Overlay

```python
# In ESP32/mock_esp32_server.py
SHOW_FRAME_ID = True

# All clients will see "Frame: 1781" overlay
```

### Testing Synchronization

1. **Open 2 browser tabs** side-by-side:
   ```
   Tab 1: http://localhost:8069/stream
   Tab 2: http://localhost:8069/stream
   ```

2. **Check frame numbers** (with `SHOW_FRAME_ID = True`):
   ```
   Tab 1: Frame 1781
   Tab 2: Frame 1781  ✅ Same!
   ```

3. **Backend logs**:
   ```
   📡 [Broadcaster a1b2c3d4] Created for: http://localhost:5069/stream
   ▶️  [Broadcaster a1b2c3d4] Started
   ➕ [Broadcaster a1b2c3d4] Raw subscriber added (total: 1)
   ➕ [Broadcaster a1b2c3d4] Raw subscriber added (total: 2)
   📊 [Broadcaster a1b2c3d4] Frame 1781 | FPS: 30.2 | Subs: 2R + 0D
   ```

## 📈 Benefits

### 1. **Perfect Synchronization**
- All clients see the same frame at the same time
- Frame IDs match across all viewers
- Like YouTube Live streaming

### 2. **Resource Efficiency**
- **Before**: 10 clients = 10 ESP32 connections
- **After**: 10 clients = 1 ESP32 connection
- Saves bandwidth and processing power

### 3. **Scalability**
- Single broadcaster can serve unlimited clients
- No performance degradation per client
- Automatic cleanup when no clients

### 4. **Reliability**
- Client disconnect doesn't affect others
- Slow clients don't slow down broadcast
- Frames dropped per-client if too slow

## ⚙️ Configuration

### Queue Buffer Size

```python
# In stream_broadcaster.py
queue = asyncio.Queue(maxsize=5)  # Buffer 5 frames

# If client is slow:
# - Queue fills up → Drop new frames for that client
# - Other clients unaffected
```

### Broadcaster Cleanup

```python
# Automatic cleanup when no subscribers
if not broadcaster.has_subscribers():
    await broadcaster.stop()
    del broadcasters[url]
```

## 🎬 Detection Stream (TODO)

Same broadcast model for detection stream:

```python
# Read from ESP32 (single thread)
frame = read_from_esp32()

# Process with YOLO (only once per frame)
annotated = yolo_detect(frame)

# Broadcast to all detection subscribers
for queue in detect_subscribers:
    queue.put(annotated)
```

**Benefits**:
- YOLO runs ONCE per frame (not once per client)
- All clients see same detections
- Massive performance improvement

## 📝 Implementation Status

### ✅ Completed
- [x] StreamBroadcaster class
- [x] BroadcastManager class
- [x] Raw stream broadcast (`/stream`)
- [x] Client connect/disconnect handling
- [x] Automatic cleanup
- [x] Frame index synchronization

### 🔄 In Progress
- [ ] Detection stream broadcast (`/stream/detect`)
- [ ] WebSocket broadcast support
- [ ] Stats endpoint (active broadcasters, client count)

### 📋 TODO
- [ ] Multi-camera dashboard with synchronized feeds
- [ ] Recording broadcast stream to file
- [ ] Replay functionality
- [ ] Adaptive quality per client

## 🐛 Troubleshooting

### Clients see different frame IDs

**Check**:
1. Are both using `/stream` endpoint? (Not `/stream/proxy`)
2. Is frame index overlay enabled in ESP32?
3. Check backend logs for broadcaster ID

### Broadcaster not starting

**Check**:
1. ESP32 mock server running on port 5069?
2. Backend can connect to ESP32?
3. Check logs for connection errors

### Memory leak / too many broadcasters

**Solution**:
```python
# Manual cleanup
await broadcast_manager.cleanup_inactive()

# Or restart server
```

## 🎉 Expected Results

### Before Broadcast Mode:
```
Client 1: Frame 482
Client 2: Frame 559
Difference: 77 frames 🔴
```

### After Broadcast Mode:
```
Client 1: Frame 1781
Client 2: Frame 1781
Difference: 0 frames ✅
```

**Like YouTube Live** - everyone watches together! 🎥📺

---

**Implementation Date**: 2024-01-04  
**Status**: ✅ Raw stream broadcast complete  
**Next**: Detection stream broadcast with YOLO
