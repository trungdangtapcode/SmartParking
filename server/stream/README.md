# 🎬 Video Streaming Directory

Thư mục này chứa các video files để test **Multi-Camera Viewer**.

## 📁 Cấu Trúc

```
server/stream/
├── README.md          # File này
├── parking_a.mp4      # Video test 1 (cần thêm)
├── parking_b.mp4      # Video test 2 (cần thêm)
└── parking_c.mp4      # Video test 3 (cần thêm)
```

## 🚀 Cách Sử Dụng

### 1. Thêm Video Files

Đặt video files (.mp4, .avi, .mov) vào thư mục này.

**Ví dụ:**
```bash
# Copy video vào thư mục stream/
copy C:\path\to\your\video.mp4 server\stream\parking_a.mp4
copy C:\path\to\another.mp4 server\stream\parking_b.mp4
```

### 2. Cấu Hình Frontend

Mở file `frontend/src/pages/MultiStreamViewerPage.tsx` và sửa:

```typescript
const VIDEO_FILES = [
  { id: 'video_1', name: 'Video 1 - Parking A', filename: 'parking_a.mp4' },
  { id: 'video_2', name: 'Video 2 - Parking B', filename: 'parking_b.mp4' },
  { id: 'video_3', name: 'Video 3 - Parking C', filename: 'parking_c.mp4' },
];
```

**Lưu ý:** `filename` phải khớp với tên file trong thư mục `stream/`.

### 3. Cấu Hình FastAPI Backend

Đảm bảo `main_fastapi.py` có endpoint hỗ trợ video streaming:

```python
@app.get("/stream")
async def stream_video(
    mode: str = "esp32",  # 'esp32', 'video_file', 'mock'
    file: str = "test_video.mp4"
):
    if mode == "video_file":
        video_path = f"stream/{file}"
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail=f"Video file not found: {file}")
        
        # Stream video as MJPEG
        return StreamingResponse(
            generate_video_stream(video_path),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )
    # ... other modes
```

### 4. Chạy Ứng Dụng

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

---

## 📝 Video File Requirements

### Định Dạng Được Hỗ Trợ
- ✅ `.mp4` (H.264/H.265)
- ✅ `.avi`
- ✅ `.mov`
- ✅ `.mkv`

### Khuyến Nghị
- **Resolution:** 1280x720 hoặc 1920x1080
- **FPS:** 25-30 fps
- **Codec:** H.264 (tương thích tốt nhất)
- **Size:** < 100MB (để stream nhanh)

### Convert Video (Optional)

Nếu video của bạn không tương thích, dùng FFmpeg để convert:

```bash
# Convert sang MP4 H.264 720p 30fps
ffmpeg -i input.avi -vf "scale=1280:720" -r 30 -c:v libx264 -preset fast -crf 23 output.mp4

# Giảm kích thước file
ffmpeg -i input.mp4 -vf "scale=640:480" -r 15 -c:v libx264 -crf 28 output_small.mp4
```

---

## 🧪 Testing

### Test từng video file:

**Option 1: Dùng Multi-Camera Viewer**
1. Mở `http://localhost:5173/stream/multi`
2. Chọn "Video File"
3. Chọn video muốn test
4. Click "Thêm Stream"

**Option 2: Direct API Test**
```bash
# Test endpoint
curl http://localhost:8000/stream?mode=video_file&file=parking_a.mp4

# Xem trong browser
http://localhost:8000/stream?mode=video_file&file=parking_a.mp4
```

---

## ⚠️ Lưu Ý

1. **Đường Dẫn File:**
   - FastAPI sẽ tìm file ở `server/stream/{filename}`
   - Đảm bảo `main_fastapi.py` chạy từ thư mục `server/`

2. **Performance:**
   - Video lớn (> 100MB) có thể stream chậm
   - Nên resize video về 720p hoặc 480p cho testing

3. **.gitignore:**
   - Video files **KHÔNG** được commit lên Git
   - File `.gitignore` đã được config để ignore `*.mp4`, `*.avi`, `*.mov`

4. **Streaming Mode:**
   - Endpoint sẽ stream video dưới dạng **MJPEG** (Motion JPEG)
   - Frontend dùng `<img>` tag để nhận stream

---

## 📊 Example Videos

Nếu chưa có video test, download từ:

1. **Pexels (Free):** https://www.pexels.com/search/videos/parking/
2. **Pixabay (Free):** https://pixabay.com/videos/search/parking%20lot/
3. **YouTube:** Download video parking lot và convert sang MP4

**Quick Download:**
```bash
# Example: Download từ Pexels (cần curl)
curl -L "https://www.pexels.com/download/video/[ID]" -o parking_a.mp4
```

---

## 🐛 Troubleshooting

### Video không stream được

**Lỗi:** `404 Not Found`
- Kiểm tra tên file có đúng không
- Kiểm tra file có tồn tại trong `server/stream/`

**Lỗi:** `500 Internal Server Error`
- Video format không được hỗ trợ → Convert sang MP4 H.264
- File bị lỗi → Test video bằng VLC player

**Stream bị lag/chậm:**
- Video quá lớn → Resize về 720p hoặc 480p
- FPS quá cao → Giảm xuống 15-20 fps

---

## 📚 Related Files

- `frontend/src/pages/MultiStreamViewerPage.tsx` - Multi-camera UI
- `server/main_fastapi.py` - FastAPI streaming endpoint
- `server/stream_video_mock.bat` - FFmpeg mock script (alternative)
- `server/VIDEO_STREAMING_TESTING.md` - Full testing guide

---

**Happy Streaming! 🎬🚀**

