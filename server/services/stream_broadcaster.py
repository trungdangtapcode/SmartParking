"""
Stream Broadcaster Service
Implements synchronized broadcast streaming (like YouTube Live)

Architecture:
- Single reader fetches frames from ESP32
- Multiple clients subscribe to the same frame feed
- All clients see the same frame ID at the same time
- Handles client connect/disconnect gracefully
"""
import asyncio
import aiohttp
import cv2
import numpy as np
from typing import Dict, Set, Optional, Tuple
import time
from dataclasses import dataclass
import uuid

@dataclass
class StreamFrame:
    """Represents a single frame in the broadcast"""
    frame_id: int
    jpeg_data: bytes
    timestamp: float
    annotated_data: Optional[bytes] = None  # For detection stream

class StreamBroadcaster:
    """
    Broadcasts a single stream to multiple clients
    Similar to YouTube Live - everyone sees the same frame at the same time
    """
    
    def __init__(self, stream_url: str, broadcaster_id: str = None):
        self.stream_url = stream_url
        self.broadcaster_id = broadcaster_id or str(uuid.uuid4())[:8]
        
        # Subscribers
        self.raw_subscribers: Set[asyncio.Queue] = set()
        self.detect_subscribers: Set[asyncio.Queue] = set()
        
        # Current frame
        self.current_frame: Optional[StreamFrame] = None
        self.frame_lock = asyncio.Lock()
        
        # Reader task
        self.reader_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Stats
        self.frames_read = 0
        self.start_time = time.time()
        
        print(f"📡 [Broadcaster {self.broadcaster_id}] Created for: {stream_url}")
    
    async def start(self):
        """Start the broadcaster (single reader thread)"""
        if self.is_running:
            return
        
        self.is_running = True
        self.reader_task = asyncio.create_task(self._read_stream())
        print(f"▶️  [Broadcaster {self.broadcaster_id}] Started")
    
    async def stop(self):
        """Stop the broadcaster"""
        self.is_running = False
        
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
        
        # Close all subscriber queues
        for queue in list(self.raw_subscribers):
            queue.put_nowait(None)  # Signal end
        for queue in list(self.detect_subscribers):
            queue.put_nowait(None)
        
        self.raw_subscribers.clear()
        self.detect_subscribers.clear()
        
        print(f"⏹️  [Broadcaster {self.broadcaster_id}] Stopped")
    
    async def subscribe_raw(self) -> asyncio.Queue:
        """Subscribe to raw stream (returns queue that receives frames)"""
        queue = asyncio.Queue(maxsize=5)  # Buffer up to 5 frames
        self.raw_subscribers.add(queue)
        
        # Send current frame immediately if available
        if self.current_frame:
            try:
                queue.put_nowait(self.current_frame)
            except asyncio.QueueFull:
                pass
        
        print(f"➕ [Broadcaster {self.broadcaster_id}] Raw subscriber added (total: {len(self.raw_subscribers)})")
        return queue
    
    async def subscribe_detect(self) -> asyncio.Queue:
        """Subscribe to detection stream"""
        queue = asyncio.Queue(maxsize=5)
        self.detect_subscribers.add(queue)
        
        if self.current_frame and self.current_frame.annotated_data:
            try:
                queue.put_nowait(self.current_frame)
            except asyncio.QueueFull:
                pass
        
        print(f"➕ [Broadcaster {self.broadcaster_id}] Detect subscriber added (total: {len(self.detect_subscribers)})")
        return queue
    
    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe a client"""
        self.raw_subscribers.discard(queue)
        self.detect_subscribers.discard(queue)
        
        total_subs = len(self.raw_subscribers) + len(self.detect_subscribers)
        print(f"➖ [Broadcaster {self.broadcaster_id}] Subscriber removed (total: {total_subs})")
    
    def has_subscribers(self) -> bool:
        """Check if broadcaster has any active subscribers"""
        return len(self.raw_subscribers) > 0 or len(self.detect_subscribers) > 0
    
    async def _read_stream(self):
        """
        Main reader loop - reads from ESP32 and broadcasts to all subscribers
        This is the SINGLE reader thread that all clients share
        """
        buffer = b""
        session = None
        response = None
        
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_read=30)
            session = aiohttp.ClientSession(timeout=timeout)
            response = await session.get(self.stream_url)
            
            if response.status != 200:
                print(f"❌ [Broadcaster {self.broadcaster_id}] ESP32 unavailable: {response.status}")
                return
            
            print(f"✅ [Broadcaster {self.broadcaster_id}] Connected to ESP32")
            
            async for chunk in response.content.iter_chunked(1024):
                if not self.is_running:
                    break
                
                buffer += chunk
                
                # Extract all frames
                while True:
                    start = buffer.find(b'\xff\xd8')
                    end = buffer.find(b'\xff\xd9')
                    
                    if start != -1 and end != -1 and end > start:
                        jpeg_data = buffer[start:end+2]
                        buffer = buffer[end+2:]
                        self.frames_read += 1
                        
                        # Create frame object
                        frame = StreamFrame(
                            frame_id=self.frames_read,
                            jpeg_data=jpeg_data,
                            timestamp=time.time()
                        )
                        
                        # Store as current frame
                        async with self.frame_lock:
                            self.current_frame = frame
                        
                        # Broadcast to all raw subscribers
                        await self._broadcast_frame(frame, self.raw_subscribers)
                        
                        # Log periodically
                        if self.frames_read % 100 == 0:
                            elapsed = time.time() - self.start_time
                            fps = self.frames_read / elapsed if elapsed > 0 else 0
                            print(f"📊 [Broadcaster {self.broadcaster_id}] "
                                  f"Frame {self.frames_read} | "
                                  f"FPS: {fps:.1f} | "
                                  f"Subs: {len(self.raw_subscribers)}R + {len(self.detect_subscribers)}D")
                    else:
                        break
        
        except Exception as e:
            print(f"❌ [Broadcaster {self.broadcaster_id}] Read error: {e}")
        finally:
            if response:
                response.close()
            if session:
                await session.close()
            
            # Notify all subscribers that stream ended
            for queue in list(self.raw_subscribers):
                try:
                    queue.put_nowait(None)
                except:
                    pass
            for queue in list(self.detect_subscribers):
                try:
                    queue.put_nowait(None)
                except:
                    pass
    
    async def _broadcast_frame(self, frame: StreamFrame, subscribers: Set[asyncio.Queue]):
        """Broadcast frame to all subscribers (non-blocking)"""
        dead_queues = set()
        
        for queue in subscribers:
            try:
                # Non-blocking put - drop frame if queue is full
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                # Client is too slow - skip this frame for them
                pass
            except Exception:
                # Queue is closed or broken
                dead_queues.add(queue)
        
        # Remove dead subscribers
        for queue in dead_queues:
            subscribers.discard(queue)


class BroadcastManager:
    """
    Manages multiple broadcasters for different ESP32 sources
    Ensures only ONE broadcaster per ESP32 URL
    """
    
    def __init__(self):
        self.broadcasters: Dict[str, StreamBroadcaster] = {}
        self.lock = asyncio.Lock()
    
    async def get_broadcaster(self, stream_url: str) -> StreamBroadcaster:
        """Get or create broadcaster for a stream URL"""
        async with self.lock:
            if stream_url not in self.broadcasters:
                # Create new broadcaster
                broadcaster = StreamBroadcaster(stream_url)
                await broadcaster.start()
                self.broadcasters[stream_url] = broadcaster
            
            return self.broadcasters[stream_url]
    
    async def cleanup_inactive(self):
        """Remove broadcasters with no subscribers"""
        async with self.lock:
            inactive = []
            
            for url, broadcaster in self.broadcasters.items():
                if not broadcaster.has_subscribers():
                    inactive.append(url)
                    await broadcaster.stop()
            
            for url in inactive:
                del self.broadcasters[url]
                print(f"🧹 [BroadcastManager] Removed inactive broadcaster: {url}")
    
    async def cleanup_all(self):
        """Stop all broadcasters"""
        async with self.lock:
            for broadcaster in self.broadcasters.values():
                await broadcaster.stop()
            self.broadcasters.clear()
            print(f"🧹 [BroadcastManager] All broadcasters stopped")


# Global broadcast manager
broadcast_manager = BroadcastManager()
