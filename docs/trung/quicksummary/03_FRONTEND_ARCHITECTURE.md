# Smart Parking System - Frontend Architecture

## 📱 Frontend Overview

The frontend is a modern React application built with TypeScript, Vite, and Tailwind CSS, providing a comprehensive user interface for parking management.

## 🛠️ Technology Stack

### Core Technologies
- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite (Fast, modern bundler)
- **Styling**: Tailwind CSS + Custom CSS
- **UI Components**: Shadcn/UI components
- **Routing**: React Router v6
- **State Management**: React Context API
- **Real-time**: Firebase SDK + WebSocket API

### Key Libraries
```json
{
  "react": "^18.x",
  "react-router-dom": "^6.x",
  "firebase": "^10.x",
  "tailwindcss": "^3.x",
  "typescript": "^5.x",
  "vite": "^5.x"
}
```

## 📁 Frontend Structure

```
frontend/
├── src/
│   ├── main.tsx                  # Application entry point
│   ├── App.tsx                   # Main app component with routing
│   ├── index.css                 # Global styles
│   │
│   ├── components/               # Reusable UI components
│   │   ├── ProtectedRoute.tsx    # Route guard for auth
│   │   ├── StreamViewer.tsx      # Video stream display
│   │   ├── ParkingSpaceCanvas.tsx # Canvas for parking spaces
│   │   └── [other components]
│   │
│   ├── pages/                    # Page components (19 pages)
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   ├── AccountPage.tsx
│   │   ├── SpaceDetectionPage.tsx
│   │   ├── DetectionViewerPage.tsx
│   │   ├── HistoryPage.tsx
│   │   ├── StatsPage.tsx
│   │   ├── AlertsPage.tsx
│   │   ├── MultiCameraPage.tsx
│   │   ├── StreamHostPage.tsx
│   │   ├── MultiStreamHostPage.tsx
│   │   ├── StreamViewerPage.tsx
│   │   ├── StreamViewerPageESP32.tsx
│   │   ├── StreamViewerPageESP32WebSocket.tsx
│   │   ├── MultiStreamViewerPage.tsx
│   │   ├── PlateHistoryPage.tsx
│   │   ├── ObjectTrackingPage.tsx
│   │   ├── ParkingLotManagementPage.tsx
│   │   ├── ParkingSpaceEditorPage.tsx
│   │   └── WorkerMonitorPage.tsx
│   │
│   ├── services/                 # API and Firebase services
│   │   ├── apiService.ts         # Backend API client
│   │   ├── parkingSpaceService.ts # Parking space operations
│   │   ├── cameraService.ts      # Camera management
│   │   └── firebaseService.ts    # Firebase operations
│   │
│   ├── config/                   # Configuration
│   │   └── firebase.ts           # Firebase client config
│   │
│   ├── context/                  # React Context providers
│   │   └── AuthContext.tsx       # Authentication context
│   │
│   ├── types/                    # TypeScript definitions
│   │   ├── parkingLot.types.ts   # Parking lot types
│   │   ├── detection.types.ts    # Detection types
│   │   └── [other types]
│   │
│   ├── utils/                    # Utility functions
│   │   ├── imageUtils.ts         # Image processing
│   │   └── dateUtils.ts          # Date formatting
│   │
│   └── assets/                   # Static assets
│       ├── images/
│       └── icons/
│
├── public/                       # Public static files
│   └── vite.svg
│
├── index.html                    # HTML template
├── package.json                  # Dependencies
├── tsconfig.json                 # TypeScript config
├── vite.config.ts                # Vite configuration
├── tailwind.config.js            # Tailwind CSS config
└── postcss.config.js             # PostCSS config
```

## 🎨 User Interface Pages

### 1. **Space Detection Page** (`/`)
**Purpose**: Main landing page for parking space detection

**Features**:
- Upload video file for processing
- Configure detection parameters
- View detection results
- Real-time progress tracking

**Key Components**:
- Video uploader
- Detection settings panel
- Results display
- Statistics dashboard

### 2. **Detection Viewer Page** (`/detection-viewer`)
**Purpose**: Real-time detection stream viewer

**Features**:
- Live WebSocket connection to worker
- Real-time annotated video stream
- Detection statistics
- Multiple camera support

**Key Components**:
- WebSocket stream viewer
- Camera selector
- Statistics panel
- Connection status indicator

**Technical Details**:
```typescript
// WebSocket connection
const ws = new WebSocket(
  `ws://localhost:8069/ws/viewer/detection?camera_id=${cameraId}&user_id=${userId}`
);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'frame') {
    // Display base64 image
    setFrameData(data.frame);
    setMetadata(data.metadata);
  }
};
```

### 3. **Worker Monitor Page** (`/worker-monitor`)
**Purpose**: Admin dashboard for monitoring worker status

**Features**:
- Real-time worker statistics
- Per-camera metrics
- ByteTrack configuration display
- System information panel
- Live detection counts

**Layout**:
```
┌────────────────────────────────────────────────────┐
│  Left: Detection Streams                           │
│  ├─ Camera 1 stream                                │
│  ├─ Camera 2 stream                                │
│  └─ Camera N stream                                │
├────────────────────────────────────────────────────┤
│  Right: Information Panels                         │
│  ├─ Detection & Tracking Stats                     │
│  │  • Total vehicles detected                      │
│  │  • Parking spaces per camera                    │
│  │  • Occupancy breakdown                          │
│  ├─ ByteTrack Configuration                        │
│  │  • Tracking parameters                          │
│  │  • Performance settings                         │
│  └─ System Information                             │
│     • GPU status                                   │
│     • AI models                                    │
│     • Backend services                             │
└────────────────────────────────────────────────────┘
```

### 4. **Parking Space Editor Page** (`/parking-spaces`)
**Purpose**: Admin tool to define parking spaces

**Features**:
- Interactive canvas for drawing spaces
- Drag and drop to move spaces
- Resize handles for adjusting dimensions
- Space naming and management
- Save/delete operations

**User Flow**:
1. Select parking lot
2. Select camera
3. View live camera feed
4. Draw rectangles for parking spaces
5. Name each space
6. Save to Firebase

**Canvas Implementation**:
```typescript
// Drawing mode
const startDrawing = (e: React.MouseEvent) => {
  const rect = canvasRef.current!.getBoundingClientRect();
  const x = (e.clientX - rect.left) / rect.width;
  const y = (e.clientY - rect.top) / rect.height;
  setDrawingStart({ x, y });
};

const finishDrawing = (e: React.MouseEvent) => {
  const rect = canvasRef.current!.getBoundingClientRect();
  const endX = (e.clientX - rect.left) / rect.width;
  const endY = (e.clientY - rect.top) / rect.height;
  
  const newSpace = {
    x: Math.min(drawingStart.x, endX),
    y: Math.min(drawingStart.y, endY),
    width: Math.abs(endX - drawingStart.x),
    height: Math.abs(endY - drawingStart.y)
  };
  
  setParkingSpaces([...parkingSpaces, newSpace]);
};
```

### 5. **Parking Lot Management Page** (`/parking-management`)
**Purpose**: Manage parking lots and cameras

**Features**:
- Add/edit parking lots
- Configure cameras
- Set parking lot capacity
- Assign cameras to lots
- View lot statistics

### 6. **History Page** (`/history`)
**Purpose**: View detection history

**Features**:
- Paginated detection records
- Date/time filtering
- Camera filtering
- Export functionality
- Detailed detection view

### 7. **Plate History Page** (`/plate-history`)
**Purpose**: View license plate recognition history

**Features**:
- Search by plate number
- Filter by date range
- View vehicle images
- Export records

### 8. **Stats Page** (`/stats`)
**Purpose**: Statistical analysis and charts

**Features**:
- Occupancy trends
- Peak hours analysis
- Camera performance metrics
- Custom date ranges

### 9. **Alerts Page** (`/alerts`)
**Purpose**: View and manage alerts

**Features**:
- Real-time alert notifications
- Alert filtering by severity
- Mark alerts as resolved
- Alert history

### 10. **Object Tracking Page** (`/object-tracking`)
**Purpose**: Upload and track objects in videos

**Features**:
- Video upload
- Track visualization
- Export tracking data

### 11. **Multi-Camera Pages**
- **MultiCameraPage**: View multiple cameras simultaneously
- **MultiStreamHostPage**: Host multiple streams
- **MultiStreamViewerPage**: View multiple live streams

### 12. **Stream Pages**
- **StreamHostPage**: Host a single stream
- **StreamViewerPage**: Basic stream viewer
- **StreamViewerPageESP32**: ESP32-specific viewer
- **StreamViewerPageESP32WebSocket**: WebSocket-based viewer

### 13. **Account Management**
- **LoginPage**: User login
- **RegisterPage**: User registration
- **AccountPage**: Profile management

## 🔐 Authentication & Authorization

### AuthContext (`context/AuthContext.tsx`)

Provides global authentication state using React Context:

```typescript
interface AuthContextType {
  user: User | null;
  role: 'user' | 'admin' | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthProvider: React.FC = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [role, setRole] = useState<'user' | 'admin' | null>(null);
  
  useEffect(() => {
    // Listen to Firebase auth state changes
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        setUser(firebaseUser);
        // Fetch user role from Firestore
        const userDoc = await getDoc(doc(db, 'users', firebaseUser.uid));
        setRole(userDoc.data()?.role || 'user');
      } else {
        setUser(null);
        setRole(null);
      }
    });
    
    return unsubscribe;
  }, []);
  
  // ... login, register, logout functions
};
```

### Protected Routes

```typescript
export const ProtectedRoute: React.FC<Props> = ({ 
  children, 
  requireAdmin = false 
}) => {
  const { user, role, loading } = useAuth();
  
  if (loading) return <LoadingSpinner />;
  
  if (!user) return <Navigate to="/login" />;
  
  if (requireAdmin && role !== 'admin') {
    return <Navigate to="/" />;
  }
  
  return <>{children}</>;
};

// Usage in App.tsx
<Route 
  path="/parking-spaces" 
  element={
    <ProtectedRoute requireAdmin>
      <ParkingSpaceEditorPage />
    </ProtectedRoute>
  } 
/>
```

## 🎨 Styling & UI Design

### Tailwind CSS Configuration

```javascript
// tailwind.config.js
module.exports = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        strawberry: {
          50: '#fff1f2',
          100: '#ffe4e6',
          200: '#fecdd3',
          // ... more shades
          900: '#881337',
        },
        matcha: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          // ... more shades
          900: '#14532d',
        }
      }
    }
  },
  plugins: []
}
```

### Design System

**Color Palette**:
- Primary: Strawberry pink tones
- Secondary: Matcha green tones
- Status colors:
  - Success: Green
  - Warning: Yellow
  - Error: Red
  - Info: Blue

**Typography**:
- Font family: System fonts (sans-serif)
- Headings: Bold, larger sizes
- Body: Regular weight, readable sizes

**Components**:
- Buttons: Rounded corners, hover effects
- Cards: White background, subtle shadows
- Inputs: Bordered, focus states
- Modals: Centered overlay with backdrop

## 🔌 API Integration

### API Service (`services/apiService.ts`)

```typescript
const API_BASE_URL = 'http://localhost:8069';

export const apiService = {
  // Plate detection
  async detectPlate(imageData: string): Promise<PlateDetection> {
    const response = await fetch(`${API_BASE_URL}/api/plate-detect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ imageData })
    });
    return response.json();
  },
  
  // Object tracking
  async trackObjects(videoFile: File): Promise<TrackingResult> {
    const formData = new FormData();
    formData.append('video', videoFile);
    
    const response = await fetch(`${API_BASE_URL}/api/object-tracking`, {
      method: 'POST',
      body: formData
    });
    return response.json();
  },
  
  // Detection history
  async getDetectionHistory(limit = 50): Promise<Detection[]> {
    const response = await fetch(
      `${API_BASE_URL}/api/firebase/history?limit=${limit}`
    );
    return response.json();
  }
};
```

### Firebase Service (`services/firebaseService.ts`)

```typescript
import { collection, addDoc, query, where, getDocs } from 'firebase/firestore';
import { db } from '../config/firebase';

export const firebaseService = {
  // Save parking space
  async saveParkingSpace(space: ParkingSpace): Promise<string> {
    const docRef = await addDoc(collection(db, 'parkingSpaceDefinitions'), {
      ...space,
      createdAt: new Date()
    });
    return docRef.id;
  },
  
  // Get parking spaces by camera
  async getParkingSpacesByCamera(cameraId: string): Promise<ParkingSpace[]> {
    const q = query(
      collection(db, 'parkingSpaceDefinitions'),
      where('cameraId', '==', cameraId)
    );
    const snapshot = await getDocs(q);
    return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
  },
  
  // Real-time listener
  subscribeToSpaces(cameraId: string, callback: (spaces: ParkingSpace[]) => void) {
    const q = query(
      collection(db, 'parkingSpaceDefinitions'),
      where('cameraId', '==', cameraId)
    );
    
    return onSnapshot(q, (snapshot) => {
      const spaces = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      callback(spaces);
    });
  }
};
```

## 🎯 State Management

### Context API Usage

```typescript
// Example: Parking Space Context
interface ParkingSpaceContextType {
  spaces: ParkingSpace[];
  selectedSpace: ParkingSpace | null;
  setSpaces: (spaces: ParkingSpace[]) => void;
  selectSpace: (space: ParkingSpace) => void;
  addSpace: (space: ParkingSpace) => void;
  updateSpace: (id: string, data: Partial<ParkingSpace>) => void;
  deleteSpace: (id: string) => void;
}

export const ParkingSpaceProvider: React.FC = ({ children }) => {
  const [spaces, setSpaces] = useState<ParkingSpace[]>([]);
  const [selectedSpace, setSelectedSpace] = useState<ParkingSpace | null>(null);
  
  const addSpace = (space: ParkingSpace) => {
    setSpaces(prev => [...prev, space]);
  };
  
  const updateSpace = (id: string, data: Partial<ParkingSpace>) => {
    setSpaces(prev => prev.map(s => 
      s.id === id ? { ...s, ...data } : s
    ));
  };
  
  const deleteSpace = (id: string) => {
    setSpaces(prev => prev.filter(s => s.id !== id));
  };
  
  return (
    <ParkingSpaceContext.Provider value={{
      spaces,
      selectedSpace,
      setSpaces,
      selectSpace: setSelectedSpace,
      addSpace,
      updateSpace,
      deleteSpace
    }}>
      {children}
    </ParkingSpaceContext.Provider>
  );
};
```

## 🔄 Real-Time Features

### WebSocket Integration

```typescript
// Custom hook for WebSocket connection
function useDetectionStream(cameraId: string, userId: string) {
  const [frame, setFrame] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<DetectionMetadata | null>(null);
  const [connected, setConnected] = useState(false);
  
  useEffect(() => {
    const ws = new WebSocket(
      `ws://localhost:8069/ws/viewer/detection?camera_id=${cameraId}&user_id=${userId}`
    );
    
    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'frame') {
        setFrame(data.frame);
        setMetadata(data.metadata);
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnected(false);
    };
    
    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };
    
    return () => {
      ws.close();
    };
  }, [cameraId, userId]);
  
  return { frame, metadata, connected };
}

// Usage in component
function DetectionViewer({ cameraId }: Props) {
  const { user } = useAuth();
  const { frame, metadata, connected } = useDetectionStream(cameraId, user.uid);
  
  return (
    <div>
      {connected ? (
        <>
          <img src={`data:image/jpeg;base64,${frame}`} />
          <p>Detected: {metadata?.detected_count} vehicles</p>
        </>
      ) : (
        <p>Connecting...</p>
      )}
    </div>
  );
}
```

### Firestore Real-Time Listeners

```typescript
useEffect(() => {
  const unsubscribe = firebaseService.subscribeToSpaces(
    cameraId,
    (spaces) => {
      // Update UI when spaces change
      setSpaces(spaces);
      
      // Update canvas visualization
      redrawCanvas(spaces);
    }
  );
  
  return () => unsubscribe();
}, [cameraId]);
```

## 🎨 Component Examples

### StreamViewer Component

```typescript
interface StreamViewerProps {
  streamUrl: string;
  showControls?: boolean;
  onError?: (error: Error) => void;
}

export const StreamViewer: React.FC<StreamViewerProps> = ({
  streamUrl,
  showControls = true,
  onError
}) => {
  const imgRef = useRef<HTMLImageElement>(null);
  const [error, setError] = useState<string | null>(null);
  
  const handleError = () => {
    const err = new Error('Failed to load stream');
    setError(err.message);
    onError?.(err);
  };
  
  return (
    <div className="relative">
      <img
        ref={imgRef}
        src={streamUrl}
        alt="Live stream"
        className="w-full h-auto"
        onError={handleError}
      />
      
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50">
          <p className="text-white">{error}</p>
        </div>
      )}
      
      {showControls && (
        <div className="absolute bottom-4 left-4 right-4">
          <button className="bg-white px-4 py-2 rounded">
            Pause
          </button>
        </div>
      )}
    </div>
  );
};
```

## 🚀 Build & Deployment

### Development
```bash
npm run dev
# Runs on http://localhost:5169
```

### Production Build
```bash
npm run build
# Outputs to dist/ directory
```

### Preview Production Build
```bash
npm run preview
```

## 📊 Performance Optimizations

### Code Splitting
```typescript
// Lazy load pages
const ParkingSpaceEditorPage = lazy(() => import('./pages/ParkingSpaceEditorPage'));
const WorkerMonitorPage = lazy(() => import('./pages/WorkerMonitorPage'));

// Wrap in Suspense
<Suspense fallback={<LoadingSpinner />}>
  <Route path="/parking-spaces" element={<ParkingSpaceEditorPage />} />
</Suspense>
```

### Memoization
```typescript
// Expensive calculations
const parkingStats = useMemo(() => {
  return calculateParkingStatistics(spaces, detections);
}, [spaces, detections]);

// Callback stability
const handleSpaceClick = useCallback((spaceId: string) => {
  selectSpace(spaceId);
}, []);

// Component memoization
export const ParkingSpace = React.memo(({ space }: Props) => {
  return <div>{space.name}</div>;
});
```

### Image Optimization
```typescript
// Lazy load images
<img
  loading="lazy"
  src={imageUrl}
  alt="Detection"
/>

// Responsive images
<img
  srcSet={`
    ${imageUrl}?w=400 400w,
    ${imageUrl}?w=800 800w,
    ${imageUrl}?w=1200 1200w
  `}
  sizes="(max-width: 768px) 100vw, 50vw"
/>
```

This comprehensive frontend architecture provides a solid foundation for the Smart Parking System's user interface.
