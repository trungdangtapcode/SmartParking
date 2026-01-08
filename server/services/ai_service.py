"""
AI Service - YOLO Object Detection & ByteTrack Tracking + License Plate Recognition
Tích hợp trực tiếp, KHÔNG spawn subprocess
Supports CUDA GPU acceleration and multi-object tracking
"""
import base64
import tempfile
import os
import cv2
import numpy as np
import torch
from typing import Dict, Any, Optional, List
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
    """AI Service quản lý YOLO và ALPR models với CUDA support và ByteTrack tracking"""
    
    def __init__(self):
        self.yolo_model = None
        self.alpr_model = None
        self.models_loaded = False
        self.device = None
        
        # Tracking state
        self.track_history = {}  # Store track trails
        self.frame_count = 0
        
        # Paths
        self.script_dir = Path(__file__).parent.parent
        self.custom_model_path = self.script_dir / "yolov8s_car_custom.pt"
        self.default_model_path = self.script_dir / "yolov8n.pt"
    
    def _get_device(self):
        """Detect and return best available device (CUDA, MPS, or CPU)"""
        if torch.cuda.is_available():
            device = 'cuda'
            gpu_name = torch.cuda.get_device_name(0)
            print(f"🚀 CUDA available: {gpu_name}")
            print(f"   GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        elif torch.backends.mps.is_available():
            device = 'mps'
            print(f"🚀 MPS (Apple Silicon) available")
        else:
            device = 'cpu'
            print(f"⚠️  No GPU detected, using CPU (slower)")
        return device
    
    async def load_models(self):
        """Load YOLO và ALPR models 1 lần duy nhất với CUDA support"""
        if self.models_loaded:
            return
        
        # Detect device
        self.device = self._get_device()
        
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
            
            # Move model to GPU if available
            if self.device != 'cpu':
                self.yolo_model.to(self.device)
                print(f"✅ YOLO model loaded on {self.device.upper()}")
            else:
                print(f"✅ YOLO model loaded on CPU")
            
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
        
        # Run ALPR prediction
        print(f"🔍 Running ALPR prediction on image shape: {frame.shape}")
        
        # # Try to enhance image quality for ALPR
        # # Resize if too small
        # h, w = frame.shape[:2]
        # if w < 640 or h < 480:
        #     scale = max(640 / w, 480 / h)
        #     new_w, new_h = int(w * scale), int(h * scale)
        #     frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        #     print(f"📐 Resized frame to {new_w}x{new_h} for better ALPR accuracy")
        
        # # Apply slight sharpening to improve text recognition
        # kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        # frame = cv2.filter2D(frame, -1, kernel)
        # print(f"✨ Applied sharpening filter")
        
        results = self.alpr_model.predict(frame)
        print(f"📊 ALPR returned {len(results)} results")
        
        # Annotate image
        annotated = frame.copy()
        plates = []
        
        for idx, result in enumerate(results):
            # fast-alpr returns ALPRResult with .detection and .ocr attributes
            detection = getattr(result, "detection", None)
            ocr = getattr(result, "ocr", None)
            
            # Extract plate text from OCR
            plate_text = ""
            confidence = 0.0
            
            if ocr:
                plate_text = getattr(ocr, "text", "") or ""
                confidence = getattr(ocr, "confidence", 0.0)
            
            # DEBUG: Print detailed info
            print(f"  Result {idx}:")
            if detection:
                det_attrs = {k: str(getattr(detection, k))[:100] for k in dir(detection) if not k.startswith('_') and not callable(getattr(detection, k))}
                print(f"    Detection: {det_attrs}")
            if ocr:
                ocr_attrs = {k: str(getattr(ocr, k))[:100] for k in dir(ocr) if not k.startswith('_') and not callable(getattr(ocr, k))}
                print(f"    OCR: {ocr_attrs}")
            
            plate_text = plate_text.upper().strip()
            
            # Skip empty plates with low confidence
            print('confidence', confidence)
            if not plate_text or confidence < 0.4:
                print(f"  ⚠️ Skipping: text='{plate_text}', confidence={confidence:.2f}")
                continue
            
            print(f"  ✅ Valid plate found: '{plate_text}' ({confidence:.2f})")
            
            # Extract bbox from detection
            bbox = [0, 0, 0, 0]
            x1, y1, x2, y2 = 0, 0, 0, 0
            
            if detection:
                # fast-alpr detection should have bbox attribute
                try:
                    # Try different possible attribute names
                    bbox_data = None
                    for attr_name in ['bbox', 'box', 'xyxy', 'bounding_box']:
                        if hasattr(detection, attr_name):
                            bbox_data = getattr(detection, attr_name)
                            if bbox_data is not None:
                                print(f"    Found bbox via {attr_name}: {bbox_data}")
                                break
                    
                    if bbox_data and len(bbox_data) >= 4:
                        x1, y1, x2, y2 = map(int, bbox_data[:4])
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
                except Exception as e:
                    print(f"    ⚠️ Error extracting bbox: {e}")
            
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
        
        # Encode annotated image
        ok, buffer = cv2.imencode(".png", annotated)
        if not ok:
            raise RuntimeError("Failed to encode annotated image")
        
        annotated_b64 = base64.b64encode(buffer.tobytes()).decode("utf-8")
        
        return {
            "plates": plates,
            "annotatedImage": f"data:image/png;base64,{annotated_b64}",
        }
    
    async def detect_objects(
        self,
        frame: np.ndarray,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        use_tracking: bool = False
    ) -> list:
        """
        Detect or track objects in a single frame using YOLO
        
        Args:
            frame: OpenCV image (numpy array)
            conf_threshold: Detection confidence threshold
            iou_threshold: IOU threshold for NMS
            use_tracking: If True, use ByteTrack tracking instead of detection only
        
        Returns:
            List of detections with format:
            [
                {
                    'class': 'car',
                    'confidence': 0.85,
                    'bbox': [x, y, width, height],  # In pixels
                    'track_id': 12  # Only if use_tracking=True
                }
            ]
        """
        if not self.models_loaded:
            await self.load_models()
        
        if frame is None or frame.size == 0:
            return []
        
        try:
            self.frame_count += 1
            
            if use_tracking:
                # Use ByteTrack tracking
                results = self.yolo_model.track(
                    source=frame,
                    conf=conf_threshold,
                    iou=iou_threshold,
                    persist=True,  # Keep track IDs between frames
                    verbose=False,
                    device=self.device,
                    tracker="bytetrack.yaml"  # Use ByteTrack
                )
            else:
                # Detection only (no tracking)
                results = self.yolo_model.predict(
                    source=frame,
                    conf=conf_threshold,
                    iou=iou_threshold,
                    verbose=False,
                    device=self.device
                )
            
            detections = []
            
            # Process results
            for result in results:
                boxes = result.boxes
                
                if boxes is None:
                    continue
                
                for box in boxes:
                    # Get box coordinates (xyxy format)
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    # Convert to xywh format
                    x = float(x1)
                    y = float(y1)
                    width = float(x2 - x1)
                    height = float(y2 - y1)
                    
                    # Get class and confidence
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = result.names[cls_id]
                    
                    detection = {
                        'class': class_name,
                        'confidence': conf,
                        'bbox': [x, y, width, height]
                    }
                    
                    # Add track_id if tracking is enabled
                    if use_tracking and hasattr(box, 'id') and box.id is not None:
                        track_id = int(box.id[0])
                        detection['track_id'] = track_id
                        
                        # Update track history for trail visualization
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        
                        if track_id not in self.track_history:
                            self.track_history[track_id] = []
                        
                        self.track_history[track_id].append((center_x, center_y))
                        
                        # Keep only last 30 points
                        if len(self.track_history[track_id]) > 30:
                            self.track_history[track_id].pop(0)
                    
                    detections.append(detection)
            
            return detections
            
        except Exception as e:
            print(f"❌ Error in detect_objects: {e}")
            return []
    
    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        show_trails: bool = True,
        show_track_id: bool = True
    ) -> np.ndarray:
        """
        Draw bounding boxes and tracking trails on frame
        
        Args:
            frame: Input image
            detections: List of detections from detect_objects()
            show_trails: Draw tracking trails
            show_track_id: Show track IDs in labels
        
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        
        for det in detections:
            x, y, w, h = det['bbox']
            x1, y1, x2, y2 = int(x), int(y), int(x + w), int(y + h)
            
            class_name = det['class']
            confidence = det['confidence']
            track_id = det.get('track_id')
            
            # Color based on track ID or class
            if track_id is not None:
                color = self._get_track_color(track_id)
            else:
                color = (0, 255, 0)  # Green for detections without tracking
            
            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            if show_track_id and track_id is not None:
                label = f"ID:{track_id} {class_name} {confidence:.2f}"
            else:
                label = f"{class_name} {confidence:.2f}"
            
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
            cv2.putText(
                annotated,
                label,
                (x1 + 3, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )
            
            # Draw tracking trail
            if show_trails and track_id is not None and track_id in self.track_history:
                points = self.track_history[track_id]
                if len(points) > 1:
                    for i in range(1, len(points)):
                        cv2.line(annotated, points[i-1], points[i], color, 2)
        
        return annotated
    
    def _get_track_color(self, track_id: int) -> tuple:
        """Generate consistent color for each track ID"""
        # Use hash to generate consistent RGB values
        np.random.seed(track_id)
        color = tuple(np.random.randint(50, 255, 3).tolist())
        np.random.seed()  # Reset seed
        return color
    
    def reset_tracking(self):
        """Reset tracking state (clear track history)"""
        self.track_history = {}
        self.frame_count = 0
    
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

