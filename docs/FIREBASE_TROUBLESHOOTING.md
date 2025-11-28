# Firebase Firestore - Troubleshooting Guide

## Vấn đề: Firebase không lưu data mới

### Các nguyên nhân phổ biến:

#### 1. **Firebase Config thiếu hoặc sai**
**Triệu chứng:** Console log: "Firestore database is not initialized"

**Cách fix:**
- Kiểm tra file `.env.local` trong `frontend/` có đầy đủ các biến:
  ```env
  VITE_FIREBASE_API_KEY=your_api_key
  VITE_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
  VITE_FIREBASE_PROJECT_ID=your_project_id
  VITE_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
  VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
  VITE_FIREBASE_APP_ID=your_app_id
  ```
- Restart dev server sau khi thêm/sửa `.env.local`
- Kiểm tra file `frontend/src/config/firebase.ts` có import đúng không

#### 2. **Firestore Security Rules chặn write**
**Triệu chứng:** Console log: "Permission denied" hoặc "PERMISSION_DENIED"

**Cách fix:**
1. Vào Firebase Console → Firestore Database → Rules
2. Kiểm tra rules hiện tại. Nếu là:
   ```javascript
   match /{document=**} {
     allow read, write: if false;  // ❌ Chặn tất cả
   }
   ```
3. Đổi thành (cho development):
   ```javascript
   match /{document=**} {
     allow read, write: if true;  // ✅ Cho phép tất cả (chỉ dùng cho dev!)
   }
   ```
4. Hoặc rules an toàn hơn:
   ```javascript
   match /detections/{document=**} {
     allow read, write: if request.auth != null;  // Cần authentication
   }
   ```

#### 3. **Firestore Quota exceeded**
**Triệu chứng:** Console log: "quota exceeded" hoặc "QUOTA_EXCEEDED"

**Cách fix:**
- Vào Firebase Console → Usage and billing
- Kiểm tra xem có vượt quota free tier không
- Nếu có, cần upgrade plan hoặc đợi reset quota (hàng tháng)

#### 4. **Network Error**
**Triệu chứng:** Console log: "Network error" hoặc timeout

**Cách fix:**
- Kiểm tra internet connection
- Kiểm tra firewall/proxy có chặn Firebase không
- Thử refresh page và thử lại

#### 5. **Data format không đúng**
**Triệu chứng:** Lỗi khi save, nhưng không có error message rõ ràng

**Cách fix:**
- Kiểm tra console log để xem data format
- Đảm bảo `bbox` là array 4 số: `[x, y, width, height]`
- Đảm bảo `confidence` là number (0-1)
- Đảm bảo `type` là string

---

## Cách Debug:

### 1. **Kiểm tra Console Logs**
Mở Browser DevTools (F12) → Console tab:
- ✅ Nếu thấy: `✅ Saved detection: { docId: "...", vehicleCount: X }` → **Thành công!**
- ❌ Nếu thấy: `❌ Failed to save detection: ...` → Xem error message

### 2. **Kiểm tra Firebase Console**
1. Vào https://console.firebase.google.com
2. Chọn project của bạn
3. Firestore Database → Collections → `detections`
4. Kiểm tra xem có documents mới không

### 3. **Test Firebase Connection**
Thêm vào code để test:
```typescript
import { db } from '../config/firebase';
console.log('Firebase DB:', db);
console.log('Firebase Config:', {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID
});
```

### 4. **Kiểm tra Error Message trong Alert**
Khi click "Save Result", nếu có lỗi sẽ hiện alert với error message cụ thể:
- "Permission denied" → Fix Security Rules
- "Network error" → Check internet
- "Quota exceeded" → Check billing
- "Firestore database is not initialized" → Check config

---

## Tính năng mới đã thêm:

### 1. **Download Data (📥 Download Data)**
- Tải tất cả detection records từ Firestore
- Export ra file JSON
- File name: `detections_YYYY-MM-DD.json`
- Format: Array of detection records với timestamp đã convert sang ISO string

**Cách dùng:**
1. Click button "📥 Download Data"
2. Đợi loading (có thể mất vài giây nếu có nhiều records)
3. File JSON sẽ tự động download

### 2. **Delete All Data (🗑️ Delete All Data)**
- Xóa TẤT CẢ detection records trong Firestore
- ⚠️ **WARNING:** Không thể undo!
- Có confirmation dialog trước khi xóa

**Cách dùng:**
1. Click button "🗑️ Delete All Data"
2. Confirm trong dialog
3. Đợi xóa xong (có thể mất vài giây)

---

## Cải thiện Error Handling:

### Trước đây:
- Chỉ log error vào console
- Không có feedback cho user
- Khó debug

### Bây giờ:
- ✅ Return result object với `success` và `error` message
- ✅ Hiển thị alert với error message cụ thể
- ✅ Log chi tiết vào console
- ✅ Check các lỗi phổ biến (permission, network, quota)
- ✅ Validate input trước khi save

---

## Code Changes:

### `detectionService.ts`:
- ✅ Improved `saveDetectionRecord()` với error handling tốt hơn
- ✅ Added `fetchDetections()` - Fetch data từ Firestore
- ✅ Added `deleteAllDetections()` - Xóa tất cả data
- ✅ Added `deleteDetection(id)` - Xóa một record
- ✅ Added `downloadDetectionsAsJSON()` - Download data as JSON

### `LiveDetection.tsx`:
- ✅ Updated `handleSave()` để hiển thị error message
- ✅ Added `handleDownloadData()` - Handler cho download button
- ✅ Added `handleDeleteAllData()` - Handler cho delete button
- ✅ Added UI buttons: "📥 Download Data" và "🗑️ Delete All Data"
- ✅ Added loading states: `isLoadingData`, `isDeletingData`

---

## Testing:

### Test Save:
1. Detect spaces
2. Click "Save Result"
3. Check console log: `✅ Saved detection: ...`
4. Check Firebase Console → Firestore → `detections` collection
5. Nếu có lỗi, sẽ hiện alert với error message

### Test Download:
1. Click "📥 Download Data"
2. Đợi loading
3. File JSON sẽ download tự động
4. Mở file để xem data

### Test Delete:
1. Click "🗑️ Delete All Data"
2. Confirm trong dialog
3. Đợi xóa xong
4. Check Firebase Console → Firestore → `detections` collection (phải empty)

---

## Next Steps:

Nếu vẫn không lưu được, hãy:
1. Check console logs (F12)
2. Check Firebase Console → Firestore → Rules
3. Check `.env.local` file
4. Check Firebase Console → Usage and billing
5. Thử test với một record đơn giản trước

