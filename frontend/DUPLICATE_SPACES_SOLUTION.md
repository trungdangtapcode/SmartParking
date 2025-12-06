# 🚗 Giải pháp cho vấn đề Duplicate Parking Spaces

## ⚠️ Vấn đề

Khi 1 chỗ đỗ xe xuất hiện trong 2 góc camera khác nhau:
- Camera 1: Detect space A tại vị trí [100, 200, 80, 120]
- Camera 2: Detect space B tại vị trí [450, 300, 85, 115] (cùng 1 chỗ vật lý)

→ Bãi đỗ có 10 chỗ thật sự nhưng system đếm là 12 chỗ (duplicate)

---

## 💡 Giải pháp đề xuất

### **Solution 1: Assign Primary Camera (Recommended - Dễ implement)**

**Concept:** Mỗi parking space chỉ được tính 1 lần bởi 1 camera "primary"

#### **Workflow:**

```
1. Admin định nghĩa parking spaces cho mỗi camera
   
2. Admin đánh dấu primary camera cho từng space:
   
   Camera 1 (CAM001):
   ✅ Space A - PRIMARY (đếm vào total)
   ✅ Space B - PRIMARY
   ⚪ Space C - OVERLAP với CAM002 (không đếm)
   
   Camera 2 (CAM002):
   ⚪ Space C - OVERLAP với CAM001 (không đếm)
   ✅ Space D - PRIMARY
   
3. System chỉ đếm spaces có isPrimary = true
```

#### **Implementation:**

```typescript
// 1. Update SavedSpace interface (DONE)
export interface SavedSpace {
  id: string;
  bbox: [number, number, number, number];
  confidence: number;
  isPrimary?: boolean; // ✅ NEW: Camera này là primary
}

// 2. LiveDetection.tsx - Thêm checkbox để mark primary
function SpaceEditor({ space, onUpdate }) {
  return (
    <div>
      <label>
        <input
          type="checkbox"
          checked={space.isPrimary ?? true}
          onChange={(e) => onUpdate({ ...space, isPrimary: e.target.checked })}
        />
        Primary (đếm vào total)
      </label>
    </div>
  );
}

// 3. updateTotalSpaces() - Chỉ đếm primary spaces
export async function updateTotalSpaces(parkingId: string, ownerId: string) {
  let totalSpaces = 0;
  
  for (const cameraId of cameras) {
    const detection = await getDetection(cameraId);
    
    // Chỉ đếm spaces có isPrimary = true
    const primarySpaces = detection.spaces.filter(s => s.isPrimary !== false);
    totalSpaces += primarySpaces.length;
  }
  
  return totalSpaces;
}
```

#### **Pros & Cons:**

✅ **Pros:**
- Dễ implement (chỉ thêm 1 field boolean)
- Admin kiểm soát rõ ràng
- Không cần AI/algorithm phức tạp
- Flexible: Admin có thể thay đổi primary camera bất cứ lúc nào

❌ **Cons:**
- Manual work: Admin phải mark từng space
- Phụ thuộc vào judgment của admin

---

### **Solution 2: Spatial Deduplication (Advanced - Auto)**

**Concept:** Dùng algorithm để tự động phát hiện và loại bỏ duplicates

#### **Algorithm: IoU-based Matching**

```typescript
function deduplicateSpaces(
  spacesFromAllCameras: Array<{ cameraId: string; spaces: SavedSpace[] }>
): SavedSpace[] {
  const allSpaces: Array<SavedSpace & { cameraId: string }> = [];
  
  // Collect all spaces
  spacesFromAllCameras.forEach(({ cameraId, spaces }) => {
    spaces.forEach(space => {
      allSpaces.push({ ...space, cameraId });
    });
  });
  
  // Deduplicate using IoU threshold
  const uniqueSpaces: SavedSpace[] = [];
  const visited = new Set<string>();
  
  for (let i = 0; i < allSpaces.length; i++) {
    if (visited.has(allSpaces[i].id)) continue;
    
    const space1 = allSpaces[i];
    uniqueSpaces.push(space1);
    visited.add(space1.id);
    
    // Check for duplicates
    for (let j = i + 1; j < allSpaces.length; j++) {
      const space2 = allSpaces[j];
      
      // Calculate IoU (Intersection over Union)
      const iou = calculateIoU(space1.bbox, space2.bbox);
      
      // If IoU > threshold → Same space physically
      if (iou > 0.5) {
        visited.add(space2.id);
        console.log(`Duplicate found: ${space1.id} (${space1.cameraId}) ≈ ${space2.id} (${space2.cameraId})`);
      }
    }
  }
  
  return uniqueSpaces;
}

function calculateIoU(
  box1: [number, number, number, number],
  box2: [number, number, number, number]
): number {
  const [x1, y1, w1, h1] = box1;
  const [x2, y2, w2, h2] = box2;
  
  // Calculate intersection
  const xLeft = Math.max(x1, x2);
  const yTop = Math.max(y1, y2);
  const xRight = Math.min(x1 + w1, x2 + w2);
  const yBottom = Math.min(y1 + h1, y2 + h2);
  
  if (xRight < xLeft || yBottom < yTop) return 0;
  
  const intersectionArea = (xRight - xLeft) * (yBottom - yTop);
  const box1Area = w1 * h1;
  const box2Area = w2 * h2;
  const unionArea = box1Area + box2Area - intersectionArea;
  
  return intersectionArea / unionArea;
}
```

#### **Pros & Cons:**

✅ **Pros:**
- Tự động, không cần manual work
- Chính xác nếu cameras có perspective/angle tương đồng
- Scalable cho nhiều cameras

❌ **Cons:**
- Phức tạp hơn nhiều
- Không work nếu 2 cameras nhìn space từ góc quá khác nhau (bbox khác hoàn toàn)
- Cần camera calibration và coordinate transformation

---

### **Solution 3: Physical Space Mapping (Best but Complex)**

**Concept:** Map các spaces về 1 hệ tọa độ chung (world coordinates)

```
Camera 1 → Transform → World Space
Camera 2 → Transform → World Space
              ↓
    Deduplicate trong world space
```

Yêu cầu:
- Camera calibration (intrinsic & extrinsic parameters)
- Homography transformation
- 3D reconstruction

→ **Quá phức tạp cho project này**

---

## 🎯 Khuyến nghị: Solution 1 (Primary Camera)

Cho project Smart Parking, tôi khuyến dùng **Solution 1** vì:

1. ✅ **Đơn giản, dễ implement** (chỉ thêm 1 checkbox)
2. ✅ **Dễ maintain** và debug
3. ✅ **Flexible** - Admin có thể adjust khi cần
4. ✅ **Không cần AI phức tạp**

### **Implementation Steps:**

#### **Step 1: Update UI - LiveDetection component**

Thêm checkbox "Primary" cho mỗi space:

```typescript
// LiveDetection.tsx
<div className="space-controls">
  <label className="flex items-center gap-2">
    <input
      type="checkbox"
      checked={space.isPrimary !== false} // Default true
      onChange={(e) => {
        const updated = spaces.map(s =>
          s.id === space.id
            ? { ...s, isPrimary: e.target.checked }
            : s
        );
        setSpaces(updated);
      }}
    />
    <span>Primary (đếm vào total)</span>
  </label>
</div>
```

#### **Step 2: Update parkingLotService.ts**

```typescript
export async function updateTotalSpaces(
  parkingId: string,
  ownerId: string
): Promise<{ success: boolean; totalSpaces: number; error?: string }> {
  try {
    const parkingLot = await getParkingLot(parkingId);
    if (!parkingLot) {
      return { success: false, totalSpaces: 0, error: 'Parking lot not found' };
    }

    // Sum ONLY primary spaces from all cameras
    let totalSpaces = 0;
    for (const cameraId of parkingLot.cameras) {
      const detectionDocId = `${ownerId}__${cameraId}`;
      const detectionDoc = await getDoc(doc(db, DETECTIONS_COLLECTION, detectionDocId));
      
      if (detectionDoc.exists()) {
        const data = detectionDoc.data();
        // Chỉ đếm spaces có isPrimary = true hoặc undefined (backward compat)
        const primarySpaces = (data.spaces || []).filter(
          (s: SavedSpace) => s.isPrimary !== false
        );
        totalSpaces += primarySpaces.length;
      }
    }

    // Update parking lot
    await updateDoc(doc(db, PARKING_LOTS_COLLECTION, parkingId), {
      totalSpaces,
      availableSpaces: totalSpaces,
      occupiedSpaces: 0,
      updatedAt: Timestamp.now(),
    });

    console.log(`✅ Updated total PRIMARY spaces for ${parkingId}: ${totalSpaces}`);
    return { success: true, totalSpaces };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to update total spaces:', errorMessage);
    return { success: false, totalSpaces: 0, error: errorMessage };
  }
}
```

#### **Step 3: Admin workflow**

1. Define spaces cho Camera 1 → Mark tất cả là Primary
2. Define spaces cho Camera 2 → Uncheck Primary cho spaces bị overlap với Camera 1
3. System tự động tính total = (Camera 1 primary) + (Camera 2 primary)

---

## 📊 Example

### **Scenario:**

```
Bãi đỗ có 10 chỗ thực tế:
- Camera 1 nhìn thấy 7 chỗ (A, B, C, D, E, F, G)
- Camera 2 nhìn thấy 6 chỗ (E, F, G, H, I, J)
- Overlap: E, F, G (3 chỗ bị duplicate)
```

### **Configuration:**

```
Camera 1 (CAM001):
✅ Space A - PRIMARY
✅ Space B - PRIMARY
✅ Space C - PRIMARY
✅ Space D - PRIMARY
✅ Space E - PRIMARY ← Chọn CAM001 làm primary
✅ Space F - PRIMARY ← Chọn CAM001 làm primary
✅ Space G - PRIMARY ← Chọn CAM001 làm primary

Camera 2 (CAM002):
⚪ Space E - NOT PRIMARY (overlap)
⚪ Space F - NOT PRIMARY (overlap)
⚪ Space G - NOT PRIMARY (overlap)
✅ Space H - PRIMARY
✅ Space I - PRIMARY
✅ Space J - PRIMARY
```

### **Result:**

```
Total Spaces = 7 (CAM001) + 3 (CAM002) = 10 ✅
```

---

## 🚀 Next Steps

1. ✅ **DONE:** Add `isPrimary` field to SavedSpace interface
2. **TODO:** Update LiveDetection UI với checkbox Primary
3. **TODO:** Update updateTotalSpaces() để filter primary spaces
4. **TODO:** Admin guide: Cách mark primary cho overlap spaces

---

**Updated:** December 5, 2025

