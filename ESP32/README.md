# ESP32 Folder - ESP32-CAM Integration

Everything you need for ESP32-CAM integration with SmartParking.

## 📁 Structure

```
ESP32/
├── esp32_cam_firmware.ino    # Arduino firmware for real ESP32
├── config_template.h          # Configuration template
├── HARDWARE_SETUP.md          # Complete hardware guide
├── mock_esp32_server.py       # Mock server for development
├── esp32_client.py            # Python client library
├── start_mock.py              # Quick start mock server
├── test_esp32_connection.py   # Test script
└── stream/                    # Place .mp4 files here (for mock)
```

## 🚀 Quick Start

### Option 1: Development (Mock - No Hardware Needed)

**Step 1: Start Mock ESP32 Server**
```bash
cd ESP32

# Make sure you have test videos in stream/ folder
mkdir -p stream
# Place some .mp4 files in stream/ folder

# Start mock server (default port 8081)
python start_mock.py

# Or specify video and port:
python start_mock.py --video videos/parking_c.mp4 --port 5069
```

**Step 2: Test Mock Connection**
```bash
# In another terminal
cd ESP32
python test_esp32_connection.py --mock
# Tests: http://localhost:8081
```

**Step 3: Run Backend with Mock**
```bash
cd ../server
eval "$(conda shell.bash hook)" && conda activate scheduler

# Configure to use mock
export USE_MOCK_ESP32=true
export MOCK_ESP32_URL=http://localhost:8081

# Start backend (port 8069)
python main_fastapi.py
```

**Step 4: Run Frontend**
```bash
cd ../frontend
npm run dev
# Frontend at http://localhost:5169
```

**Access Points:**
- Mock ESP32: `http://localhost:8081/stream`
- Backend Proxy: `http://localhost:8069/stream` (proxies to mock)
- Frontend: `http://localhost:5169`

---

### Option 2: Production (Real ESP32-CAM Hardware)

**Step 1: Hardware Setup**
```bash
# See HARDWARE_SETUP.md for complete wiring guide
# 1. Wire ESP32-CAM board
# 2. Install Arduino IDE
# 3. Flash esp32_cam_firmware.ino
# 4. Update WiFi credentials in firmware
# 5. Note ESP32's IP address (e.g., 192.168.33.122)
```

**Step 2: Test Real ESP32 Connection**
```bash
cd ESP32

# Replace with your ESP32's actual IP
python test_esp32_connection.py --url http://192.168.33.122:81

# Or test both mock and real
python test_esp32_connection.py --both
```

**Step 3: Run Backend with Real ESP32**
```bash
cd ../server
eval "$(conda shell.bash hook)" && conda activate scheduler

# Configure to use real ESP32
export USE_MOCK_ESP32=false
export ESP32_URL=http://192.168.33.122:81  # Your ESP32's IP

# Start backend (port 8069)
python main_fastapi.py
```

**Step 4: Run Frontend**
```bash
cd ../frontend
npm run dev
# Frontend at http://localhost:5169
```

**Access Points:**
- Real ESP32: `http://192.168.33.122:81/stream`
- Backend Proxy: `http://localhost:8069/stream` (proxies to real ESP32)
- Frontend: `http://localhost:5169`

## � Testing Commands

```bash
# List available test videos for mock
python start_mock.py --list-videos

# Test mock server
python test_esp32_connection.py --mock

# Test real ESP32 (replace with your IP)
python test_esp32_connection.py --url http://192.168.33.122:81

# Test both at once
python test_esp32_connection.py --both

# Quick capture test
python test_esp32_connection.py --mock --test capture
```

## �📚 Documentation

- **README.md** - This file (quick start)
- **HARDWARE_SETUP.md** - Hardware wiring, Arduino setup, troubleshooting
- **SUMMARY.md** - Complete overview of ESP32 integration
- **QUICK_REFERENCE.md** - Command cheat sheet
- See code files for detailed comments

## 🔗 Integration Architecture

```
Frontend (localhost:5169)
    ↓
Backend (localhost:8069/stream) ← Proxy layer
    ↓
    ├─→ Mock ESP32 (localhost:8081/stream)     [Development]
    └─→ Real ESP32 (192.168.33.122:81/stream) [Production]
```

**Switch between mock/real:**
```bash
# Use mock (development)
export USE_MOCK_ESP32=true
export MOCK_ESP32_URL=http://localhost:8081

# Use real (production)
export USE_MOCK_ESP32=false
export ESP32_URL=http://192.168.33.122:81
```

No frontend changes needed - it always connects to backend at port 8069!

---

For complete documentation, see files in this folder.
