# 🎬 VIDEO STREAMING FOR TESTING

Hướng dẫn sử dụng video file để testing thay vì ESP32-CAM thật.

---

## 🎯 3 CHẾ ĐỘ STREAMING

### 1. **ESP32-CAM (Production)** 🔄
```
ESP32-CAM → FastAPI Proxy → Frontend
```
- Dùng cho production
- ESP32-CAM phải online
- URL: `http://localhost:8000/stream`

### 2. **Video File (Testing)** 📹
```
Video File (test_video.mp4) → FastAPI → Frontend
```
- Dùng để test khi không có ESP32-CAM
- FastAPI đọc video file và stream như MJPEG
- URL: `http://localhost:8000/stream?mode=video_file`

### 3. **Mock FFmpeg (Testing)** 🎬
```
Video File → FFmpeg → Mock Server :8081 → FastAPI Proxy → Frontend
```
- Giống hệt ESP32-CAM (MJPEG stream)
- Dùng FFmpeg để mô phỏng ESP32-CAM
- URL: `http://localhost:8000/stream?mode=mock`

---

## 🚀 CÁCH SỬ DỤNG

### **Option 1: Video File Mode (ĐƠN GIẢN NHẤT)** ⭐

#### Bước 1: Chuẩn bị video file
```bash
cd server
# Đổi tên video của bạn thành test_video.mp4
# Hoặc copy video vào folder server/
copy path\to\your\video.mp4 test_video.mp4
```

#### Bước 2: Chạy FastAPI server
```bash
conda activate smartparking
python main_fastapi.py
```

#### Bước 3: Truy cập frontend
```
http://localhost:5173/stream/view
```

#### Bước 4: Chọn chế độ "📹 Video File"
- Click nút "Video File" trên giao diện
- Stream sẽ tự động load từ `test_video.mp4`

✅ **Ưu điểm:**
- Không cần cài FFmpeg
- Không cần ESP32-CAM
- Đơn giản nhất

❌ **Nhược điểm:**
- Load CPU cao (FastAPI phải encode JPEG mỗi frame)
- Không giống 100% ESP32-CAM

---

### **Option 2: Mock FFmpeg Mode (GIỐNG ESP32 NHẤT)** 🎯

#### Bước 1: Cài FFmpeg
**Windows:**
```bash
# Tải từ: https://ffmpeg.org/download.html
# Hoặc dùng Chocolatey:
choco install ffmpeg
```

**Ubuntu/Linux:**
```bash
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

#### Bước 2: Chuẩn bị video file
```bash
cd server
copy path\to\your\video.mp4 test_video.mp4
```

#### Bước 3: Chạy Mock ESP32 server
**Windows:**
```bash
cd server
stream_video_mock.bat
```

**Linux/Mac:**
```bash
cd server
chmod +x stream_video_mock.sh
./stream_video_mock.sh
```

Sẽ thấy:
```
========================================
 Mock ESP32-CAM Video Streaming
========================================
[OK] FFmpeg found
[OK] Video file: test_video.mp4

Starting mock ESP32-CAM stream on http://localhost:8081/stream
Press Ctrl+C to stop
```

#### Bước 4: Chạy FastAPI server (terminal mới)
```bash
conda activate smartparking
python main_fastapi.py
```

#### Bước 5: Truy cập frontend
```
http://localhost:5173/stream/view
```

#### Bước 6: Chọn chế độ "🎬 Mock FFmpeg"
- Click nút "Mock FFmpeg" trên giao diện
- Stream sẽ tự động load từ mock server

✅ **Ưu điểm:**
- Giống hệt ESP32-CAM (MJPEG over HTTP)
- Load CPU thấp (FFmpeg xử lý)
- Test chính xác như production

❌ **Nhược điểm:**
- Cần cài FFmpeg
- Phải chạy 2 servers (FFmpeg + FastAPI)

---

## 🎨 GIAO DIỆN FRONTEND

Frontend hiện có **4 nút chọn**:

```
┌─────────────────────────────────────────┐
│  🔄 ESP32 Proxy  │  ⚡ Direct ESP32     │
│  📹 Video File   │  🎬 Mock FFmpeg      │
└─────────────────────────────────────────┘
```

### **🔄 ESP32 Proxy** (Default)
- Stream từ ESP32-CAM thật qua FastAPI
- Dùng cho production
- Cần ESP32-CAM online

### **⚡ Direct ESP32**
- Stream trực tiếp từ ESP32-CAM (bypass FastAPI)
- Latency thấp nhất
- Không có AI processing

### **📹 Video File**
- Stream từ `test_video.mp4`
- Không cần ESP32-CAM
- Đơn giản nhất

### **🎬 Mock FFmpeg**
- Stream từ FFmpeg mock server
- Giống ESP32 nhất
- Tốt nhất cho testing

---

## 🧪 USE CASES

### **1. Development khi chưa có ESP32-CAM**
```
Dùng: 📹 Video File
- Đơn giản, nhanh
- Test AI detection
- Test UI/UX
```

### **2. Testing AI với video chất lượng cao**
```
Dùng: 🎬 Mock FFmpeg
- Video HD không bị giảm chất lượng
- Giống ESP32 nhất
- Test performance
```

### **3. Demo cho khách hàng/giáo viên**
```
Dùng: 🎬 Mock FFmpeg hoặc 📹 Video File
- Video chuẩn bị sẵn
- Không phụ thuộc ESP32
- Ổn định 100%
```

### **4. Production**
```
Dùng: 🔄 ESP32 Proxy
- ESP32-CAM thật
- AI processing real-time
- Lưu Firebase
```

---

## ⚙️ CONFIGURATION

### **Đổi video file path**
Sửa trong `server/main_fastapi.py`:
```python
TEST_VIDEO_PATH = Path(__file__).parent / "test_video.mp4"
# Hoặc đường dẫn tuyệt đối:
TEST_VIDEO_PATH = Path("D:/Videos/parking_test.mp4")
```

### **Đổi mock server port**
Sửa trong `server/stream_video_mock.bat`:
```bash
# Từ port 8081 → 9000
http://localhost:9000/stream
```

Và trong `server/main_fastapi.py`:
```python
MOCK_STREAM_URL = "http://localhost:9000/stream"
```

### **Đổi video resolution/quality**
Sửa trong `server/stream_video_mock.bat`:
```bash
# 640x480 → 1280x720
-vf "scale=1280:720"

# Quality: 5 (cao) → 10 (thấp hơn, nhẹ hơn)
-q:v 10
```

### **Đổi FPS**
FFmpeg tự động detect FPS từ video. Để force FPS:
```bash
ffmpeg -re -stream_loop -1 -i test_video.mp4 \
    -vf "scale=640:480,fps=30" \  # Force 30 FPS
    -f mjpeg -q:v 5 -listen 1 http://localhost:8081/stream
```

---

## 🐛 TROUBLESHOOTING

### **Lỗi: "Video file not found"**
```
[ERROR] Video file not found: test_video.mp4

Fix:
cd server
copy path\to\video.mp4 test_video.mp4
```

### **Lỗi: "FFmpeg not found"**
```
[ERROR] FFmpeg not found!

Fix:
# Windows
choco install ffmpeg
# hoặc tải từ https://ffmpeg.org/download.html

# Linux
sudo apt install ffmpeg

# Mac
brew install ffmpeg
```

### **Lỗi: "Mock stream unavailable"**
```
Fix:
1. Kiểm tra FFmpeg mock đang chạy: http://localhost:8081/stream
2. Chạy script: server/stream_video_mock.bat
3. Đợi 2-3 giây cho stream khởi động
```

### **Stream bị giật/lag**
```
Option 1: Giảm resolution
-vf "scale=320:240"

Option 2: Giảm quality
-q:v 10  # Cao hơn = quality thấp hơn, nhẹ hơn

Option 3: Tăng frame skip
-vf "fps=15"  # 15 FPS thay vì 30
```

---

## 📊 SO SÁNH PERFORMANCE

| Chế độ | CPU Usage | RAM | Latency | Giống ESP32 |
|--------|-----------|-----|---------|-------------|
| ESP32 Proxy | Thấp | 50MB | 100-200ms | 100% ✅ |
| Direct ESP32 | Rất thấp | 10MB | 50-100ms | 100% ✅ |
| Video File | Cao ⚠️ | 200MB | 0ms | 70% |
| Mock FFmpeg | Trung bình | 100MB | 50ms | 95% ✅ |

**Khuyên dùng:** 🎬 **Mock FFmpeg** cho testing, giống ESP32 nhất!

---

## 🎓 KẾT LUẬN

- ✅ **Development:** Dùng 📹 Video File (đơn giản)
- ✅ **Testing AI:** Dùng 🎬 Mock FFmpeg (chính xác)
- ✅ **Demo:** Dùng 🎬 Mock FFmpeg (ổn định)
- ✅ **Production:** Dùng 🔄 ESP32 Proxy (thật)

---

## 📝 QUICK START

**Testing nhanh nhất (không cần FFmpeg):**
```bash
# Terminal 1
cd server
# Copy video vào folder
python main_fastapi.py

# Terminal 2
cd frontend
npm run dev

# Browser: http://localhost:5173/stream/view
# Click: 📹 Video File
```

**Testing tốt nhất (cần FFmpeg):**
```bash
# Terminal 1
cd server
stream_video_mock.bat

# Terminal 2
cd server
conda activate smartparking
python main_fastapi.py

# Terminal 3
cd frontend
npm run dev

# Browser: http://localhost:5173/stream/view
# Click: 🎬 Mock FFmpeg
```

✅ Done! Bây giờ bạn có thể test mà không cần ESP32-CAM thật! 🎉

