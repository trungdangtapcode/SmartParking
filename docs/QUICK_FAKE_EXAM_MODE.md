# 🎓 FAKE EXAM MODE - Đơn Giản & Nhanh!

## Cách Hoạt Động (FAKE - Chỉ Để Demo Cho Thầy)

### Khi Click "Detect Plates":

1. **Detect plate** → Ví dụ: ABC123, XYZ789
2. **Tự động chọn ngẫu nhiên** một space đang **AVAILABLE** (P7, P9, P11, P12...)
3. **Fake kết quả**: 
   - Đánh dấu space đó thành **OCCUPIED** 
   - Gán plate vào space đó
   - Cập nhật Firebase ngay lập tức

### Ví Dụ:

**Trước khi detect:**
```
P7  - Available
P9  - Available  
P12 - Available   <-- Sẽ bị chọn random
P13 - Occupied
```

**Click "Detect Plates" → Detect được: "51A-12345"**

**Sau khi detect:**
```
P7  - Available
P9  - Available  
P12 - Occupied    <-- ĐÃ FAKE: 🚗 51A-12345
P13 - Occupied
```

## Cách Dùng Cho Thi

### Bước 1: Đảm Bảo Có Space Available
- Vào http://localhost:8069/static/tracking_debug.html
- Check phần "🅿️ Parking Spaces"
- Cần có ít nhất 1 space "Available"

### Bước 2: Detect Plates
- Mở Detection Viewer
- Chọn camera Barrier
- Click "Detect Plates"
- **Alert hiện ra**: "🎓 FAKE EXAM MODE: Detected 1 plate(s), randomly picked 1 AVAILABLE space(s) → now OCCUPIED with plates!"

### Bước 3: Xem Kết Quả
- Refresh trang tracking_debug.html
- Space available giờ đã thành **Occupied** với plate hiện to đỏ: **🚗 51A-12345**

## Code Changes

### `services/vehicle_plate_service.py`
- Method mới: `assign_plates_to_random_available_spaces()`
- Query tất cả spaces với `isOccupied = False`
- Random shuffle danh sách
- Update Firebase:
  ```python
  {
      'isOccupied': True,           # ← FAKE occupied
      'vehiclePlate': 'ABC123',     # ← Gán plate
      'occupiedAt': now,            # ← Timestamp fake
      'updatedAt': now
  }
  ```

### `routers/manual_alpr.py`
- Gọi `assign_plates_to_random_available_spaces()` thay vì method cũ
- Message: "FAKE EXAM MODE" để biết là đang fake

## Logs Để Check

Khi chạy sẽ thấy logs:
```
📋 Added plate '51A-12345' to queue for parking lot_xxx (queue size: 1)
🎓 FAKE EXAM MODE: Assigning plates to random available spaces...
✅ Found 3 available spaces
✅ Retrieved plate '51A-12345' from queue
🎓 FAKE EXAM MODE: Space P12 → OCCUPIED with plate '51A-12345'
✅ FAKE assigned 1 plate(s) to available spaces (now OCCUPIED)
  → 51A-12345 → P12 (AVAILABLE → OCCUPIED)
```

## Ưu Điểm

✅ **Đơn giản** - Không cần xe thật, không cần chờ 30s
✅ **Nhanh** - Kết quả ngay lập tức
✅ **Rõ ràng** - Thấy được space AVAILABLE → OCCUPIED ngay
✅ **Dễ demo** - Chỉ cần click 1 nút là xong

## Lưu Ý

- ⚠️ Đây là **FAKE** hoàn toàn để demo cho thầy
- ⚠️ Không có xe thật, không có detection thật
- ⚠️ Chỉ cần kết quả show đẹp trên màn hình là đủ
- ⚠️ Nếu không còn space Available thì sẽ không fake được (cần free một số spaces trước)

## Test Nhanh

1. Ensure có spaces Available
2. Click "Detect Plates" 
3. Refresh tracking_debug.html
4. ✅ Thấy plate hiện to đỏ trên space vừa fake

**Chúc thi tốt! 🎓🚀**
