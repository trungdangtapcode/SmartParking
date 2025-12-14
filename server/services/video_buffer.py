"""
Video buffer manager: lưu last frame cho mỗi nguồn video file.
"""
import threading
import time
from typing import Dict, Optional, Tuple

import numpy as np


class VideoBufferManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._frames: Dict[str, Tuple[np.ndarray, float]] = {}  # key: file name, value: (frame, timestamp_ms)

    def update_frame(self, key: str, frame: np.ndarray) -> None:
        """Lưu last frame (copy) kèm timestamp hiện tại (ms)."""
        if frame is None:
            return
        with self._lock:
            self._frames[key] = (frame.copy(), time.time() * 1000.0)

    def get_frame(self, key: str) -> Optional[np.ndarray]:
        """Lấy bản copy frame mới nhất cho key; nếu không có trả None."""
        with self._lock:
            item = self._frames.get(key)
            if item is None:
                return None
            frame, _ = item
            return frame.copy()

