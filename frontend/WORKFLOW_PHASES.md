# 🚗 Smart Parking - Workflow Phases

## 📋 Tổng quan

Hệ thống Smart Parking chỉ xử lý **PHASE 1: Define Parking Slots**.

**Vehicle detection/tracking** sẽ được xử lý riêng bằng **tracking system** (không lưu trong detection collection).

---

## 🛠️ PHASE 1: Tiền xử lý (Pre-processing) - Define Parking Slots

### Mục đích
Xác định vị trí các **chỗ đỗ xe** (parking slots/spaces) trong bãi đỗ.

### Công việc
1. Chụp ảnh/quay video bãi đỗ **RỖNG** (không có xe)
2. Sử dụng AI hoặc vẽ thủ công để định nghĩa các parking slots
3. Lưu thông tin vào Firestore → field `spaces`

### Components liên quan
- **SpaceDetectionPage**: Trang chính để define parking slots
- **LiveDetection**: Component để detect và edit parking slots
- **aiDetection.detectParkingSpaces()**: AI detect parking slots

### Data structure: `spaces`
```typescript
interface SavedSpace {
  id: string;                           // "space-1234567890-0"
  bbox: [number, number, number, number]; // [x, y, width, height]
  confidence: number;                    // 0-1
}
```

### Output (Firestore)
```typescript
// Collection: detections
// Document ID: {ownerId}__{cameraId}
{
  timestamp: Timestamp,
  ownerId: string,
  cameraId: string,
  parkingId: string,
  inputImageUrl: string,
  spaces: SavedSpace[],      // ✅ Chỗ đỗ xe đã định nghĩa
  spaceCount: number,        // ✅ Số lượng parking slots
  updateCount: number
}
```

**Note:** Không có field `vehicles` hay `vehicleCount` - tracking được xử lý riêng!

---

## 🚗 Vehicle Tracking (Handled Separately)

### Mục đích
Phát hiện **xe thật sự** trong các parking slots đã được định nghĩa (Phase 1).

### Công nghệ
- **Tracking system** riêng biệt (không dùng detection collection)
- Có thể dùng: Object tracking, IoU matching, Kalman filter, etc.

### Workflow
1. Load parking slots từ Firestore (Phase 1)
2. Detect vehicles real-time trên video stream
3. Match vehicles với slots bằng tracking algorithm
4. Xác định slot occupied/empty
5. Lưu tracking data vào collection riêng (không phải `detections`)

**→ Chi tiết implementation sẽ được thiết kế riêng sau**

---

## 🔄 Workflow Diagram

```
┌─────────────────────────────────────────────────────────┐
│  PHASE 1: Define Parking Slots (ONLY)                 │
│                                                         │
│  📷 Chụp ảnh bãi đỗ trống                               │
│       ↓                                                 │
│  🤖 AI detect hoặc vẽ thủ công                          │
│       ↓                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Space 1  │  │ Space 2  │  │ Space 3  │            │
│  │ [x,y,w,h]│  │ [x,y,w,h]│  │ [x,y,w,h]│            │
│  └──────────┘  └──────────┘  └──────────┘            │
│                                                         │
│  ✅ Lưu Firestore: detections/{owner}_{camera}         │
│     - spaces: SavedSpace[]                             │
│     - spaceCount: 3                                    │
│     - inputImageUrl: string                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
                          ↓
                    (Sau đó...)
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Vehicle Tracking (Handled by Tracking System)         │
│                                                         │
│  🎥 Video stream real-time                              │
│       ↓                                                 │
│  🤖 Detect vehicles + Track movement                    │
│       ↓                                                 │
│  🔄 Match với parking slots (Phase 1)                   │
│       ↓                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Space 1  │  │ Space 2  │  │ Space 3  │            │
│  │ (Empty)  │  │ 🚗       │  │ 🏍️       │            │
│  └──────────┘  └──────────┘  └──────────┘            │
│                                                         │
│  ✅ Lưu tracking collection (RIÊNG)                     │
│     - Không lưu vào detections collection!             │
│     - Chi tiết implementation: TBD                     │
└─────────────────────────────────────────────────────────┘
```

---

## ⚠️ Lưu ý quan trọng

### 1. Tách biệt rõ ràng giữa Spaces và Vehicles
- ✅ **Spaces:** Parking slots definition → Lưu trong `detections` collection
- ✅ **Vehicles:** Tracking data → Lưu trong collection RIÊNG (không dùng detections)

### 2. Không có field `vehicles` trong detections collection
```typescript
// ❌ KHÔNG CÓ trong Firestore detections collection:
vehicles: DetectedVehicle[]  // ← REMOVED
vehicleCount: number         // ← REMOVED

// ✅ CHỈ CÓ:
spaces: SavedSpace[]
spaceCount: number
```

### 3. Workflow hiện tại
```
✅ PHASE 1: Define parking slots
   → Detect parking spaces
   → Lưu vào Firestore detections collection
   → DONE!

⏳ Vehicle Tracking: TBD
   → Sẽ implement riêng bằng tracking system
   → Không liên quan đến detections collection
```

---

## 📂 Files liên quan

### PHASE 1 (Define Parking Slots)
- `frontend/src/pages/SpaceDetectionPage.tsx` - UI để define parking slots
- `frontend/src/components/LiveDetection.tsx` - Component chính
- `frontend/src/services/ai/aiDetection.ts` → `detectParkingSpaces()` - AI detection
- `frontend/src/services/detectionService.ts` → `saveDetectionRecord()` - Lưu Firestore

### Vehicle Tracking (Separate System - TBD)
- `frontend/src/pages/StreamHostPage.tsx` - Live video stream (TODO)
- Tracking algorithm implementation (TODO)
- Matching algorithm (IoU, tracking) (TODO)
- Separate Firestore collection for tracking data (TODO)

---

## 🎯 Status & Next Steps

### ✅ Completed
1. Define parking spaces (Phase 1)
2. Tách biệt rõ ràng: spaces vs vehicles
3. Xóa field `vehicles` khỏi detections collection
4. Rename `detectVehicles()` → `detectParkingSpaces()`

### ⏳ Future Work (Tracking System)
1. Thiết kế tracking system architecture
2. Implement vehicle detection + tracking
3. Matching algorithm với parking slots
4. Real-time update occupied/empty status
5. Separate Firestore collection cho tracking data

---

**Cập nhật:** December 5, 2025

