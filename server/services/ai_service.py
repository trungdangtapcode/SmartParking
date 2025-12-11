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

from services.alpr_service import ALPRService

# Import AI libraries
try:
    from ultralytics import YOLO
except ImportError as e:
    print(f"❌ Missing AI libraries: {e}")
    print("Run: pip install ultralytics opencv-python")
    raise


class AIService:
    """AI Service quản lý YOLO và ALPR models"""
    
    def __init__(self):
        self.yolo_model = None
        self.models_loaded = False
        self.alpr_service = ALPRService()
        
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
        
        # Load ALPR model (delegate)
        await self.alpr_service.load_model()
        
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
        
        return await self.alpr_service.detect_plate(image_data)

    async def detect_plate_from_video_file(
        self,
        video_path: Path,
        time_ms: Optional[float] = None,
        frame_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Lấy 1 frame từ video file tại time_ms hoặc frame_index rồi chạy ALPR.
        """
        if not self.models_loaded:
            await self.load_models()

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        try:
            if time_ms is not None:
                cap.set(cv2.CAP_PROP_POS_MSEC, float(time_ms))
            elif frame_index is not None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))

            ret, frame = cap.read()
            if not ret or frame is None:
                raise ValueError("Failed to read frame from video")

            return await self.alpr_service.detect_plate_from_frame(frame)
        finally:
            cap.release()
    
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

