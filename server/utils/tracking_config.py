"""
Configuration loader for tracking settings
"""
import yaml
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class TrackingConfig:
    """Load and manage tracking configuration"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to config/tracking_config.yaml
            self.config_path = Path(__file__).parent.parent / "config" / "tracking_config.yaml"
        else:
            self.config_path = Path(config_path)
        
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            logger.warning(f"⚠️ Config file not found: {self.config_path}, using defaults")
            return self._get_default_config()
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"✅ Loaded tracking config from: {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"❌ Failed to load config: {e}, using defaults")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            'tracking': {
                'enabled': True,
                'tracker': 'bytetrack',
                'bytetrack': {
                    'track_high_thresh': 0.5,
                    'track_low_thresh': 0.1,
                    'new_track_thresh': 0.6,
                    'track_buffer': 30,
                    'match_thresh': 0.8,
                },
                'persist': True,
                'max_age': 30,
                'min_hits': 3,
            },
            'detection': {
                'conf_threshold': 0.25,
                'iou_threshold': 0.45,
                'max_det': 300,
                'classes': [2, 3, 5, 7],  # car, motorcycle, bus, truck
            },
            'performance': {
                'fps': 10,
                'skip_frames': 0,
                'use_half': True,
                'imgsz': 640,
                'workers': 4,
            },
            'visualization': {
                'show_boxes': True,
                'show_labels': True,
                'show_conf': True,
                'show_track_id': True,
                'show_trail': True,
                'trail_length': 30,
                'box_thickness': 2,
                'font_scale': 0.6,
            },
            'hardware': {
                'device': 'cuda',
                'batch_size': 1,
            },
            'logging': {
                'level': 'INFO',
                'log_detections': True,
                'log_tracks': True,
                'log_performance': True,
            }
        }
    
    def get(self, key_path: str, default=None):
        """
        Get configuration value by dot-separated key path
        
        Example:
            config.get('tracking.bytetrack.track_high_thresh', 0.5)
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    @property
    def tracking_enabled(self) -> bool:
        return self.get('tracking.enabled', True)
    
    @property
    def tracker_type(self) -> str:
        return self.get('tracking.tracker', 'bytetrack')
    
    @property
    def conf_threshold(self) -> float:
        return self.get('detection.conf_threshold', 0.25)
    
    @property
    def iou_threshold(self) -> float:
        return self.get('detection.iou_threshold', 0.45)
    
    @property
    def target_fps(self) -> int:
        return self.get('performance.fps', 10)
    
    @property
    def skip_frames(self) -> int:
        return self.get('performance.skip_frames', 0)
    
    @property
    def imgsz(self) -> int:
        return self.get('performance.imgsz', 640)
    
    @property
    def device(self) -> str:
        return self.get('hardware.device', 'cuda')
    
    def get_tracker_args(self) -> Dict[str, Any]:
        """Get tracker-specific arguments"""
        tracker = self.tracker_type
        
        if tracker == 'bytetrack':
            return {
                'tracker': 'bytetrack.yaml',
                'persist': self.get('tracking.persist', True),
                'conf': self.conf_threshold,
                'iou': self.iou_threshold,
            }
        elif tracker == 'botsort':
            return {
                'tracker': 'botsort.yaml',
                'persist': self.get('tracking.persist', True),
                'conf': self.conf_threshold,
                'iou': self.iou_threshold,
            }
        else:
            # Default tracker args
            return {
                'persist': True,
                'conf': self.conf_threshold,
                'iou': self.iou_threshold,
            }
    
    def print_summary(self):
        """Print configuration summary"""
        logger.info("=" * 50)
        logger.info("🎯 TRACKING CONFIGURATION")
        logger.info("=" * 50)
        logger.info(f"Tracking Enabled: {self.tracking_enabled}")
        logger.info(f"Tracker Type: {self.tracker_type}")
        logger.info(f"Confidence Threshold: {self.conf_threshold}")
        logger.info(f"IOU Threshold: {self.iou_threshold}")
        logger.info(f"Target FPS: {self.target_fps}")
        logger.info(f"Skip Frames: {self.skip_frames}")
        logger.info(f"Image Size: {self.imgsz}")
        logger.info(f"Device: {self.device}")
        
        if self.tracker_type == 'bytetrack':
            logger.info("ByteTrack Settings:")
            logger.info(f"  - Track High Thresh: {self.get('tracking.bytetrack.track_high_thresh')}")
            logger.info(f"  - Track Low Thresh: {self.get('tracking.bytetrack.track_low_thresh')}")
            logger.info(f"  - New Track Thresh: {self.get('tracking.bytetrack.new_track_thresh')}")
            logger.info(f"  - Track Buffer: {self.get('tracking.bytetrack.track_buffer')}")
        
        logger.info("=" * 50)


# Global config instance
_config_instance = None

def get_tracking_config() -> TrackingConfig:
    """Get singleton config instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = TrackingConfig()
    return _config_instance
