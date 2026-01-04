# Parking Space Editor - User Guide

## 📐 Overview

The **Parking Space Editor** allows administrators to define parking space locations on camera feeds by drawing boxes on the video stream. These defined spaces are then used to match against detected vehicles to determine parking occupancy.

## 🎯 How It Works

### Detection Matching Logic

When a vehicle is detected by the AI system:
1. The detection bounding box is compared against all defined parking spaces for that camera
2. If the **Intersection over Union (IoU)** between the detection box and a parking space exceeds a threshold (default: 0.5), the space is marked as **occupied**
3. If no detection overlaps with a space, it's marked as **available**

### IoU (Intersection over Union)

```
IoU = (Area of Intersection) / (Area of Union)
```

- **IoU = 1.0**: Perfect overlap (detection completely covers parking space)
- **IoU = 0.5**: 50% overlap (default threshold)
- **IoU = 0.0**: No overlap

## 🚀 Getting Started

### Prerequisites

1. **Admin account** - Only admins can access the Parking Space Editor
2. **Created parking lot** - Go to `/parking-lots` to create a parking lot first
3. **Configured camera** - Go to `/stream/multi` to save ESP32 camera configurations

### Step-by-Step Guide

#### 1. Navigate to Parking Space Editor

- Click **📐 Parking Space Editor** in the sidebar
- Or go to `/parking-spaces`

#### 2. Select Parking Lot and Camera

- **Select Parking Lot**: Choose which parking lot this camera belongs to
- **Select Camera**: Choose the camera feed to configure
- The video stream will load automatically

#### 3. Draw Parking Spaces

**Create New Space:**
- Click and drag on the canvas to draw a rectangular parking space
- Release to create the space
- The space will be automatically named (P1, P2, P3, etc.)

**Move Space:**
- Click on a parking space to select it (turns red)
- Drag to move the space to a new position

**Resize Space:**
- Select a parking space
- Click and drag the corner handles to resize

**Rename Space:**
- In the right sidebar, click on the space name
- Type a new name (e.g., "A1", "VIP-01", "Disabled Parking")

#### 4. Save Your Configuration

- Click **💾 Lưu tất cả** button to save all parking spaces to Firebase
- The count shows how many spaces will be saved

#### 5. Delete Spaces

**Delete Selected:**
- Select a space by clicking on it
- Click **🗑️ Xóa đã chọn** button

**Clear All:**
- Click **🧹 Xóa tất cả** to remove all spaces
- Useful for starting fresh

## 📊 Data Structure

### Firebase Collection: `parkingSpaceDefinitions`

Each parking space is stored with:

```typescript
{
  id: "CAM001_space_1735976400000",  // Unique ID
  parkingId: "P01",                   // Parking lot ID
  cameraId: "CAM001",                 // Camera ID (ESP32 config ID)
  name: "A1",                         // Display name
  
  // Normalized coordinates (0-1 based on image dimensions)
  x: 0.25,                            // X position (25% from left)
  y: 0.30,                            // Y position (30% from top)
  width: 0.15,                        // Width (15% of image width)
  height: 0.20,                       // Height (20% of image height)
  
  createdAt: Timestamp,               // Creation time
  updatedAt: Timestamp,               // Last update time
  createdBy: "userId123"              // Admin who created it
}
```

### Why Normalized Coordinates?

Coordinates are stored as 0-1 ratios instead of pixel values:
- **Resolution independent**: Works across different camera resolutions
- **Scaling**: Automatically adapts to display size
- **Consistent**: Same coordinates work on 640x480, 1920x1080, etc.

## 🎨 Visual Indicators

| Color | Meaning |
|-------|---------|
| 🟢 Green | Unselected parking space |
| 🔴 Red | Selected parking space |
| 🔵 Blue (dashed) | Currently drawing new space |
| ⬛ Corner handles | Resize handles (only on selected space) |

## 💡 Best Practices

### 1. Camera Positioning

- Mount cameras at an angle for better spatial coverage
- Avoid extreme perspectives that distort space geometry
- Ensure adequate lighting for detection

### 2. Space Definition

- **Draw slightly larger** than actual parking lines to accommodate detection variance
- **Leave gaps** between spaces for detection accuracy
- **Use consistent naming**: A1-A10, B1-B10, etc.
- **Label special spaces**: "VIP", "Disabled", "EV Charging", etc.

### 3. Testing

After defining spaces:
1. Go to detection/monitoring page
2. Watch real-time detections
3. Adjust space boundaries if needed
4. Fine-tune IoU threshold if too many false positives/negatives

### 4. Multiple Cameras

- Each camera needs its own space definitions
- Use naming conventions to distinguish: "Floor1-A1", "Floor2-A1"
- Total parking lot capacity = sum of all camera spaces

## 🔧 Advanced Usage

### Custom IoU Threshold

The default IoU threshold (0.5) works well for most cases, but you can adjust it:

```typescript
// In parkingSpaceService.ts - checkOverlap function
export function checkOverlap(
  detectionBox: {...},
  parkingSpace: {...},
  threshold: number = 0.5  // Change this value
): boolean {
  // ...
}
```

**Recommended thresholds:**
- **0.3-0.4**: Loose matching (more occupied detections, some false positives)
- **0.5**: Balanced (default)
- **0.6-0.7**: Strict matching (fewer false positives, may miss some occupancies)

### Bulk Import/Export

For managing many spaces, you can:

1. **Export current spaces**:
```typescript
const spaces = await getParkingSpacesByCamera(cameraId);
console.log(JSON.stringify(spaces, null, 2));
```

2. **Import spaces** (batch create):
```typescript
const spacesToImport = [
  { id: '...', parkingId: 'P01', cameraId: 'CAM001', name: 'A1', ... },
  { id: '...', parkingId: 'P01', cameraId: 'CAM001', name: 'A2', ... },
  // ... more spaces
];

await batchSaveParkingSpaces(spacesToImport);
```

## 🐛 Troubleshooting

### Video Not Loading

- Check ESP32 camera is online and streaming
- Verify camera IP address is correct
- Check network connectivity
- Try refreshing the page

### Spaces Not Saving

- Ensure you're logged in as admin
- Check Firebase connection
- Look for errors in browser console (F12)
- Verify parking lot and camera are selected

### Detection Not Matching Spaces

- Check if spaces are saved (refresh page and see if they load)
- Verify camera ID matches between editor and detection system
- Adjust IoU threshold
- Redraw spaces to better match parking area

### Performance Issues

- Limit spaces per camera to ~50 for optimal performance
- Use multiple cameras instead of one wide-angle camera
- Close other tabs running video streams

## 📱 Mobile Support

The editor works on tablets and desktops but is **not recommended for phones** due to:
- Small screen size makes precise drawing difficult
- Touch controls are less accurate than mouse
- Video streaming may consume significant mobile data

## 🔐 Security & Permissions

- Only **admin users** can access the editor
- Space definitions are tied to `ownerId` (user who created parking lot)
- Each space tracks `createdBy` for audit purposes
- Regular users can view spaces but cannot edit

## 📚 Related Pages

- **Parking Lot Management** (`/parking-lots`): Create and manage parking lots
- **Camera Configuration** (`/stream/multi`): Save ESP32 camera IPs
- **Multi Stream View** (`/stream/multi`): View all configured cameras
- **Detection/Monitoring**: See real-time parking occupancy

## 🎓 Example Workflow

### Complete Setup for a New Parking Lot

1. **Create Parking Lot** (`/parking-lots`)
   - ID: `P01`
   - Name: "Building A Parking"
   - Total Spaces: 0 (will be calculated)

2. **Save Camera** (`/stream/multi`)
   - Name: "Floor 1 Camera"
   - IP: `http://192.168.1.100:81/stream`

3. **Define Spaces** (`/parking-spaces`)
   - Select "Building A Parking"
   - Select "Floor 1 Camera"
   - Draw 20 parking spaces (A1-A20)
   - Save configuration

4. **Add Camera to Parking Lot** (`/stream/host-multi`)
   - Select "Building A Parking"
   - Select "Floor 1 Camera"
   - Click "Thêm host"

5. **Monitor** (Detection Page)
   - Watch real-time vehicle detections
   - See spaces turn occupied/available
   - View parking lot dashboard

---

## 📞 Support

For issues or questions:
- Check browser console for errors (F12 → Console)
- Review Firebase logs
- Verify camera and network connectivity
- Contact system administrator

**Last Updated**: January 2026
