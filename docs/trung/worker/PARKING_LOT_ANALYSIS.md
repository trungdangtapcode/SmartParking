# Parking Lot Analysis Service

Intelligent parking space occupancy analysis based on IOU (Intersection over Union) matching between vehicle detections and parking space definitions.

## Overview

The Parking Lot Analysis Service provides real-time occupancy analysis for parking lots by:
- Matching vehicle detections to parking spaces using configurable IOU thresholds
- Tracking which spaces are occupied and which are available
- Providing detailed statistics and vehicle information
- Supporting multiple cameras per parking lot

## Configuration

All parameters are configurable in `server/config/tracking_config.yaml`:

```yaml
# Parking Space Occupancy Settings
parking:
  iou_threshold: 0.5          # IOU threshold for vehicle-space matching (0.3-0.8)
  min_overlap_ratio: 0.3      # Minimum overlap ratio to consider occupied (0.2-0.6)
  confidence_threshold: 0.3   # Minimum detection confidence for occupancy check
```

### Configuration Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `iou_threshold` | 0.5 | 0.3-0.8 | Minimum IOU between vehicle bbox and parking space to consider a match |
| `min_overlap_ratio` | 0.3 | 0.2-0.6 | Minimum overlap percentage required |
| `confidence_threshold` | 0.3 | 0.1-0.9 | Minimum vehicle detection confidence to include in analysis |

### Tuning Guidelines

**Higher IOU Threshold (0.6-0.8):**
- ✅ More accurate - requires better alignment
- ✅ Reduces false positives
- ❌ May miss partially parked vehicles
- ❌ More strict matching

**Lower IOU Threshold (0.3-0.4):**
- ✅ Catches more vehicles
- ✅ Works with partial parking
- ❌ May increase false positives
- ❌ Less strict matching

**Recommended Settings:**
- **Tight parking lots**: `iou_threshold: 0.6`
- **Loose parking lots**: `iou_threshold: 0.4`
- **Mixed/General**: `iou_threshold: 0.5` (default)

## API Endpoints

### 1. Analyze Single Parking Lot

```http
GET /debug/parking-lot-analysis/{parking_id}
```

**Response:**
```json
{
  "parking_id": "lot_123",
  "timestamp": "2026-01-07T04:30:00",
  "total_spaces": 50,
  "occupied_spaces": 32,
  "available_spaces": 18,
  "occupancy_rate": 64.0,
  "vehicle_count": 35,
  "spaces": [
    {
      "space_id": "space_001",
      "space_name": "A1",
      "camera_id": "cam_001",
      "is_occupied": true,
      "bbox": {
        "x": 0.1,
        "y": 0.2,
        "width": 0.05,
        "height": 0.08
      },
      "occupying_vehicle": {
        "class": "car",
        "confidence": 0.85,
        "track_id": 42,
        "bbox": [100, 200, 50, 80],
        "iou": 0.67
      }
    }
  ],
  "config": {
    "iou_threshold": 0.5,
    "min_overlap_ratio": 0.3,
    "confidence_threshold": 0.3
  }
}
```

### 2. Analyze All Parking Lots

```http
GET /debug/parking-lot-analysis
```

**Response:**
```json
{
  "timestamp": "2026-01-07T04:30:00",
  "parking_lots": [
    {
      "parking_id": "lot_123",
      "total_spaces": 50,
      "occupied_spaces": 32,
      "occupancy_rate": 64.0
    }
  ],
  "summary": {
    "total_lots": 5,
    "total_spaces": 250,
    "total_occupied": 180,
    "total_available": 70,
    "average_occupancy_rate": 72.0
  }
}
```

### 3. Get Empty Spaces

```http
GET /debug/empty-spaces/{parking_id}
```

**Response:**
```json
{
  "parking_id": "lot_123",
  "timestamp": "2026-01-07T04:30:00",
  "empty_spaces": [
    {
      "space_id": "space_002",
      "space_name": "A2",
      "camera_id": "cam_001",
      "is_occupied": false,
      "bbox": {...}
    }
  ],
  "count": 18,
  "total_spaces": 50
}
```

### 4. Get Occupied Spaces

```http
GET /debug/occupied-spaces/{parking_id}
```

**Response:**
```json
{
  "parking_id": "lot_123",
  "timestamp": "2026-01-07T04:30:00",
  "occupied_spaces": [
    {
      "space_id": "space_001",
      "space_name": "A1",
      "is_occupied": true,
      "occupying_vehicle": {
        "class": "car",
        "confidence": 0.85,
        "track_id": 42,
        "iou": 0.67
      }
    }
  ],
  "count": 32,
  "total_spaces": 50
}
```

## Python Service Usage

### Basic Usage

```python
from services.parking_lot_analysis_service import get_parking_lot_analysis_service

# Get service instance
analysis_service = get_parking_lot_analysis_service()

# Analyze a parking lot
result = analysis_service.analyze_parking_lot(
    parking_id="lot_123",
    detections=vehicle_detections,
    image_width=1920,
    image_height=1080
)

print(f"Occupancy: {result['occupied_spaces']}/{result['total_spaces']}")
print(f"Rate: {result['occupancy_rate']}%")
```

### Analyze All Lots

```python
# Collect detections by camera
detections_by_camera = {
    "cam_001": [detection1, detection2, ...],
    "cam_002": [detection3, detection4, ...]
}

# Analyze all parking lots
result = analysis_service.analyze_all_parking_lots(detections_by_camera)

print(f"Total lots: {result['summary']['total_lots']}")
print(f"Average occupancy: {result['summary']['average_occupancy_rate']}%")
```

## Debug UI Integration

The parking lot analysis is integrated into the tracking debug UI at:
```
http://localhost:8069/static/tracking_debug.html
```

### Features:
1. **Camera Selection**: Choose a camera to view its parking lot
2. **Real-time Tracking**: View live vehicle detections and track IDs
3. **Parking Analysis Button**: Click "🅿️ Parking Lot Analysis" to see:
   - Total/Occupied/Available spaces
   - Occupancy rate with color coding
   - List of occupied spaces with vehicle details
   - List of available spaces
   - Configuration parameters used

### UI Color Coding:
- 🟢 **Green** (0-50%): Low occupancy - plenty of space
- 🟠 **Orange** (51-80%): Medium occupancy - filling up
- 🔴 **Red** (81-100%): High occupancy - nearly full

## How It Works

### 1. Data Collection
- Worker processes camera frames and detects vehicles
- Detections include bounding box, confidence, and track ID
- Data is broadcast to backend via `/api/broadcast-detection`

### 2. Space Matching
- Service fetches parking space definitions from Firestore
- Each space has normalized coordinates (x, y, width, height)
- Detections are converted to normalized coordinates

### 3. IOU Calculation
```
IOU = Area of Overlap / Area of Union

If IOU >= iou_threshold:
    Space is OCCUPIED by this vehicle
Else:
    Continue checking other detections
```

### 4. Best Match Selection
- For each parking space, find the vehicle with highest IOU
- Only match if IOU meets threshold
- Each space can only be occupied by one vehicle (best match)

### 5. Results
- Generate occupancy map: space_id → is_occupied
- Include vehicle details for occupied spaces
- Calculate statistics (total, occupied, available, rate)

## Business Logic Examples

### 1. Find Available Parking

```python
# Get empty spaces
response = requests.get(f"{API_URL}/debug/empty-spaces/lot_123")
empty_spaces = response.json()['empty_spaces']

# Guide user to nearest empty space
nearest_space = find_nearest(empty_spaces, user_location)
print(f"Park at space {nearest_space['space_name']}")
```

### 2. Monitor Occupancy Trends

```python
import time

occupancy_history = []

while True:
    result = analysis_service.analyze_parking_lot("lot_123", detections, w, h)
    occupancy_history.append({
        'timestamp': result['timestamp'],
        'rate': result['occupancy_rate']
    })
    
    # Alert if parking lot is filling up
    if result['occupancy_rate'] > 90:
        send_alert("Parking lot nearly full!")
    
    time.sleep(60)  # Check every minute
```

### 3. Space Usage Statistics

```python
# Analyze all parking lots
result = analysis_service.analyze_all_parking_lots(detections_by_camera)

# Generate report
for lot in result['parking_lots']:
    print(f"Lot {lot['parking_id']}:")
    print(f"  Occupancy: {lot['occupancy_rate']}%")
    print(f"  Revenue potential: ${lot['occupied_spaces'] * hourly_rate}")
```

## Firestore Data Structure

### Parking Spaces Collection

```javascript
parkingSpaces/{spaceId}
{
  id: "space_001",
  name: "A1",
  parkingId: "lot_123",
  cameraId: "cam_001",
  x: 0.1,        // Normalized 0-1
  y: 0.2,
  width: 0.05,
  height: 0.08,
  status: "active"
}
```

### Parking Lots Collection

```javascript
parkingLots/{lotId}
{
  id: "lot_123",
  name: "Main Parking Lot",
  cameras: ["cam_001", "cam_002"],
  status: "active",
  totalSpaces: 50
}
```

## Performance Considerations

1. **Caching**: Service caches parking space definitions to avoid repeated Firestore queries
2. **Async Operations**: All Firebase queries use async/await for non-blocking operation
3. **Rate Limiting**: Worker processes at 10 FPS by default (configurable)
4. **Firebase Quota**: Consider caching duration to avoid hitting Firestore quotas

## Troubleshooting

### No spaces detected as occupied

**Check:**
1. IOU threshold too high - try lowering to 0.4
2. Parking spaces not defined in Firestore
3. Detection confidence below threshold
4. Camera calibration - spaces may be misaligned with camera view

### Too many false positives

**Check:**
1. IOU threshold too low - try increasing to 0.6
2. Detection confidence too low - increase to 0.4
3. Vehicle class filtering - ensure only relevant vehicles counted

### Occupancy rate incorrect

**Check:**
1. Multiple cameras covering same spaces
2. Spaces defined for wrong camera
3. Worker not running or not broadcasting data
4. Time synchronization between worker and analysis

## See Also

- [Tracking Data Usage Guide](./TRACKING_DATA_USAGE.md)
- [Tracking Debug API](./TRACKING_DEBUG_API.md)
- [Worker Implementation Details](./IMPLEMENTATION_DETAILS.md)
