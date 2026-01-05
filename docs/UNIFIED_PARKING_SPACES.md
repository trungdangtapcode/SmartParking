# Unified Parking Space System

## Overview

The parking space detection and management system has been **unified** to use a single Firebase collection (`parkingSpaceDefinitions`) for both AI detection and manual editing. This ensures data consistency and allows seamless workflow between automatic detection and manual refinement.

## Key Changes

### Before (Old System)
- ❌ **LiveDetection** saved to `detections` collection with pixel coordinates
- ❌ **ParkingSpaceEditor** saved to `parkingSpaceDefinitions` with normalized coordinates
- ❌ Two incompatible data formats
- ❌ Manual camera ID input (prone to typos)
- ❌ No way to edit AI-detected spaces

### After (Unified System)
- ✅ **Both components** save to `parkingSpaceDefinitions` collection
- ✅ **Single format**: Normalized coordinates (0-1 range)
- ✅ **Camera dropdown** in LiveDetection (same as Editor)
- ✅ **Seamless workflow**: AI detect → Manual edit
- ✅ **Data consistency** across entire application

## Data Structure

### Unified Format: `ParkingSpaceDefinition`

```typescript
interface ParkingSpaceDefinition {
  // Identity
  id: string;                    // Unique ID: "{cameraId}_space_{timestamp}_{index}"
  parkingId: string;             // "PARKING_A"
  cameraId: string;              // ESP32 config ID
  name: string;                  // "P1", "P2", "A1", etc.
  
  // Normalized location (0-1 based on image dimensions)
  x: number;                     // x position (0-1)
  y: number;                     // y position (0-1)
  width: number;                 // width (0-1)
  height: number;                // height (0-1)
  
  // Metadata
  createdBy: string;             // User ID
  createdAt: Timestamp;
  updatedAt: Timestamp;
}
```

### Why Normalized Coordinates?

**Resolution Independence**: Coordinates are stored as 0-1 (percentage), not pixels:
- ✅ Works with any camera resolution
- ✅ Survives camera upgrades/changes
- ✅ Easy to scale for different displays
- ✅ Backend worker can process any resolution

**Conversion Formula**:
```typescript
// Pixel → Normalized (for saving)
normalizedX = pixelX / imageWidth
normalizedY = pixelY / imageHeight

// Normalized → Pixel (for rendering)
pixelX = normalizedX * imageWidth
pixelY = normalizedY * imageHeight
```

## Workflow

### 1. AI Detection (LiveDetection Component)

**Step 1: Select Parking Lot & Camera**
```tsx
// Dropdown selection (no manual typing!)
<select value={parkingLotId} onChange={...}>
  <option>🅿️ Parking Lot A (PARKING_A)</option>
  <option>🅿️ Parking Lot B (PARKING_B)</option>
</select>

<select value={cameraId} onChange={...}>
  <option>📹 Front Camera (ESP32_001)</option>
  <option>📹 Rear Camera (ESP32_002)</option>
</select>
```

**Step 2: Upload Image & Detect**
```typescript
// Upload image/video
<MediaUpload onMediaReady={handleMediaReady} />

// Click "🔍 Detect Spaces" button
const detections = await aiDetection.detectParkingSpaces(videoElement);

// AI returns pixel coordinates + confidence
// Example: [[x:100, y:200, w:80, h:120], confidence:0.95]
```

**Step 3: Save to Database**
```typescript
// Convert pixel → normalized coordinates
const spaceDefs = detections.map((detection, index) => ({
  id: `${cameraId}_space_${Date.now()}_${index}`,
  parkingId: parkingLotId,
  cameraId: cameraId,
  name: `P${index + 1}`,  // Auto-name: P1, P2, P3...
  x: detection.bbox[0] / imageWidth,      // Normalize
  y: detection.bbox[1] / imageHeight,     // Normalize
  width: detection.bbox[2] / imageWidth,  // Normalize
  height: detection.bbox[3] / imageHeight, // Normalize
  createdBy: user.uid,
}));

// Save to parkingSpaceDefinitions
await batchSaveParkingSpaces(spaceDefs);
```

**Result**: Parking spaces saved to unified database ✅

### 2. Manual Editing (ParkingSpaceEditor)

**Step 1: Select Same Parking Lot & Camera**
```tsx
// Same dropdown UI as LiveDetection
<select value={selectedParkingLot}>...</select>
<select value={selectedCamera}>...</select>
```

**Step 2: Load Existing Spaces**
```typescript
// Automatically loads AI-detected spaces
const spaces = await getParkingSpacesByCamera(cameraId);

// Spaces are already in normalized format
// Draw on canvas using current image dimensions
spaces.forEach(space => {
  const x = space.x * canvas.width;     // Scale up
  const y = space.y * canvas.height;    // Scale up
  const w = space.width * canvas.width; // Scale up
  const h = space.height * canvas.height; // Scale up
  
  ctx.strokeRect(x, y, w, h); // Draw
});
```

**Step 3: Edit Spaces**
- ✏️ **Drag**: Move spaces to correct position
- 📏 **Resize**: Adjust boundaries using corner handles
- ➕ **Add**: Draw new spaces manually
- 🗑️ **Delete**: Remove incorrect detections
- ✍️ **Rename**: Change "P1" → "A1", etc.

**Step 4: Save Changes**
```typescript
// Save updated spaces (same format)
await batchSaveParkingSpaces(updatedSpaces);
```

**Result**: Refined parking spaces saved back to database ✅

### 3. Background Worker Monitoring

The worker reads from `parkingSpaceDefinitions`:

```python
# server/parking_monitor_worker.py

async def get_parking_spaces(self, camera_id):
    # Query parkingSpaceDefinitions collection
    spaces_ref = db.collection('parkingSpaceDefinitions')
    query = spaces_ref.where('cameraId', '==', camera_id)
    spaces = query.get()
    
    # Spaces already in normalized format (0-1)
    return [space.to_dict() for space in spaces]

async def process_camera(self, camera_info):
    # 1. Fetch frame from camera
    frame = await fetch_camera_frame(camera_url)
    
    # 2. Run YOLO detection
    detections = detect_vehicles(frame)  # Returns pixel coords
    
    # 3. Load parking space definitions (normalized 0-1)
    spaces = await get_parking_spaces(camera_id)
    
    # 4. Convert detections to normalized coords for matching
    frame_height, frame_width = frame.shape[:2]
    normalized_detections = [
        {
            'x': det['x'] / frame_width,
            'y': det['y'] / frame_height,
            'width': det['width'] / frame_width,
            'height': det['height'] / frame_height,
        }
        for det in detections
    ]
    
    # 5. Match detections to spaces using IoU
    matches = match_detections_to_spaces(normalized_detections, spaces)
    
    # 6. Update occupancy status in Firebase
    update_space_occupancy(camera_id, matches)
```

## Firebase Collections

### `parkingSpaceDefinitions` (Unified Collection)

**Purpose**: Store parking space definitions (both AI-detected and manually created)

**Documents**:
```
parkingSpaceDefinitions/
  ├── ESP32_001_space_1704470400000_0/
  │   ├── id: "ESP32_001_space_1704470400000_0"
  │   ├── parkingId: "PARKING_A"
  │   ├── cameraId: "ESP32_001"
  │   ├── name: "P1"
  │   ├── x: 0.15      (15% from left)
  │   ├── y: 0.20      (20% from top)
  │   ├── width: 0.12  (12% of image width)
  │   ├── height: 0.18 (18% of image height)
  │   ├── createdBy: "user123"
  │   ├── createdAt: Timestamp
  │   └── updatedAt: Timestamp
  │
  ├── ESP32_001_space_1704470400000_1/
  └── ESP32_002_space_1704470400000_0/
```

### `parkingSpaces` (Runtime State)

**Purpose**: Real-time occupancy status (updated by worker)

**Documents**:
```
parkingSpaces/
  ├── PARKING_A_ESP32_001_space_1704470400000_0/
  │   ├── parkingId: "PARKING_A"
  │   ├── cameraId: "ESP32_001"
  │   ├── spaceId: "ESP32_001_space_1704470400000_0"
  │   ├── spaceName: "P1"
  │   ├── occupied: true
  │   ├── lastChecked: Timestamp
  │   └── vehicleDetected: {
  │       bbox: [0.15, 0.20, 0.12, 0.18],  // Normalized
  │       confidence: 0.92,
  │       class: "car"
  │     }
  └── ...
```

## Component Integration

### LiveDetection Component

**File**: `frontend/src/components/LiveDetection.tsx`

**Key Changes**:
```typescript
// ✅ Import ESP32 configs
import { getUserESP32Configs } from '../services/esp32ConfigService';
import { batchSaveParkingSpaces } from '../services/parkingSpaceService';

// ✅ Camera dropdown state
const [cameras, setCameras] = useState<ESP32Config[]>([]);

// ✅ Load cameras on mount
useEffect(() => {
  const cams = await getUserESP32Configs(user.uid);
  setCameras(cams);
}, [user]);

// ✅ Save to unified format
const handleSave = async () => {
  const spaceDefs = spaces.map((space, i) => ({
    id: `${cameraId}_space_${Date.now()}_${i}`,
    parkingId,
    cameraId,
    name: `P${i + 1}`,
    x: space.bbox[0] / imgWidth,      // Normalize!
    y: space.bbox[1] / imgHeight,     // Normalize!
    width: space.bbox[2] / imgWidth,  // Normalize!
    height: space.bbox[3] / imgHeight, // Normalize!
    createdBy: user.uid,
  }));
  
  await batchSaveParkingSpaces(spaceDefs);
};
```

### ParkingSpaceEditor Component

**File**: `frontend/src/pages/ParkingSpaceEditorPage.tsx`

**No changes needed** - Already uses unified format! ✅

**Key Features**:
```typescript
// Load spaces (already normalized 0-1)
const spaces = await getParkingSpacesByCamera(cameraId);

// Draw on canvas (scale to current dimensions)
const drawSpace = (space) => {
  const x = space.x * canvas.width;     // Scale up
  const y = space.y * canvas.height;    // Scale up
  const w = space.width * canvas.width;
  const h = space.height * canvas.height;
  
  ctx.strokeRect(x, y, w, h);
};

// Save changes (convert back to normalized)
const handleSave = async () => {
  const normalized = spaces.map(space => ({
    ...space,
    x: space.x,        // Already normalized
    y: space.y,        // Already normalized
    width: space.width,  // Already normalized
    height: space.height, // Already normalized
  }));
  
  await batchSaveParkingSpaces(normalized);
};
```

## Migration Guide

### For Existing Data

If you have old data in the `detections` collection, you can migrate it:

```typescript
// Migration script (run once)
async function migrateOldDetections() {
  const oldDetections = await fetchDetections({ limitCount: 1000 });
  
  for (const detection of oldDetections) {
    if (!detection.spaces || !detection.inputImageUrl) continue;
    
    // Parse image dimensions from inputImageUrl
    const img = new Image();
    img.src = detection.inputImageUrl;
    await new Promise(resolve => img.onload = resolve);
    
    const imgWidth = img.naturalWidth;
    const imgHeight = img.naturalHeight;
    
    // Convert pixel spaces to normalized
    const spaceDefs = detection.spaces.map((space, i) => ({
      id: `${detection.cameraId}_space_migrated_${i}`,
      parkingId: detection.parkingId,
      cameraId: detection.cameraId,
      name: `P${i + 1}`,
      x: space.bbox[0] / imgWidth,
      y: space.bbox[1] / imgHeight,
      width: space.bbox[2] / imgWidth,
      height: space.bbox[3] / imgHeight,
      createdBy: detection.ownerId,
    }));
    
    await batchSaveParkingSpaces(spaceDefs);
    console.log(`✅ Migrated ${spaceDefs.length} spaces from ${detection.cameraId}`);
  }
}
```

### For New Projects

Just use the unified system from the start:
1. Configure cameras in ESP32 settings
2. Use LiveDetection to AI-detect spaces
3. Use ParkingSpaceEditor to refine
4. Worker automatically monitors using unified data

## Benefits

### For Developers
- ✅ **Single source of truth** for parking space data
- ✅ **Consistent data format** across frontend/backend
- ✅ **Easy to maintain** (one collection, one format)
- ✅ **Type safety** with TypeScript interfaces

### For Users
- ✅ **No manual typing** of camera IDs (dropdown selection)
- ✅ **AI + Manual workflow** seamlessly integrated
- ✅ **Edit AI results** without re-detecting
- ✅ **Consistent UI** between Detection and Editor pages

### For Operations
- ✅ **Resolution independent** (works with any camera)
- ✅ **Scalable** (normalized coords = smaller data)
- ✅ **Worker compatible** (reads same format)
- ✅ **Migration friendly** (easy to upgrade cameras)

## Testing Checklist

### Test AI Detection → Editor Flow

1. ✅ **LiveDetection**: Select parking lot + camera from dropdowns
2. ✅ **LiveDetection**: Upload image and click "🔍 Detect Spaces"
3. ✅ **LiveDetection**: Verify spaces detected with confidence scores
4. ✅ **LiveDetection**: Click "💾 Save Results"
5. ✅ **LiveDetection**: Check success message mentions Editor
6. ✅ **ParkingSpaceEditor**: Navigate to Editor page
7. ✅ **ParkingSpaceEditor**: Select same parking lot + camera
8. ✅ **ParkingSpaceEditor**: Verify AI-detected spaces appear on canvas
9. ✅ **ParkingSpaceEditor**: Drag/resize spaces
10. ✅ **ParkingSpaceEditor**: Click "💾 Lưu tất cả"
11. ✅ **ParkingSpaceEditor**: Reload page and verify changes persisted

### Test Editor → Worker Flow

1. ✅ **ParkingSpaceEditor**: Create/edit parking spaces
2. ✅ **ParkingSpaceEditor**: Save to database
3. ✅ **Worker**: Start `python parking_monitor_worker.py`
4. ✅ **Worker**: Enable camera in UI (workerEnabled = true)
5. ✅ **Worker**: Check logs for "Found worker-enabled camera"
6. ✅ **Worker**: Verify spaces loaded from parkingSpaceDefinitions
7. ✅ **Worker**: Check occupancy updates in parkingSpaces collection
8. ✅ **Dashboard**: View real-time occupancy on dashboard

## Troubleshooting

### Spaces not appearing in Editor

**Problem**: AI-detected spaces not visible in Editor

**Solutions**:
- Verify same parkingId and cameraId selected
- Check Firebase Console → `parkingSpaceDefinitions` collection
- Ensure spaces have correct cameraId field
- Check browser console for errors

### Spaces in wrong position

**Problem**: Spaces appear in wrong location after editing

**Solutions**:
- Verify image dimensions match original detection image
- Check normalization: coordinates should be 0-1, not pixels
- Ensure canvas size matches camera stream resolution
- Clear cache and reload page

### Worker not processing spaces

**Problem**: Worker doesn't detect occupancy

**Solutions**:
- Check workerEnabled=true for camera in Firebase
- Verify spaces exist in parkingSpaceDefinitions
- Check worker logs for "Found worker-enabled camera"
- Ensure camera URL is accessible from worker
- Verify normalized coordinates are 0-1 range

## Related Documentation

- [PARKING_SPACE_EDITOR.md](./PARKING_SPACE_EDITOR.md) - Editor user guide
- [PARKING_MONITOR_WORKER.md](./PARKING_MONITOR_WORKER.md) - Worker documentation
- [WORKER_CONTROL.md](./WORKER_CONTROL.md) - Worker control guide
- [PARKING_SPACE_INTEGRATION.md](./PARKING_SPACE_INTEGRATION.md) - Integration guide

## API Reference

### Frontend Services

#### `batchSaveParkingSpaces(spaces[])`
Save multiple parking spaces to parkingSpaceDefinitions

```typescript
const result = await batchSaveParkingSpaces([
  {
    id: 'space_001',
    parkingId: 'PARKING_A',
    cameraId: 'ESP32_001',
    name: 'P1',
    x: 0.1, y: 0.2, width: 0.15, height: 0.2,
    createdBy: 'user123'
  }
]);

if (result.success) {
  console.log(`✅ Saved ${result.savedCount} spaces`);
}
```

#### `getParkingSpacesByCamera(cameraId)`
Load parking spaces for specific camera

```typescript
const spaces = await getParkingSpacesByCamera('ESP32_001');
// Returns: ParkingSpaceDefinition[]
```

#### `deleteParkingSpace(spaceId)`
Delete single parking space

```typescript
await deleteParkingSpace('ESP32_001_space_0');
```

### Backend Worker

#### `get_parking_spaces(camera_id)`
Load spaces from Firebase (Python)

```python
spaces = await parking_service.get_parking_spaces('ESP32_001')
# Returns: List[Dict] with normalized coordinates
```

#### `match_detections_to_spaces(detections, spaces)`
Match YOLO detections to parking spaces using IoU

```python
matches = parking_service.match_detections_to_spaces(
    detections=[{'x': 0.1, 'y': 0.2, 'width': 0.15, 'height': 0.2}],
    spaces=[{'x': 0.1, 'y': 0.2, 'width': 0.15, 'height': 0.2}]
)
# Returns: List[Tuple[detection, space, iou_score]]
```

## Conclusion

The unified parking space system provides:
- **Consistency**: One format across all components
- **Flexibility**: AI detection + manual editing
- **Scalability**: Resolution-independent coordinates
- **Usability**: Dropdown selection, no manual typing
- **Integration**: Seamless workflow from detection → editing → monitoring

All components now work together using the same data structure in `parkingSpaceDefinitions` collection! 🎉
