"""
ALPR Service - chịu trách nhiệm load và chạy mô hình biển số (detector + OCR).
Tách riêng để dễ bảo trì và tránh "god object".
"""
import base64
import cv2
import numpy as np
from typing import Dict, Any
from dataclasses import dataclass

try:
    from fast_alpr import ALPR
except ImportError as e:
    print(f"❌ Missing ALPR library: {e}")
    print("Run: pip install fast-alpr opencv-python")
    raise


@dataclass
class ALPRResult:
    plates: list
    annotated_image_b64: str


class ALPRService:
    """Quản lý model ALPR và suy luận biển số."""

    def __init__(self):
        self.alpr_model = None
        self.model_loaded = False

    async def load_model(self):
        """Load ALPR model một lần."""
        if self.model_loaded:
            return

        self.alpr_model = ALPR(
            detector_model="yolo-v9-t-384-license-plate-end2end",
            ocr_model="global-plates-mobile-vit-v2-model",
        )
        self.model_loaded = True
        print("✅ ALPR model loaded successfully")

    def _run_alpr_on_frame(self, frame: np.ndarray) -> ALPRResult:
        """Chạy ALPR trên numpy frame, trả kết quả và annotated PNG base64."""
        if frame is None:
            raise ValueError("Frame is None")

        # Analyze image quality for debugging
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        contrast = np.std(gray)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()

        results = self.alpr_model.predict(frame)
        print(f"📊 ALPR returned {len(results)} results")

        annotated = frame.copy()
        plates = []

        for idx, result in enumerate(results):
            plate_text = getattr(result, "plate", "") or ""
            confidence = getattr(result, "confidence", 0.0)
            detection = getattr(result, "detection", None)

            if not plate_text and hasattr(result, "ocr"):
                ocr_obj = getattr(result, "ocr", None)
                if ocr_obj:
                    plate_text = getattr(ocr_obj, "text", "") or ""
                    confidence = getattr(ocr_obj, "confidence", 0.0)
                    print(f"  Result {idx}: Found in OCR object - plate='{plate_text}', confidence={confidence}")

            print(f"  Result {idx}: plate='{plate_text}', confidence={confidence}")

            if not plate_text:
                print(f"    Debug - result attributes: {dir(result)}")
                if detection:
                    print(f"    Debug - detection attributes: {dir(detection)}")

            plate_text = plate_text.upper().strip()
            if not plate_text:
                print(f"  ⚠️ Skipping empty plate text")
                continue

            bbox = [0, 0, 0, 0]
            if detection and hasattr(detection, "box"):
                box = detection.box
                if len(box) == 4:
                    x1, y1, x2, y2 = map(int, box)
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (64, 255, 120), 3)
                    label = f"{plate_text} ({confidence * 100:.1f}%)"
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
                    text_y = max(y2 - 8, y1 + th + 8)
                    cv2.rectangle(annotated, (x1, text_y - th - 8), (x1 + tw + 12, text_y + 6), (64, 255, 120), -1)
                    cv2.putText(
                        annotated,
                        label,
                        (x1 + 6, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.75,
                        (0, 40, 20),
                        2,
                    )
                    bbox = [x1, y1, x2 - x1, y2 - y1]
                    print(f"  📦 BBox: ({x1}, {y1}) → ({x2}, {y2}) size: {bbox[2]}x{bbox[3]}")

            plates.append(
                {
                    "text": plate_text,
                    "confidence": float(confidence),
                    "bbox": bbox,
                }
            )

        print(f"✅ Total valid plates after filtering: {len(plates)}")

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

        ok, buffer = cv2.imencode(".png", annotated)
        if not ok:
            raise RuntimeError("Failed to encode annotated image")
        annotated_b64 = base64.b64encode(buffer.tobytes()).decode("utf-8")

        return ALPRResult(
            plates=plates,
            annotated_image_b64=annotated_b64,
        )

    async def detect_plate(self, image_data: str) -> Dict[str, Any]:
        """Nhận diện biển số từ ảnh base64 và trả về plates + annotatedImage."""
        if not self.model_loaded:
            await self.load_model()

        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            raise ValueError(f"Invalid base64 image: {e}")

        np_array = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

        if frame is None:
            raise ValueError("Unable to decode image")

        result = self._run_alpr_on_frame(frame)
        return {
            "plates": result.plates,
            "annotatedImage": f"data:image/png;base64,{result.annotated_image_b64}",
        }

    async def detect_plate_from_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """Nhận diện biển số từ numpy frame (BGR)."""
        if not self.model_loaded:
            await self.load_model()

        result = self._run_alpr_on_frame(frame)
        return {
            "plates": result.plates,
            "annotatedImage": f"data:image/png;base64,{result.annotated_image_b64}",
        }

