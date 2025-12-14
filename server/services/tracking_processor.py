"""
Real-time Object Tracking Processor
Multi-threaded processor for real-time tracking with YOLO + ByteTrack
- Producer thread: Continuously reads frames from video source
- Consumer thread: Processes frames with YOLO tracking
- Thread-safe with latest frame buffer (drops old frames for real-time performance)
"""
import cv2
import numpy as np
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from collections import deque


class TrackingProcessor:
    """
    Multi-threaded tracking processor for one camera stream.
    Implements Producer-Consumer pattern for real-time performance.
    """
    
    def __init__(
        self,
        video_source: str,
        yolo_model,
        camera_id: str,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        frame_skip: int = 1,
        resize_width: Optional[int] = None,
        max_fps: int = 30,
        barrier_zones: Optional[Dict] = None,
        plate_assigner=None
    ):
        """
        Initialize tracking processor.
        
        Args:
            video_source: Path to video file or camera index
            yolo_model: Loaded YOLO model instance
            camera_id: Unique identifier for this camera
            conf_threshold: Detection confidence threshold
            iou_threshold: IOU threshold for tracking
            frame_skip: Process every Nth frame (1 = all frames)
            resize_width: Resize frame width for processing (None = no resize)
            max_fps: Maximum FPS for output stream
            barrier_zones: Dict with entry/exit zones {'entry': {...}, 'exit': {...}} (optional)
            plate_assigner: PlateTrackAssigner instance for plate-to-track mapping (optional)
        """
        self.video_source = video_source
        self.model = yolo_model
        self.camera_id = camera_id
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.frame_skip = frame_skip
        self.resize_width = resize_width
        self.max_fps = max_fps
        self.frame_delay = 1.0 / max_fps
        
        # Barrier zones (entry & exit) loaded from Firestore
        # Format: {'entry': {'x', 'y', 'width', 'height'}, 'exit': {...}}
        self.barrier_zones = barrier_zones or {}
        if self.barrier_zones:
            print(f"✅ TrackingProcessor initialized with {len(self.barrier_zones)} barrier zone(s): {list(self.barrier_zones.keys())}")
        else:
            print(f"ℹ️  TrackingProcessor initialized without barrier zones")
        
        # Plate assignment service
        self.plate_assigner = plate_assigner
        
        # Thread control
        self.running = False
        self.producer_thread = None
        self.consumer_thread = None
        
        # Frame buffers (thread-safe with locks)
        self.latest_raw_frame = None
        self.latest_annotated_frame = None
        self.raw_frame_lock = threading.Lock()
        self.annotated_frame_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            "fps": 0,
            "objects_tracked": 0,
            "unique_tracks": set(),
            "latency_ms": 0,
            "frames_processed": 0,
            "frames_dropped": 0
        }
        self.stats_lock = threading.Lock()
        
        # FPS calculation
        self.fps_queue = deque(maxlen=30)  # Last 30 frame timestamps
        self.last_process_time = None
        
        # Vehicles in barrier zone (for plate assignment)
        self.barrier_vehicles: List[Dict] = []  # List of {track_id, bbox, confidence}
        self.barrier_vehicles_lock = threading.Lock()
        
        # VideoCapture (will be initialized in producer thread)
        self.cap = None
        self.video_width = 0
        self.video_height = 0
        self.video_fps = 30
    
    def start(self):
        """Start producer and consumer threads."""
        if self.running:
            print(f"⚠️  TrackingProcessor for {self.camera_id} is already running")
            return
        
        self.running = True
        
        # Start producer thread (reads frames)
        self.producer_thread = threading.Thread(
            target=self._producer_loop,
            daemon=True,
            name=f"Producer-{self.camera_id}"
        )
        self.producer_thread.start()
        
        # Start consumer thread (processes with YOLO)
        self.consumer_thread = threading.Thread(
            target=self._consumer_loop,
            daemon=True,
            name=f"Consumer-{self.camera_id}"
        )
        self.consumer_thread.start()
        
        print(f"✅ TrackingProcessor started for camera: {self.camera_id}")
    
    def stop(self):
        """Stop all threads and release resources."""
        if not self.running:
            return
        
        print(f"🛑 Stopping TrackingProcessor for {self.camera_id}...")
        self.running = False
        
        # Wait for threads to finish
        if self.producer_thread:
            self.producer_thread.join(timeout=2.0)
        if self.consumer_thread:
            self.consumer_thread.join(timeout=2.0)
        
        # Release video capture
        if self.cap:
            self.cap.release()
            self.cap = None
        
        print(f"✅ TrackingProcessor stopped for {self.camera_id}")
    
    def _producer_loop(self):
        """
        Producer thread: Continuously reads frames from video source.
        Only keeps the latest frame (drops old frames if consumer is busy).
        """
        try:
            # Open video source
            self.cap = cv2.VideoCapture(self.video_source)
            if not self.cap.isOpened():
                print(f"❌ Failed to open video source: {self.video_source}")
                self.running = False
                return
            
            # Get video properties
            self.video_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.video_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.video_fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30
            
            print(f"📹 Producer started: {self.video_width}x{self.video_height} @ {self.video_fps}fps")
            
            frame_count = 0
            while self.running:
                ret, frame = self.cap.read()
                
                # Loop video if ended
                if not ret:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                # Only update if this frame should be processed (frame_skip logic)
                if frame_count % self.frame_skip == 0:
                    # Update latest raw frame (thread-safe)
                    with self.raw_frame_lock:
                        self.latest_raw_frame = frame.copy()
                
                frame_count += 1
                
                # Control read speed (don't read faster than necessary)
                time.sleep(self.frame_delay)
        
        except Exception as e:
            print(f"❌ Producer error for {self.camera_id}: {e}")
            self.running = False
    
    def _consumer_loop(self):
        """
        Consumer thread: Processes frames with YOLO + ByteTrack.
        Takes latest frame, runs inference, and stores annotated frame.
        """
        try:
            print(f"🎯 Consumer started for {self.camera_id}")
            
            # Determine classes filter based on model type
            num_classes = len(self.model.names)
            is_custom_model = num_classes == 1
            
            if is_custom_model:
                classes_filter = None  # Detect all classes
                print(f"ℹ️  Custom model detected ({num_classes} class): detecting all classes")
            else:
                # COCO model: filter vehicle classes
                classes_filter = [2, 3, 5, 7]  # car, motorcycle, bus, truck
                print(f"ℹ️  COCO model detected ({num_classes} classes): filtering vehicles {classes_filter}")
            
            while self.running:
                # Get latest raw frame
                with self.raw_frame_lock:
                    if self.latest_raw_frame is None:
                        time.sleep(0.01)  # Wait for first frame
                        continue
                    frame = self.latest_raw_frame.copy()
                
                # Record start time for latency calculation
                start_time = time.time()
                
                # Resize frame if needed (for performance)
                process_frame = frame
                resize_scale = 1.0
                if self.resize_width and self.resize_width < frame.shape[1]:
                    resize_scale = self.resize_width / frame.shape[1]
                    new_height = int(frame.shape[0] * resize_scale)
                    process_frame = cv2.resize(frame, (self.resize_width, new_height))
                
                # Run YOLO tracking with ByteTrack
                track_kwargs = {
                    "persist": True,  # ByteTrack persistence
                    "conf": self.conf_threshold,
                    "iou": self.iou_threshold,
                    "verbose": False
                }
                if classes_filter is not None:
                    track_kwargs["classes"] = classes_filter
                
                results = self.model.track(process_frame, **track_kwargs)
                
                # Extract detections and track IDs
                detections = []
                unique_tracks = set()
                
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
                        
                        # Scale bbox back to original size if resized
                        if self.resize_width and self.resize_width < frame.shape[1]:
                            x1 = int(x1 / resize_scale)
                            y1 = int(y1 / resize_scale)
                            x2 = int(x2 / resize_scale)
                            y2 = int(y2 / resize_scale)
                        
                        track_id = int(tid) if tid >= 0 else None
                        
                        detections.append({
                            'bbox': [x1, y1, x2, y2],
                            'confidence': float(score),
                            'class': int(cls),
                            'class_name': str(self.model.names[int(cls)]),
                            'track_id': track_id
                        })
                        
                        if track_id is not None:
                            unique_tracks.add(track_id)
                            
                            # Check if vehicle is in barrier zone (entry or exit)
                            if self._is_in_barrier_zone([x1, y1, x2, y2]):
                                barrier_info = {
                                    'track_id': track_id,
                                    'bbox': [x1, y1, x2, y2],
                                    'confidence': float(score),
                                    'class_name': str(self.model.names[int(cls)])
                                }
                                # Store in barrier vehicles list (thread-safe)
                                with self.barrier_vehicles_lock:
                                    # Remove old entry for this track_id if exists
                                    self.barrier_vehicles = [v for v in self.barrier_vehicles 
                                                            if v['track_id'] != track_id]
                                    self.barrier_vehicles.append(barrier_info)
                
                # Draw annotations on original frame (full resolution)
                annotated_frame = self._draw_annotations(frame, detections)
                
                # Update annotated frame buffer (thread-safe)
                with self.annotated_frame_lock:
                    self.latest_annotated_frame = annotated_frame
                
                # Update statistics
                latency_ms = (time.time() - start_time) * 1000
                self._update_stats(len(detections), unique_tracks, latency_ms)
                
                # Small delay to prevent CPU overload
                time.sleep(0.001)
        
        except Exception as e:
            print(f"❌ Consumer error for {self.camera_id}: {e}")
            import traceback
            traceback.print_exc()
            self.running = False
    
    def _is_in_barrier_zone(self, bbox: List[int], zone_type: str = None) -> bool:
        """
        Check if bounding box center is in a barrier zone (entry or exit).
        
        Args:
            bbox: [x1, y1, x2, y2]
            zone_type: 'entry' or 'exit'. If None, check both zones.
        
        Returns:
            True if center of bbox is in the specified barrier zone(s)
        """
        if not self.barrier_zones:
            return False
        
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        # Check specific zone type or all zones
        zones_to_check = []
        if zone_type:
            if zone_type in self.barrier_zones:
                zones_to_check = [self.barrier_zones[zone_type]]
        else:
            zones_to_check = list(self.barrier_zones.values())
        
        # Check if center is in any of the zones
        for zone in zones_to_check:
            zone_x = zone['x']
            zone_y = zone['y']
            zone_width = zone['width']
            zone_height = zone['height']
            
            if (zone_x <= center_x <= zone_x + zone_width and
                zone_y <= center_y <= zone_y + zone_height):
                return True
        
        return False
    
    def get_vehicles_in_barrier_zone(self) -> List[Dict]:
        """
        Get list of vehicles currently in barrier zone.
        
        Returns:
            List of dicts with track_id, bbox, confidence, class_name
        """
        with self.barrier_vehicles_lock:
            return self.barrier_vehicles.copy()
    
    def _draw_barrier_zones(self, frame: np.ndarray):
        """
        Draw barrier zones (entry & exit) on the frame.
        
        Args:
            frame: Frame to draw on (modified in-place)
        """
        if not self.barrier_zones:
            return
        
        for zone_type, zone in self.barrier_zones.items():
            x = zone['x']
            y = zone['y']
            width = zone['width']
            height = zone['height']
            
            # Color: Green for entry, Red for exit
            if zone_type == 'entry':
                color = (0, 255, 0)  # Green
                label = "ENTRY ZONE"
            else:  # exit
                color = (0, 0, 255)  # Red
                label = "EXIT ZONE"
            
            # Draw semi-transparent rectangle
            overlay = frame.copy()
            cv2.rectangle(overlay, (x, y), (x + width, y + height), color, -1)
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
            
            # Draw border
            cv2.rectangle(frame, (x, y), (x + width, y + height), color, 3)
            
            # Draw label
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            label_x = x + 10
            label_y = y + 40
            
            # Label background
            cv2.rectangle(frame, 
                         (label_x - 5, label_y - label_size[1] - 5),
                         (label_x + label_size[0] + 5, label_y + 5),
                         color, -1)
            
            # Label text
            cv2.putText(frame, label, (label_x, label_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    def _draw_annotations(self, frame: np.ndarray, detections: list) -> np.ndarray:
        """
        Draw bounding boxes, track IDs, license plates, and labels on frame.
        
        Args:
            frame: Original frame
            detections: List of detection dicts
        
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        frame_height, frame_width = frame.shape[:2]
        
        # Draw barrier zones first (so they appear behind bounding boxes)
        self._draw_barrier_zones(annotated)
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            track_id = det['track_id']
            class_name = det['class_name']
            confidence = det['confidence']
            
            # Check if in barrier zone
            in_barrier = self._is_in_barrier_zone([x1, y1, x2, y2])
            
            # Get plate number if assigned
            plate = None
            if track_id is not None and self.plate_assigner:
                plate = self.plate_assigner.get_plate_for_track(track_id)
            
            # Color based on track ID (consistent color per ID)
            if track_id is not None:
                color = (
                    int((track_id * 50) % 255),
                    int((track_id * 100) % 255),
                    int((track_id * 150) % 255)
                )
            else:
                color = (0, 255, 0)
            
            # Draw bounding box (thicker if in barrier zone)
            thickness = 3 if in_barrier else 2
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
            
            # Draw labels (2 lines if plate exists)
            if plate:
                # Line 1: Plate number (larger, on top)
                plate_label = f"{plate}"
                (tw1, th1), _ = cv2.getTextSize(plate_label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cv2.rectangle(annotated, (x1, y1 - th1 - 35), (x1 + tw1 + 6, y1 - 28), color, -1)
                cv2.putText(
                    annotated,
                    plate_label,
                    (x1 + 3, y1 - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )
                
                # Line 2: Track ID + class (smaller, below)
                track_label = f"ID:{track_id} {class_name} {confidence:.2f}"
                (tw2, th2), _ = cv2.getTextSize(track_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(annotated, (x1, y1 - 28), (x1 + tw2 + 6, y1), color, -1)
                cv2.putText(
                    annotated,
                    track_label,
                    (x1 + 3, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )
            else:
                # Single line: Track ID + class
                label = f"ID:{track_id} {class_name}" if track_id is not None else class_name
                label += f" {confidence:.2f}"
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
            
            # Draw "BARRIER" indicator if in zone
            if in_barrier:
                cv2.putText(
                    annotated,
                    "BARRIER",
                    (x1, y2 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 255),
                    2
                )
        
        # Draw statistics overlay
        self._draw_stats_overlay(annotated)
        
        return annotated
    
    def _draw_stats_overlay(self, frame: np.ndarray):
        """Draw statistics overlay on top-left corner."""
        with self.stats_lock:
            fps = self.stats['fps']
            objects = self.stats['objects_tracked']
            unique = len(self.stats['unique_tracks'])
            latency = self.stats['latency_ms']
        
        # Background box
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (250, 110), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        # Text
        y_offset = 30
        cv2.putText(frame, f"FPS: {fps:.1f}", (20, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        y_offset += 25
        cv2.putText(frame, f"Objects: {objects}", (20, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        y_offset += 25
        cv2.putText(frame, f"Unique IDs: {unique}", (20, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        y_offset += 25
        cv2.putText(frame, f"Latency: {latency:.0f}ms", (20, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    def _update_stats(self, objects_count: int, unique_tracks: set, latency_ms: float):
        """Update statistics (thread-safe)."""
        current_time = time.time()
        
        with self.stats_lock:
            self.stats['objects_tracked'] = objects_count
            self.stats['unique_tracks'].update(unique_tracks)
            self.stats['latency_ms'] = latency_ms
            self.stats['frames_processed'] += 1
            
            # Calculate FPS
            if self.last_process_time:
                self.fps_queue.append(current_time)
                if len(self.fps_queue) > 1:
                    time_span = self.fps_queue[-1] - self.fps_queue[0]
                    if time_span > 0:
                        self.stats['fps'] = len(self.fps_queue) / time_span
            
            self.last_process_time = current_time
    
    def get_latest_annotated(self) -> Optional[np.ndarray]:
        """
        Get latest annotated frame (thread-safe).
        
        Returns:
            Annotated frame or None if not available
        """
        with self.annotated_frame_lock:
            if self.latest_annotated_frame is not None:
                return self.latest_annotated_frame.copy()
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current statistics (thread-safe).
        
        Returns:
            Dictionary with statistics
        """
        with self.stats_lock:
            return {
                'fps': self.stats['fps'],
                'objects_tracked': self.stats['objects_tracked'],
                'unique_tracks_count': len(self.stats['unique_tracks']),
                'latency_ms': self.stats['latency_ms'],
                'frames_processed': self.stats['frames_processed'],
                'frames_dropped': self.stats['frames_dropped']
            }
    
    def is_running(self) -> bool:
        """Check if processor is running."""
        return self.running
