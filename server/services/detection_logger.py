"""
Detection Logger Service
Logs detection results to file for analysis and debugging
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import asyncio
from collections import deque

logger = logging.getLogger(__name__)


class DetectionLogger:
    """
    Logs detection results to .log files
    Thread-safe, async-friendly, buffered logging
    """
    
    def __init__(self, log_dir: str = "logs/detections", buffer_size: int = 100):
        """
        Initialize detection logger
        
        Args:
            log_dir: Directory to store log files
            buffer_size: Number of entries to buffer before flushing to disk
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Buffer for batch writing
        self.buffer: deque = deque(maxlen=buffer_size)
        self.buffer_size = buffer_size
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Current log file handles per camera
        self._log_files: Dict[str, Path] = {}
        
        logger.info(f"📝 Detection logger initialized: {self.log_dir}")
    
    def _get_log_file_path(self, camera_id: str) -> Path:
        """Get log file path for a camera (creates new file per day)"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"detection_{camera_id}_{today}.log"
    
    async def log_detection(
        self,
        camera_id: str,
        detections: List[Dict],
        parking_spaces: List[Dict],
        space_occupancy: Dict[str, bool],
        metadata: Dict = None
    ):
        """
        Log detection results for a camera
        
        Args:
            camera_id: Camera identifier
            detections: List of detected vehicles with bounding boxes
            parking_spaces: List of parking space definitions
            space_occupancy: Dict mapping space_id to occupied status
            metadata: Additional metadata (timestamp, frame size, etc.)
        """
        try:
            async with self._lock:
                # Prepare log entry
                timestamp = datetime.now().isoformat()
                
                log_entry = {
                    "timestamp": timestamp,
                    "camera_id": camera_id,
                    "summary": {
                        "vehicle_count": len(detections),
                        "total_spaces": len(parking_spaces),
                        "occupied_spaces": sum(space_occupancy.values()),
                        "available_spaces": len(parking_spaces) - sum(space_occupancy.values()),
                        "occupancy_rate": f"{(sum(space_occupancy.values()) / len(parking_spaces) * 100):.1f}%"
                            if parking_spaces else "0.0%"
                    },
                    "detections": [
                        {
                            "bbox": det.get("bbox", []),
                            "confidence": det.get("confidence", 0),
                            "class": det.get("class", "unknown")
                        }
                        for det in detections
                    ],
                    "space_occupancy": space_occupancy,
                    "metadata": metadata or {}
                }
                
                # Get log file path
                log_file = self._get_log_file_path(camera_id)
                
                # Write to file (append mode, one JSON per line)
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry) + '\n')
                
                logger.debug(f"📝 Logged detection for {camera_id}: {len(detections)} vehicles, "
                           f"{sum(space_occupancy.values())}/{len(parking_spaces)} occupied")
        
        except Exception as e:
            logger.error(f"Error logging detection for {camera_id}: {e}")
    
    async def log_detection_batch(self, entries: List[Dict]):
        """
        Log multiple detection entries at once (for batch processing)
        
        Args:
            entries: List of log entries (each with camera_id, detections, etc.)
        """
        try:
            async with self._lock:
                # Group by camera_id
                by_camera: Dict[str, List[Dict]] = {}
                for entry in entries:
                    camera_id = entry.get("camera_id")
                    if camera_id:
                        if camera_id not in by_camera:
                            by_camera[camera_id] = []
                        by_camera[camera_id].append(entry)
                
                # Write each camera's entries
                for camera_id, camera_entries in by_camera.items():
                    log_file = self._get_log_file_path(camera_id)
                    
                    with open(log_file, 'a', encoding='utf-8') as f:
                        for entry in camera_entries:
                            f.write(json.dumps(entry) + '\n')
                    
                    logger.debug(f"📝 Batch logged {len(camera_entries)} entries for {camera_id}")
        
        except Exception as e:
            logger.error(f"Error in batch logging: {e}")
    
    def get_log_stats(self) -> Dict:
        """Get statistics about log files"""
        stats = {
            "log_directory": str(self.log_dir),
            "log_files": [],
            "total_size_mb": 0
        }
        
        for log_file in self.log_dir.glob("detection_*.log"):
            file_size = log_file.stat().st_size
            line_count = sum(1 for _ in open(log_file, 'r'))
            
            stats["log_files"].append({
                "filename": log_file.name,
                "size_mb": file_size / (1024 * 1024),
                "entries": line_count,
                "modified": datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
            })
            stats["total_size_mb"] += file_size / (1024 * 1024)
        
        return stats
    
    async def read_latest_detections(self, camera_id: str, limit: int = 100) -> List[Dict]:
        """
        Read latest detection entries for a camera
        
        Args:
            camera_id: Camera identifier
            limit: Maximum number of entries to return
        
        Returns:
            List of detection entries (most recent first)
        """
        try:
            log_file = self._get_log_file_path(camera_id)
            
            if not log_file.exists():
                return []
            
            # Read last N lines efficiently
            with open(log_file, 'r', encoding='utf-8') as f:
                # Read all lines (for now - optimize later with tail if needed)
                lines = f.readlines()
            
            # Parse last N lines
            entries = []
            for line in lines[-limit:]:
                try:
                    entry = json.loads(line.strip())
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue
            
            # Return in reverse order (most recent first)
            return list(reversed(entries))
        
        except Exception as e:
            logger.error(f"Error reading detections for {camera_id}: {e}")
            return []
    
    def cleanup_old_logs(self, days: int = 7):
        """
        Delete log files older than specified days
        
        Args:
            days: Delete files older than this many days
        """
        try:
            import time
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            
            deleted_count = 0
            for log_file in self.log_dir.glob("detection_*.log"):
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    deleted_count += 1
                    logger.info(f"🗑️ Deleted old log file: {log_file.name}")
            
            if deleted_count > 0:
                logger.info(f"🗑️ Cleaned up {deleted_count} old log files")
        
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}")


# Global logger instance
detection_logger = DetectionLogger()
