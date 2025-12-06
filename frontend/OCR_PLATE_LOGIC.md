# 🚗 Smart Parking - OCR Plate Detection Logic

## 📋 Tổng quan

Hệ thống nhận dạng biển số xe (License Plate Recognition - LPR) sử dụng **fast-alpr** library với 2 models:
- **Detector**: `yolo-v9-t-384-license-plate-end2end` - Phát hiện vị trí biển số
- **OCR**: `global-plates-mobile-vit-v2-model` - Nhận dạng ký tự trên biển số

---

## 🔄 **Workflow tổng thể**

```
User Capture Frame
    ↓
Frontend: Convert to base64
    ↓
POST /api/plate-detect
    ↓
Backend: Decode base64 → OpenCV image
    ↓
ALPR Model: Detect + OCR
    ↓
Backend: Annotate image (draw boxes + text)
    ↓
Response: { plates: [...], annotatedImage: "data:image/..." }
    ↓
Frontend: Save to Firestore (plateDetections collection)
    ↓
Display in UI
```

---

## 🖥️ **Backend Implementation**

### **1. Standalone Script: `server/plate_detect.py`**

Script độc lập có thể chạy từ command line hoặc được gọi từ FastAPI.

#### **Input:**
```json
{
  "imageData": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
}
```

#### **Processing:**

```71:94:server/plate_detect.py
def main():
    payload = json.loads(sys.stdin.read() or "{}")
    image_data = payload.get("imageData")
    if not image_data:
        raise SystemExit(json.dumps({"success": False, "error": "Missing imageData"}))

    if "," in image_data:
        image_data = image_data.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(image_data)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(json.dumps({"success": False, "error": "Invalid base64 image", "details": str(exc)}))

    np_array = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    if frame is None:
        raise SystemExit(json.dumps({"success": False, "error": "Unable to decode image"}))

    alpr = ALPR(
        detector_model="yolo-v9-t-384-license-plate-end2end",
        ocr_model="global-plates-mobile-vit-v2-model",
    )
    results = alpr.predict(frame)
```

#### **ALPR Model:**
- **Library**: `fast-alpr` (Python package)
- **Detector**: YOLO v9 tiny 384 - Phát hiện biển số
- **OCR**: Mobile ViT v2 - Nhận dạng ký tự

#### **Extract Results:**

```103:155:server/plate_detect.py
    for result in results:
        # Check for object attributes directly
        plate_text = getattr(result, "plate", "") or ""
        confidence = getattr(result, "confidence", 0.0)
        detection = getattr(result, "detection", None)

        if not plate_text and hasattr(result, "ocr"):
            # Maybe nested?
            ocr_obj = getattr(result, "ocr", None)
            if ocr_obj:
                plate_text = getattr(ocr_obj, "text", "") or ""
                confidence = getattr(ocr_obj, "confidence", 0.0)

        plate_text = plate_text.upper().strip()

        # Chỉ thêm plate nếu có text (không filter theo độ dài để không bỏ sót)
        # Bỏ qua các detection không có text
        if not plate_text:
            continue  # Skip plates without text

        bbox = [0, 0, 0, 0]
        if detection and hasattr(detection, "box"):
            # [x1, y1, x2, y2]
            box = detection.box
            if len(box) == 4:
                x1, y1, x2, y2 = map(int, box)
                bbox = [x1, y1, x2 - x1, y2 - y1] # Convert to [x, y, w, h] for frontend
                
                # Draw green box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (64, 255, 120), 3)

                # Draw text background and text inside box bottom
                label = f"{plate_text} ({confidence * 100:.1f}%)"
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
                text_y = max(y2 - 8, y1 + h + 8)
                cv2.rectangle(annotated, (x1, text_y - h - 8), (x1 + w + 12, text_y + 6), (64, 255, 120), -1)
                cv2.putText(
                    annotated,
                    label,
                    (x1 + 6, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    (0, 40, 20),
                    2,
                )

        plates.append(
            {
                "text": plate_text,
                "confidence": float(confidence),
                "bbox": bbox,
            }
        )
```

#### **Output:**
```json
{
  "plates": [
    {
      "text": "30A-12345",
      "confidence": 0.95,
      "bbox": [100, 200, 150, 50]
    }
  ],
  "annotatedImage": "data:image/png;base64,..."
}
```

---

### **2. AI Service: `server/services/ai_service.py`**

Class-based service tích hợp trực tiếp vào FastAPI (không spawn subprocess).

#### **Initialization:**

```23:35:server/services/ai_service.py
class AIService:
    """AI Service quản lý YOLO và ALPR models"""
    
    def __init__(self):
        self.yolo_model = None
        self.alpr_model = None
        self.models_loaded = False
        
        # Paths
        self.script_dir = Path(__file__).parent.parent
        self.custom_model_path = self.script_dir / "yolov8s_car_custom.pt"
        self.default_model_path = self.script_dir / "yolov8n.pt"
```

#### **Load Models:**

```36:74:server/services/ai_service.py
    async def load_models(self):
        """Load YOLO và ALPR models 1 lần duy nhất"""
        if self.models_loaded:
            return
        
        # Load YOLO model
        try:
            # Ưu tiên custom model
            if self.custom_model_path.exists():
                model_path = str(self.custom_model_path)
                print(f"✅ Loading custom YOLO model: {model_path}")
            elif self.default_model_path.exists():
                model_path = str(self.default_model_path)
                print(f"ℹ️  Loading default YOLO model: {model_path}")
            else:
                model_path = "yolov8n.pt"
                print(f"ℹ️  Downloading YOLO model: {model_path}")
            
            self.yolo_model = YOLO(model_path)
            print(f"✅ YOLO model loaded successfully")
            
        except Exception as e:
            print(f"❌ Failed to load YOLO model: {e}")
            raise
        
        # Load ALPR model
        try:
            self.alpr_model = ALPR(
                detector_model="yolo-v9-t-384-license-plate-end2end",
                ocr_model="global-plates-mobile-vit-v2-model",
            )
            print(f"✅ ALPR model loaded successfully")
            
        except Exception as e:
            print(f"❌ Failed to load ALPR model: {e}")
            raise
        
        self.models_loaded = True
        print(f"🎉 All AI models loaded and ready!")
```

#### **Detect Plate Method:**

```76:183:server/services/ai_service.py
    async def detect_plate(self, image_data: str) -> Dict[str, Any]:
        """
        Detect license plates trong image
        
        Args:
            image_data: Base64 encoded image string
        
        Returns:
            Dict với plates và annotated image
        """
        if not self.models_loaded:
            await self.load_models()
        
        # Decode base64 image
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        
        try:
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            raise ValueError(f"Invalid base64 image: {e}")
        
        # Convert to OpenCV format
        np_array = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise ValueError("Unable to decode image")
        
        # Run ALPR prediction
        results = self.alpr_model.predict(frame)
        
        # Annotate image
        annotated = frame.copy()
        plates = []
        
        for result in results:
            # Extract plate info
            plate_text = getattr(result, "plate", "") or ""
            confidence = getattr(result, "confidence", 0.0)
            detection = getattr(result, "detection", None)
            
            plate_text = plate_text.upper().strip()
            
            # Skip empty plates
            if not plate_text:
                continue
            
            # Extract bbox
            bbox = [0, 0, 0, 0]
            if detection and hasattr(detection, "box"):
                box = detection.box
                if len(box) == 4:
                    x1, y1, x2, y2 = map(int, box)
                    bbox = [x1, y1, x2 - x1, y2 - y1]  # [x, y, w, h]
                    
                    # Draw green box
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (64, 255, 120), 3)
                    
                    # Draw label
                    label = f"{plate_text} ({confidence * 100:.1f}%)"
                    (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
                    text_y = max(y2 - 8, y1 + h + 8)
                    cv2.rectangle(annotated, (x1, text_y - h - 8), (x1 + w + 12, text_y + 6), (64, 255, 120), -1)
                    cv2.putText(
                        annotated,
                        label,
                        (x1 + 6, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.75,
                        (0, 40, 20),
                        2,
                    )
            
            plates.append({
                "text": plate_text,
                "confidence": float(confidence),
                "bbox": bbox,
            })
        
        # Add banner if plates detected
        if plates:
            banner = f"[{plates[0]['text']}]"
            (tw, th), _ = cv2.getTextSize(banner, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 3)
            bx = max(20, (annotated.shape[1] - tw) // 2 - 20)
            by = annotated.shape[0] - 25
            cv2.rectangle(annotated, (bx - 10, by - th - 15), (bx + tw + 10, by + 15), (255, 255, 255), -1)
            cv2.putText(
                annotated,
                banner,
                (bx, by),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.1,
                (0, 0, 0),
                3,
            )
        
        # Encode annotated image
        ok, buffer = cv2.imencode(".png", annotated)
        if not ok:
            raise RuntimeError("Failed to encode annotated image")
        
        annotated_b64 = base64.b64encode(buffer.tobytes()).decode("utf-8")
        
        return {
            "plates": plates,
            "annotatedImage": f"data:image/png;base64,{annotated_b64}",
        }
```

---

### **3. FastAPI Endpoint: `server/main_fastapi.py`**

```283:307:server/main_fastapi.py
async def detect_license_plate(request: dict):
    """
    Detect license plate từ image
    Input: { "imageData": "data:image/jpeg;base64,..." }
    """
    try:
        image_data = request.get("imageData")
        if not image_data:
            raise HTTPException(status_code=400, detail="imageData is required")
        
        print(f"📥 Received plate detection request")
        
        # Gọi AI service trực tiếp (KHÔNG spawn subprocess)
        result = await ai_service.detect_plate(image_data)
        
        # Lưu vào Firebase
        if result.get("plates"):
            await firebase_service.save_plate_detection(result)
        
        print(f"✅ Detected {len(result.get('plates', []))} plates")
        return {"success": True, **result}
        
    except Exception as e:
        print(f"❌ Plate detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Endpoint:** `POST /api/plate-detect`

**Request:**
```json
{
  "imageData": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
}
```

**Response:**
```json
{
  "success": true,
  "plates": [
    {
      "text": "30A-12345",
      "confidence": 0.95,
      "bbox": [100, 200, 150, 50]
    }
  ],
  "annotatedImage": "data:image/png;base64,..."
}
```

---

## 💻 **Frontend Implementation**

### **1. Plate Detection Service: `frontend/src/services/plateDetectionService.ts`**

#### **Data Structure:**

```17:28:frontend/src/services/plateDetectionService.ts
export interface PlateDetectionRecord {
  id: string;
  ownerId: string;
  parkingId: string;
  cameraId: string;
  plateText: string;
  confidence: number;
  inputImageUrl: string;
  annotatedImageUrl?: string;
  rawResponse?: unknown;
  createdAt: Date;
}
```

#### **Save to Firestore:**

```41:68:frontend/src/services/plateDetectionService.ts
export async function savePlateDetection(payload: SavePlateDetectionPayload) {
  try {
    // Filter out undefined values - Firebase doesn't accept undefined
    const firestoreData: Record<string, unknown> = {
      ownerId: payload.ownerId,
      parkingId: payload.parkingId,
      cameraId: payload.cameraId,
      plateText: payload.plateText,
      confidence: payload.confidence,
      inputImageUrl: payload.inputImageUrl,
      createdAt: serverTimestamp(),
    };
    
    // Only add optional fields if they are defined
    if (payload.annotatedImageUrl !== undefined) {
      firestoreData.annotatedImageUrl = payload.annotatedImageUrl;
    }
    if (payload.rawResponse !== undefined) {
      firestoreData.rawResponse = payload.rawResponse;
    }
    
    const docRef = await addDoc(collection(db, COLLECTION), firestoreData);
    return { success: true, id: docRef.id };
  } catch (error) {
    console.error('Failed to save plate detection', error);
    return { success: false, error: error instanceof Error ? error.message : String(error) };
  }
}
```

**Collection:** `plateDetections`

---

### **2. Stream Host Page: `frontend/src/pages/StreamHostPage.tsx`**

#### **Capture & Detect Flow:**

```696:850:frontend/src/pages/StreamHostPage.tsx
  // Handle capture and detect plate number
  const handleCaptureAndDetect = async () => {
    if (!ownerId || !parkingLotId.trim() || !cameraId.trim()) {
      setError('Vui lòng nhập Parking Lot ID và Camera ID trước khi detect');
      return;
    }

    if (status !== 'streaming') {
      setError('Vui lòng bắt đầu stream trước khi detect');
      return;
    }
    
    setDetectingPlate(true);
    setError(null);
    
    try {
      // Capture frame from video
      const frameDataUrl = captureFrameFromVideo();
      if (!frameDataUrl) {
        throw new Error('Không thể capture frame từ video');
      }
      
      // Send to plate detection API
      let response: Response;
      try {
        response = await fetch(`${API_BASE}/api/plate-detect`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ imageData: frameDataUrl }),
        });
      } catch (fetchError) {
        throw new Error(`Network error: ${fetchError}`);
      }

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      
      console.log('📥 Plate detection response:', {
        success: data.success,
        platesCount: data.plates?.length || 0,
        hasAnnotatedImage: !!data.annotatedImage,
        error: data.error,
      });
      
      if (!data.success) {
        throw new Error(data.error || 'Plate detection failed');
      }
      
      const detectedPlates: PlateResult[] = data.plates || [];
      
      console.log('🔍 Detected plates:', detectedPlates);
      
      if (detectedPlates.length === 0) {
        setError('Không tìm thấy biển số nào trong frame này. Hãy thử capture lại hoặc đảm bảo biển số rõ ràng trong video.');
        setDetectingPlate(false);
        return;
      }
      
      // Filter plates với confidence thấp (dưới 10% - giảm threshold để dễ detect hơn)
      // Chỉ lọc bỏ text rỗng, không filter theo độ dài
      const validPlates = detectedPlates.filter(plate => {
        const conf = plate.confidence || 0;
        // Chỉ cần có text (không rỗng) và confidence >= 10%
        const hasValidText = plate.text && plate.text.trim().length > 0;
        return conf >= 0.1 && hasValidText;
      });
      
      if (validPlates.length === 0 && detectedPlates.length > 0) {
        // Có detect nhưng confidence thấp hoặc text không hợp lệ
        const platesInfo = detectedPlates.map(p => `${p.text || '(empty)'} (${((p.confidence || 0) * 100).toFixed(1)}%)`).join(', ');
        setError(`Tìm thấy ${detectedPlates.length} biển số nhưng không đủ tin cậy: ${platesInfo}. Hãy thử capture lại khi biển số rõ hơn.`);
        setDetectingPlate(false);
        return;
      }
      
      if (validPlates.length === 0) {
        // Hiển thị thông báo với thông tin debug
        let errorMsg = 'Không tìm thấy biển số nào trong frame này.\n';
        if (detectedPlates.length > 0) {
          errorMsg += `Model đã detect ${detectedPlates.length} kết quả nhưng không đủ điều kiện (confidence hoặc text không hợp lệ).\n`;
          errorMsg += `Chi tiết: ${detectedPlates.map(p => `"${p.text || '(rỗng)'}" (${((p.confidence || 0) * 100).toFixed(1)}%)`).join(', ')}`;
        } else {
          errorMsg += 'Hãy thử capture lại khi biển số rõ ràng và đầy đủ trong video.';
        }
        setError(errorMsg);
        setDetectingPlate(false);
        return;
      }
      
      console.log('✅ Valid plates (confidence >= 20%):', validPlates);
      
      // Compress input image để lưu vào Firebase (giảm kích thước)
      const compressedInputImage = compressImageDataUrl(frameDataUrl, 0.7);
      console.log('📊 Image sizes:', {
        original: `${(estimateDataUrlBytes(frameDataUrl) / 1024).toFixed(1)} KB`,
        compressedInput: `${(estimateDataUrlBytes(compressedInputImage) / 1024).toFixed(1)} KB`,
        annotatedImage: data.annotatedImage ? `${(estimateDataUrlBytes(data.annotatedImage) / 1024).toFixed(1)} KB` : 'N/A',
        note: 'Annotated image chỉ hiển thị trong UI, không lưu vào Firebase (quá lớn)',
      });
      
      // Save each detected plate to Firebase
      // NOTE: Không lưu annotatedImageUrl vào Firebase vì quá lớn (>1MB)
      // Annotated image chỉ được lưu trong local state để hiển thị trong UI
      const now = new Date();
      const savedDetections: StreamPlateDetection[] = [];
      
      // Sử dụng validPlates thay vì detectedPlates
      for (const plate of validPlates) {
        // Save to Firebase - CHỈ lưu inputImageUrl, KHÔNG lưu annotatedImageUrl
        const saveResult = await savePlateDetection({
          ownerId,
          parkingId: parkingLotId.trim(),
          cameraId: cameraId.trim(),
          plateText: plate.text,
          confidence: plate.confidence,
          inputImageUrl: compressedInputImage,
          annotatedImageUrl: undefined,
          rawResponse: data.raw,
        });
        
        if (saveResult.success) {
          const detection: StreamPlateDetection = {
            id: saveResult.id || `detection-${Date.now()}-${Math.random()}`,
            plateText: plate.text,
            detectedAt: now,
            confidence: plate.confidence,
            inputImageUrl: compressedInputImage,
            parkingId: parkingLotId.trim(),
            annotatedImageUrl: data.annotatedImage || undefined,
```

#### **Filter Logic:**

- **Confidence threshold**: ≥ 10% (rất thấp để dễ detect)
- **Text validation**: Phải có text (không rỗng)
- **Không filter theo độ dài**: Để không bỏ sót biển số ngắn

---

### **3. Plate History Page: `frontend/src/pages/PlateHistoryPage.tsx`**

Hiển thị lịch sử tất cả plate detections:

```24:43:frontend/src/pages/PlateHistoryPage.tsx
  useEffect(() => {
    const loadRecords = async () => {
      if (!ownerId) {
        setRecords([]);
        setLoading(false);
        return;
      }
      setLoading(true);
      const result = await fetchPlateDetections({ ownerId });
      if (result.success && result.data) {
        setRecords(result.data);
        setError(null);
      } else {
        setRecords([]);
        setError(result.error || 'Không thể tải dữ liệu');
      }
      setLoading(false);
    };
    loadRecords();
  }, [ownerId]);
```

**Features:**
- Filter theo parking lot
- Sort theo time, plate text, confidence, etc.
- Delete records
- View annotated images

---

## 📊 **Data Flow Diagram**

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND: StreamHostPage                               │
│                                                         │
│  1. User clicks "Detect Plate"                         │
│  2. captureFrameFromVideo() → base64 image             │
│  3. POST /api/plate-detect                             │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  BACKEND: FastAPI (/api/plate-detect)                  │
│                                                         │
│  1. Receive { imageData: "base64..." }                  │
│  2. Call ai_service.detect_plate()                     │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  AI SERVICE: ai_service.py                             │
│                                                         │
│  1. Decode base64 → OpenCV image                       │
│  2. ALPR.predict(frame)                                │
│     ├─ Detector: Find plate location                   │
│     └─ OCR: Recognize text                              │
│  3. Annotate image (draw boxes + labels)                │
│  4. Return { plates: [...], annotatedImage: "..." }     │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  FRONTEND: Save to Firestore                           │
│                                                         │
│  1. Filter valid plates (confidence >= 10%)            │
│  2. For each plate:                                     │
│     - savePlateDetection() → Firestore                 │
│     - Collection: plateDetections                      │
│  3. Update UI với annotated image                      │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 **Technical Details**

### **ALPR Model Architecture:**

```
Input Image
    ↓
YOLO v9 Tiny 384 (Detector)
    ↓
License Plate Bounding Boxes
    ↓
Crop each plate region
    ↓
Mobile ViT v2 (OCR)
    ↓
Text Recognition
    ↓
Output: { text, confidence, bbox }
```

### **Bounding Box Format:**

- **Backend (ALPR)**: `[x1, y1, x2, y2]` (absolute coordinates)
- **Frontend**: `[x, y, width, height]` (top-left + size)
- **Conversion**: `[x1, y1, x2-x1, y2-y1]`

### **Confidence Threshold:**

- **Minimum**: 10% (rất thấp để không bỏ sót)
- **Filter**: Chỉ bỏ qua plates không có text
- **Reason**: Biển số Việt Nam có nhiều format khác nhau

### **Image Processing:**

1. **Input**: Base64 encoded image (JPEG/PNG)
2. **Decode**: `base64.b64decode()` → bytes
3. **OpenCV**: `cv2.imdecode()` → numpy array
4. **ALPR**: Process → Results
5. **Annotate**: Draw boxes + text
6. **Encode**: `cv2.imencode()` → PNG → base64

---

## 💾 **Firestore Structure**

### **Collection: `plateDetections`**

```typescript
{
  id: "auto-generated",
  ownerId: "yt88rSJpBsMzjnWX2SfCN687iex1",
  parkingId: "PARKING_A",
  cameraId: "CAM001",
  plateText: "30A-12345",
  confidence: 0.95,
  inputImageUrl: "data:image/jpeg;base64,...",  // Compressed
  annotatedImageUrl: undefined,  // NOT saved (too large)
  rawResponse: {...},  // Optional
  createdAt: Timestamp
}
```

**Note:** `annotatedImageUrl` không được lưu vào Firestore vì quá lớn (>1MB). Chỉ lưu trong local state để hiển thị.

---

## 🎯 **Use Cases**

### **1. Real-time Detection từ Video Stream**
- User stream video từ camera
- Click "Detect Plate" → Capture frame
- Gửi frame đến API → Nhận kết quả
- Hiển thị annotated image với bounding boxes

### **2. Batch Processing**
- Upload nhiều ảnh
- Process từng ảnh
- Lưu tất cả results vào Firestore

### **3. History & Analytics**
- Xem lịch sử tất cả detections
- Filter theo parking lot, camera
- Sort theo confidence, time
- Export data

---

## ⚙️ **Configuration**

### **API Endpoint:**
```typescript
// frontend/src/config/api.ts
endpoints: {
  plateDetect: '/api/plate-detect',
}
```

### **Model Names:**
```python
# server/services/ai_service.py
ALPR(
    detector_model="yolo-v9-t-384-license-plate-end2end",
    ocr_model="global-plates-mobile-vit-v2-model",
)
```

### **Confidence Threshold:**
```typescript
// frontend/src/pages/StreamHostPage.tsx
const validPlates = detectedPlates.filter(plate => {
  const conf = plate.confidence || 0;
  const hasValidText = plate.text && plate.text.trim().length > 0;
  return conf >= 0.1 && hasValidText;  // 10% minimum
});
```

---

## 🐛 **Error Handling**

### **Backend Errors:**
- `Missing imageData` → 400 Bad Request
- `Invalid base64 image` → 400 Bad Request
- `Unable to decode image` → 400 Bad Request
- `Failed to encode annotated image` → 500 Internal Server Error

### **Frontend Errors:**
- Network errors → Retry hoặc show error message
- No plates detected → Show helpful message
- Low confidence → Show confidence details
- Firebase save errors → Log và show alert

---

## 📈 **Performance**

### **Processing Time:**
- **ALPR Detection**: ~200-500ms per image (depends on image size)
- **Image Annotation**: ~50-100ms
- **Total**: ~250-600ms per request

### **Optimization:**
- Models loaded once (singleton pattern)
- Image compression before saving to Firestore
- Annotated images not saved (too large)

---

## 🔮 **Future Improvements**

1. **Multi-frame averaging**: Combine results từ nhiều frames
2. **Plate format validation**: Validate Vietnamese plate format
3. **Tracking**: Link plates với vehicle tracking IDs
4. **Real-time stream**: Process mỗi N frames automatically
5. **Confidence calibration**: Fine-tune threshold per camera

---

**Updated:** December 5, 2025

