# Environment Variables Configuration

All hardcoded URLs have been replaced with environment variables for easier configuration and deployment.

## 📋 Configuration Files

### Frontend: `frontend/.env`

```bash
# Backend API URLs
VITE_BACKEND_URL=http://localhost:8069
VITE_ESP32_DIRECT_URL=http://192.168.33.122:81
VITE_MOCK_ESP32_URL=http://localhost:5069

# Firebase Configuration
VITE_FIREBASE_API_KEY=your_key
VITE_FIREBASE_AUTH_DOMAIN=your_domain
VITE_FIREBASE_PROJECT_ID=your_project_id
VITE_FIREBASE_STORAGE_BUCKET=your_bucket
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id
VITE_FIREBASE_MEASUREMENT_ID=your_measurement_id

# Roboflow API
VITE_ROBOFLOW_API_KEY=YOUR_API_KEY_HERE
VITE_ROBOFLOW_MODEL_ID=deteksiparkirkosong
VITE_ROBOFLOW_MODEL_VERSION=6
```

### Backend: `server/.env` (or export in terminal)

```bash
# ESP32 Configuration
USE_MOCK_ESP32=true                           # or false for real ESP32
MOCK_ESP32_URL=http://localhost:5069          # Mock server
ESP32_URL=http://192.168.33.122:81            # Real ESP32-CAM IP

# Firebase Admin SDK (optional)
FIREBASE_CREDENTIALS_PATH=/path/to/credentials.json
```

### Mock ESP32: Environment variable

```bash
# Set default video via environment variable (used by start_mock.py)
MOCK_DEFAULT_VIDEO=videos/parking_c.mp4
```

---

## 🔧 Files Updated

### 1. **Frontend Components**

#### `frontend/src/config/api.ts`
- ✅ Uses `VITE_BACKEND_URL` instead of hardcoded `http://localhost:8000`
- ✅ Dynamic `baseURL` and `streamURL`

#### `frontend/src/pages/StreamViewerPageESP32.tsx`
- ✅ Uses `VITE_BACKEND_URL` (default: `http://localhost:8069`)
- ✅ Uses `VITE_ESP32_DIRECT_URL` (default: `http://192.168.33.122:81`)
- ✅ Uses `VITE_MOCK_ESP32_URL` (default: `http://localhost:5069`)
- ✅ Displays current URLs in connection info

### 2. **Backend Configuration**

#### `server/main_fastapi.py`
- ✅ Reads `USE_MOCK_ESP32`, `MOCK_ESP32_URL`, `ESP32_URL` from environment

### 3. **Mock ESP32 Server**

#### `ESP32/mock_esp32_server.py`
- ✅ Reads `MOCK_DEFAULT_VIDEO` from environment

#### `ESP32/start_mock.py`
- ✅ Sets `MOCK_DEFAULT_VIDEO` when `--video` argument is provided

### 4. **Documentation**

#### `frontend/.env.example`
- ✅ Template with all required variables
- ✅ Comments explaining each variable

#### `QUICK_START_OBJECT_TRACKING.md`
- ✅ Updated with environment variable configuration section

---

## 🚀 Usage Examples

### Development (Default Ports)

```bash
# Frontend .env (already configured)
VITE_BACKEND_URL=http://localhost:8069
VITE_MOCK_ESP32_URL=http://localhost:5069

# Start services (no changes needed)
cd ESP32 && python start_mock.py --video videos/parking_c.mp4 --port 5069
cd server && python main_fastapi.py
cd frontend && npm run dev
```

### Production (Custom Ports)

```bash
# Frontend .env
VITE_BACKEND_URL=http://your-server:8080
VITE_ESP32_DIRECT_URL=http://192.168.1.200:81

# Backend
export USE_MOCK_ESP32=false
export ESP32_URL=http://192.168.1.200:81

# Start backend
cd server && python main_fastapi.py --port 8080
```

### Remote Deployment

```bash
# Frontend .env
VITE_BACKEND_URL=https://api.yourserver.com
VITE_ESP32_DIRECT_URL=https://esp32.yourserver.com

# Backend (on remote server)
export USE_MOCK_ESP32=false
export ESP32_URL=http://internal-esp32-ip:81

# Build frontend
cd frontend && npm run build
# Deploy dist/ folder to web server
```

---

## 🔒 Security Notes

### Frontend `.env`

- ⚠️ **Frontend env vars are PUBLIC** - they are embedded in the built JavaScript
- ✅ Safe to include non-sensitive URLs (backend API endpoints)
- ❌ **Never** put API keys, passwords, or secrets in `VITE_*` variables
- ✅ Firebase config is OK (it's designed to be public with Security Rules)

### Backend `.env`

- ✅ Backend env vars are PRIVATE - server-side only
- ✅ Can include sensitive data (Firebase admin credentials, API keys)
- ✅ Add `.env` to `.gitignore` (never commit to git)

### Best Practices

```bash
# ✅ Good - Frontend
VITE_BACKEND_URL=http://localhost:8069

# ✅ Good - Backend
FIREBASE_CREDENTIALS_PATH=/secrets/firebase-admin.json

# ❌ Bad - Never do this in frontend
VITE_ADMIN_PASSWORD=secretpass123  # Will be visible in browser!
```

---

## 🧪 Testing Configuration

### Test if environment variables are loaded:

**Frontend:**
```bash
cd frontend
npm run dev

# Check browser console:
# The URLs should use your .env values, not hardcoded ones
```

**Backend:**
```bash
cd server
python -c "import os; print('Backend URL:', os.getenv('USE_MOCK_ESP32', 'true'))"
```

### Override for testing:

```bash
# Temporarily override without editing .env
VITE_BACKEND_URL=http://test-server:9000 npm run dev
```

---

## 📦 Deployment Checklist

### Before deploying:

- [ ] Copy `frontend/.env.example` to `frontend/.env`
- [ ] Update all URLs in `frontend/.env` with production values
- [ ] Set `USE_MOCK_ESP32=false` on production backend
- [ ] Update `ESP32_URL` with real ESP32 IP address
- [ ] Test all endpoints with new URLs
- [ ] Build frontend: `npm run build`
- [ ] Verify built files use correct URLs

### Production environment files:

```
frontend/.env          # Production URLs
frontend/.env.example  # Template (commit to git)
server/.env           # Backend config (DO NOT commit)
```

---

## 🆘 Troubleshooting

### Environment variables not working?

1. **Check file name**: Must be `.env` (not `env.txt` or `.env.local`)
2. **Restart dev server**: Changes require restart
3. **Verify variable names**: Must start with `VITE_` for Vite
4. **Check for typos**: Variable names are case-sensitive

### Variables showing as undefined?

```typescript
// ✅ Correct
const url = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8069';

// ❌ Wrong
const url = process.env.VITE_BACKEND_URL;  // process.env doesn't work in Vite!
```

### URLs still hardcoded?

```bash
# Search for hardcoded URLs
cd frontend/src
grep -r "localhost:80" .
grep -r "192.168" .
```

---

## 📚 References

- [Vite Environment Variables](https://vitejs.dev/guide/env-and-mode.html)
- [Frontend .env file](frontend/.env)
- [Frontend .env.example](frontend/.env.example)
- [API Config](frontend/src/config/api.ts)
- [Quick Start Guide](QUICK_START_OBJECT_TRACKING.md)
