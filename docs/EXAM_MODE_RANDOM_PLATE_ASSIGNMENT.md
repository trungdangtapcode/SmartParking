# 🎓 Exam Mode: Random Plate Assignment

## Overview

For the final exam demonstration, the system has been modified to randomly assign detected license plates to **occupied parking spaces that have been occupied for at least 30 seconds**.

This simulates a more realistic parking scenario where:
1. Vehicles park in spaces (detected by occupancy detection)
2. After some time (30 seconds), admin detects license plates at the barrier
3. System randomly assigns those plates to the already-occupied spaces

## How It Works

### 1. Plate Detection
When admin clicks "Detect Plates" on the barrier camera:
- All detected plates are added to the queue
- System searches for occupied parking spaces
- Only spaces occupied for 30+ seconds are eligible
- Plates are randomly assigned to eligible spaces

### 2. Key Changes Made

#### `services/vehicle_plate_service.py`
- **Added**: `assign_plates_to_random_occupied_spaces()` method
  - Queries Firebase for occupied spaces without plates
  - Filters spaces by occupation time (30+ seconds)
  - Randomly shuffles eligible spaces
  - Assigns plates from queue to random spaces
  
- **Modified**: `detect_new_occupancy()` method
  - Disabled automatic assignment on new occupancy
  - Now only tracks occupancy changes (for future use)

#### `routers/manual_alpr.py`
- After detecting plates, calls `assign_plates_to_random_occupied_spaces()`
- Shows exam mode message in alert: "🎓 EXAM MODE: Detected X plate(s), randomly assigned Y to occupied parking spaces (30s+ occupation)"
- Logs detailed assignment information

#### `parking_monitor_worker.py`
- Commented out automatic plate assignment on new occupancy
- Worker still detects occupancy changes but doesn't auto-assign plates

## Usage Flow for Exam

### Step 1: Ensure Spaces Are Occupied
- Make sure parking spaces are occupied (vehicles detected and spaces marked occupied)
- **Wait at least 30 seconds** after spaces become occupied

### Step 2: Detect Plates
- Go to Detection Viewer page
- Select the Barrier camera
- Click "Detect Plates" button
- Multiple plates can be detected at once

### Step 3: See Results
- Alert box shows: "🎓 EXAM MODE: Detected X plate(s), randomly assigned Y to occupied parking spaces (30s+ occupation)"
- Check `tracking_debug.html` to see plates displayed in parking space grid
- Plates appear in large bold red text: **🚗 PLATE_NUMBER**

### Step 4: Verify in Firebase
- Open Firebase Console → parkingSpaces collection
- Check that `vehiclePlate` field is populated for occupied spaces
- Verify `occupiedAt` timestamp shows 30+ seconds ago

## Technical Details

### Eligibility Criteria
A parking space is eligible for random plate assignment if:
1. `isOccupied = true`
2. `vehiclePlate` is null or empty (no plate assigned yet)
3. `occupiedAt` timestamp is 30+ seconds in the past
4. Valid `occupiedAt` field exists

### Assignment Algorithm
```python
1. Get all occupied spaces from Firebase
2. Filter: no plate AND occupied 30+ seconds
3. Shuffle eligible spaces randomly
4. For each space (random order):
   - Get next plate from queue (LIFO)
   - Update Firebase with plate number
   - Log assignment
5. Return list of assigned spaces
```

### Firebase Updates
For each assigned space:
```python
{
    'vehiclePlate': 'PLATE_NUMBER',
    'updatedAt': 'current_timestamp_ISO'
    # Note: isOccupied and occupiedAt remain unchanged
}
```

## Logs to Watch

When detecting plates, you'll see:
```
📋 Added plate 'ABC123' to queue for parking lot_xxx (queue size: 1)
🎓 EXAM MODE: Triggering random plate assignment to occupied spaces...
✅ Space A-01 eligible (occupied for 45.2s)
✅ Space B-03 eligible (occupied for 38.7s)
✅ Retrieved plate 'ABC123' from queue for parking lot_xxx
🎓 EXAM MODE: Randomly assigned plate 'ABC123' to space A-01 (occupied for 45.2s)
✅ Randomly assigned 1 plate(s) to occupied spaces
  → ABC123 → A-01 (occupied 45.2s)
```

## Advantages for Exam Demo

1. **Realistic**: Simulates real-world scenario where vehicles park before plate detection
2. **Visual**: Clear indication with 🎓 EXAM MODE messages
3. **Flexible**: Works with any number of plates and spaces
4. **Transparent**: Detailed logging shows exactly what happens
5. **Safe**: 30-second delay ensures stable occupancy detection
6. **Random**: Demonstrates that assignment is not deterministic

## Testing Checklist

- [ ] Park vehicles in spaces (wait for occupancy detection)
- [ ] Wait 30+ seconds after parking
- [ ] Click "Detect Plates" on barrier camera
- [ ] Verify plates appear in occupied spaces (tracking_debug.html)
- [ ] Check Firebase parkingSpaces collection for vehiclePlate
- [ ] Test with multiple plates (should assign to multiple random spaces)
- [ ] Test with queue empty (should show appropriate message)
- [ ] Test with no eligible spaces (should show "waiting for 30+ seconds" message)

## Reverting to Normal Mode

To disable exam mode and restore automatic assignment:

1. Uncomment the assignment code in `parking_monitor_worker.py` (lines ~577-597)
2. Modify `detect_new_occupancy()` to re-enable auto-assignment
3. Update `manual_alpr.py` to remove random assignment call

## Notes

- Queue size: Maximum 10 plates (FIFO with LIFO retrieval)
- Plates are marked as "assigned" after use
- Once assigned, plates won't be reassigned to other spaces
- System continues to track occupancy changes for real-time updates
- Random assignment ensures fairness in demo scenarios

Good luck with your final exam! 🎓✨
