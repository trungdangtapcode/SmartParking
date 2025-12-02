"""
Demo Script: Test Model Tracking trong SmartParking
Script demo để test model tracking đã tích hợp
"""

import os
import sys
from pathlib import Path

# Thêm thư mục hiện tại vào path để import
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ultralytics import YOLO
    import cv2
except ImportError:
    print("❌ Cần cài đặt: pip install ultralytics opencv-python")
    print("💡 Chạy: cd server && venv\\Scripts\\activate && pip install -r requirements.txt")
    sys.exit(1)

# Đường dẫn model trong SmartParking
MODEL_PATH = Path(__file__).parent / "yolov8s_car_custom.pt"

def print_header(text):
    """In header đẹp"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def check_model():
    """Kiểm tra model có tồn tại không"""
    if not MODEL_PATH.exists():
        print(f"❌ Model không tồn tại: {MODEL_PATH}")
        print(f"💡 Hãy copy model vào: {MODEL_PATH}")
        return None
    
    size_mb = MODEL_PATH.stat().st_size / (1024 * 1024)
    print(f"✅ Model found: {MODEL_PATH}")
    print(f"📦 Size: {size_mb:.2f} MB")
    return MODEL_PATH


def demo_model_info():
    """Demo 1: Hiển thị thông tin model"""
    print_header("📊 THÔNG TIN MODEL / MODEL INFORMATION")
    
    model_path = check_model()
    if not model_path:
        return None
    
    try:
        model = YOLO(str(model_path))
        print(f"✅ Model loaded successfully!")
        print(f"📁 Path: {model_path}")
        print(f"📦 Classes: {len(model.names)}")
        print(f"🏷️  Class names: {model.names}")
        
        # Model info
        total_params = sum(p.numel() for p in model.model.parameters())
        print(f"🔢 Total parameters: {total_params:,}")
        
        return model
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return None


def demo_detection_image(model, image_path=None):
    """Demo 2: Detection trên ảnh"""
    print_header("🔍 DETECTION TRÊN ẢNH / IMAGE DETECTION")
    
    if not image_path:
        print("⚠️  Chưa có ảnh để test")
        print("💡 Sử dụng: demo_detection_image(model, 'path/to/image.jpg')")
        return
    
    if not os.path.exists(image_path):
        print(f"❌ File không tồn tại: {image_path}")
        return
    
    print(f"📸 Processing image: {image_path}")
    
    try:
        results = model.predict(
            source=image_path,
            conf=0.3,
            imgsz=1024,
            save=True,
            verbose=False
        )
        
        result = results[0]
        if result.boxes is not None and len(result.boxes) > 0:
            print(f"✅ Detected {len(result.boxes)} cars!")
            for i, box in enumerate(result.boxes):
                conf = float(box.conf[0])
                print(f"   Car {i+1}: Confidence = {conf:.2%}")
            print(f"💾 Result saved to: runs/detect/predict/")
        else:
            print("⚠️  No cars detected (try lowering conf threshold to 0.2)")
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_tracking_video(model, video_path=None):
    """Demo 3: Tracking trên video"""
    print_header("🎯 TRACKING TRÊN VIDEO / VIDEO TRACKING")
    
    if not video_path:
        print("⚠️  Chưa có video để test")
        print("💡 Sử dụng: demo_tracking_video(model, 'path/to/video.mp4')")
        return
    
    if not os.path.exists(video_path):
        print(f"❌ File không tồn tại: {video_path}")
        return
    
    print(f"🎬 Processing video: {video_path}")
    
    try:
        # Get video info
        cap = cv2.VideoCapture(video_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        print(f"📹 Video info: {width}x{height}, {total_frames} frames @ {fps} fps")
        print("⏳ This may take a while...")
        
        # Tracking
        results = model.track(
            source=video_path,
            conf=0.3,
            iou=0.5,
            imgsz=1280,
            tracker="bytetrack.yaml",
            save=True,
            verbose=True
        )
        
        print(f"\n✅ Tracking completed!")
        print(f"💾 Result saved to: runs/track/")
        
        # Count unique tracks
        unique_tracks = set()
        for result in results:
            if result.boxes is not None and result.boxes.id is not None:
                track_ids = result.boxes.id.int().cpu().tolist()
                unique_tracks.update(track_ids)
        
        print(f"🎯 Found {len(unique_tracks)} unique tracks")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def demo_api_test():
    """Demo 4: Test API endpoint"""
    print_header("🌐 TEST API ENDPOINT / TEST API")
    
    print("💡 Để test API, bạn cần:")
    print("   1. Start server: cd server && node signaling.js")
    print("   2. Gửi POST request đến: http://localhost:3001/api/object-tracking")
    print("   3. Hoặc sử dụng frontend: http://localhost:5173/tracking")
    print("\n📝 Example request body:")
    print("""
{
  "videoData": "data:video/mp4;base64,...",
  "frameSkip": 1,
  "confThreshold": 0.3,
  "iouThreshold": 0.5,
  "useSAM3": false
}
    """)


def main():
    """Main function"""
    print("\n" + "🚀 " * 20)
    print("SmartParking - YOLOv8 + ByteTrack Model Demo")
    print("🚀 " * 20)
    
    # Load model
    model = demo_model_info()
    if model is None:
        print("\n❌ Cannot proceed without model")
        print("💡 Make sure model is at: server/yolov8s_car_custom.pt")
        return
    
    # Menu
    print_header("📋 MENU / MENU")
    print("1. Test Detection trên ảnh")
    print("2. Test Tracking trên video (lưu file)")
    print("3. Test API endpoint info")
    print("4. Tất cả (nếu có file test)")
    print("0. Thoát")
    
    choice = input("\n👉 Chọn option (0-4): ").strip()
    
    if choice == "1":
        image_path = input("📸 Nhập đường dẫn ảnh (hoặc Enter để skip): ").strip()
        if image_path:
            demo_detection_image(model, image_path)
    
    elif choice == "2":
        video_path = input("🎬 Nhập đường dẫn video (hoặc Enter để skip): ").strip()
        if video_path:
            demo_tracking_video(model, video_path)
    
    elif choice == "3":
        demo_api_test()
    
    elif choice == "4":
        image_path = input("📸 Đường dẫn ảnh (Enter để skip): ").strip()
        video_path = input("🎬 Đường dẫn video (Enter để skip): ").strip()
        
        if image_path:
            demo_detection_image(model, image_path)
        if video_path:
            demo_tracking_video(model, video_path)
        demo_api_test()
    
    elif choice == "0":
        print("👋 Goodbye!")
        return
    
    else:
        print("❌ Invalid choice")
    
    print("\n" + "=" * 60)
    print("✅ Demo completed!")
    print("=" * 60)
    print("\n💡 Next steps:")
    print("   - Xem hướng dẫn: docs/HUONG_DAN_MODEL_TRACKING.md")
    print("   - Test API: Start server và truy cập /tracking")
    print("   - Model location: server/yolov8s_car_custom.pt")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

