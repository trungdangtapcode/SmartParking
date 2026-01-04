# Multi-Camera Viewer Updates

## Overview
Updated `MultiStreamViewerPage.tsx` to work with backend on `localhost:8069` and added custom ESP32 IP input feature.

## Key Changes

### 1. Backend Configuration
- **Backend URL**: Now uses `VITE_BACKEND_URL` from environment variables (defaults to `http://localhost:8069`)
- **Removed Dependencies**: No longer imports `API_CONFIG`
- All streams are proxied through the backend

### 2. Custom ESP32 IP Feature
Users can now input their own ESP32-CAM IP addresses:

#### Frontend Changes (`MultiStreamViewerPage.tsx`):
- Added "Custom ESP32 IP" option in ESP32 camera selection
- New state: `customESP32IP` for storing user-entered IP
- Validation: Ensures IP is provided when custom option is selected
- Stream URL format: `${BACKEND_URL}/stream/proxy?esp32_url=${encodeURIComponent(customIP)}`

#### Predefined ESP32 Options:
```typescript
const ESP32_CAMERAS = [
  { id: 'esp32_1', name: 'ESP32-CAM 1', ip: 'http://192.168.1.100:81' },
  { id: 'esp32_2', name: 'ESP32-CAM 2', ip: 'http://192.168.1.101:81' },
  { id: 'esp32_3', name: 'ESP32-CAM 3', ip: 'http://192.168.1.102:81' },
  { id: 'esp32_custom', name: '✏️ Custom ESP32 IP', ip: 'custom' }, // NEW
];
```

#### Custom IP Input UI:
- Yellow-themed input box appears when "Custom ESP32 IP" is selected
- Accepts formats:
  - `192.168.1.100:81`
  - `http://192.168.1.100:81`
- Auto-adds `http://` if missing
- Clear instructions and examples provided

### 3. Backend Proxy Endpoint
Added new endpoint in `server/main_fastapi.py`:

```python
@app.get("/stream/proxy")
async def proxy_custom_esp32_stream(
    esp32_url: str = Query(..., description="Custom ESP32-CAM URL")
):
    """
    Proxy custom ESP32-CAM stream from any IP address
    
    Usage:
    - <img src="http://localhost:8069/stream/proxy?esp32_url=http://192.168.1.100:81" />
    """
    # Auto-appends /stream if not present
    # Proxies MJPEG stream from custom ESP32
```

### 4. Architecture
```
┌─────────────┐         ┌──────────────┐         ┌─────────────────┐
│  Frontend   │ ───────>│   Backend    │ ───────>│   ESP32-CAM     │
│  (Port      │         │  (Port 8069) │         │  (Custom IP)    │
│   5169)     │         │              │         │  192.168.x.x:81 │
└─────────────┘         └──────────────┘         └─────────────────┘
     │                        │
     │                        │ proxies stream
     │                        │
     └─── ALWAYS goes ────────┘
          through backend
          (no direct ESP32 connection)
```

### 5. Removed Features
- ❌ Removed "Mock FFmpeg" option (streamlined to 2 options: ESP32 & Video)
- ❌ Removed `API_CONFIG` dependency
- ❌ Removed direct ESP32 connection mode

### 6. UI Improvements
- Source type selection: 2 options (ESP32-CAM, Video File)
- Informative note box explaining backend proxy architecture
- Numbered steps (1️⃣, 2️⃣, 3️⃣, 4️⃣) for user guidance
- Custom IP input with visual feedback and validation

## Usage Example

### Adding Custom ESP32-CAM:

1. **Select Source Type**: Click "ESP32-CAM"
2. **Select Custom Option**: Click "✏️ Custom ESP32 IP"
3. **Enter IP**: Type `192.168.1.123:81` or `http://192.168.1.123:81`
4. **Optional**: Add custom label and parking/camera config
5. **Add Stream**: Click "➕ Thêm Stream"
6. **Start Streaming**: Click "▶️ START ALL STREAMS"

### Backend Proxy:
```bash
# Frontend requests:
http://localhost:5169 → img src="http://localhost:8069/stream/proxy?esp32_url=http://192.168.1.123:81"

# Backend proxies to:
http://192.168.1.123:81/stream

# MJPEG stream flows back through backend to frontend
```

## Environment Setup

### Frontend `.env`:
```bash
VITE_BACKEND_URL=http://localhost:8069
```

### Backend `.env`:
```bash
# Default ESP32 (for /stream endpoint)
ESP32_URL=http://localhost:5069
```

## Benefits

1. ✅ **Flexible**: Users can add any ESP32-CAM by IP
2. ✅ **Secure**: All streams go through backend (CORS, auth, etc.)
3. ✅ **Simple**: No need to reconfigure code for new cameras
4. ✅ **Development-Friendly**: Still supports local mock server
5. ✅ **Production-Ready**: Works with real ESP32-CAM hardware

## Testing

### Test with Mock Server:
```bash
# Terminal 1: Start backend
cd server
conda activate scheduler
python main_fastapi.py

# Terminal 2: Start ESP32 mock
cd ESP32
python start_mock.py --port 5069

# Terminal 3: Start frontend
cd frontend
npm run dev
```

### Test with Real ESP32:
1. Flash ESP32-CAM with streaming firmware
2. Note ESP32 IP (e.g., 192.168.1.100:81)
3. In frontend, select "Custom ESP32 IP"
4. Enter IP and start streaming

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stream` | GET | Proxy default ESP32 from env var |
| `/stream/proxy?esp32_url=<url>` | GET | Proxy custom ESP32 from any IP |
| `/stream/detect` | GET | Stream with YOLO detection |
| `/api/esp32/snapshot` | GET | Capture single frame |

## Notes

- **CORS**: Backend allows all origins in development
- **Timeout**: Stream connections have 30s read timeout
- **Error Handling**: Clear error messages if ESP32 unreachable
- **Auto-Stream**: `/stream` auto-appends if not in URL
- **Validation**: Frontend validates IP before adding stream
