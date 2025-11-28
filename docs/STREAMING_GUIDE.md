# 📹 Hướng Dẫn Streaming Video - WebRTC

## Tổng Quan

Hệ thống streaming sử dụng **WebRTC** để phát video trực tiếp từ:
- **Camera** (webcam/device camera)
- **Video File** (upload và phát lặp lại liên tục)

## Kiến Trúc

### 1. Signaling Server (`server/signaling.js`)
- **Chức năng**: Điều phối kết nối WebRTC giữa Host và Viewer
- **Cổng**: `3001` (WebSocket)
- **Room-based**: Mỗi stream có Room ID = `{parkingLotId}__{cameraId}`

### 2. Stream Host Page (`/stream/host`)
- **Quyền**: Chỉ Admin
- **Chức năng**: 
  - Chọn nguồn stream (Camera hoặc Video File)
  - Chọn Parking Lot ID và Camera ID
  - Phát video trực tiếp

### 3. Stream Viewer Page (`/stream/view`)
- **Quyền**: Tất cả người dùng
- **Chức năng**: 
  - Chọn Parking Lot ID và Camera ID
  - Xem stream từ Host tương ứng

## Logic Chi Tiết

### A. Stream từ Camera

```typescript
// 1. Lấy stream từ device camera
const stream = await navigator.mediaDevices.getUserMedia({
  video: { width: 1280, height: 720 },
  audio: true,
});

// 2. Tạo RTCPeerConnection
const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

// 3. Thêm tracks vào PeerConnection
stream.getTracks().forEach((track) => {
  pc.addTrack(track, stream);
});

// 4. Kết nối WebSocket và tạo offer
socket.send(JSON.stringify({ type: 'join', role: 'host', roomId }));
const offer = await pc.createOffer();
await pc.setLocalDescription(offer);
socket.send(JSON.stringify({ type: 'offer', offer }));
```

### B. Stream từ Video File

#### Bước 1: Load Video File
```typescript
// User chọn file → tạo Object URL
const file = event.target.files?.[0];
const url = URL.createObjectURL(file);
sourceVideoRef.current.src = url;
```

#### Bước 2: Tạo MediaStream từ Video

**Cách 1: Sử dụng `captureStream()` (Chrome, Edge)**
```typescript
// Video element có method captureStream()
const stream = video.captureStream();

// Xử lý loop
video.onended = () => {
  video.currentTime = 0;
  video.play();
};
```

**Cách 2: Fallback - Canvas (Firefox, Safari)**
```typescript
// Tạo canvas và capture stream từ canvas
const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d');
const stream = canvas.captureStream(30); // 30 FPS

// Vẽ video lên canvas liên tục
const drawFrame = () => {
  if (video.ended || video.paused) {
    video.currentTime = 0; // Loop
    video.play();
  }
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  requestAnimationFrame(drawFrame);
};

video.play().then(() => {
  drawFrame();
});
```

#### Bước 3: Stream qua WebRTC
```typescript
// Tương tự như camera stream
stream.getTracks().forEach((track) => {
  pc.addTrack(track, stream);
});
```

### C. WebRTC Signaling Flow

```
Host                          Signaling Server                    Viewer
  |                                 |                                |
  |-- join (host, roomId) -------->|                                |
  |                                 |                                |
  |-- offer ---------------------->|                                |
  |                                 |-- join (viewer, roomId) ------>|
  |                                 |<-- offer ----------------------|
  |                                 |                                |
  |<-- answer ---------------------|-- answer --------------------->|
  |                                 |                                |
  |<-- ice candidate --------------|-- ice candidate -------------->|
  |                                 |                                |
```

## Validation

### Parking Lot ID & Camera ID
- **Format**: Chỉ chữ cái tiếng Anh và số (A-Z, a-z, 0-9)
- **Regex**: `/^[A-Za-z0-9]+$/`
- **Không được**: Dấu, khoảng trắng, ký tự đặc biệt

### Room ID
- **Format**: `{parkingLotId}__{cameraId}`
- **Ví dụ**: `PARKING01__CAM01`
- **Mục đích**: Phân biệt các stream khác nhau

## Cách Sử Dụng

### 1. Khởi động Signaling Server
```bash
cd server
npm start
```
→ Server sẽ chạy tại `ws://localhost:3001`

### 2. Stream từ Camera

**Bước 1**: Mở `/stream/host` (đăng nhập Admin)

**Bước 2**: 
- Chọn "📷 Camera"
- Nhập/chọn Parking Lot ID
- Nhập/chọn Camera ID
- Click "Bắt đầu phát"

**Bước 3**: Cho phép browser truy cập camera

### 3. Stream từ Video File

**Bước 1**: Mở `/stream/host` (đăng nhập Admin)

**Bước 2**:
- Chọn "🎬 Video File"
- Nhập/chọn Parking Lot ID
- Nhập/chọn Camera ID
- Chọn video file (MP4, WebM, etc.)
- Click "Bắt đầu phát"

**Lưu ý**: Video sẽ tự động loop khi hết

### 4. Xem Stream

**Bước 1**: Mở `/stream/view` (không cần đăng nhập)

**Bước 2**:
- Nhập/chọn Parking Lot ID (giống Host)
- Nhập/chọn Camera ID (giống Host)
- Click "Kết nối"

**Bước 3**: Video sẽ hiển thị trong player

## Xử Lý Lỗi

### 1. "Lỗi kết nối signaling server"
- **Nguyên nhân**: Signaling server chưa chạy
- **Giải pháp**: Chạy `npm start` trong folder `server`

### 2. "Không thể truy cập camera"
- **Nguyên nhân**: Browser chưa được cấp quyền
- **Giải pháp**: Cho phép truy cập camera trong browser settings

### 3. "Vui lòng chọn video file"
- **Nguyên nhân**: Chưa chọn file hoặc file không hợp lệ
- **Giải pháp**: Chọn file video (MP4, WebM, etc.)

### 4. "Mất kết nối với viewer/host"
- **Nguyên nhân**: Network issue hoặc host/viewer đã disconnect
- **Giải pháp**: Kiểm tra network, đảm bảo cả 2 đều online

## Browser Compatibility

### `captureStream()` Support
- ✅ Chrome 51+
- ✅ Edge 79+
- ❌ Firefox (dùng Canvas fallback)
- ❌ Safari (dùng Canvas fallback)

### WebRTC Support
- ✅ Tất cả browser hiện đại

## Tối Ưu Hóa

### 1. Video Quality
- **Camera**: 1280x720 (có thể điều chỉnh)
- **Video File**: Giữ nguyên resolution gốc

### 2. Frame Rate
- **Canvas fallback**: 30 FPS (có thể tăng lên 60)

### 3. Bandwidth
- WebRTC tự động điều chỉnh quality dựa trên bandwidth
- Có thể thêm TURN server cho NAT traversal tốt hơn

## Mở Rộng

### 1. Nhiều Viewer
- Hiện tại: 1 Host → Nhiều Viewer (broadcast)
- Signaling server đã hỗ trợ multiple viewers

### 2. Recording
- Có thể thêm `MediaRecorder` để ghi lại stream

### 3. Authentication
- Có thể thêm token-based authentication cho rooms

### 4. TURN Server
- Thêm TURN server cho NAT traversal tốt hơn:
```typescript
const ICE_SERVERS = [
  { urls: 'stun:stun.l.google.com:19302' },
  { 
    urls: 'turn:your-turn-server.com:3478',
    username: 'user',
    credential: 'pass'
  }
];
```

## Troubleshooting

### Video không loop
- Kiểm tra `video.loop = true`
- Kiểm tra `video.onended` handler

### Canvas không vẽ được
- Đảm bảo `video.readyState >= 2` (có metadata)
- Kiểm tra `canvas.width` và `canvas.height`

### Stream bị giật
- Giảm frame rate (30 → 24 FPS)
- Giảm video resolution
- Kiểm tra network bandwidth

