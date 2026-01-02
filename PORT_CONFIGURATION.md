# Port Configuration Summary

Quick reference for all service ports in SmartParking system.

## 🔌 Default Ports

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| **Frontend** | 5169 | http://localhost:5169 | React app (Vite dev server) |
| **Backend** | 8069 | http://localhost:8069 | FastAPI server (AI + API) |
| **ESP32 Server** | 5069 | http://localhost:5069 | ESP32 streaming (dev/prod) |

## 📝 Configuration Files

### Frontend: `frontend/.env`
```bash
VITE_BACKEND_URL=http://localhost:8069
VITE_ESP32_URL=http://localhost:5069
```

### Backend: `server/main_fastapi.py`
```python
ESP32_URL = os.getenv("ESP32_URL", "http://192.168.33.122:81")      # Real hardware
MOCK_ESP32_URL = os.getenv("MOCK_ESP32_URL", "http://localhost:5069") # Development
USE_MOCK_ESP32 = os.getenv("USE_MOCK_ESP32", "true").lower() == "true"
```

### ESP32 Server: Command line
```bash
python start_mock.py --port 5069
```

## 🚀 Quick Start Commands

```bash
# Terminal 1: ESP32 Server
cd ESP32
python start_mock.py --video videos/parking_c.mp4 --port 5069

# Terminal 2: Backend
cd server
eval "$(conda shell.bash hook)" && conda activate scheduler
python main_fastapi.py

# Terminal 3: Frontend
cd frontend
npm run dev
```

## 🔧 Troubleshooting Port Issues

### Check if ports are in use:
```bash
lsof -i :5069  # ESP32 server
lsof -i :8069  # Backend
lsof -i :5169  # Frontend
```

### Test endpoints:
```bash
# ESP32 server
curl http://localhost:5069/status

# Backend health
curl http://localhost:8069/health

# Backend stream (should return data)
timeout 2 curl -s http://localhost:8069/stream | head -c 100

# Frontend
curl http://localhost:5169
```

### Kill processes on port:
```bash
# Find process
lsof -ti :5069

# Kill it
kill -9 $(lsof -ti :5069)
```

## ⚠️ Common Mistakes

### ❌ Wrong: ESP32 server on different port than backend expects
```bash
# ESP32 running on 8081
python start_mock.py --port 8081

# Backend expects 5069
MOCK_ESP32_URL=http://localhost:5069  # ← Mismatch!
```

### ✅ Correct: Ports must match
```bash
# ESP32 on 5069
python start_mock.py --port 5069

# Backend configured for 5069
MOCK_ESP32_URL=http://localhost:5069  # ← Match!
```

## 🔄 Changing Ports

### To change ESP32 port:

1. **Update ESP32 startup:**
   ```bash
   python start_mock.py --port NEW_PORT
   ```

2. **Update frontend `.env`:**
   ```bash
   VITE_ESP32_URL=http://localhost:NEW_PORT
   ```

3. **Update backend (if needed):**
   ```bash
   export MOCK_ESP32_URL=http://localhost:NEW_PORT
   ```

4. **Restart services** (frontend needs restart after .env change)

### To change backend port:

1. **Edit `server/main_fastapi.py`:**
   ```python
   uvicorn.run("main_fastapi:app", port=NEW_PORT, ...)
   ```

2. **Update frontend `.env`:**
   ```bash
   VITE_BACKEND_URL=http://localhost:NEW_PORT
   ```

3. **Restart both backend and frontend**

## 🌐 Production Deployment

For production with real ESP32-CAM hardware:

```bash
# Frontend .env
VITE_BACKEND_URL=http://your-server.com:8069
VITE_ESP32_URL=http://192.168.33.122:81

# Backend
export USE_MOCK_ESP32=false
export ESP32_URL=http://192.168.33.122:81

# No ESP32 server needed (using real hardware)
```

## 📊 Port Flow Diagram

```
User Browser
    ↓ (port 5169)
Frontend React App
    ↓ (http://localhost:8069)
Backend FastAPI
    ↓ (http://localhost:5069)
ESP32 Server
    ↓ (streams video)
MJPEG Stream
```

## 🔍 Quick Diagnosis

**Problem:** Frontend shows "Cannot connect to stream"

**Check:**
1. ✅ ESP32 server running? → `curl http://localhost:5069/status`
2. ✅ Backend running? → `curl http://localhost:8069/health`
3. ✅ Backend can reach ESP32? → `curl http://localhost:8069/stream`
4. ✅ Ports match in config?
5. ✅ Restart frontend after .env changes?

**Most common fix:** Restart backend (it has auto-reload but sometimes needs manual restart)
