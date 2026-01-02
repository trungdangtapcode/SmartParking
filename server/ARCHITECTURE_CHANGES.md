# 🚀 SmartParking - Separated Architecture

## What Changed?

The ESP32 streaming functionality has been **separated** from the main API server into dedicated components:

### Before (Monolithic)
```
main_fastapi.py
├── AI Detection
├── Firebase
├── ESP32 Streaming (embedded)
└── Video file streaming (embedded)
```

### After (Separated)
```
mock_esp32_server.py (Port 8081)
├── MJPEG streaming
├── Frame capture
├── Camera control
└── Status endpoints

main_fastapi.py (Port 8069)
├── AI Detection (YOLO + ALPR)
├── Firebase integration
├── Stream proxy (from ESP32)
└── API endpoints

esp32_client.py
└── Reusable ESP32 client library
```

## New Files

1. **`mock_esp32_server.py`** - Mock ESP32-CAM server
   - Simulates real ESP32-CAM behavior
   - Serves video files as MJPEG streams
   - Ready for real ESP32 integration

2. **`esp32_client.py`** - ESP32 client library
   - Reusable client for ESP32 communication
   - Works with both mock and real ESP32
   - Async/await support

3. **`start_project.sh`** - One-command startup
   - Starts all services automatically
   - Handles conda environment
   - Logs to /tmp/*.log

4. **`stop_project.sh`** - One-command shutdown
   - Stops all services cleanly
   - Cleans up PIDs and ports

5. **`ESP32_INTEGRATION.md`** - Complete guide
   - Architecture documentation
   - Real ESP32 integration steps
   - Troubleshooting guide

## Benefits

### 1. **Separation of Concerns**
- Main API focuses on AI and business logic
- Mock server handles streaming only
- Easy to swap mock with real ESP32

### 2. **Development Friendly**
- Test without real ESP32 hardware
- Multiple video sources (stream/*.mp4)
- Fast iteration

### 3. **Production Ready**
- Template for real ESP32 integration
- Environment variable configuration
- No code changes needed to switch modes

### 4. **Easier Debugging**
- Separate logs for each service
- Independent service restart
- Clear error messages

## Quick Start

### Option 1: Automatic (Recommended)
```bash
cd server
./start_project.sh
```

This starts:
- Mock ESP32 on port 8081
- Main API on port 8069
- Frontend on port 5169

### Option 2: Manual
```bash
# Terminal 1: Mock ESP32
conda activate scheduler
python mock_esp32_server.py

# Terminal 2: Main API
python main_fastapi.py

# Terminal 3: Frontend
cd ../frontend
npm run dev
```

### Option 3: Real ESP32
```bash
# Set environment
export USE_MOCK_ESP32=false
export ESP32_URL=http://192.168.33.122:81

# Start (mock server not needed)
python main_fastapi.py
```

## Testing

### 1. Check Mock ESP32
```bash
# Browser
http://localhost:8081/docs

# Stream test
http://localhost:8081/stream

# API test
curl http://localhost:8081/status
```

### 2. Check Main API
```bash
# Browser
http://localhost:8069/docs

# Health check
curl http://localhost:8069/health

# ESP32 connection test
curl http://localhost:8069/test/esp32

# Proxied stream
http://localhost:8069/stream
```

### 3. Check Frontend
```bash
# Browser
http://localhost:5169
```

## Adding Test Videos

1. Create `server/stream/` folder (if not exists)
2. Add MP4 files:
   ```bash
   server/stream/
     parking_a.mp4
     parking_b.mp4
     test_video.mp4
   ```
3. Access via:
   ```
   http://localhost:8081/stream?video=parking_a.mp4
   ```

## Configuration

### Environment Variables
```bash
# Mock ESP32 (default)
export USE_MOCK_ESP32=true
export MOCK_ESP32_URL=http://localhost:8081

# Real ESP32
export USE_MOCK_ESP32=false
export ESP32_URL=http://192.168.33.122:81
```

### Code Configuration
Edit `server/main_fastapi.py`:
```python
ESP32_URL = "http://192.168.33.122:81"  # Your ESP32 IP
USE_MOCK_ESP32 = False
```

## Logs

When using `start_project.sh`, logs are saved to:
```bash
tail -f /tmp/mock_esp32.log      # Mock ESP32 server
tail -f /tmp/main_api.log        # Main API server
tail -f /tmp/frontend.log        # Frontend
```

## Stopping Services

```bash
# Option 1: Use stop script
./stop_project.sh

# Option 2: Ctrl+C if running in foreground

# Option 3: Kill by port
lsof -ti:8081 | xargs kill -9  # Mock ESP32
lsof -ti:8069 | xargs kill -9  # Main API
lsof -ti:5169 | xargs kill -9  # Frontend
```

## Next Steps

### For Development
1. ✅ Use mock server with test videos
2. ✅ Develop features without hardware
3. ✅ Test with different video sources

### For Production
1. Get ESP32-CAM hardware
2. Upload firmware (see ESP32_INTEGRATION.md)
3. Configure ESP32_URL
4. Set USE_MOCK_ESP32=false
5. Deploy!

## API Endpoints Unchanged

The frontend doesn't need any changes:
- `GET /stream` - Still works (proxied)
- `GET /api/esp32/snapshot` - Still works
- All AI endpoints - Same as before

## Migration Guide

### Old Code
```python
# Embedded in main_fastapi.py
@app.get("/stream")
async def stream_video():
    # Complex streaming logic
    pass
```

### New Code
```python
# Separated: mock_esp32_server.py handles streaming
# main_fastapi.py just proxies
@app.get("/stream")
async def proxy_esp32_stream():
    return proxy_to_esp32()
```

### Frontend (No Changes)
```html
<!-- Same URL, different architecture -->
<img src="http://localhost:8069/stream" />
```

## Architecture Diagram

```
┌─────────────────┐
│    Frontend     │
│   Port 5169     │
└────────┬────────┘
         │
         │ HTTP Requests
         ▼
┌─────────────────┐
│   Main API      │
│   Port 8069     │
│                 │
│  • AI Detection │
│  • Firebase     │
│  • Stream Proxy │
└────────┬────────┘
         │
         │ Proxy Stream
         ▼
┌─────────────────┐      ┌─────────────────┐
│  Mock ESP32     │  OR  │  Real ESP32-CAM │
│  Port 8081      │      │  192.168.x.x:81 │
│                 │      │                 │
│  • MJPEG Stream │      │  • MJPEG Stream │
│  • Video Files  │      │  • Live Camera  │
└─────────────────┘      └─────────────────┘
```

## Documentation

- **ESP32_INTEGRATION.md** - Complete integration guide
- **mock_esp32_server.py** - Mock server source (well commented)
- **esp32_client.py** - Client library (with usage examples)
- **start_project.sh** - Startup script (self-documented)

## Support

If you encounter issues:
1. Check logs in `/tmp/*.log`
2. Verify ports are not in use
3. Ensure conda environment is activated
4. Review ESP32_INTEGRATION.md
5. Test mock server independently

---

**Ready to use!** Run `./start_project.sh` and everything will start automatically. 🚀
