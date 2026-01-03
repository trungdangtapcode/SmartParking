"""
Stream connection tracking models
"""
import time
import weakref

# Global stream registry to track active streams
active_streams = weakref.WeakSet()

class StreamConnection:
    """Track individual stream connection"""
    def __init__(self, stream_id: str):
        self.stream_id = stream_id
        self.is_alive = True
        self.created_at = time.time()
        active_streams.add(self)
    
    def stop(self):
        """Mark this stream as dead"""
        self.is_alive = False
        print(f"🛑 Stream {self.stream_id} marked for termination")
    
    def __str__(self):
        age = time.time() - self.created_at
        return f"Stream({self.stream_id}, alive={self.is_alive}, age={age:.1f}s)"
