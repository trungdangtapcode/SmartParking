**Đừng lo! Firebase Storage CÓ FREE TIER rất hào phóng. Và có nhiều options miễn phí khác!** 😊

## 💰 Firebase Storage - MIỄN PHÍ (Có thể đủ dùng!)

### Free Tier (Spark Plan):

```
✅ Storage: 5 GB miễn phí
✅ Download: 1 GB/ngày miễn phí
✅ Upload: 20,000 operations/ngày
```

**Đủ cho:**
- ~1,000 ảnh xe (mỗi ảnh 5MB)
- ~50 video (mỗi video 100MB)
- Demo và testing

**Không cần thẻ tín dụng!**

---

## 🎯 Các Options MIỄN PHÍ

### **Option 1: Firebase Storage** ⭐ (Khuyến nghị)

**Lý do:**
- ✅ Tích hợp sẵn với Firestore
- ✅ 5GB free
- ✅ Dễ dùng
- ✅ Không cần thẻ tín dụng

```typescript
// Code y như trước, 100% miễn phí
const storageRef = ref(storage, `vehicles/${vehicleId}.jpg`);
await uploadBytes(storageRef, file);
const url = await getDownloadURL(storageRef);
```

---

### **Option 2: Cloudinary** (Free tier tốt)

**Free tier:**
```
✅ 25 GB storage
✅ 25 GB bandwidth/tháng
✅ Tự động resize, optimize ảnh
```

**Code:**

```typescript
// npm install cloudinary
import { v2 as cloudinary } from 'cloudinary';

cloudinary.config({
  cloud_name: 'your_cloud_name',
  api_key: 'your_api_key',
  api_secret: 'your_api_secret'
});

// Upload
const result = await cloudinary.uploader.upload(file);
const imageUrl = result.secure_url;
```

---

### **Option 3: ImgBB** (Đơn giản nhất)

**Free tier:**
```
✅ Unlimited storage
✅ Miễn phí 100%
✅ Không cần đăng ký (có API key free)
```

**Code:**

```typescript
const uploadToImgBB = async (file: File): Promise<string> => {
  const formData = new FormData();
  formData.append('image', file);
  
  const response = await fetch(
    'https://api.imgbb.com/1/upload?key=YOUR_API_KEY',
    {
      method: 'POST',
      body: formData
    }
  );
  
  const data = await response.json();
  return data.data.url;
};
```

---

### **Option 4: Supabase Storage** (Firebase alternative)

**Free tier:**
```
✅ 1 GB storage
✅ 2 GB bandwidth
✅ Giống Firebase
```

**Code:**

```typescript
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  'YOUR_PROJECT_URL',
  'YOUR_ANON_KEY'
);

// Upload
const { data, error } = await supabase.storage
  .from('vehicles')
  .upload(`${vehicleId}.jpg`, file);

// Get URL
const { data: { publicUrl } } = supabase.storage
  .from('vehicles')
  .getPublicUrl(`${vehicleId}.jpg`);
```

---

### **Option 5: Google Drive** (Bạn đề cập)

**Free tier:**
```
✅ 15 GB miễn phí
```

**Nhược điểm:**
- ❌ Setup phức tạp (cần Google Drive API)
- ❌ Không tối ưu cho web apps
- ❌ Rate limiting nghiêm ngặt

**Code (phức tạp):**

```typescript
// Cần Google Drive API credentials
import { google } from 'googleapis';

const drive = google.drive({
  version: 'v3',
  auth: oauth2Client
});

// Upload
const response = await drive.files.create({
  requestBody: {
    name: 'vehicle.jpg',
    mimeType: 'image/jpeg',
  },
  media: {
    mimeType: 'image/jpeg',
    body: fileStream,
  },
});

// Share file publicly và lấy link
await drive.permissions.create({
  fileId: response.data.id,
  requestBody: {
    role: 'reader',
    type: 'anyone',
  },
});
```

**⚠️ KHÔNG khuyến nghị vì quá phức tạp!**

---

### **Option 6: GitHub (Hack - chỉ cho ảnh nhỏ)**

```typescript
// Upload ảnh lên GitHub repo của bạn
// Miễn phí nhưng... không professional
const imageUrl = `https://raw.githubusercontent.com/yourusername/your-repo/main/images/${vehicleId}.jpg`;
```

**Chỉ dùng cho demo!**

---

### **Option 7: Local Storage (Development only)**

```typescript
// Lưu trên máy local (chỉ dùng khi dev)
const handleUpload = (file: File) => {
  const reader = new FileReader();
  reader.onload = (e) => {
    const base64 = e.target?.result;
    localStorage.setItem(`vehicle_${vehicleId}`, base64 as string);
  };
  reader.readAsDataURL(file);
};

// Lấy ảnh
const imageData = localStorage.getItem(`vehicle_${vehicleId}`);
<img src={imageData} />
```

**Chỉ cho development, không dùng production!**

---

## 📊 So Sánh Chi Tiết

| Service | Free Storage | Dễ dùng | Tích hợp Firebase | Khuyến nghị |
|---------|--------------|---------|-------------------|-------------|
| **Firebase Storage** | 5 GB | ⭐⭐⭐ | ✅ | ✅ Tốt nhất |
| **Cloudinary** | 25 GB | ⭐⭐ | ❌ | ✅ Nếu cần resize ảnh |
| **ImgBB** | Unlimited | ⭐⭐⭐ | ❌ | ✅ Đơn giản |
| **Supabase** | 1 GB | ⭐⭐ | ❌ | ✅ Nếu không dùng Firebase |
| **Google Drive** | 15 GB | ⭐ | ❌ | ❌ Quá phức tạp |
| **GitHub** | Unlimited | ⭐⭐ | ❌ | ❌ Chỉ demo |
| **LocalStorage** | ~10 MB | ⭐⭐⭐ | ✅ | ❌ Chỉ dev |

---

## ✅ Khuyến Nghị Cho Bạn

### **Dùng Firebase Storage (Free tier)** - MIỄN PHÍ!

**Lý do:**
1. ✅ Đã setup Firebase rồi
2. ✅ 5GB đủ dùng cho project học tập
3. ✅ Code đơn giản nhất
4. ✅ Tích hợp tốt với Firestore
5. ✅ Không cần thẻ tín dụng

**Nếu vượt free tier:**
- Chuyển sang **Cloudinary** (25GB free)
- Hoặc **ImgBB** (unlimited)

---

## 🚀 Code Hoàn Chỉnh - Firebase Storage (Miễn Phí)

```typescript
// src/services/uploadService.ts
import { ref, uploadBytes, getDownloadURL } from 'firebase/storage';
import { storage } from '@/config/firebase';

/**
 * Upload ảnh miễn phí lên Firebase Storage
 */
export async function uploadVehicleImage(
  file: File,
  vehicleId: string
): Promise<string> {
  try {
    // 1. Compress ảnh trước khi upload (tiết kiệm storage)
    const compressedFile = await compressImage(file);
    
    // 2. Upload lên Firebase Storage
    const storageRef = ref(storage, `vehicles/${vehicleId}.jpg`);
    await uploadBytes(storageRef, compressedFile);
    
    // 3. Lấy URL
    const downloadURL = await getDownloadURL(storageRef);
    
    console.log('✅ Uploaded! URL:', downloadURL);
    console.log('📊 File size:', compressedFile.size / 1024, 'KB');
    
    return downloadURL;
  } catch (error) {
    console.error('❌ Upload failed:', error);
    throw error;
  }
}

/**
 * Compress ảnh để tiết kiệm storage (optional)
 */
async function compressImage(file: File): Promise<File> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const MAX_WIDTH = 1280;
        const MAX_HEIGHT = 720;
        
        let width = img.width;
        let height = img.height;
        
        if (width > height) {
          if (width > MAX_WIDTH) {
            height *= MAX_WIDTH / width;
            width = MAX_WIDTH;
          }
        } else {
          if (height > MAX_HEIGHT) {
            width *= MAX_HEIGHT / height;
            height = MAX_HEIGHT;
          }
        }
        
        canvas.width = width;
        canvas.height = height;
        
        const ctx = canvas.getContext('2d')!;
        ctx.drawImage(img, 0, 0, width, height);
        
        canvas.toBlob((blob) => {
          resolve(new File([blob!], file.name, {
            type: 'image/jpeg',
            lastModified: Date.now()
          }));
        }, 'image/jpeg', 0.8); // 80% quality
      };
      img.src = e.target?.result as string;
    };
    reader.readAsDataURL(file);
  });
}
```

---

## 💡 Tips Tiết Kiệm Storage

### 1. Compress ảnh trước khi upload
```typescript
// Giảm từ 5MB → 500KB
const compressed = await compressImage(file);
```

### 2. Dùng WebP format (nhẹ hơn JPEG)
```typescript
canvas.toBlob((blob) => {
  // Save as WebP (50% lighter than JPEG)
}, 'image/webp', 0.8);
```

### 3. Xóa ảnh cũ khi không dùng
```typescript
import { ref, deleteObject } from 'firebase/storage';

const deleteOldImage = async (vehicleId: string) => {
  const imageRef = ref(storage, `vehicles/${vehicleId}.jpg`);
  await deleteObject(imageRef);
};
```

---

## 🎯 Tóm Tắt

**Đừng lo về tiền!**

1. ✅ **Firebase Storage free tier** (5GB) - Đủ dùng!
2. ✅ Nếu hết → **Cloudinary** (25GB free)
3. ✅ Nếu vẫn hết → **ImgBB** (unlimited free)

**Google Drive KHÔNG cần thiết - quá phức tạp!**

---

**Bạn muốn tôi setup code upload với compress ảnh để tiết kiệm storage không?** 😊