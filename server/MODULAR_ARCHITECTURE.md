# SmartParking Server - Modular Architecture

## 📁 Project Structure

```
server/
├── main_fastapi.py          # Main application entry point (slim, ~130 lines)
├── main_fastapi_old.py      # Old monolithic file (backup)
│
├── middleware/              # Middleware components
│   ├── __init__.py
│   └── disconnect_watcher.py   # Client disconnect detection for streaming
│
├── models/                  # Data models and tracking
│   ├── __init__.py
│   └── stream_tracking.py      # Stream connection tracking (WeakSet registry)
│
├── routers/                 # API route modules
│   ├── __init__.py
│   ├── health.py               # Health check & debug endpoints
│   ├── user_config.py          # User ESP32 configuration (save/get/delete)
│   ├── streams.py              # Streaming endpoints (raw, proxy, detection)
│   ├── esp32.py                # ESP32 hardware endpoints (snapshot, status, test)
│   ├── ai_detection.py         # AI endpoints (plate detection, object tracking)
│   └── firebase.py             # Firebase history endpoints
│
└── services/                # Business logic services (existing)
    ├── ai_service.py
    └── firebase_service.py
```

## 🔧 Key Features

### 1. **Modular Router System**
Each router module is self-contained with:
- Route definitions
- Service dependency injection via `init_router()`
- Proper error handling
- Type hints and docstrings

### 2. **Disconnect Detection Middleware**
`middleware/disconnect_watcher.py` - Watches for `http.disconnect` messages:
```python
async with cancel_on_disconnect(request):
    # Your streaming code here
    # Raises CancelledError when client disconnects
```

### 3. **Stream Connection Tracking**
`models/stream_tracking.py` - Tracks active streams using WeakSet:
```python
from models.stream_tracking import active_streams, StreamConnection

stream = StreamConnection("abc123")
# Automatically added to global registry
# Automatically cleaned up when garbage collected
```

## 🚀 Running the Server

```bash
cd server
conda activate scheduler
python main_fastapi.py
```

## 📖 API Documentation

After starting the server, visit:
- **Swagger UI**: http://localhost:8069/docs
- **ReDoc**: http://localhost:8069/redoc

## 🧩 Adding New Endpoints

1. **Create new router** in `routers/` directory:
```python
# routers/my_feature.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/my-feature", tags=["My Feature"])

# Global service instances
my_service = None

def init_router(svc):
    global my_service
    my_service = svc

@router.get("/endpoint")
async def my_endpoint():
    return {"status": "ok"}
```

2. **Register router** in `main_fastapi.py`:
```python
from routers import my_feature

# In lifespan function:
my_feature.init_router(my_service)

# After app creation:
app.include_router(my_feature.router)
```

## 🔍 Benefits of Modular Structure

✅ **Maintainability** - Each module < 300 lines, easy to understand
✅ **Testability** - Routers can be tested independently  
✅ **Scalability** - Easy to add new features without touching main file
✅ **Code Organization** - Related endpoints grouped together
✅ **Dependency Injection** - Services injected via `init_router()`
✅ **Type Safety** - Proper imports and type hints throughout

## 📝 Migration Notes

- Old monolithic file backed up as `main_fastapi_old.py`
- All functionality preserved, just reorganized
- No breaking changes to API endpoints
- Same performance characteristics

## 🐛 Debugging

Check active streams:
```bash
curl http://localhost:8069/debug/streams
```

Health check:
```bash
curl http://localhost:8069/health
```

## 🔄 Reverting to Old Structure

If needed:
```bash
cd server
mv main_fastapi.py main_fastapi_modular.py
mv main_fastapi_old.py main_fastapi.py
```
