# 🎬 MULTI-CAMERA VIEWER SETUP

Hướng dẫn cấu hình **Multi-Camera Viewer** để xem nhiều camera ESP32 hoặc video file đồng thời.

---

## 🎯 Tính Năng

✅ Xem **3 ESP32-CAM** đồng thời  
✅ Xem **3 Video Files** đồng thời  
✅ Mix ESP32 + Video Files  
✅ Mock FFmpeg stream  
✅ Giao diện đẹp, dễ sử dụng  
✅ Thêm/Xóa stream dễ dàng  

---

## 🚀 CÁCH 1: ESP32-CAM (PRODUCTION)

### **Bước 1: Cấu hình IP ESP32-CAM**

Mở file `frontend/src/pages/MultiStreamViewerPage.tsx`:

```typescript
const ESP32_CAMERAS = [
  { id: 'esp32_1', name: 'ESP32-CAM 1', ip: 'http://192.168.1.100:81/stream' },
  { id: 'esp32_2', name: 'ESP32-CAM 2', ip: 'http://192.168.1.101:81/stream' },
  { id: 'esp32_3', name: 'ESP32-CAM 3', ip: 'http://192.168.1.102:81/stream' },
];
```

**Sửa:**
- `ip`: IP address + port của ESP32-CAM của bạn
- `name`: Tên hiển thị (tùy chọn)
- Có thể thêm nhiều ESP32 hơn bằng cách thêm object mới

### **Bước 2: Test ESP32 trực tiếp**

```bash
# Test từng ESP32 trong browser
http://192.168.1.100:81/stream  # ESP32 #1
http://192.168.1.101:81/stream  # ESP32 #2
http://192.168.1.102:81/stream  # ESP32 #3
```

Nếu thấy video stream → ESP32 hoạt động ✅

### **Bước 3: Chạy ứng dụng**

**Terminal 1: Frontend**
```bash
cd frontend
npm run dev
```

**Browser:**
```
http://localhost:5173/stream/multi
```

### **Bước 4: Thêm camera**

1. Chọn "📹 ESP32-CAM"
2. Chọn camera muốn xem (ESP32-CAM 1/2/3)
3. (Tùy chọn) Đặt tên hiển thị
4. Click "➕ Thêm Stream"
5. Lặp lại để thêm nhiều camera

---

## 🎬 CÁCH 2: VIDEO FILES (TESTING)

### **Bước 1: Chuẩn bị video files**

```bash
# Tạo thư mục stream/ (nếu chưa có)
mkdir server\stream

# Copy video files vào
copy C:\path\to\video1.mp4 server\stream\parking_a.mp4
copy C:\path\to\video2.mp4 server\stream\parking_b.mp4
copy C:\path\to\video3.mp4 server\stream\parking_c.mp4
```

**Video requirements:**
- Format: `.mp4`, `.avi`, `.mov`
- Codec: H.264 (khuyên dùng)
- Resolution: 720p hoặc 1080p
- Size: < 100MB (tốt nhất)

### **Bước 2: Cấu hình video files**

Mở file `frontend/src/pages/MultiStreamViewerPage.tsx`:

```typescript
const VIDEO_FILES = [
  { id: 'video_1', name: 'Video 1 - Parking A', filename: 'parking_a.mp4' },
  { id: 'video_2', name: 'Video 2 - Parking B', filename: 'parking_b.mp4' },
  { id: 'video_3', name: 'Video 3 - Parking C', filename: 'parking_c.mp4' },
];
```

**Sửa:**
- `filename`: Phải khớp với tên file trong `server/stream/`
- `name`: Tên hiển thị
- Có thể thêm nhiều video hơn

### **Bước 3: Chạy backend + frontend**

**Terminal 1: FastAPI Backend**
```bash
cd server
conda activate smartparking
python main_fastapi.py
```

**Terminal 2: Frontend**
```bash
cd frontend
npm run dev
```

**Browser:**
```
http://localhost:5173/stream/multi
```

### **Bước 4: Thêm video stream**

1. Chọn "🎬 Video File"
2. Chọn video muốn xem
3. (Tùy chọn) Đặt tên hiển thị
4. Click "➕ Thêm Stream"
5. Lặp lại để thêm nhiều video

---

## 🧪 CÁCH 3: MOCK FFMPEG STREAM

Dùng FFmpeg để mô phỏng ESP32-CAM từ video file.

### **Bước 1: Cài FFmpeg**

**Windows:**
```bash
# Option 1: Chocolatey
choco install ffmpeg

# Option 2: Manual
# Download: https://ffmpeg.org/download.html
# Extract và thêm vào PATH
```

**Linux:**
```bash
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

Hoặc dùng script tự động: `server/install_ffmpeg_windows.bat`

### **Bước 2: Chạy mock stream**

**Windows:**
```bash
cd server
# Sửa VIDEO_FILE trong stream_video_mock.bat nếu cần
.\stream_video_mock.bat
```

**Linux/macOS:**
```bash
cd server
chmod +x stream_video_mock.sh
./stream_video_mock.sh
```

### **Bước 3: Thêm mock stream vào Multi-Camera**

1. Chọn "🧪 Mock FFmpeg"
2. Click "➕ Thêm Stream"

Mock stream sẽ available tại: `http://localhost:8081/stream`

---

## 📊 SỬ DỤNG

### **Thêm Stream**

1. **Chọn loại nguồn:**
   - 📹 ESP32-CAM (phần cứng thật)
   - 🎬 Video File (test)
   - 🧪 Mock FFmpeg (test)

2. **Chọn nguồn cụ thể:**
   - Với ESP32: chọn từ danh sách 3 camera
   - Với Video: chọn từ danh sách 3 video
   - Với Mock: tự động

3. **Tùy chọn tên hiển thị** (optional)

4. **Click "Thêm Stream"**

### **Xóa Stream**

- Click nút ❌ trên góc phải mỗi stream
- Hoặc click "🗑️ Xóa tất cả" để xóa hết

### **Layout**

- **1-3 streams:** Hiển thị lớn
- **4-6 streams:** Grid 2 cột
- **7-9 streams:** Grid 3 cột

---

## ⚙️ CẤU HÌNH NÂNG CAO

### **Thêm nhiều ESP32 hơn**

Edit `frontend/src/pages/MultiStreamViewerPage.tsx`:

```typescript
const ESP32_CAMERAS = [
  { id: 'esp32_1', name: 'Entrance Gate', ip: 'http://192.168.1.100:81/stream' },
  { id: 'esp32_2', name: 'Exit Gate', ip: 'http://192.168.1.101:81/stream' },
  { id: 'esp32_3', name: 'Parking Area A', ip: 'http://192.168.1.102:81/stream' },
  { id: 'esp32_4', name: 'Parking Area B', ip: 'http://192.168.1.103:81/stream' },
  { id: 'esp32_5', name: 'VIP Section', ip: 'http://192.168.1.104:81/stream' },
];
```

### **Thêm nhiều video hơn**

```typescript
const VIDEO_FILES = [
  { id: 'video_1', name: 'Test - Day Scene', filename: 'day.mp4' },
  { id: 'video_2', name: 'Test - Night Scene', filename: 'night.mp4' },
  { id: 'video_3', name: 'Test - Rain', filename: 'rain.mp4' },
  { id: 'video_4', name: 'Test - Busy Hour', filename: 'busy.mp4' },
];
```

### **Đổi resolution stream**

Edit `server/main_fastapi.py`:

```python
# Trong function stream_from_video_file()
# Tìm dòng:
frame = cv2.resize(frame, (640, 480))

# Đổi thành:
frame = cv2.resize(frame, (1280, 720))  # 720p
# hoặc
frame = cv2.resize(frame, (1920, 1080))  # 1080p (tốn băng thông)
```

---

## 🐛 TROUBLESHOOTING

### **ESP32 không stream được**

```
❌ Lỗi: Không thể kết nối
```

**Fix:**
1. Kiểm tra ESP32 đã bật và kết nối WiFi
2. Test trực tiếp IP trong browser: `http://192.168.1.100:81/stream`
3. Đảm bảo ESP32 và máy tính cùng mạng WiFi
4. Check firewall không block port 81

### **Video file không load được**

```
❌ Lỗi: Video file not found: parking_a.mp4
```

**Fix:**
1. Kiểm tra file tồn tại trong `server/stream/`
2. Kiểm tra tên file khớp với config (case-sensitive)
3. Test file bằng VLC player để đảm bảo video hợp lệ

### **Mock FFmpeg không chạy**

```
❌ Lỗi: ffmpeg is not recognized
```

**Fix:**
1. Cài FFmpeg: `choco install ffmpeg` (Windows)
2. Hoặc dùng script: `server/install_ffmpeg_windows.bat`
3. Restart terminal sau khi cài

### **Stream bị lag**

**Nguyên nhân:**
- Video resolution quá cao
- Network chậm
- CPU yếu

**Fix:**
1. Giảm resolution: Edit `main_fastapi.py` (640x480 thay vì 1280x720)
2. Giảm FPS: Sửa `delay = 1.0 / fps` thành `delay = 1.0 / 15`
3. Giảm JPEG quality: `[cv2.IMWRITE_JPEG_QUALITY, 80]` → `60`

### **Không kết nối được FastAPI**

```
❌ Lỗi: Failed to fetch
```

**Fix:**
1. Kiểm tra FastAPI đang chạy: `http://localhost:8000/health`
2. Check CORS settings trong `main_fastapi.py`
3. Đảm bảo port 8000 không bị chiếm

---

## 📂 RELATED FILES

- `frontend/src/pages/MultiStreamViewerPage.tsx` - Multi-camera UI
- `server/main_fastapi.py` - FastAPI streaming endpoint
- `server/stream/` - Video files directory
- `server/stream_video_mock.bat` - FFmpeg mock script
- `server/install_ffmpeg_windows.bat` - FFmpeg installer

---

## 🎓 TIPS & BEST PRACTICES

### **Testing Strategy**

1. **Start simple:** Test với 1 video file trước
2. **Progress gradually:** Thêm dần nhiều stream
3. **Mix sources:** Test mix ESP32 + Video
4. **Monitor performance:** Check CPU & network usage

### **Production Deployment**

1. **Use real ESP32-CAM:** Không dùng video files
2. **Optimize network:** Đảm bảo băng thông đủ
3. **Set lower resolution:** 640x480 cho nhiều camera
4. **Use CDN:** Nếu deploy lên cloud

### **Development Workflow**

1. **Local testing:** Dùng video files
2. **Integration testing:** Dùng Mock FFmpeg
3. **Pre-production:** Test với 1 ESP32 thật
4. **Production:** Deploy tất cả ESP32

---

## 📸 DEMO SCREENSHOTS

```
┌─────────────────────────────────────────┐
│  🎬 Multi-Camera Viewer                 │
├─────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ CAM 1   │  │ CAM 2   │  │ CAM 3   │ │
│  │ [LIVE]  │  │ [LIVE]  │  │ [LIVE]  │ │
│  │ 📹 ESP32│  │ 🎬 Video│  │ 🧪 Mock │ │
│  │         │  │         │  │         │ │
│  └─────────┘  └─────────┘  └─────────┘ │
└─────────────────────────────────────────┘
```

---

## 🆘 SUPPORT

**Issues?** Check:
1. This guide: `MULTI_CAMERA_SETUP.md`
2. Video streaming guide: `server/VIDEO_STREAMING_TESTING.md`
3. FFmpeg guide: `server/install_ffmpeg_windows.bat`
4. Stream folder: `server/stream/README.md`

**Still stuck?**
- Kiểm tra terminal logs (backend & frontend)
- Test từng component riêng lẻ
- Đảm bảo tất cả dependencies đã cài

---

**Happy Multi-Camera Viewing! 🎬📹🚀**

