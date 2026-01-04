# How to Use Custom ESP32 IP in Multi-Camera Viewer

## Quick Start

### 1. Start the Backend
```bash
cd server
conda activate scheduler
python main_fastapi.py
```
Backend will run on **http://localhost:8069**

### 2. Start the Frontend
```bash
cd frontend
npm run dev
```
Frontend will run on **http://localhost:5169**

### 3. Navigate to Multi-Camera Viewer
In your browser, go to the Multi-Camera page.

## Adding Custom ESP32-CAM

### Step-by-Step:

1. **Select "ESP32-CAM"** as source type
   - The first option with 📹 icon

2. **Choose "✏️ Custom ESP32 IP"**
   - This is the last option in ESP32 selection

3. **Enter Your ESP32 IP Address**
   - A yellow input box will appear
   - Enter IP in one of these formats:
     - `192.168.1.100:81`
     - `http://192.168.1.100:81`
   
   Example:
   ```
   192.168.1.123:81
   ```

4. **Optional: Add Custom Label**
   - Give your camera a friendly name
   - Example: "Entrance Camera" or "Parking Lot A"

5. **Optional: Configure Parking & Camera**
   - Select Parking Lot ID
   - Enter Camera ID (e.g., CAM1, CAM2)
   - Check "Use for Check-in" if this is the entrance camera

6. **Click "➕ Thêm Stream"**
   - Stream tile will be added to the grid

7. **Start Streaming**
   - Click the big green "▶️ START ALL STREAMS" button
   - All streams will start simultaneously

## Multiple ESP32 Cameras

You can add multiple custom ESP32 cameras:

```
Camera 1: 192.168.1.100:81 → "Main Entrance"
Camera 2: 192.168.1.101:81 → "Parking Area A"
Camera 3: 192.168.1.102:81 → "Parking Area B"
Camera 4: 192.168.10.50:81 → "Exit Gate"
```

Simply repeat the process for each camera!

## Troubleshooting

### ❌ Stream shows "Cannot connect"
**Solution:**
1. Check ESP32 is powered on
2. Verify IP address is correct
3. Test ESP32 stream in browser: `http://192.168.1.100:81/stream`
4. Ensure backend is running on port 8069
5. Check network connectivity

### ❌ Backend not starting
**Solution:**
```bash
# Check port 8069 is available
lsof -i :8069

# Kill process if needed
kill -9 <PID>

# Restart backend
python main_fastapi.py
```

### ❌ Frontend not connecting to backend
**Solution:**
Check `.env` file:
```bash
# frontend/.env
VITE_BACKEND_URL=http://localhost:8069
```

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      Frontend (5169)                     │
│  User enters: 192.168.1.100:81                          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         │ Requests:
                         │ /stream/proxy?esp32_url=http://192.168.1.100:81
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│                   Backend (8069)                         │
│  • Proxies stream from custom ESP32                     │
│  • Handles CORS, errors, timeouts                       │
│  • Adds /stream to URL if missing                       │
└────────────────────────┬─────────────────────────────────┘
                         │
                         │ Proxies to:
                         │ http://192.168.1.100:81/stream
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│              ESP32-CAM (192.168.1.100:81)                │
│  • Returns MJPEG stream                                 │
│  • Real hardware camera                                 │
└──────────────────────────────────────────────────────────┘
```

## Benefits

✅ **No code changes needed** - Just enter IP and go!
✅ **Secure** - All streams go through backend
✅ **Flexible** - Add unlimited cameras
✅ **Easy** - User-friendly interface
✅ **Production-ready** - Works with real ESP32-CAM hardware

## API Endpoint

The backend exposes:
```
GET /stream/proxy?esp32_url=<url>

Example:
http://localhost:8069/stream/proxy?esp32_url=http://192.168.1.100:81
```

This endpoint:
- Accepts any ESP32-CAM URL
- Auto-appends `/stream` if missing
- Proxies MJPEG stream
- Returns 502 if ESP32 unreachable

## Testing with Mock Server

For development without real ESP32:

```bash
# Terminal 1: Start ESP32 mock
cd ESP32
python start_mock.py --port 5069

# Terminal 2: Start backend
cd server
python main_fastapi.py

# Terminal 3: Start frontend
cd frontend
npm run dev
```

Then use:
- Predefined cameras (ESP32-CAM 1, 2, 3)
- Or custom: `localhost:5069`

## Next Steps

1. Flash your ESP32-CAM with streaming firmware
2. Connect ESP32 to your network
3. Note the IP address
4. Add it in the Multi-Camera Viewer!

Happy streaming! 📹
