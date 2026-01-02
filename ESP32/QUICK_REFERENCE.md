# 📋 ESP32 Quick Reference Card

## 🚀 Quick Start Commands

### Development (Mock ESP32)
```bash
cd ESP32 && python start_mock.py
```
Mock at: http://localhost:8081

### Production (Real ESP32)  
```bash
export USE_MOCK_ESP32=false
export ESP32_URL=http://192.168.33.122:81
cd server && python main_fastapi.py
```

### Testing
```bash
cd ESP32
python test_esp32_connection.py --mock    # Test mock
python test_esp32_connection.py --url IP  # Test real
python test_esp32_connection.py --both    # Test both
```

## 📁 File Locations

```
ESP32/
├── mock_esp32_server.py      → Mock server
├── esp32_cam_firmware.ino    → Real firmware
├── esp32_client.py           → Client library
├── start_mock.py             → Quick start
├── test_esp32_connection.py  → Tests
├── HARDWARE_SETUP.md         → Hardware guide
└── stream/                   → Test videos
```

## 🌐 Endpoints

| URL | Description |
|-----|-------------|
| `http://localhost:8081` | Mock ESP32 |
| `http://localhost:8069` | Backend API |
| `http://localhost:5169` | Frontend |

### ESP32 Endpoints (Mock or Real)
- `/stream` - MJPEG stream
- `/capture` - Single frame
- `/status` - Status JSON
- `/control` - Control POST

## ⚙️ Configuration

### Switch to Real ESP32
```bash
export USE_MOCK_ESP32=false
export ESP32_URL=http://192.168.33.122:81
```

### Switch to Mock
```bash
export USE_MOCK_ESP32=true
export MOCK_ESP32_URL=http://localhost:8081
```

## 🔧 Common Tasks

### Add Test Video
```bash
cp video.mp4 ESP32/stream/
```

### List Videos
```bash
cd ESP32 && python start_mock.py --list-videos
```

### Flash ESP32 Firmware
1. Open `ESP32/esp32_cam_firmware.ino` in Arduino IDE
2. Update WiFi credentials
3. Select "AI Thinker ESP32-CAM" board
4. Connect GPIO0 to GND
5. Upload
6. Disconnect GPIO0
7. Reset

### Find ESP32 IP
```bash
# Serial monitor or router admin panel
```

## 🐛 Troubleshooting

### Mock won't start
```bash
lsof -ti:8081 | xargs kill -9
python start_mock.py
```

### Real ESP32 not connecting
- Check power (need 5V 2A)
- Check WiFi credentials
- See `ESP32/HARDWARE_SETUP.md`

### Backend can't find ESP32
```bash
curl http://localhost:8081/status  # Mock
curl http://192.168.33.122:81/status  # Real
```

## 📚 Documentation

- **Quick Start:** `ESP32/README.md`
- **Hardware:** `ESP32/HARDWARE_SETUP.md`
- **Overview:** `ESP32/SUMMARY.md`
- **Architecture:** `server/ARCHITECTURE_CHANGES.md`

## ✅ Checklist

### Development Setup
- [ ] Start mock: `cd ESP32 && python start_mock.py`
- [ ] Add videos to `ESP32/stream/`
- [ ] Test: `python test_esp32_connection.py --mock`
- [ ] Start backend: `cd server && python main_fastapi.py`
- [ ] Start frontend: `cd frontend && npm run dev`

### Production Setup
- [ ] Order ESP32-CAM hardware
- [ ] Follow `ESP32/HARDWARE_SETUP.md`
- [ ] Flash firmware
- [ ] Find ESP32 IP
- [ ] Test: `python test_esp32_connection.py`
- [ ] Configure: `USE_MOCK_ESP32=false`
- [ ] Deploy!

---

**Keep this card handy for quick reference!** 📌
