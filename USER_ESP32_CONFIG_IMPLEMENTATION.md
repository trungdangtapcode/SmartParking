# Per-User ESP32 Configuration Implementation

## Overview

Implemented a system where each authenticated user can configure their own ESP32-CAM URL, save it to Firebase, and have the system automatically use their configured camera for streaming.

## Architecture

```
User (authenticated) → Frontend (React)
  → Backend API (FastAPI) - sends X-User-ID header
    → Firebase Firestore - fetch user's esp32_url
      → Proxy stream from user's ESP32-CAM
```

**Fallback**: If no user configuration exists, system uses default `ESP32_URL` environment variable.

---

## Backend Implementation

### 1. Firebase Service (`server/services/firebase_service.py`)

Added 3 new methods to handle user ESP32 configuration:

```python
async def save_user_esp32_config(user_id: str, esp32_url: str, label: Optional[str] = None)
async def get_user_esp32_config(user_id: str) -> Optional[Dict[str, Any]]
async def delete_user_esp32_config(user_id: str) -> bool
```

**Firestore Structure:**
- Collection: `user_esp32_configs`
- Document ID: `user_id` (from Firebase Auth)
- Fields:
  ```json
  {
    "esp32_url": "http://192.168.1.100:81",
    "label": "My Garage Camera",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
  ```

### 2. API Endpoints (`server/main_fastapi.py`)

#### Save User Configuration
```http
POST /api/user/esp32-config
Headers:
  X-User-ID: <firebase_user_id>
  Content-Type: application/json
Body:
  {
    "esp32_url": "http://192.168.1.100:81",
    "label": "My Camera"  // optional
  }
Response: 200 OK with saved configuration
```

#### Get User Configuration
```http
GET /api/user/esp32-config
Headers:
  X-User-ID: <firebase_user_id>
Response: 200 OK with configuration, or 404 if not found
```

#### Delete User Configuration
```http
DELETE /api/user/esp32-config
Headers:
  X-User-ID: <firebase_user_id>
Response: 200 OK with success message
```

### 3. Modified Stream Endpoints

Both stream endpoints now accept optional `X-User-ID` header:

#### Raw Stream
```http
GET /stream
Headers:
  X-User-ID: <firebase_user_id>  // optional
```

#### Stream with Object Detection
```http
GET /stream/detect?conf=0.25&show_labels=true
Headers:
  X-User-ID: <firebase_user_id>  // optional
```

**Logic:**
1. If `X-User-ID` header provided → fetch user's configuration from Firebase
2. If configuration exists → use user's `esp32_url`
3. Otherwise → use default `ESP32_URL` environment variable

**URL Validation:**
- Auto-adds `http://` if protocol missing
- Strips trailing slashes to prevent `//stream` bug
- Validates URL format

---

## Frontend Implementation

### Updated File: `frontend/src/pages/StreamViewerPageESP32.tsx`

#### New Features:

1. **User Configuration Display**
   - Shows current ESP32 configuration status
   - Displays configured URL and label
   - "Configure" button to open modal

2. **Configuration Modal**
   - Input field for ESP32 URL
   - Optional label/name input
   - Save/Delete/Cancel buttons
   - Real-time save status feedback

3. **Auto-fetch Configuration**
   - Automatically loads user's config on component mount
   - Uses Firebase Auth user ID

4. **API Integration**
   ```typescript
   // Fetch user config
   GET /api/user/esp32-config
   Headers: { 'X-User-ID': user.uid }

   // Save user config
   POST /api/user/esp32-config
   Headers: { 'X-User-ID': user.uid }
   Body: { esp32_url, label }

   // Delete user config
   DELETE /api/user/esp32-config
   Headers: { 'X-User-ID': user.uid }
   ```

---

## Usage Flow

### For End Users:

1. **First Time Setup:**
   - User logs in with Firebase Auth
   - Navigates to ESP32 Stream page
   - Clicks "⚙️ Configure" button
   - Enters their ESP32-CAM URL (e.g., `http://192.168.1.100:81`)
   - Optionally adds a label (e.g., "My Garage Camera")
   - Clicks "💾 Save Configuration"
   - System saves to Firebase

2. **Streaming:**
   - User opens stream viewer
   - Frontend automatically sends `X-User-ID` header with stream requests
   - Backend fetches user's ESP32 URL from Firebase
   - Backend proxies stream from user's camera
   - User sees their own camera feed

3. **Updating Configuration:**
   - User clicks "⚙️ Configure"
   - Changes ESP32 URL or label
   - Saves (updates existing configuration)

4. **Removing Configuration:**
   - User opens configuration modal
   - Clicks "🗑️ Delete"
   - System reverts to default ESP32 URL

---

## Testing

### 1. Test API Endpoints

```bash
# Save configuration
curl -X POST http://localhost:8069/api/user/esp32-config \
  -H "X-User-ID: test_user_123" \
  -H "Content-Type: application/json" \
  -d '{"esp32_url": "http://192.168.1.100:81", "label": "Test Camera"}'

# Get configuration
curl -X GET http://localhost:8069/api/user/esp32-config \
  -H "X-User-ID: test_user_123"

# Test stream with user config
curl -I http://localhost:8069/stream \
  -H "X-User-ID: test_user_123"

# Delete configuration
curl -X DELETE http://localhost:8069/api/user/esp32-config \
  -H "X-User-ID: test_user_123"
```

### 2. Test Frontend

1. Start backend: `cd server && python main_fastapi.py`
2. Start frontend: `cd frontend && npm run dev`
3. Login with Firebase Auth
4. Navigate to ESP32 Stream page
5. Configure your ESP32 URL
6. Verify stream uses your camera

### 3. Test Fallback

- Don't configure ESP32 URL
- System should use default `ESP32_URL` from environment
- No errors should occur

---

## Environment Variables

### Backend (`server/.env`)

```bash
# Default ESP32 URL (fallback)
ESP32_URL=http://localhost:5069

# Firebase configuration
FIREBASE_SERVICE_ACCOUNT_PATH=path/to/serviceAccountKey.json
```

### Frontend (`frontend/.env`)

```bash
VITE_BACKEND_URL=http://localhost:8069
```

---

## Database Schema

### Firestore Collection: `user_esp32_configs`

```
user_esp32_configs/
  {user_id}/
    esp32_url: string
    label: string (optional)
    created_at: timestamp
    updated_at: timestamp
```

**Example Document:**
```json
{
  "esp32_url": "http://192.168.1.100:81",
  "label": "Living Room Camera",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T15:45:00Z"
}
```

---

## Security Considerations

1. **Authentication Required:**
   - All endpoints require `X-User-ID` header
   - Frontend gets user ID from Firebase Auth
   - Backend validates user ID exists

2. **User Isolation:**
   - Each user can only access their own configuration
   - Document ID = user_id (prevents cross-user access)

3. **URL Validation:**
   - Backend validates URL format
   - Prevents injection attacks
   - Auto-sanitizes URLs (strips trailing slashes)

4. **Firebase Security Rules:**
   ```javascript
   // Firestore security rules
   match /user_esp32_configs/{userId} {
     allow read, write: if request.auth != null && request.auth.uid == userId;
   }
   ```

---

## Backward Compatibility

- System remains backward compatible
- If `X-User-ID` header not provided → uses default `ESP32_URL`
- Existing functionality unchanged
- No breaking changes

---

## Future Enhancements

1. **Multiple Cameras per User:**
   - Allow users to configure multiple ESP32 cameras
   - Add camera selection dropdown
   - Store array of cameras in Firestore

2. **Camera Presets:**
   - Save multiple camera profiles
   - Quick switch between cameras
   - Share camera configs with team

3. **Health Monitoring:**
   - Ping user's ESP32 to check if online
   - Show connection status in UI
   - Alert when camera goes offline

4. **Camera Discovery:**
   - Auto-discover ESP32 cameras on local network
   - Suggest available cameras to user
   - One-click configuration

---

## Files Modified

### Backend:
- ✅ `server/services/firebase_service.py` - Added user ESP32 config methods
- ✅ `server/main_fastapi.py` - Added API endpoints and modified stream endpoints

### Frontend:
- ✅ `frontend/src/pages/StreamViewerPageESP32.tsx` - Added configuration UI and API integration

### New Files:
- ✅ `USER_ESP32_CONFIG_IMPLEMENTATION.md` - This documentation

---

## Summary

Successfully implemented a per-user ESP32 configuration system that:

- ✅ Stores each user's ESP32-CAM URL in Firebase
- ✅ Automatically uses user's camera when streaming
- ✅ Falls back to default ESP32 URL if not configured
- ✅ Provides UI for users to configure their camera
- ✅ Maintains backward compatibility
- ✅ Includes proper security and validation

Users can now use their own ESP32-CAM instead of a shared camera, making the system truly multi-user and personalized.
