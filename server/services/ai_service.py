"""
AI Service - YOLO Object Tracking + License Plate Recognition
Tích hợp trực tiếp, KHÔNG spawn subprocess
"""
import base64
import tempfile
import os
import cv2
import numpy as np
from typing import Dict, Any, Optional
from pathlib import Path

# Import AI libraries
try:
    from ultralytics import YOLO
    from fast_alpr import ALPR
except ImportError as e:
    print(f"❌ Missing AI libraries: {e}")
    print("Run: pip install ultralytics fast-alpr opencv-python")
    raise


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
        
        # Analyze image quality for debugging
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        contrast = np.std(gray)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        print(f"🔍 Running ALPR prediction on image shape: {frame.shape}")
        print(f"   Image quality - Brightness: {brightness:.1f}, Contrast: {contrast:.1f}, Sharpness: {sharpness:.2f}")
        
        # Preprocessing: Denoise và Upscale (dựa trên phân tích chất lượng ảnh)
        original_shape = frame.shape[:2]  # (height, width)
        original_h, original_w = original_shape
        scale_factor = 1.0  # Track scale factor for bbox adjustment
        
        # 1. Denoise preprocessing (nếu cần)
        # Noise level cao → cần denoise
        noise_level = cv2.Laplacian(gray, cv2.CV_64F).var()
        if noise_level > 50:  # Threshold từ phân tích
            print(f"   🔧 Applying denoise preprocessing (noise level: {noise_level:.2f})")
            frame = cv2.fastNlMeansDenoisingColored(frame, None, 10, 10, 7, 21)
        
        # 2. Upscale preprocessing (nếu ảnh quá nhỏ)
        # Nếu ảnh nhỏ hơn 1280x720 → upscale 2x
        h, w = frame.shape[:2]
        if w < 1280 or h < 720:
            scale_factor = max(1280 / w, 720 / h, 2.0)  # Tối thiểu 2x
            new_w = int(w * scale_factor)
            new_h = int(h * scale_factor)
            print(f"   🔧 Upscaling image: {w}x{h} → {new_w}x{new_h} (scale: {scale_factor:.2f}x)")
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        
        results = self.alpr_model.predict(frame)
        print(f"📊 ALPR returned {len(results)} results")
        
        # Annotate image
        annotated = frame.copy()
        plates = []
        
        for idx, result in enumerate(results):
            # Extract plate info
            plate_text = getattr(result, "plate", "") or ""
            confidence = getattr(result, "confidence", 0.0)
            detection = getattr(result, "detection", None)
            
            # Try nested OCR object if plate_text is empty
            if not plate_text and hasattr(result, "ocr"):
                ocr_obj = getattr(result, "ocr", None)
                if ocr_obj:
                    plate_text = getattr(ocr_obj, "text", "") or ""
                    confidence = getattr(ocr_obj, "confidence", 0.0)
                    print(f"  Result {idx}: Found in OCR object - plate='{plate_text}', confidence={confidence}")
            
            print(f"  Result {idx}: plate='{plate_text}', confidence={confidence}")
            
            # Debug: Print all attributes
            if not plate_text:
                print(f"    Debug - result attributes: {dir(result)}")
                if detection:
                    print(f"    Debug - detection attributes: {dir(detection)}")
            
            plate_text = plate_text.upper().strip()
            
            # Skip empty plates
            if not plate_text:
                print(f"  ⚠️ Skipping empty plate text")
                continue
            
            # Extract bbox
            bbox = [0, 0, 0, 0]
            if detection and hasattr(detection, "box"):
                box = detection.box
                if len(box) == 4:
                    # Tọa độ từ model (trên ảnh đã preprocess/upscale)
                    x1_model, y1_model, x2_model, y2_model = map(int, box)
                    
                    # Vẽ bbox trực tiếp trên ảnh annotated (dùng tọa độ từ model)
                    # Box màu xanh lá, độ dày 3px
                    cv2.rectangle(annotated, (x1_model, y1_model), (x2_model, y2_model), (64, 255, 120), 3)
                    
                    # Vẽ label với background
                    label = f"{plate_text} ({confidence * 100:.1f}%)"
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
                    text_y = max(y2_model - 8, y1_model + th + 8)
                    # Background màu xanh lá cho label
                    cv2.rectangle(annotated, (x1_model, text_y - th - 8), (x1_model + tw + 12, text_y + 6), (64, 255, 120), -1)
                    # Text màu đen
                    cv2.putText(
                        annotated,
                        label,
                        (x1_model + 6, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.75,
                        (0, 40, 20),
                        2,
                    )
                    
                    # Scale bbox về kích thước gốc để trả về cho frontend
                    if scale_factor > 1.0:
                        x1_original = int(x1_model / scale_factor)
                        y1_original = int(y1_model / scale_factor)
                        x2_original = int(x2_model / scale_factor)
                        y2_original = int(y2_model / scale_factor)
                    else:
                        x1_original, y1_original, x2_original, y2_original = x1_model, y1_model, x2_model, y2_model
                    
                    bbox = [x1_original, y1_original, x2_original - x1_original, y2_original - y1_original]  # [x, y, w, h]
                    print(f"  📦 BBox on processed image: ({x1_model}, {y1_model}) → ({x2_model}, {y2_model})")
                    if scale_factor > 1.0:
                        print(f"  📦 BBox scaled to original: ({x1_original}, {y1_original}) → ({x2_original}, {y2_original}) size: {x2_original-x1_original}x{y2_original-y1_original}")
            
            plates.append({
                "text": plate_text,
                "confidence": float(confidence),
                "bbox": bbox,
            })
        
        print(f"✅ Total valid plates after filtering: {len(plates)}")
        
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
        
        # Resize annotated image về kích thước gốc nếu đã upscale (để tiết kiệm bandwidth)
        if scale_factor > 1.0:
            annotated = cv2.resize(annotated, (original_w, original_h), interpolation=cv2.INTER_AREA)
            print(f"   🔧 Resized annotated image back to original size: {original_w}x{original_h}")
        
        # Encode annotated image
        ok, buffer = cv2.imencode(".png", annotated)
        if not ok:
            raise RuntimeError("Failed to encode annotated image")
        
        annotated_b64 = base64.b64encode(buffer.tobytes()).decode("utf-8")
        
        return {
            "plates": plates,
            "annotatedImage": f"data:image/png;base64,{annotated_b64}",
        }
    
    async def track_objects(
        self,
        video_data: str,
        frame_skip: int = 1,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45
    ) -> Dict[str, Any]:
        """
        Track objects trong video sử dụng YOLO + ByteTrack
        
        Args:
            video_data: Base64 encoded video
            frame_skip: Process mỗi N frames
            conf_threshold: Detection confidence threshold
            iou_threshold: IOU threshold for NMS
        
        Returns:
            Dict với tracking results và annotated video
        """
        if not self.models_loaded:
            await self.load_models()
        
        # Decode video
        if "," in video_data:
            video_data = video_data.split(",", 1)[1]
        
        try:
            video_bytes = base64.b64decode(video_data)
        except Exception as e:
            raise ValueError(f"Invalid base64 video: {e}")
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
            tmp.write(video_bytes)
            video_path = tmp.name
        
        try:
            result = await self._process_video(
                video_path,
                frame_skip,
                conf_threshold,
                iou_threshold
            )
            return result
        finally:
            # Cleanup temp file
            try:
                os.remove(video_path)
            except:
                pass
    
    async def _process_video(
        self,
        video_path: str,
        frame_skip: int,
        conf_threshold: float,
        iou_threshold: float
    ) -> Dict[str, Any]:
        """Process video với YOLO tracking (internal method)"""
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Output video
        output_path = os.path.join(tempfile.gettempdir(), f"tracked_{os.path.basename(video_path)}")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        frame_count = 0
        processed_frames = 0
        all_tracks = []
        track_history = {}
        
        print(f"📹 Processing video: {width}x{height} @ {fps}fps, {total_frames} frames")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Skip frames
            if frame_count % frame_skip != 0:
                frame_count += 1
                continue
            
            # YOLO tracking với ByteTrack built-in
            results = self.yolo_model.track(
                frame,
                persist=True,
                conf=conf_threshold,
                iou=iou_threshold,
                verbose=False
            )
            
            # Extract detections
            detections = []
            if results[0].boxes is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                scores = results[0].boxes.conf.cpu().numpy()
                classes = results[0].boxes.cls.cpu().numpy().astype(int)
                track_ids = results[0].boxes.id
                
                if track_ids is not None:
                    track_ids = track_ids.cpu().numpy().astype(int)
                else:
                    track_ids = np.array([-1] * len(boxes))
                
                for box, score, cls, tid in zip(boxes, scores, classes, track_ids):
                    x1, y1, x2, y2 = map(int, box)
                    track_id = int(tid) if tid >= 0 else None
                    
                    detections.append({
                        'bbox': [x1, y1, x2 - x1, y2 - y1],
                        'confidence': float(score),
                        'class': int(cls),
                        'class_name': str(self.yolo_model.names[int(cls)]),
                        'track_id': track_id
                    })
                    
                    # Update track history
                    if tid >= 0:
                        if int(tid) not in track_history:
                            track_history[int(tid)] = []
                        center_x = (x1 + x2) // 2
                        center_y = (y1 + y2) // 2
                        track_history[int(tid)].append({
                            'frame': frame_count,
                            'center': [center_x, center_y],
                            'bbox': [x1, y1, x2, y2]
                        })
            
            # Annotate frame
            annotated_frame = self._draw_annotations(frame.copy(), detections, track_history)
            out.write(annotated_frame)
            
            all_tracks.append({
                'frame': frame_count,
                'timestamp': frame_count / fps,
                'detections': detections
            })
            
            processed_frames += 1
            frame_count += 1
            
            if processed_frames % 10 == 0:
                progress = (frame_count / total_frames) * 100
                print(f"⏳ Progress: {progress:.1f}% ({processed_frames} frames)")
        
        cap.release()
        out.release()
        
        # Encode output video
        with open(output_path, 'rb') as f:
            video_bytes = f.read()
        video_b64 = base64.b64encode(video_bytes).decode('utf-8')
        
        # Cleanup
        try:
            os.remove(output_path)
        except:
            pass
        
        # Calculate stats
        unique_tracks = set()
        for frame_data in all_tracks:
            for det in frame_data['detections']:
                if det['track_id'] is not None:
                    unique_tracks.add(det['track_id'])
        
        return {
            'success': True,
            'total_frames': total_frames,
            'processed_frames': processed_frames,
            'unique_tracks': len(unique_tracks),
            'video_width': width,
            'video_height': height,
            'fps': fps,
            'annotatedVideo': f"data:video/mp4;base64,{video_b64}",
            'tracks': all_tracks,
            'track_history': track_history,
            'summary': {
                'total_objects_detected': len(unique_tracks),
                'total_detections': sum(len(f['detections']) for f in all_tracks),
                'avg_detections_per_frame': sum(len(f['detections']) for f in all_tracks) / max(processed_frames, 1)
            }
        }
    
    def _draw_annotations(self, frame, detections, track_history):
        """Draw bounding boxes và trajectories"""
        for det in detections:
            x, y, w, h = det['bbox']
            x1, y1, x2, y2 = x, y, x + w, y + h
            track_id = det['track_id']
            class_name = det['class_name']
            confidence = det['confidence']
            
            # Color based on track ID
            color = (
                int((track_id * 50) % 255) if track_id else 0,
                int((track_id * 100) % 255) if track_id else 255,
                int((track_id * 150) % 255) if track_id else 0
            )
            
            # Draw box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"ID:{track_id} {class_name}" if track_id else class_name
            label += f" {confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
            cv2.putText(frame, label, (x1 + 3, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Draw trajectory
            if track_id and track_id in track_history:
                trail = track_history[track_id][-10:]
                if len(trail) > 1:
                    points = [t['center'] for t in trail]
                    for i in range(1, len(points)):
                        cv2.line(frame, tuple(points[i-1]), tuple(points[i]), color, 2)
        
        return frame
    
    def cleanup(self):
        """Cleanup models khi shutdown"""
        self.yolo_model = None
        self.alpr_model = None
        self.models_loaded = False
        print("✅ AI models cleaned up")

