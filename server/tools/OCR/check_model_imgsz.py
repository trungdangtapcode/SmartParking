"""
Script kiểm tra model YOLO được train với imgsz nào.
"""

import sys
from pathlib import Path

# Thêm server/ vào sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from ultralytics import YOLO
except ImportError:
    print("❌ Cần cài đặt: pip install ultralytics")
    sys.exit(1)


def check_model_imgsz(model_path: str):
    """Kiểm tra imgsz được train trong model."""
    print(f"\n🔍 Kiểm tra model: {model_path}\n")
    
    try:
        model = YOLO(model_path)
        print(f"✅ Model loaded successfully\n")
        
        trained_imgsz = None
        info_sources = []
        
        # Cách 1: Kiểm tra trong model.overrides
        if hasattr(model, 'overrides') and model.overrides:
            trained_imgsz = model.overrides.get('imgsz', None)
            if trained_imgsz:
                info_sources.append(f"model.overrides['imgsz'] = {trained_imgsz}")
        
        # Cách 2: Kiểm tra trong model.args
        if trained_imgsz is None and hasattr(model, 'args') and model.args:
            trained_imgsz = getattr(model.args, 'imgsz', None)
            if trained_imgsz:
                info_sources.append(f"model.args.imgsz = {trained_imgsz}")
        
        # Cách 3: Kiểm tra trong model metadata
        if trained_imgsz is None and hasattr(model, 'model'):
            if hasattr(model.model, 'args'):
                trained_imgsz = getattr(model.model.args, 'imgsz', None)
                if trained_imgsz:
                    info_sources.append(f"model.model.args.imgsz = {trained_imgsz}")
        
        # Cách 4: Kiểm tra trong model info
        if trained_imgsz is None:
            # Thử kiểm tra metadata khác
            if hasattr(model, 'info'):
                print(f"   Model info: {model.info}")
        
        # Hiển thị kết quả
        print("=" * 60)
        if trained_imgsz:
            print(f"✅ Model được train với imgsz: {trained_imgsz}")
            print(f"   Nguồn: {', '.join(info_sources)}")
            print(f"\n💡 Khuyến nghị:")
            print(f"   → Dùng imgsz={trained_imgsz} khi inference để đạt độ chính xác tốt nhất")
            print(f"   → Hoặc để None để YOLO tự động dùng default (thường là 640)")
        else:
            print(f"⚠️  Không tìm thấy thông tin imgsz trong model")
            print(f"   → Model có thể được train với imgsz mặc định (640)")
            print(f"   → Hoặc thông tin không được lưu trong model file")
            print(f"\n💡 Khuyến nghị:")
            print(f"   → Dùng imgsz=640 (default) khi inference")
            print(f"   → Hoặc kiểm tra training logs/config để xác nhận")
        print("=" * 60)
        
        # Hiển thị thêm thông tin model
        print(f"\n📊 Thông tin model:")
        print(f"   Classes: {len(model.names)}")
        print(f"   Class names: {list(model.names.values())}")
        
        if hasattr(model, 'overrides'):
            print(f"\n   Overrides: {model.overrides}")
        
        if hasattr(model, 'args'):
            print(f"\n   Args: {model.args}")
        
        return trained_imgsz
        
    except Exception as e:
        print(f"❌ Lỗi khi load model: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Kiểm tra imgsz của YOLO model")
    parser.add_argument(
        "model_path",
        type=str,
        nargs="?",
        default=None,
        help="Đường dẫn đến model file (.pt). Nếu không chỉ định, sẽ kiểm tra custom model."
    )
    
    args = parser.parse_args()
    
    if args.model_path:
        model_path = args.model_path
    else:
        # Tự động tìm custom model
        custom_model_path = ROOT_DIR / "yolov8s_car_custom.pt"
        if custom_model_path.exists():
            model_path = str(custom_model_path)
            print(f"📁 Tự động tìm thấy custom model: {model_path}")
        else:
            print("❌ Không tìm thấy model. Hãy chỉ định đường dẫn:")
            print("   python check_model_imgsz.py <path_to_model.pt>")
            sys.exit(1)
    
    check_model_imgsz(model_path)


if __name__ == "__main__":
    main()

