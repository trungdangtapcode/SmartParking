# 🚀 Parking Space Editor - Quick Start Guide

Get your parking space detection running in **5 minutes**!

## ✅ Prerequisites Checklist

- [ ] Admin account created and logged in
- [ ] At least one parking lot created (`/parking-lots`)
- [ ] At least one camera configured (`/stream/multi`)
- [ ] Camera is streaming video

---

## 📝 Step-by-Step Setup

### Step 1: Create Parking Lot (if not done)

1. Navigate to **🏢 Parking Lots** in sidebar
2. Click **➕ Thêm bãi đỗ xe mới**
3. Fill in:
   - **ID**: `P01`
   - **Name**: `Building A Parking`
   - **Address**: Your address
4. Click **Lưu**

**Time**: 30 seconds

---

### Step 2: Configure Camera (if not done)

1. Navigate to **🧩 Multi Stream View** in sidebar
2. Select **ESP32 Camera** as source
3. Enter camera IP: `http://192.168.1.100:81/stream`
4. Enter camera name: `Floor 1 Camera`
5. Click **💾 Lưu Camera**

**Time**: 30 seconds

---

### Step 3: Open Parking Space Editor

1. Navigate to **📐 Parking Space Editor** in sidebar
2. Or go directly to: `/parking-spaces`

**Time**: 5 seconds

---

### Step 4: Select Configuration

1. **Select Parking Lot**: Choose `Building A Parking`
2. **Select Camera**: Choose `Floor 1 Camera`
3. Wait for video to load (should appear in ~2 seconds)

**Time**: 10 seconds

---

### Step 5: Draw Parking Spaces

**First Space:**
1. Click and drag on the canvas where you see a parking spot
2. Release to create the space
3. It will be named **P1** automatically

**More Spaces:**
4. Repeat for each parking spot
5. Spaces will be named P2, P3, P4... automatically

**Tips:**
- Draw boxes slightly **larger** than the actual parking lines
- Leave **gaps** between spaces
- Cover the entire parking area visible in the frame

**Time**: 2-3 minutes (depending on number of spaces)

---

### Step 6: Adjust Spaces (Optional)

**Move a space:**
- Click on the space to select it (turns red)
- Drag to move

**Resize a space:**
- Select the space
- Drag the corner handles

**Rename a space:**
- Click on the name in the right sidebar
- Type new name (e.g., "A1", "VIP-01")

**Time**: 1 minute

---

### Step 7: Save Configuration

1. Click **💾 Lưu tất cả** button
2. Wait for success message: `✅ Đã lưu X parking spaces!`
3. Spaces are now saved to Firebase

**Time**: 5 seconds

---

### Step 8: Test Detection

**Frontend Test:**
1. Go to your detection/monitoring page
2. Select the same camera
3. Watch as detected vehicles highlight parking spaces

**Backend Integration:**
```python
from services.firebase_service import FirebaseService
from services.parking_space_service import ParkingSpaceService

# Initialize
firebase = FirebaseService()
parking_service = ParkingSpaceService(firebase)

# Load spaces
camera_id = "your_camera_id_here"
spaces = parking_service.get_parking_spaces_by_camera(camera_id)

print(f"Loaded {len(spaces)} parking spaces ✓")
```

**Time**: 30 seconds

---

## 🎉 Complete! You're Done!

Your parking space detection is now active!

---

## 🔍 Verification

Check if everything is working:

### 1. Frontend Check
- [ ] Can see parking lot in dropdown
- [ ] Can see camera in dropdown
- [ ] Video stream loads
- [ ] Can draw and save spaces
- [ ] Spaces appear after page refresh

### 2. Firebase Check
Open Firebase Console:
- [ ] Collection `parkingSpaceDefinitions` exists
- [ ] Documents exist with your camera ID
- [ ] Each space has coordinates (x, y, width, height)

### 3. Backend Check
Run this test:
```python
spaces = parking_service.get_parking_spaces_by_camera(camera_id)
print(f"Found {len(spaces)} spaces")  # Should show your count

# Example output:
# ✅ Loaded 5 parking spaces for camera: CAM001
# Found 5 spaces
```

---

## 📊 Example Result

After setup, your system should look like this:

**Parking Space Editor:**
```
┌─────────────────────────────────────┐
│   Camera Feed                       │
│                                     │
│   ┌────┐  ┌────┐  ┌────┐          │
│   │ A1 │  │ A2 │  │ A3 │          │
│   └────┘  └────┘  └────┘          │
│                                     │
│   ┌────┐  ┌────┐                   │
│   │ B1 │  │ B2 │                   │
│   └────┘  └────┘                   │
│                                     │
└─────────────────────────────────────┘

Spaces Created: 5
Status: ✅ Saved
```

**Detection Output:**
```
Frame processed:
- Detected 2 cars
- Car 1 matched to space A1 (IoU: 0.65) ✓
- Car 2 matched to space B1 (IoU: 0.72) ✓

Occupancy:
  A1: 🔴 OCCUPIED
  A2: 🟢 AVAILABLE
  A3: 🟢 AVAILABLE
  B1: 🔴 OCCUPIED
  B2: 🟢 AVAILABLE
```

---

## 🐛 Troubleshooting

### Video not loading?
**Solutions:**
- Check camera IP is correct
- Verify camera is online: Open IP in browser
- Check network connection
- Try refreshing the page

### Spaces not saving?
**Solutions:**
- Ensure you clicked "Lưu tất cả" button
- Check browser console for errors (F12)
- Verify Firebase connection
- Check you're logged in as admin

### Detection not matching?
**Solutions:**
- Lower IoU threshold to 0.3 (in code)
- Redraw spaces to match parking area better
- Verify camera_id matches

---

## 🎯 Next Steps

Now that your parking space editor is set up:

1. **Monitor Real-Time**
   - Watch detections on your monitoring page
   - See occupancy updates in real-time

2. **Add More Cameras**
   - Repeat setup for other cameras
   - Each camera has its own parking spaces

3. **Fine-Tune Detection**
   - Adjust IoU threshold if needed
   - Redraw spaces for better accuracy

4. **Integrate with Backend**
   - See [PARKING_SPACE_INTEGRATION.md](./PARKING_SPACE_INTEGRATION.md)
   - Add to your detection pipeline

5. **View Analytics**
   - Check parking lot dashboard
   - Monitor occupancy rates
   - Track usage patterns

---

## 📚 More Resources

- **User Guide**: [PARKING_SPACE_EDITOR.md](./PARKING_SPACE_EDITOR.md)
- **Integration Guide**: [PARKING_SPACE_INTEGRATION.md](./PARKING_SPACE_INTEGRATION.md)
- **Visual Workflow**: [PARKING_SPACE_VISUAL.md](./PARKING_SPACE_VISUAL.md)
- **Implementation Details**: [PARKING_SPACE_SUMMARY.md](./PARKING_SPACE_SUMMARY.md)

---

## ⏱️ Total Setup Time

- Prerequisites: 1 minute
- Create parking lot: 30 seconds
- Configure camera: 30 seconds
- Open editor: 5 seconds
- Select config: 10 seconds
- Draw 5 spaces: 2 minutes
- Adjust & rename: 1 minute
- Save: 5 seconds
- Test: 30 seconds

**Total: ~5 minutes** ⚡

---

## 💡 Pro Tips

1. **Use consistent naming**: A1-A10, B1-B10 makes it easier to find spaces
2. **Draw slightly larger**: Detection boxes aren't pixel-perfect
3. **Test immediately**: Draw 1-2 spaces first, test detection, then continue
4. **Save frequently**: Click save after every few spaces
5. **Label special spaces**: "VIP", "Disabled", "EV Charging"

---

## 🎓 Common Patterns

### Parallel Parking (Side by Side)
```
┌────┐ ┌────┐ ┌────┐ ┌────┐
│ A1 │ │ A2 │ │ A3 │ │ A4 │
└────┘ └────┘ └────┘ └────┘
```

### Perpendicular Parking
```
┌────┐
│ A1 │
└────┘
┌────┐
│ A2 │
└────┘
┌────┐
│ A3 │
└────┘
```

### Angled Parking
```
    ┌────┐
   ╱ A1  │
  ╱──────┘
 ╱
┌────┐
│ A2 ╱
└───╱
   ╱
```

---

**Ready to go? Start now!** → `/parking-spaces`

---

**Questions?** Check the troubleshooting section or full documentation!

**Last Updated**: January 4, 2026
