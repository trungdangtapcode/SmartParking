# 🐍 CONDA QUICKSTART - SMARTPARKING

Hướng dẫn nhanh cho người dùng **Conda/Anaconda/Miniconda**.

---

## 📦 **SETUP LẦN ĐẦU (5 PHÚT)**

### **Bước 1: Tạo environment**

```bash
cd server

# Cách 1: Từ file environment.yml (KHUYẾN NGHỊ)
conda env create -f environment.yml

# Cách 2: Tạo thủ công
conda create -n smartparking python=3.10 -y
```

### **Bước 2: Kích hoạt environment**

```bash
conda activate smartparking
```

### **Bước 3: Cài packages (nếu tạo thủ công)**

```bash
# Core packages
conda install -c conda-forge numpy opencv pytorch-cpu torchvision-cpu -y

# FastAPI & dependencies
pip install fastapi uvicorn[standard] python-multipart aiohttp websockets

# AI packages
pip install ultralytics lap fast-alpr[onnx]

# Firebase
pip install firebase-admin
```

### **Bước 4: Verify**

```bash
python -c "import fastapi, ultralytics, cv2, firebase_admin; print('✅ All packages OK!')"
```

---

## 🚀 **CHẠY SERVER (HÀNG NGÀY)**

### **Terminal 1: Backend FastAPI**

```bash
cd F:\KHKT2025\AIIII\WEB\SmartParking\server

# Kích hoạt environment
conda activate smartparking

# Chạy server
python main_fastapi.py
```

**Kết quả:**
```
============================================================
🚀 SmartParking FastAPI Server
============================================================
📹 ESP32-CAM: http://192.168.1.158:81/stream
🌐 Server will start at: http://localhost:8000
📖 API Docs: http://localhost:8000/docs
============================================================
✅ YOLO model loaded successfully
✅ ALPR model loaded successfully
✅ Firebase initialized
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### **Terminal 2: Frontend React**

```bash
cd F:\KHKT2025\AIIII\WEB\SmartParking\frontend

npm run dev
```

---

## 🛠️ **CONDA COMMANDS HỮU ÍCH**

```bash
# Liệt kê tất cả environments
conda env list

# Kiểm tra environment đang active
conda info --envs

# Liệt kê packages trong environment
conda list

# Update package
conda update <package_name>
pip install --upgrade <package_name>

# Export environment (để chia sẻ)
conda env export > environment_backup.yml

# Xóa environment (nếu muốn tạo lại từ đầu)
conda deactivate
conda env remove -n smartparking

# Tạo lại
conda env create -f environment.yml
```

---

## 🐛 **TROUBLESHOOTING**

### **❌ "conda: command not found"**

**Giải pháp:**
- Mở **Anaconda Prompt** hoặc **Anaconda PowerShell Prompt**
- Hoặc thêm Conda vào PATH:
  ```bash
  # Tìm đường dẫn Conda
  # Thường là: C:\Users\<YourName>\anaconda3
  # Hoặc: C:\ProgramData\Anaconda3
  
  # Thêm vào PATH trong Environment Variables
  ```

### **❌ "Solving environment: failed"**

**Giải pháp:**
```bash
# Clear cache
conda clean --all

# Thử lại
conda env create -f environment.yml

# Hoặc tạo thủ công với pip
conda create -n smartparking python=3.10 -y
conda activate smartparking
pip install -r requirements_fastapi.txt
```

### **❌ "ImportError: DLL load failed" (Windows)**

**Giải pháp:**
```bash
# Cài Visual C++ Redistributable
# Download từ: https://aka.ms/vs/17/release/vc_redist.x64.exe

# Hoặc cài opencv từ conda thay vì pip
conda install -c conda-forge opencv
```

### **❌ "CUDA not available" (GPU không hoạt động)**

**Kiểm tra:**
```bash
conda activate smartparking
python -c "import torch; print(torch.cuda.is_available())"
```

**Nếu False:**
```bash
# Gỡ PyTorch CPU version
pip uninstall torch torchvision

# Cài PyTorch GPU version (ví dụ CUDA 11.8)
conda install pytorch torchvision pytorch-cuda=11.8 -c pytorch -c nvidia

# Hoặc CUDA 12.1
conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia
```

**Check CUDA version:**
```bash
nvidia-smi
# Xem dòng "CUDA Version: 12.x"
```

---

## ⚡ **GPU vs CPU PERFORMANCE**

### **Cài PyTorch GPU (nếu có NVIDIA GPU):**

```bash
conda activate smartparking

# Gỡ CPU version
pip uninstall torch torchvision

# Cài GPU version
conda install pytorch torchvision pytorch-cuda=11.8 -c pytorch -c nvidia

# Verify
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

### **Benchmark:**

| Hardware | YOLO Inference Time | Recommendation |
|----------|---------------------|----------------|
| **CPU** (Intel i7) | ~500ms/frame | OK cho testing |
| **GPU** (GTX 1660) | ~50ms/frame | ✅ Khuyến nghị |
| **GPU** (RTX 3060) | ~20ms/frame | ⚡ Tốt nhất |

---

## 📊 **KIỂM TRA ENVIRONMENT**

```bash
conda activate smartparking

# Check Python version
python --version
# Expected: Python 3.10.x

# Check packages
python << EOF
import sys
import fastapi
import ultralytics
import cv2
import torch
import firebase_admin

print("=" * 50)
print("📦 PACKAGES INSTALLED:")
print("=" * 50)
print(f"Python:        {sys.version}")
print(f"FastAPI:       {fastapi.__version__}")
print(f"Ultralytics:   {ultralytics.__version__}")
print(f"OpenCV:        {cv2.__version__}")
print(f"PyTorch:       {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
print("Firebase Admin: OK")
print("=" * 50)
print("✅ All packages ready!")
EOF
```

---

## 🎯 **TÓM TẮT**

| Task | Command |
|------|---------|
| **Tạo env lần đầu** | `conda env create -f environment.yml` |
| **Activate** | `conda activate smartparking` |
| **Chạy server** | `python main_fastapi.py` |
| **Deactivate** | `conda deactivate` |
| **List envs** | `conda env list` |
| **Xóa env** | `conda env remove -n smartparking` |

---

## 🎓 **CONDA vs VENV**

| Feature | venv | Conda | Winner |
|---------|------|-------|--------|
| **Quản lý Python version** | ❌ | ✅ | Conda |
| **Binary packages** | ❌ | ✅ | Conda |
| **Cross-platform** | ⚠️ | ✅ | Conda |
| **AI/ML packages** | ⚠️ | ✅ | Conda |
| **Speed** | ⚠️ | ✅ | Conda |
| **Disk space** | ✅ | ⚠️ | venv |

**Kết luận:** Conda tốt hơn cho AI/ML projects! 🎉

---

## ✅ **CHECKLIST**

- [ ] Anaconda/Miniconda đã cài đặt
- [ ] `conda env create -f environment.yml` thành công
- [ ] `conda activate smartparking` hoạt động
- [ ] `python main_fastapi.py` chạy được
- [ ] Truy cập `http://localhost:8000/docs` → Thấy API docs
- [ ] Test `/health` endpoint → Status OK
- [ ] Test `/test/esp32` → Connected

---

**Done!** 🚀 Backend FastAPI đã sẵn sàng với Conda!

