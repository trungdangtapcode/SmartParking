# Parking Space Detection Integration Example

This document shows how to integrate the parking space matching system into your existing detection pipeline.

## Quick Start

### 1. Import the Service

```python
from services.firebase_service import FirebaseService
from services.parking_space_service import ParkingSpaceService

# Initialize services
firebase_service = FirebaseService()
parking_service = ParkingSpaceService(firebase_service)
```

### 2. Load Parking Spaces (Once at Startup)

```python
# Load parking spaces for your camera
camera_id = "Dna1o7ve8UcaYALcJWYJEDBo9ct1_1767472893089"  # Your ESP32 config ID
parking_spaces = parking_service.get_parking_spaces_by_camera(camera_id)

print(f"Loaded {len(parking_spaces)} parking spaces")
```

### 3. Match Detections in Your Detection Loop

```python
# Your existing YOLO detection code
results = model(frame)
detections = []

for result in results:
    boxes = result.boxes
    for box in boxes:
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        conf = float(box.conf[0])
        cls = int(box.cls[0])
        
        detections.append({
            'bbox': [x1, y1, x2, y2],
            'class': model.names[cls],
            'confidence': conf
        })

# Match detections to parking spaces
image_height, image_width = frame.shape[:2]
matched_detections, space_occupancy = parking_service.match_detections_to_spaces(
    detections=detections,
    parking_spaces=parking_spaces,
    image_width=image_width,
    image_height=image_height,
    iou_threshold=0.5  # Adjust as needed
)

# Now matched_detections includes parking_space_id and parking_space_name
# space_occupancy is a dict: {space_id: True/False}
```

### 4. Update Firebase (Optional)

```python
# Update parking space occupancy in Firebase
parking_id = "P01"  # Your parking lot ID
parking_service.update_space_occupancy(
    parking_id=parking_id,
    camera_id=camera_id,
    space_occupancy=space_occupancy
)
```

### 5. Get Parking Summary (Optional)

```python
# Get overall parking lot statistics
summary = parking_service.get_parking_summary(parking_id="P01")

print(f"Total spaces: {summary['total_spaces']}")
print(f"Occupied: {summary['occupied_spaces']}")
print(f"Available: {summary['available_spaces']}")
print(f"Occupancy rate: {summary['occupancy_rate']:.1%}")
```

## Full Integration Example

### Detection Endpoint with Parking Space Matching

```python
from fastapi import FastAPI, UploadFile
from services.firebase_service import FirebaseService
from services.parking_space_service import ParkingSpaceService
import cv2
import numpy as np
from ultralytics import YOLO

app = FastAPI()

# Initialize services (once at startup)
firebase_service = FirebaseService()
parking_service = ParkingSpaceService(firebase_service)
model = YOLO('yolov8n.pt')

# Cache parking spaces per camera
parking_spaces_cache = {}

@app.post("/api/detect-with-parking")
async def detect_with_parking(
    file: UploadFile,
    camera_id: str,
    parking_id: str
):
    """
    Detect vehicles and match to parking spaces
    """
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        image_height, image_width = frame.shape[:2]
        
        # Load parking spaces (use cache)
        if camera_id not in parking_spaces_cache:
            parking_spaces_cache[camera_id] = parking_service.get_parking_spaces_by_camera(camera_id)
        
        parking_spaces = parking_spaces_cache[camera_id]
        
        # Run YOLO detection
        results = model(frame)
        detections = []
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                class_name = model.names[cls]
                
                # Only process vehicles
                if class_name in ['car', 'truck', 'bus', 'motorcycle']:
                    detections.append({
                        'bbox': [float(x1), float(y1), float(x2), float(y2)],
                        'class': class_name,
                        'confidence': conf
                    })
        
        # Match detections to parking spaces
        matched_detections, space_occupancy = parking_service.match_detections_to_spaces(
            detections=detections,
            parking_spaces=parking_spaces,
            image_width=image_width,
            image_height=image_height,
            iou_threshold=0.5
        )
        
        # Update Firebase
        parking_service.update_space_occupancy(
            parking_id=parking_id,
            camera_id=camera_id,
            space_occupancy=space_occupancy
        )
        
        # Get summary
        summary = parking_service.get_parking_summary(parking_id)
        
        # Return results
        return {
            'success': True,
            'detections': matched_detections,
            'summary': summary,
            'occupancy': space_occupancy
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
```

## Visualization Example

### Draw Parking Spaces and Detections on Frame

```python
def draw_parking_spaces(frame, parking_spaces, space_occupancy):
    """
    Draw parking spaces on frame with color-coded occupancy
    """
    height, width = frame.shape[:2]
    
    for space in parking_spaces:
        # Convert normalized to pixel coordinates
        x = int(space['x'] * width)
        y = int(space['y'] * height)
        w = int(space['width'] * width)
        h = int(space['height'] * height)
        
        # Color based on occupancy
        is_occupied = space_occupancy.get(space['id'], False)
        color = (0, 0, 255) if is_occupied else (0, 255, 0)  # Red if occupied, Green if available
        
        # Draw rectangle
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        
        # Draw label
        label = f"{space['name']} - {'OCCUPIED' if is_occupied else 'AVAILABLE'}"
        cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    return frame


def draw_detections(frame, matched_detections):
    """
    Draw detection boxes on frame
    """
    for det in matched_detections:
        x1, y1, x2, y2 = [int(v) for v in det['bbox']]
        
        # Color based on whether matched to parking space
        color = (255, 0, 0) if det['parking_space_id'] else (128, 128, 128)  # Blue if matched, Gray if not
        
        # Draw box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Label
        label = f"{det['class']} {det['confidence']:.2f}"
        if det['parking_space_id']:
            label += f" - {det['parking_space_name']}"
        
        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    return frame


# Usage in detection loop
frame_with_spaces = draw_parking_spaces(frame, parking_spaces, space_occupancy)
frame_with_all = draw_detections(frame_with_spaces, matched_detections)
```

## Performance Optimization

### 1. Cache Parking Spaces

Don't reload parking spaces on every frame:

```python
# At startup
parking_spaces = parking_service.get_parking_spaces_by_camera(camera_id)

# Use cached spaces in loop
for frame in video_stream:
    matched, occupancy = parking_service.match_detections_to_spaces(
        detections, parking_spaces, width, height
    )
```

### 2. Batch Firebase Updates

Update Firebase less frequently (e.g., every 5 seconds):

```python
import time

last_update_time = time.time()
UPDATE_INTERVAL = 5  # seconds

for frame in video_stream:
    # ... detection and matching ...
    
    # Only update Firebase every 5 seconds
    if time.time() - last_update_time >= UPDATE_INTERVAL:
        parking_service.update_space_occupancy(parking_id, camera_id, space_occupancy)
        last_update_time = time.time()
```

### 3. Adjust IoU Threshold

Fine-tune the IoU threshold based on your setup:

```python
# Strict matching (fewer false positives)
iou_threshold = 0.7

# Loose matching (catch more occupancies)
iou_threshold = 0.3

# Balanced (default)
iou_threshold = 0.5
```

## Troubleshooting

### No Matches Found

**Problem**: Detections aren't matching any parking spaces

**Solutions**:
1. Check if parking spaces exist: `len(parking_spaces) > 0`
2. Lower IoU threshold: Try 0.3 instead of 0.5
3. Verify camera_id matches between editor and detection system
4. Print detection boxes and space boxes to compare coordinates

### Wrong Matches

**Problem**: Detections matching incorrect spaces

**Solutions**:
1. Increase IoU threshold: Try 0.6-0.7
2. Redraw parking spaces in editor to better match actual parking areas
3. Check if spaces are overlapping in editor

### Performance Issues

**Problem**: Detection is slow

**Solutions**:
1. Cache parking spaces (don't reload every frame)
2. Reduce number of parking spaces per camera (<50)
3. Update Firebase less frequently (every 5-10 seconds)
4. Use batch operations for Firebase updates

## Testing

### Unit Test Example

```python
def test_parking_space_matching():
    """Test parking space matching logic"""
    
    # Mock parking space
    parking_spaces = [{
        'id': 'test_space_1',
        'name': 'A1',
        'parkingId': 'P01',
        'cameraId': 'CAM001',
        'x': 0.25,
        'y': 0.25,
        'width': 0.2,
        'height': 0.3
    }]
    
    # Mock detection that overlaps with space
    detections = [{
        'bbox': [160, 120, 288, 264],  # 25% x, 25% y, 45% x2, 55% y2 (on 640x480)
        'class': 'car',
        'confidence': 0.95
    }]
    
    # Match
    matched, occupancy = parking_service.match_detections_to_spaces(
        detections, parking_spaces, 640, 480, iou_threshold=0.3
    )
    
    # Assertions
    assert len(matched) == 1
    assert matched[0]['parking_space_id'] == 'test_space_1'
    assert occupancy['test_space_1'] == True
    
    print("✅ Test passed!")


test_parking_space_matching()
```

---

## Next Steps

1. **Integrate into existing detection endpoint** - Add parking space matching to your current detection API
2. **Test with real camera feeds** - Verify matching works with actual detections
3. **Tune IoU threshold** - Adjust based on your camera angles and parking layout
4. **Add visualization** - Draw parking spaces on video stream for debugging
5. **Monitor performance** - Track matching accuracy and system performance

For more details, see [PARKING_SPACE_EDITOR.md](./PARKING_SPACE_EDITOR.md)
