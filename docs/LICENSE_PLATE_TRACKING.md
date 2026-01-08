# License Plate Tracking System Implementation

## Overview
This system automatically assigns license plates to vehicles detected in the barrier zone and tracks them as they move through parking spaces.

## How It Works

### 1. Manual ALPR Trigger (Admin Button)
**Location:** Detection Viewer UI → Barrier Camera
**Process:**
1. Admin clicks "🔍 Detect Plates (Manual)" button on Barrier camera
2. System captures current frame from camera
3. Runs ALPR detection to find license plates
4. **NEW:** Automatically runs vehicle detection with tracking
5. **NEW:** Finds vehicles in barrier zone (using `barrierBoxes` collection)
6. **NEW:** Auto-assigns highest confidence plate to first vehicle in barrier
7. Shows alert with detected plates and confidence levels

**Code:** `/server/routers/manual_alpr.py`
- `detect_plate_manual()` endpoint enhanced with auto-assignment

### 2. Vehicle Plate Service
**Location:** `/server/services/vehicle_plate_service.py`
**Purpose:** Central service for managing vehicle-plate assignments

**Key Features:**
- **Barrier Detection:** Check if vehicle is in barrier zone using normalized bbox
- **Plate Assignment:** Store plate→track_id mapping in Firebase
- **Parking Space Tracking:** Update parking spaces with plate numbers
- **Lost Track Cleanup:** Automatically free parking spaces when vehicles leave

**Firebase Collections Used:**
- `vehicle_tracking` - Active vehicles with plates
  ```json
  {
    "cameraId": "cam_123",
    "parkingId": "P01", 
    "trackId": 42,
    "plate": "51A12345",
    "confidence": 0.92,
    "assignedAt": "2026-01-08T10:30:00Z",
    "parkingSpaceId": "space_5",
    "status": "parked"  // in_barrier | moving | parked | exited
  }
  ```

- `parkingSpaces` - Updated with plate info
  ```json
  {
    "id": "space_5",
    "name": "A-05",
    "isOccupied": true,
    "vehiclePlate": "51A12345",
    "trackId": 42,
    "occupiedAt": "2026-01-08T10:31:00Z"
  }
  ```

- `barrierBoxes` - Barrier zone definitions
  ```json
  {
    "cameraId": "cam_123",
    "parkingId": "P01",
    "x": 0.165625,
    "y": 0.333333,
    "width": 0.059375,
    "height": 0.139583
  }
  ```

### 3. Worker Integration
**Location:** `/server/parking_monitor_worker.py`
**Enhanced Workflow:**

```
Frame received → Detect vehicles with tracking
                ↓
                Check if vehicles have assigned plates
                ↓
                Match detections to parking spaces
                ↓
                Update parking spaces with plate numbers
                ↓
                Draw frames with plates visible
                ↓
                Broadcast to Detection Viewer
```

**Key Changes:**
1. **Line 95-97:** Initialize `VehiclePlateService`
2. **Line 478-493:** After detection, add plate info and cleanup lost tracks
3. **Line 527:** Include plate in detection metadata
4. **Line 579-589:** Update parking spaces when vehicle parks
5. **Line 683-697:** Draw plate numbers on vehicles (green text)
6. **Line 721-728:** Show plate in parking space label

### 4. Frontend Display
**Location:** `/frontend/src/pages/DetectionViewerPage.tsx`
**Alert Box Enhanced:**
```
🚗 Detected 1 plate(s):

1. 51A12345 (89.5%)

Tracked vehicles: 1
```

**Detection View Shows:**
- Vehicle bounding boxes with `[PLATE] ID:42 car: 0.95`
- Parking spaces: `A-05: [51A12345]` (when occupied)
- Real-time tracking with ByteTrack

## Data Flow Example

### Scenario: Car enters parking lot

1. **Barrier Entry**
   ```
   Admin clicks detect → Camera captures frame
   ↓
   ALPR finds: "51A12345" (92% confidence)
   ↓
   Vehicle detection: track_id=42 in barrier zone
   ↓
   Auto-assign: "51A12345" → track_id=42
   ↓
   Firebase: vehicle_tracking/cam_123_42 created
   ```

2. **Moving to Parking Space**
   ```
   Worker processes frames
   ↓
   Track_id=42 detected, plate="51A12345" attached
   ↓
   Vehicle moves to Space A-05
   ↓
   IoA match: track_id=42 overlaps space_5
   ↓
   Update: vehicle_tracking → status="parked", parkingSpaceId="space_5"
   Update: parkingSpaces/space_5 → isOccupied=true, vehiclePlate="51A12345"
   ```

3. **Display**
   ```
   Detection Viewer shows:
   - Vehicle bbox: "[51A12345] ID:42 car: 0.95"
   - Parking space: "A-05: [51A12345]" in RED
   ```

4. **Vehicle Exits**
   ```
   Track_id=42 no longer detected for 10+ frames
   ↓
   cleanup_lost_tracks() called
   ↓
   Update: parkingSpaces/space_5 → isOccupied=false, vehiclePlate=null
   Update: vehicle_tracking/cam_123_42 → status="exited"
   ```

## API Endpoints

### POST `/api/detect-plate-manual`
**Request:**
```json
{
  "camera_id": "cam_123",
  "user_role": "admin"
}
```

**Response:**
```json
{
  "success": true,
  "plates": [
    {
      "text": "51A12345",
      "confidence": 0.92,
      "bbox": [100, 200, 150, 50]
    }
  ],
  "annotated_image": "data:image/png;base64,...",
  "tracked_vehicles": [],
  "message": "Detected 1 license plate(s), auto-assigned 1 to vehicles in barrier zone"
}
```

### POST `/api/assign-plate-to-vehicle` (Future)
Manual override to assign plate to specific vehicle

## Configuration Requirements

### Firebase Collections Setup

1. **barrierBoxes** collection:
   - Create barrier zone for each camera
   - Use normalized coordinates (0-1)
   - Match `cameraId` and `parkingId`

2. **parkingSpaces** collection:
   - Add fields: `vehiclePlate`, `trackId`, `occupiedAt`
   - These will be auto-populated by the system

3. **vehicle_tracking** collection:
   - Auto-created by system
   - Stores active vehicle-plate mappings

### Worker Configuration
- **Must enable tracking:** `--use-tracking` flag
- ByteTrack configured in `config/tracking_config.yaml`
- FPS: 10-30 recommended for balance

## Benefits

✅ **Automatic:** Plates assigned when admin clicks button
✅ **Tracked:** Vehicles followed across entire parking lot
✅ **Persistent:** Plate info stored in Firebase
✅ **Visual:** Plates shown on detection stream
✅ **Real-time:** Updates as vehicles move
✅ **Clean:** Auto-cleanup when vehicles exit

## Testing Checklist

- [ ] Barrier boxes configured in Firebase
- [ ] Admin can click detect button on barrier camera
- [ ] Alert shows detected plate number
- [ ] Worker shows plate on vehicle bbox
- [ ] Vehicle moves to parking space
- [ ] Parking space shows plate when occupied
- [ ] Vehicle exits and space becomes free
- [ ] Firebase data updates correctly

## Future Enhancements

1. **Automatic ALPR:** Trigger detection when vehicle enters barrier (no button)
2. **Entry/Exit Logs:** Record all vehicle movements with timestamps
3. **Search:** Find vehicle by plate number
4. **Analytics:** Duration, frequency, etc.
5. **Multiple Plates:** Handle multiple vehicles in barrier simultaneously
