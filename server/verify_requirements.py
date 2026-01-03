#!/usr/bin/env python3
"""
Verify all requirements are installed correctly with GPU support
"""
import sys

def check_package(package_name, import_name=None):
    """Check if a package is installed"""
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
        print(f"✅ {package_name} installed")
        return True
    except ImportError:
        print(f"❌ {package_name} NOT installed")
        return False

def check_gpu():
    """Check GPU availability"""
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            print(f"✅ GPU available: {device_name}")
            print(f"   CUDA version: {torch.version.cuda}")
            print(f"   PyTorch version: {torch.__version__}")
            return True
        else:
            print("⚠️  GPU not available (running on CPU)")
            return False
    except ImportError:
        print("❌ PyTorch not installed")
        return False

def main():
    print("=" * 60)
    print("SmartParking Requirements Verification")
    print("=" * 60)
    
    packages = [
        ("FastAPI", "fastapi"),
        ("Uvicorn", "uvicorn"),
        ("aiohttp", "aiohttp"),
        ("python-dotenv", "dotenv"),
        ("OpenCV", "cv2"),
        ("NumPy", "numpy"),
        ("Ultralytics (YOLO)", "ultralytics"),
        ("LAP", "lap"),
        ("fast-alpr", "fast_alpr"),
        ("PyTorch", "torch"),
        ("TorchVision", "torchvision"),
        ("Firebase Admin", "firebase_admin"),
    ]
    
    print("\n📦 Checking packages...")
    all_installed = all(check_package(name, imp) for name, imp in packages)
    
    print("\n🎮 Checking GPU support...")
    gpu_available = check_gpu()
    
    print("\n" + "=" * 60)
    if all_installed and gpu_available:
        print("✅ All requirements installed with GPU support!")
        print("   System ready for SmartParking backend")
        sys.exit(0)
    elif all_installed:
        print("⚠️  All packages installed but GPU not available")
        print("   System will run on CPU (slower)")
        sys.exit(0)
    else:
        print("❌ Some packages are missing")
        print("   Run: pip install -r requirements.txt")
        sys.exit(1)

if __name__ == "__main__":
    main()
