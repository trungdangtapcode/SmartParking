# Queue-Based License Plate Assignment System

## Overview
A heuristic/trick system that uses a **queue** to automatically assign recently detected license plates to newly occupied parking spaces, even without direct vehicle tracking.

## How It Works

### 1. Plate Detection → Queue
When admin clicks "Detect Plates" button on barrier camera:
```
ALPR detects plate "51A12345" (confidence: 92%)
          ↓
Add to queue: parking_id → deque(["51A12345", ...])
          ↓
Queue keeps last 10 detected plates
```

**Code:** `VehiclePlateService.add_plate_to_queue()`

### 2. Occupancy Change Detection
Worker continuously monitors parking space occupancy:
```python
Previous frame: Space A-05 = FREE
Current frame:  Space A-05 = OCCUPIED  ← NEW OCCUPATION!
          ↓
Trigger: Assign plate from queue
```

**Code:** `VehiclePlateService.detect_new_occupancy()`

### 3. Auto-Assignment (The Trick!)
When new occupation detected:
```
Queue: ["51A12345", "59B67890", "29C11111"]
          ↓
Get most recent unassigned plate: "29C11111"
          ↓
Assign to Space A-05
          ↓
Update Firebase: parkingSpaces/A-05 → vehiclePlate="29C11111"
```

**Code:** `VehiclePlateService.get_next_plate_from_queue()`

### 4. Display on Tracking Debug
Visit `http://localhost:8069/static/tracking_debug.html`:
```
Space Grid:
┌─────────────────┐
│ A-05            │
│ Occupied        │
│ 🚗 29C11111     │  ← Plate shown!
└─────────────────┘

Occupied Spaces:
• A-05 [29C11111]
• B-03 [51A12345]
```

## Implementation Details

### Queue Management
**Location:** `/server/services/vehicle_plate_service.py`

```python
class VehiclePlateService:
    def __init__(self):
        # Queue structure: {parking_id: deque([plate_info])}
        self.plate_queue: Dict[str, Deque[Dict[str, Any]]] = {}
        # Track previous occupancy to detect changes
        self.previous_space_occupancy: Dict[str, Dict[str, bool]] = {}
```

**Key Features:**
- **Max size 10:** Only keeps last 10 detected plates per parking lot
- **LIFO priority:** Most recent plate assigned first (like a stack)
- **Mark assigned:** Plates marked to avoid double-assignment
- **Per parking lot:** Each parking lot has its own queue

### Occupancy Detection Logic
**Location:** `/server/parking_monitor_worker.py` (Lines 574-592)

```python
# Before processing frame
previous_occupancy = {
    "space_A-05": False,
    "space_B-03": True
}

# After processing frame
current_occupancy = {
    "space_A-05": True,   # Changed! FREE → OCCUPIED
    "space_B-03": True
}

# Detect changes
newly_occupied = detect_new_occupancy(
    previous=previous_occupancy,
    current=current_occupancy
)
# Result: ["space_A-05"]

# Assign plate from queue
plate = get_next_plate_from_queue(parking_id="P01")
# Result: "29C11111"

# Update Firebase
update_parking_space(
    space_id="space_A-05",
    vehicle_plate="29C11111"
)
```

### Manual ALPR Integration
**Location:** `/server/routers/manual_alpr.py` (Lines 162-170)

When button clicked:
```python
# Run ALPR
plates = detect_plates(frame)
# Result: [{"text": "51A12345", "confidence": 0.92}, ...]

# Add ALL plates to queue (heuristic!)
for plate in plates:
    vehicle_plate_service.add_plate_to_queue(
        parking_id=parking_id,
        plate=plate['text'],
        confidence=plate['confidence']
    )

# Also assign to tracked vehicle if in barrier zone
if vehicles_in_barrier:
    assign_to_vehicle(track_id, plate)
```

### Frontend Display
**Location:** `/server/static/tracking_debug.html`

**Space Grid:**
```html
<div class="space-item occupied">
    A-05
    <br><small>Occupied</small>
    <br><small style="color: #4caf50; font-weight: bold;">🚗 51A12345</small>
</div>
```

**Occupied List:**
```javascript
occupiedSpaces.map(space => {
    const plate = space.vehicle_plate ? ` [${space.vehicle_plate}]` : '';
    return `<div>${space.space_name}${plate}</div>`;
})
// Output: "A-05 [51A12345]"
```

**Analysis Section:**
```html
<div style="background: #ffebee;">
    <strong>A-05</strong>
    <br>Vehicle: car | Confidence: 95.3% | Track ID: 42 | IOU: 78.5%
    <br><span style="color: #4caf50;">🚗 Plate: 51A12345</span>
</div>
```

## Data Flow Example

### Scenario: Car enters, parks, exits

**Step 1: Plate Detection**
```
Admin clicks detect → ALPR finds "51A12345"
↓
Queue state: ["51A12345"]
```

**Step 2: Car Moves to Parking**
```
Frame N:   Space A-05 = FREE
Frame N+1: Space A-05 = OCCUPIED  ← Detection!
↓
previous_occupancy["A-05"] = False
current_occupancy["A-05"] = True
↓
Newly occupied detected!
```

**Step 3: Auto-Assignment**
```
Get from queue: "51A12345"
↓
Update Firebase:
  parkingSpaces/A-05 → {
    isOccupied: true,
    vehiclePlate: "51A12345",
    occupiedAt: "2026-01-08T10:30:00Z"
  }
↓
Mark plate as assigned in queue
```

**Step 4: Display**
```
tracking_debug.html shows:
  Space Grid: "A-05 | Occupied | 🚗 51A12345"
  Occupied List: "A-05 [51A12345]"
```

**Step 5: Car Exits**
```
Frame M:   Space A-05 = OCCUPIED
Frame M+1: Space A-05 = FREE  ← Detection!
↓
Update Firebase:
  parkingSpaces/A-05 → {
    isOccupied: false,
    vehiclePlate: null
  }
↓
Update previous_occupancy
```

## Advantages of This Approach

✅ **Simple:** No complex tracking required
✅ **Robust:** Works even if tracking fails
✅ **Fast:** Immediate assignment on occupation
✅ **Visual:** Plates visible on debug page
✅ **Queue-based:** Handles multiple vehicles naturally

## Limitations

⚠️ **Assumes FIFO:** Assumes cars park in the order they entered
⚠️ **No validation:** Doesn't verify the plate matches the vehicle
⚠️ **Manual trigger:** Requires admin to click detect button
⚠️ **Single assignment:** Each plate assigned only once from queue

## Configuration

### Queue Size
Default: 10 plates per parking lot
```python
self.plate_queue[parking_id] = deque(maxlen=10)
```

### Assignment Priority
Most recent plate assigned first (LIFO):
```python
for i in range(len(queue) - 1, -1, -1):  # Reverse iteration
    if not plate_info['assigned']:
        return plate_info['plate']
```

## Testing Checklist

1. **Detect Plate:**
   - [ ] Click detect button on barrier camera
   - [ ] Alert shows detected plate
   - [ ] Check logs: "📋 Added plate to queue"

2. **Park Vehicle:**
   - [ ] Car moves into empty parking space
   - [ ] Check logs: "🆕 NEW OCCUPATION DETECTED"
   - [ ] Check logs: "🎯 Auto-assigned plate"

3. **View on Tracking Debug:**
   - [ ] Visit http://localhost:8069/static/tracking_debug.html
   - [ ] Select camera and parking lot
   - [ ] See plate in space grid: "🚗 51A12345"
   - [ ] See plate in occupied list: "[51A12345]"
   - [ ] See plate in analysis section

4. **Exit Vehicle:**
   - [ ] Car leaves parking space
   - [ ] Space becomes free
   - [ ] Plate removed from display

5. **Multiple Vehicles:**
   - [ ] Detect 3 plates: A, B, C
   - [ ] 3 cars park sequentially
   - [ ] Spaces assigned: C, B, A (LIFO order)

## Future Enhancements

1. **Confidence scoring:** Prioritize high-confidence plates
2. **Time-based expiry:** Remove old plates from queue after N minutes
3. **Multiple cameras:** Share queue across barrier cameras
4. **Validation:** Match plate to vehicle appearance (color, size)
5. **History:** Log all plate assignments for analytics
