# Smart Parking System 🚗

Hệ thống quản lý bãi đỗ xe thông minh sử dụng AI/Computer Vision.

## 📁 Cấu Trúc Project

- `frontend/` - React + TypeScript + Vite application
- `docs/` - Tài liệu và hướng dẫn
- `scripts/` - Scripts và commands

## 🚀 Quick Start

### Frontend
cd frontend
npm install
npm run dev

### Server (FastAPI)
cd server
pip install -r requirements_fastapi.txt
uvicorn main_fastapi:app --host 0.0.0.0 --port 8000 --reload

> Lưu ý: Signaling server bằng Node.js đã gỡ bỏ. Muốn dùng WebRTC Host/Viewer cần triển khai signaling mới (có thể tích hợp vào FastAPI). Hiện tại chỉ còn các API AI/streaming của FastAPI trên port 8000.


## 🎯 Object Tracking

Hệ thống đã tích hợp model YOLOv8 + ByteTrack cho object tracking với hiệu suất cao (mAP50 = 99.49%).

### Quick Start Tracking

```bash
# 1. Kiểm tra model
cd server
dir yolov8s_car_custom.pt

# 2. Test model
python demo_tracking.py

# 3. Start server
node signaling.js

# 4. Truy cập frontend
# http://localhost:5173/tracking
```

### Tài Liệu Tracking

- `docs/TRACKING_QUICK_START.md` - Hướng dẫn nhanh
- `docs/TICH_HOP_MODEL_TRACKING.md` - Hướng dẫn tích hợp
- `docs/HUONG_DAN_MODEL_TRACKING.md` - Hướng dẫn chi tiết

## 📚 Tài Liệu

Xem thêm trong folder `docs/`:
- `step_by_step.md` - Hướng dẫn từng bước
- `pipeline_tong_quat.md` - Pipeline tổng quát
- `TRACKING_QUICK_START.md` - Quick start cho Object Tracking