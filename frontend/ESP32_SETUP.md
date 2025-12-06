# 📹 ESP32-CAM SETUP GUIDE

## ✅ **ĐÃ SỬA LỖI**

Tôi đã sửa lại code để hỗ trợ **ESP32-CAM HTTP MJPEG stream** thay vì WebRTC!

### **Thay đổi:**
- ❌ **Cũ:** WebRTC với signaling server (phức tạp)
- ✅ **Mới:** HTTP MJPEG stream (đơn giản, trực tiếp)

---

## 🚀 **CÁCH SỬ DỤNG**

### **Bước 1: Đảm bảo ESP32-CAM đang chạy**

```bash
# Test từ browser:
http://192.168.1.158:81/stream

# Bạn phải thấy video stream
```

### **Bước 2: Chạy FastAPI server (Optional - để proxy)**

```bash
# Terminal 1: Backend
cd server
conda activate smartparking
python main_fastapi.py

# Server sẽ chạy tại: http://localhost:8000
```

### **Bước 3: Chạy Frontend**

```bash
# Terminal 2: Frontend
cd frontend
npm run dev

# Frontend tại: http://localhost:5173
```

### **Bước 4: Xem stream**

1. Mở browser: `http://localhost:5173`
2. Vào trang **"Stream View"** (từ sidebar)
3. Chọn nguồn stream:
   - **🔄 Qua FastAPI Proxy** - Nếu muốn xử lý thêm (AI detection...)
   - **⚡ Trực tiếp từ ESP32** - Nhanh nhất, không qua server

---

## 🎯 **2 OPTIONS: PROXY vs DIRECT**

### **Option 1: FastAPI Proxy (Khuyến nghị)**

```
Frontend → http://localhost:8000/stream → ESP32 (192.168.1.158:81/stream)
```

**Ưu điểm:**
- ✅ Có thể thêm AI processing (plate detection, object tracking)
- ✅ Có thể record/save frames
- ✅ CORS friendly

**Nhược điểm:**
- ⚠️ Cần chạy FastAPI server
- ⚠️ Một chút latency

---

### **Option 2: Direct từ ESP32**

```
Frontend → http://192.168.1.158:81/stream (trực tiếp)
```

**Ưu điểm:**
- ✅ Không cần FastAPI server
- ✅ Latency thấp nhất

**Nhược điểm:**
- ⚠️ CORS issues (có thể bị block)
- ⚠️ Không có AI processing

---

## 🔧 **TROUBLESHOOTING**

### **Lỗi: Không thấy stream**

**Check 1: ESP32 có online không?**
```bash
ping 192.168.1.158
```

**Check 2: Test stream trực tiếp**
```bash
# Mở browser:
http://192.168.1.158:81/stream

# Phải thấy video!
```

**Check 3: FastAPI server đang chạy?**
```bash
# Test health:
curl http://localhost:8000/health

# Test ESP32 connection:
curl http://localhost:8000/test/esp32
```

**Check 4: Cùng mạng WiFi?**
- ESP32 và máy dev phải cùng mạng
- Kiểm tra IP: `ipconfig` (Windows) hoặc `ifconfig` (Mac/Linux)

---

### **Lỗi: CORS blocked (nếu dùng Direct)**

**Giải pháp:** Dùng FastAPI proxy thay vì direct.

Hoặc thêm CORS vào ESP32 code:
```cpp
// ESP32 Arduino code
server.sendHeader("Access-Control-Allow-Origin", "*");
```

---

### **Lỗi: Stream lag/chậm**

**Giải pháp:**
1. Giảm FPS trên ESP32 (từ 30fps → 15fps)
2. Giảm resolution (từ SVGA → VGA)
3. Tăng JPEG quality setting

---

## 📊 **SO SÁNH VỚI WEBRTC**

| Feature | WebRTC (Cũ) | ESP32 HTTP (Mới) |
|---------|-------------|------------------|
| **Complexity** | ⚠️ High | ✅ Low |
| **Latency** | ✅ Very low | ✅ Low |
| **Setup** | ⚠️ Hard | ✅ Easy |
| **Code lines** | ~400 | ~150 |
| **Dependencies** | signaling server | None |
| **Works with ESP32?** | ❌ No | ✅ Yes |

---

## 💡 **NEXT STEPS**

### **1. Thêm AI Detection từ stream**

Capture frame từ stream và gửi đến FastAPI:

```typescript
// Trong StreamViewerPageESP32.tsx
const captureFrame = async () => {
  const img = document.querySelector('img') as HTMLImageElement;
  
  // Convert img to base64
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d');
  ctx?.drawImage(img, 0, 0);
  const base64 = canvas.toDataURL('image/jpeg');
  
  // Send to FastAPI
  const response = await fetch('http://localhost:8000/api/plate-detect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ imageData: base64 })
  });
  
  const result = await response.json();
  console.log('Detected plates:', result.plates);
};
```

### **2. Record video**

FastAPI có thể record stream:

```python
# server/main_fastapi.py
@app.post("/api/record-start")
async def start_recording():
    # Start recording stream from ESP32
    pass
```

### **3. Multiple cameras**

Hỗ trợ nhiều ESP32-CAM:

```typescript
const cameras = [
  { id: 'cam1', url: 'http://192.168.1.158:81/stream' },
  { id: 'cam2', url: 'http://192.168.1.159:81/stream' },
  { id: 'cam3', url: 'http://192.168.1.160:81/stream' },
];
```

---

## 📖 **RESOURCES**

- **ESP32-CAM Tutorial:** https://randomnerdtutorials.com/esp32-cam-video-streaming-web-server-camera-home-assistant/
- **MJPEG Stream:** https://en.wikipedia.org/wiki/Motion_JPEG
- **FastAPI Docs:** https://fastapi.tiangolo.com/

---

## ✅ **SUMMARY**

**Đã hoàn thành:**
- ✅ Tạo `StreamViewerPageESP32.tsx` - Simple HTTP stream viewer
- ✅ Update routing trong `App.tsx`
- ✅ Support cả proxy và direct stream
- ✅ Error handling và troubleshooting UI

**Để test:**
1. Chạy FastAPI: `python main_fastapi.py`
2. Chạy Frontend: `npm run dev`
3. Vào trang "Stream View"
4. Thấy video từ ESP32! 🎉

---

**Good luck!** 🚀

