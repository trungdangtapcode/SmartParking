---
name: Real-time Multi-threaded YOLO Streaming
overview: Refactor backend để đạt real-time performance trên CPU bằng Producer-Consumer multi-threading, tách frame reading khỏi AI inference để giảm latency.
todos:
  - id: create_camera_stream
    content: Tạo server/tracking_app/camera_stream.py với CameraStream class - producer thread đọc frames liên tục, chỉ giữ frame mới nhất
    status: pending
  - id: create_inference_processor
    content: Tạo server/tracking_app/inference_processor.py với InferenceProcessor class - consumer thread xử lý YOLO + ByteTrack, skip frames nếu busy
    status: pending
  - id: implement_model_loading
    content: Implement model loading trong app.py với OpenVINO support (fallback về .pt), cấu hình imgsz=320/416
    status: pending
  - id: create_flask_streaming
    content: Tạo server/tracking_app/app.py với Flask app, route /stream/<camera_id> và generate_frames() function cho MJPEG streaming
    status: pending
  - id: add_thread_management
    content: Thêm startup/shutdown logic trong app.py để quản lý threads cho 2 cameras, cleanup khi app stop
    status: pending
  - id: add_annotations
    content: Implement frame annotation trong inference_processor.py với bounding boxes, track IDs, và confidence scores từ YOLO results
    status: pending
---

# Real-time Multi-threaded YOLO Streaming Architecture

## Overview

Tạo Flask app trong `server/tracking_app/` với kiến trúc Producer-Consumer để xử lý 2 camera streams real-time với YOLOv8 + ByteTrack trên CPU. Frame reading và AI inference chạy trên các thread riêng để tránh blocking.

## Architecture Components

### 1. CameraStream Class (Producer Thread)

**File**: `server/tracking_app/camera_stream.py` (class `CameraStream`)

- Chạy trong thread riêng, đọc frames liên tục từ `cv2.VideoCapture`
- Chỉ lưu frame mới nhất (drop older frames nếu chưa xử lý)
- Thread-safe với `threading.Lock` để bảo vệ shared frame buffer
- Hỗ trợ cả USB camera (index) và video files (path)
- Method `get_latest_frame()` để consumer lấy frame mới nhất

**Key Implementation**:

```python
class CameraStream:
    def __init__(self, source, camera_id):
        self.source = source  # 0, 1 (USB) hoặc "path/to/video.mp4"
        self.camera_id = camera_id
        self.cap = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.running = False
        self.thread = None
    
    def start(self):
        # Start producer thread
        self.running = True
        self.thread = threading.Thread(target=self._read_frames, daemon=True)
        self.thread.start()
    
    def _read_frames(self):
        # Continuously read, only keep latest
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.frame_lock:
                    self.latest_frame = frame.copy()
```

### 2. Inference Thread (Consumer)

**File**: `server/tracking_app/inference_processor.py` (class `InferenceProcessor`)

- Thread riêng xử lý YOLO detection + ByteTrack
- Lấy frame mới nhất từ `CameraStream` khi sẵn sàng
- Nếu AI đang busy, skip frame cũ và lấy frame mới nhất
- Lưu annotated frame vào buffer để streaming
- Sử dụng `persist=True` để ByteTrack duy trì ID tracking qua các frames

**Key Implementation**:

```python
class InferenceProcessor:
    def __init__(self, camera_stream, yolo_model):
        self.camera_stream = camera_stream
        self.model = yolo_model
        self.latest_annotated = None
        self.annotated_lock = threading.Lock()
        self.running = False
        self.thread = None
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()
    
    def _process_loop(self):
        while self.running:
            frame = self.camera_stream.get_latest_frame()
            if frame is not None:
                # YOLO + ByteTrack
                results = self.model.track(
                    frame,
                    persist=True,  # Maintains tracking IDs across frames
                    tracker="bytetrack.yaml",
                    imgsz=320,  # or 416 for CPU optimization
                    verbose=False
                )
                # Annotate and store
                annotated = self._annotate_frame(frame, results)
                with self.annotated_lock:
                    self.latest_annotated = annotated
```

### 3. Model Loading với OpenVINO Support

**File**: `server/tracking_app/app.py` (function `load_yolo_model`)

- Ưu tiên load OpenVINO format (directory path) nếu có
- Fallback về `.pt` nếu chưa export
- Cấu hình `imgsz=320` hoặc `416` để tối ưu CPU

**Implementation**:

```python
def load_yolo_model(model_path_or_dir):
    from ultralytics import YOLO
    
    # Check if OpenVINO directory exists
    if os.path.isdir(model_path_or_dir):
        # OpenVINO format: directory with .xml and .bin
        model = YOLO(model_path_or_dir)
    else:
        # Standard .pt format
        model = YOLO(model_path_or_dir)
    
    return model
```

### 4. Flask MJPEG Streaming

**File**: `server/tracking_app/app.py` (route `/stream/<camera_id>`)

- Generator function `generate_frames(camera_id)` yield MJPEG bytes
- Luôn stream annotated frame mới nhất (hoặc frame gốc nếu chưa có annotated)
- Không block nếu AI chậm - hiển thị frame cuối cùng đã xử lý

**Implementation**:

```python
@app.route('/stream/<int:camera_id>')
def stream_camera(camera_id):
    def generate_frames():
        processor = inference_processors.get(camera_id)
        while True:
            frame = None
            if processor:
                frame = processor.get_latest_annotated()
            if frame is None:
                # Fallback to raw frame
                stream = camera_streams.get(camera_id)
                if stream:
                    frame = stream.get_latest_frame()
            
            if frame is not None:
                ret, buffer = cv2.imencode('.jpg', frame, 
                    [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + 
                           buffer.tobytes() + b'\r\n')
            time.sleep(0.033)  # ~30 FPS
    
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')
```

## File Structure

```
server/
└── tracking_app/
    ├── app.py                # Main Flask app với threading architecture
    ├── camera_stream.py      # CameraStream class (Producer thread)
    ├── inference_processor.py # InferenceProcessor class (Consumer thread)
    ├── __init__.py           # Package init
    └── requirements.txt      # Dependencies (Flask, ultralytics, opencv-python)
```

## Key Design Decisions

1. **Latest Frame Only**: Producer chỉ giữ frame mới nhất để tránh memory buildup và đảm bảo real-time
2. **Non-blocking Inference**: Nếu AI busy, skip frame cũ và lấy frame mới nhất ngay khi sẵn sàng
3. **persist=True**: ByteTrack duy trì tracking IDs qua các frames trong cùng thread, đảm bảo consistency
4. **Thread Safety**: Sử dụng `threading.Lock` cho tất cả shared state
5. **OpenVINO Ready**: Code hỗ trợ OpenVINO nhưng fallback về .pt nếu chưa export

## Integration với FastAPI

Sau khi có Flask version, có thể adapt sang FastAPI:

- Thay `@app.route` → `@app.get` với `StreamingResponse`
- Thay `threading` → `asyncio` + `asyncio.to_thread()` nếu muốn async
- Giữ nguyên Producer-Consumer pattern

## Testing

- Test với 2 video files trước (dễ debug)
- Sau đó test với USB cameras hoặc IP cameras
- Monitor FPS và latency để đảm bảo real-time performance