# Firebase Architecture Explanation

## 📍 Where is Firebase Service?

Firebase exists in **BOTH** frontend and backend, but they serve **different purposes** and use **different SDKs**:

```
┌─────────────────────────────────────────────────────────────┐
│                    Firebase Project                          │
│              (cs311-95828.firebaseapp.com)                   │
└─────────────────────────────────────────────────────────────┘
                    ↙                        ↘
         ┌──────────────────┐        ┌──────────────────┐
         │    FRONTEND      │        │     BACKEND      │
         │  (React + Vite)  │        │  (Python FastAPI)│
         └──────────────────┘        └──────────────────┘
         │                           │
         │ Firebase JS SDK           │ Firebase Admin SDK
         │ (Client-side)             │ (Server-side)
         │                           │
         ├─ Authentication           ├─ Firestore Database
         ├─ User Login/Logout        ├─ Save/Read Data
         └─ Get user.uid             └─ Admin Operations
```

---

## 🎯 Two Different Firebase Services

### 1. **Frontend Firebase** (`frontend/src/config/firebase.ts`)

**SDK Used:** Firebase JavaScript SDK (Client-side)

**Configuration:** Uses `.env` file with `VITE_` prefix
```properties
VITE_FIREBASE_API_KEY=AIzaSyDAuQJFF1YWa6qluE34hQZzDvETuYoIO6E
VITE_FIREBASE_AUTH_DOMAIN=cs311-95828.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=cs311-95828
...
```

**Purpose:**
- ✅ User Authentication (Login/Logout/Register)
- ✅ Get current user information (`user.uid`, `user.email`)
- ✅ Real-time UI updates
- ✅ Client-side Firebase operations

**Code:**
```typescript
// frontend/src/config/firebase.ts
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY, // From .env
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  // ...
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
```

**Why API Key is Exposed:**
- ✅ **This is SAFE and NORMAL!**
- Firebase API keys are meant to be public (they're in frontend code)
- Security is handled by Firebase Security Rules, not by hiding the API key
- API key just identifies which Firebase project to connect to
- Real security comes from:
  - Firebase Authentication (user must login)
  - Firestore Security Rules (who can read/write what)

---

### 2. **Backend Firebase** (`server/services/firebase_service.py`)

**SDK Used:** Firebase Admin SDK (Server-side)

**Configuration:** Uses Service Account JSON file (NOT API key!)
```python
# Backend looks for these files:
server/firebase_credentials.json
server/serviceAccountKey.json
server/firebase-adminsdk.json
```

**Purpose:**
- ✅ Database operations (Firestore)
- ✅ Admin-level access (bypass security rules)
- ✅ Save detection results
- ✅ Save plate history
- ✅ Save user ESP32 configurations
- ✅ Manage all database operations

**Code:**
```python
# server/services/firebase_service.py
import firebase_admin
from firebase_admin import credentials, firestore

class FirebaseService:
    def __init__(self, credentials_path: Optional[str] = None):
        # Look for service account JSON file
        if credentials_path is None:
            possible_paths = [
                "firebase_credentials.json",
                "serviceAccountKey.json",
                "firebase-adminsdk.json",
            ]
        
        cred = credentials.Certificate(credentials_path)
        firebase_admin.initialize_app(cred)
        self.db = firestore.client()
```

**Why NO API Key in Backend .env?**
- ❌ Backend doesn't use API keys!
- ✅ Backend uses **Service Account** credentials (JSON file)
- Service Account = Admin access with private key
- Much more powerful than API key
- Should NEVER be committed to git or exposed publicly

---

## 🔐 Authentication Flow

```
1. User visits frontend → Enters email/password
                ↓
2. Frontend → Firebase Auth → Verifies credentials
                ↓
3. Firebase returns: user.uid, user.email, token
                ↓
4. Frontend stores: user info in React context
                ↓
5. Frontend sends API request to backend
   Headers: { 'X-User-ID': user.uid }
                ↓
6. Backend receives user_id → Uses Firebase Admin SDK
                ↓
7. Backend queries Firestore: "Get data for this user_id"
                ↓
8. Backend returns data to frontend
```

**Example:**
```typescript
// Frontend: User is logged in
const { user } = useAuth(); // user.uid = "abc123"

// Frontend sends request
fetch('/api/user/esp32-config', {
  headers: {
    'X-User-ID': user.uid  // Send user ID to backend
  }
});
```

```python
# Backend receives request
@app.get("/api/user/esp32-config")
async def get_config(user_id: str = Header(None, alias="X-User-ID")):
    # Use Firebase Admin SDK to query Firestore
    config = await firebase_service.get_user_esp32_config(user_id)
    return config
```

---

## 📂 File Structure

```
project/
├── frontend/
│   ├── .env                         ← Firebase API keys (PUBLIC, safe to expose)
│   │   ├── VITE_FIREBASE_API_KEY
│   │   ├── VITE_FIREBASE_PROJECT_ID
│   │   └── ...
│   │
│   └── src/config/firebase.ts       ← Firebase JS SDK (Authentication)
│
├── server/
│   ├── .env                         ← NO Firebase config here!
│   │   └── ESP32_URL=...            ← Only ESP32 URL
│   │
│   ├── serviceAccountKey.json       ← Service Account (SECRET, don't commit!)
│   │   └── Contains private_key     ← Admin credentials
│   │
│   └── services/firebase_service.py ← Firebase Admin SDK (Database)
```

---

## ❓ Why This Architecture?

### Frontend Firebase (JS SDK):
- ✅ Handles user authentication (login/logout)
- ✅ Lightweight, works in browser
- ✅ Real-time updates for UI
- ✅ Limited by security rules (users can only access their own data)

### Backend Firebase (Admin SDK):
- ✅ Full admin access to Firestore
- ✅ Can read/write any data (bypasses security rules)
- ✅ Secure server-side operations
- ✅ Perfect for saving detection results, logs, admin tasks

---

## 🔒 Security Model

### Frontend (Public):
```
User → Firebase Auth → Get user.uid
     ↓
User can only access their own data
Security enforced by Firestore Rules
```

### Backend (Private):
```
Backend → Service Account → Admin access
       ↓
Backend can access ALL data
Security enforced by:
  - Service account kept secret
  - Backend validates X-User-ID header
  - Backend enforces business logic
```

---

## 🎯 Summary

| Aspect | Frontend Firebase | Backend Firebase |
|--------|------------------|------------------|
| **Location** | `frontend/src/config/firebase.ts` | `server/services/firebase_service.py` |
| **SDK** | Firebase JS SDK | Firebase Admin SDK |
| **Config** | API keys in `.env` (public) | Service Account JSON (secret) |
| **Purpose** | Authentication, User login | Database operations, Admin access |
| **Access Level** | User-level (limited) | Admin-level (full access) |
| **Security** | Firestore security rules | Service account private key |
| **Can See** | Only user's own data | ALL data in Firestore |

---

## 📝 Current Setup Status

### ✅ Frontend Firebase - WORKING
- Configuration: `frontend/.env` exists with all keys
- Service: `frontend/src/config/firebase.ts` configured
- Auth Context: `frontend/src/context/AuthContext.tsx` working
- Users can login/logout successfully

### ⚠️ Backend Firebase - NEEDS SERVICE ACCOUNT
- Configuration: **Missing `serviceAccountKey.json`**
- Service: `server/services/firebase_service.py` ready
- Status: Will work once service account file is added

---

## 🚀 To Make Backend Firebase Work

### Step 1: Get Service Account Key from Firebase Console

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project: **cs311-95828**
3. Click ⚙️ Settings → Project Settings
4. Go to "Service Accounts" tab
5. Click "Generate new private key"
6. Download the JSON file

### Step 2: Add to Server

```bash
# Place the downloaded file in server directory
cp ~/Downloads/cs311-95828-firebase-adminsdk-xxxxx.json server/serviceAccountKey.json

# Or rename to one of these:
server/firebase_credentials.json
server/serviceAccountKey.json  ← Recommended
server/firebase-adminsdk.json
```

### Step 3: Add to .gitignore

```bash
# Make sure this is in server/.gitignore
echo "serviceAccountKey.json" >> server/.gitignore
echo "firebase_credentials.json" >> server/.gitignore
echo "firebase-adminsdk.json" >> server/.gitignore
```

### Step 4: Test

```bash
cd server
python main_fastapi.py

# Should see:
# 🔥 Initializing Firebase Admin SDK...
# ✅ Firebase initialized
```

---

## 🎓 Key Takeaway

**Two Firebase Services, One Project:**
- **Frontend**: User authentication & UI (public API keys)
- **Backend**: Database operations & admin tasks (private service account)
- Both connect to same Firebase project: `cs311-95828`
- Both work together to create a secure, scalable app

This is the **standard architecture** for Firebase applications! ✅
