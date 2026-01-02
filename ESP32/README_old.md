# ESP32-CAM Integration Guide

## Architecture

The streaming functionality has been separated into two servers:

1. **Mock ESP32 Server** (`mock_esp32_server.py`) - Port 8081
   - Simulates ESP32-CAM behavior
   - Serves video files as MJPEG streams
   - Provides all ESP32-CAM endpoints for development

2. **Main API Server** (`main_fastapi.py`) - Port 8069
   - AI detection (YOLO + ALPR)
   - Firebase integration
   - Proxies stream from ESP32 (real or mock)

## Quick Start

### Development Mode (Mock ESP32)

```bash
# Terminal 1: Start mock ESP32 server
cd server
conda activate scheduler
python mock_esp32_server.py

# Terminal 2: Start main API server
python main_fastapi.py

# Terminal 3: Start frontend
cd ../frontend
npm run dev
```

### Production Mode (Real ESP32)

```bash
# Set environment variable for real ESP32
export USE_MOCK_ESP32=false
export ESP32_URL=http://192.168.33.122:81

# Start main server (mock server not needed)
python main_fastapi.py
```

## ESP32 Mock Server

### Endpoints

- `GET /stream` - MJPEG stream
  - `?video=parking_a.mp4` - Stream specific video
  - `?fps=20` - Custom frame rate
  - `?resolution=800x600` - Custom resolution

- `GET /capture` - Single frame capture
  - `?quality=90` - JPEG quality

- `GET /status` - Camera status
- `POST /control` - Control commands
- `GET /videos` - List available videos

### Adding Test Videos

Place video files in `server/stream/` folder:

```bash
server/
  stream/
    parking_a.mp4
    parking_b.mp4
    test_video.mp4
```

Access them:
```
http://localhost:8081/stream?video=parking_a.mp4
```

## ESP32 Client

Use `esp32_client.py` to interact with ESP32 (real or mock):

```python
from esp32_client import ESP32Client

# Connect to mock
async with ESP32Client("http://localhost:8081") as client:
    # Test connection
    result = await client.test_connection()
    
    # Capture frame
    frame_bytes = await client.capture_frame()
    
    # Stream frames
    async for frame in client.stream_frames():
        # Process frame
        pass
    
    # Control camera
    await client.control({"action": "set_quality", "quality": 90})
```

## Real ESP32-CAM Integration

### 1. Hardware Setup

- ESP32-CAM module
- Power supply (5V)
- WiFi network connection

### 2. ESP32 Firmware

Upload firmware that provides these endpoints:

```
GET  /                  - Root/status page
GET  /stream            - MJPEG stream
GET  /capture           - Single frame capture
GET  /status            - JSON status
POST /control           - Control commands
```

### 3. Configuration

Update `server/main_fastapi.py`:

```python
ESP32_URL = "http://192.168.33.122:81"  # Your ESP32 IP
USE_MOCK_ESP32 = False
```

Or use environment variables:

```bash
export ESP32_URL=http://192.168.33.122:81
export USE_MOCK_ESP32=false
```

### 4. Test Connection

```bash
# Test API endpoint
curl http://localhost:8069/test/esp32

# View stream in browser
http://localhost:8069/stream
```

## Frontend Integration

The frontend doesn't need to know about mock vs real ESP32.
Always use the proxy endpoint:

```html
<!-- Stream -->
<img src="http://localhost:8069/stream" />

<!-- Snapshot -->
<button onclick="captureFrame()">Capture</button>
<script>
async function captureFrame() {
    const response = await fetch('http://localhost:8069/api/esp32/snapshot');
    const data = await response.json();
    // Use data.imageData
}
</script>
```

## Environment Variables

```bash
# ESP32 Configuration
ESP32_URL=http://192.168.33.122:81        # Real ESP32 URL
MOCK_ESP32_URL=http://localhost:8081      # Mock server URL
USE_MOCK_ESP32=true                        # Use mock (true/false)

# Server Configuration
PORT=8069                                  # Main API port
```

## Troubleshooting

### Mock server not starting

```bash
# Check if port 8081 is in use
lsof -ti:8081 | xargs kill -9

# Check video files exist
ls -la server/stream/*.mp4
```

### Cannot connect to ESP32

```bash
# Test connection
curl http://192.168.33.122:81/status

# Check network
ping 192.168.33.122
```

### Stream lag or buffering

- Reduce FPS: `http://localhost:8081/stream?fps=15`
- Reduce quality in ESP32 settings
- Check network bandwidth

## API Documentation

- Mock ESP32: http://localhost:8081/docs
- Main API: http://localhost:8069/docs
