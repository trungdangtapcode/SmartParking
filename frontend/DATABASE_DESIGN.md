# 🚗 Smart Parking - Database Design

## 📊 Database Structure (Firestore)

### **Collection 1: `parkingLots` (Parking Lot Management)**

Quản lý thông tin tổng quan của từng bãi đỗ xe.

#### Document ID: `{parkingId}`

```typescript
interface ParkingLot {
  // Basic Info
  id: string;                    // "PARKING_A"
  name: string;                  // "Bãi đỗ xe tòa nhà A"
  address: string;               // "123 Nguyễn Văn A, TP.HCM"
  ownerId: string;               // User ID của chủ bãi
  
  // Capacity
  totalSpaces: number;           // Tổng số chỗ (aggregate từ cameras)
  availableSpaces: number;       // Số chỗ trống (updated by tracking)
  occupiedSpaces: number;        // Số chỗ đã đỗ (updated by tracking)
  
  // Cameras
  cameras: string[];             // ["CAM001", "CAM002", "CAM003"]
  
  // Metadata
  createdAt: Timestamp;
  updatedAt: Timestamp;
  status: 'active' | 'inactive'; // Bãi có đang hoạt động không
  
  // Optional: Business info
  pricePerHour?: number;         // Giá tiền/giờ
  openTime?: string;             // "00:00"
  closeTime?: string;            // "23:59"
}
```

**Example:**
```json
{
  "id": "PARKING_A",
  "name": "Bãi đỗ xe tòa nhà A",
  "address": "123 Nguyễn Văn A, TP.HCM",
  "ownerId": "yt88rSJpBsMzjnWX2SfCN687iex1",
  "totalSpaces": 25,
  "availableSpaces": 18,
  "occupiedSpaces": 7,
  "cameras": ["CAM001", "CAM002", "CAM003"],
  "createdAt": "2025-12-05T10:00:00Z",
  "updatedAt": "2025-12-05T11:30:00Z",
  "status": "active",
  "pricePerHour": 15000
}
```

---

### **Collection 2: `detections` (Camera-level Parking Spaces)**

Quản lý parking spaces definition cho từng camera (Phase 1).

#### Document ID: `{ownerId}__{cameraId}`

```typescript
interface CameraDetection {
  // Camera Info
  cameraId: string;              // "CAM001"
  ownerId: string;               // User ID
  parkingId: string;             // "PARKING_A" (reference to parkingLots)
  
  // Parking Spaces (Phase 1 - Tiền xử lý)
  spaces: SavedSpace[];          // Các parking slots của camera này
  spaceCount: number;            // spaces.length
  
  // Snapshot
  inputImageUrl: string;         // Ảnh gốc khi define spaces
  
  // Metadata
  timestamp: Timestamp;
  updateCount: number;
}

interface SavedSpace {
  id: string;                    // "space-1733479028875-0"
  bbox: [number, number, number, number]; // [x, y, width, height]
  confidence: number;            // 0-1
}
```

**Example:**
```json
{
  "cameraId": "CAM001",
  "ownerId": "yt88rSJpBsMzjnWX2SfCN687iex1",
  "parkingId": "PARKING_A",
  "spaces": [
    { "id": "space-001", "bbox": [100, 200, 80, 120], "confidence": 0.95 },
    { "id": "space-002", "bbox": [200, 200, 80, 120], "confidence": 0.92 }
  ],
  "spaceCount": 2,
  "inputImageUrl": "data:image/jpeg;base64,...",
  "timestamp": "2025-12-05T10:30:00Z",
  "updateCount": 3
}
```

---

### **Collection 3: `parkingSpaces` (Individual Space Status)**

Track trạng thái từng parking slot (Phase 2 - Tracking system).

#### Document ID: `{parkingId}__{spaceId}`

```typescript
interface ParkingSpaceStatus {
  // Space Identity
  spaceId: string;               // "space-001"
  parkingId: string;             // "PARKING_A"
  cameraId: string;              // "CAM001" (camera có thể nhìn thấy slot này)
  
  // Location
  bbox: [number, number, number, number];
  
  // Status (Updated by tracking system)
  occupied: boolean;             // true = có xe, false = trống
  lastDetectionTime: Timestamp;  // Lần cuối detect
  
  // Vehicle Info (if occupied)
  vehicleType?: string;          // "car", "motorbike"
  vehicleId?: string;            // Tracking ID
  entryTime?: Timestamp;         // Thời gian xe vào
  licensePlate?: string;         // Biển số (from OCR)
  
  // Metadata
  createdAt: Timestamp;
  updatedAt: Timestamp;
}
```

**Example:**
```json
{
  "spaceId": "space-001",
  "parkingId": "PARKING_A",
  "cameraId": "CAM001",
  "bbox": [100, 200, 80, 120],
  "occupied": true,
  "lastDetectionTime": "2025-12-05T11:30:00Z",
  "vehicleType": "car",
  "vehicleId": "vehicle-track-123",
  "entryTime": "2025-12-05T09:15:00Z",
  "licensePlate": "51A-12345",
  "createdAt": "2025-12-05T08:00:00Z",
  "updatedAt": "2025-12-05T11:30:00Z"
}
```

---

### **Collection 4: `vehicleTracking` (Vehicle Tracking History)**

Lưu lịch sử xe ra vào (cho báo cáo, tính tiền).

#### Document ID: Auto-generated

```typescript
interface VehicleTrackingRecord {
  // Vehicle Info
  vehicleId: string;             // Tracking ID
  licensePlate?: string;         // Biển số
  vehicleType: string;           // "car", "motorbike"
  
  // Location
  parkingId: string;             // "PARKING_A"
  spaceId: string;               // "space-001"
  cameraId: string;              // "CAM001"
  
  // Timing
  entryTime: Timestamp;          // Thời gian vào
  exitTime?: Timestamp;          // Thời gian ra (null nếu chưa ra)
  duration?: number;             // Thời gian đỗ (seconds)
  
  // Images
  entryImage?: string;           // Ảnh lúc vào
  exitImage?: string;            // Ảnh lúc ra
  
  // Payment
  fee?: number;                  // Phí đỗ xe
  paid?: boolean;                // Đã thanh toán chưa
  
  // Metadata
  createdAt: Timestamp;
  updatedAt: Timestamp;
}
```

---

## 🔄 Data Flow

### **Phase 1: Setup Parking Lot**

```
1. Admin tạo Parking Lot
   → Collection: parkingLots
   → Data: name, address, cameras[], etc.

2. Admin define parking spaces cho từng camera
   → Collection: detections
   → Data: spaces[], cameraId, parkingId

3. System tự động aggregate totalSpaces
   → Update parkingLots.totalSpaces
   → Sum tất cả spaces từ cameras trong bãi
```

### **Phase 2: Real-time Tracking**

```
1. Video stream → Detect vehicles

2. Match vehicles với parking spaces
   → Collection: parkingSpaces
   → Update occupied status

3. Aggregate data cho parking lot
   → Update parkingLots.availableSpaces
   → Update parkingLots.occupiedSpaces

4. Log vehicle entry/exit
   → Collection: vehicleTracking
   → Create/update records
```

---

## 🎯 Queries Examples

### **1. Lấy tổng quan bãi đỗ**
```typescript
// Get parking lot info
const parkingDoc = await getDoc(doc(db, 'parkingLots', 'PARKING_A'));
const data = parkingDoc.data();

console.log(`Bãi ${data.name}:`);
console.log(`- Tổng: ${data.totalSpaces} chỗ`);
console.log(`- Trống: ${data.availableSpaces} chỗ`);
console.log(`- Đầy: ${data.occupiedSpaces} chỗ`);
```

### **2. Lấy danh sách cameras trong bãi**
```typescript
const cameras = data.cameras; // ["CAM001", "CAM002", "CAM003"]

// Get spaces cho từng camera
for (const camId of cameras) {
  const detectionDoc = await getDoc(
    doc(db, 'detections', `${ownerId}__${camId}`)
  );
  console.log(`${camId}: ${detectionDoc.data().spaceCount} spaces`);
}
```

### **3. Lấy trạng thái chi tiết từng chỗ đỗ**
```typescript
const spacesQuery = query(
  collection(db, 'parkingSpaces'),
  where('parkingId', '==', 'PARKING_A')
);
const spacesSnapshot = await getDocs(spacesQuery);

spacesSnapshot.forEach(doc => {
  const space = doc.data();
  console.log(`${space.spaceId}: ${space.occupied ? '🚗 Đầy' : '✅ Trống'}`);
});
```

### **4. Real-time listener cho bãi đỗ**
```typescript
// Listen to parking lot changes
const unsubscribe = onSnapshot(
  doc(db, 'parkingLots', 'PARKING_A'),
  (snapshot) => {
    const data = snapshot.data();
    updateUI({
      available: data.availableSpaces,
      occupied: data.occupiedSpaces
    });
  }
);
```

---

## 📝 Migration Steps (Từ cấu trúc cũ sang mới)

### **Step 1: Create parkingLots collection**
```typescript
// Tạo parking lot document
await setDoc(doc(db, 'parkingLots', 'PARKING_A'), {
  id: 'PARKING_A',
  name: 'Bãi đỗ xe tòa nhà A',
  address: '...',
  ownerId: 'xxx',
  totalSpaces: 0,  // Will be calculated
  availableSpaces: 0,
  occupiedSpaces: 0,
  cameras: [],
  status: 'active',
  createdAt: Timestamp.now(),
  updatedAt: Timestamp.now()
});
```

### **Step 2: Link cameras to parking lot**
```typescript
// Update detection records to reference parking lot
// (Already have parkingId field)

// Add camera to parking lot's cameras array
await updateDoc(doc(db, 'parkingLots', 'PARKING_A'), {
  cameras: arrayUnion('CAM001')
});
```

### **Step 3: Calculate totalSpaces**
```typescript
async function calculateTotalSpaces(parkingId: string) {
  // Get parking lot
  const parkingDoc = await getDoc(doc(db, 'parkingLots', parkingId));
  const cameras = parkingDoc.data().cameras;
  
  // Sum spaces from all cameras
  let total = 0;
  for (const camId of cameras) {
    const detectionDoc = await getDoc(
      doc(db, 'detections', `${ownerId}__${camId}`)
    );
    if (detectionDoc.exists()) {
      total += detectionDoc.data().spaceCount || 0;
    }
  }
  
  // Update parking lot
  await updateDoc(doc(db, 'parkingLots', parkingId), {
    totalSpaces: total,
    availableSpaces: total,  // Initially all available
    updatedAt: Timestamp.now()
  });
}
```

### **Step 4: Create parkingSpaces documents**
```typescript
// For each space in detections, create a parkingSpaces document
const detectionDoc = await getDoc(doc(db, 'detections', `${ownerId}__CAM001`));
const { spaces, parkingId, cameraId } = detectionDoc.data();

for (const space of spaces) {
  await setDoc(
    doc(db, 'parkingSpaces', `${parkingId}__${space.id}`),
    {
      spaceId: space.id,
      parkingId,
      cameraId,
      bbox: space.bbox,
      occupied: false,  // Initially empty
      lastDetectionTime: Timestamp.now(),
      createdAt: Timestamp.now(),
      updatedAt: Timestamp.now()
    }
  );
}
```

---

## 🎨 UI Components

### **Parking Lot Dashboard**
```typescript
function ParkingLotDashboard({ parkingId }: { parkingId: string }) {
  const [parkingLot, setParkingLot] = useState<ParkingLot | null>(null);
  
  useEffect(() => {
    const unsubscribe = onSnapshot(
      doc(db, 'parkingLots', parkingId),
      (snapshot) => {
        setParkingLot(snapshot.data() as ParkingLot);
      }
    );
    return unsubscribe;
  }, [parkingId]);
  
  if (!parkingLot) return <div>Loading...</div>;
  
  const occupancyRate = (parkingLot.occupiedSpaces / parkingLot.totalSpaces) * 100;
  
  return (
    <div>
      <h1>{parkingLot.name}</h1>
      <div className="stats">
        <div className="stat">
          <div className="label">Tổng số chỗ</div>
          <div className="value">{parkingLot.totalSpaces}</div>
        </div>
        <div className="stat green">
          <div className="label">Chỗ trống</div>
          <div className="value">{parkingLot.availableSpaces}</div>
        </div>
        <div className="stat red">
          <div className="label">Đã đỗ</div>
          <div className="value">{parkingLot.occupiedSpaces}</div>
        </div>
        <div className="stat">
          <div className="label">Tỷ lệ lấp đầy</div>
          <div className="value">{occupancyRate.toFixed(1)}%</div>
        </div>
      </div>
      
      <div className="cameras">
        <h3>Cameras ({parkingLot.cameras.length})</h3>
        {parkingLot.cameras.map(camId => (
          <CameraCard key={camId} cameraId={camId} />
        ))}
      </div>
    </div>
  );
}
```

---

## 📊 Comparison: Old vs New

| Feature | Old Structure | New Structure |
|---------|--------------|---------------|
| **Parking lot info** | ❌ Không có | ✅ Collection `parkingLots` |
| **Total spaces** | ❌ Phải query nhiều cameras | ✅ Field `totalSpaces` |
| **Available spaces** | ❌ Không track | ✅ Field `availableSpaces` |
| **Cameras management** | ❌ Scatter trong detections | ✅ Array `cameras[]` |
| **Real-time tracking** | ❌ Không có | ✅ Collection `parkingSpaces` |
| **Vehicle history** | ❌ Không lưu | ✅ Collection `vehicleTracking` |
| **Scalability** | ⚠️ Khó scale | ✅ Dễ scale, optimize |

---

**Updated:** December 5, 2025

