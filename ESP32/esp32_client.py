"""
ESP32-CAM Client - Template for real ESP32 integration
Use this to connect to actual ESP32-CAM or mock server
"""
import aiohttp
from typing import AsyncGenerator, Optional
import asyncio

class ESP32Client:
    """Client for ESP32-CAM communication"""
    
    def __init__(self, base_url: str = "http://localhost:5069"):
        """
        Initialize ESP32 client
        
        Args:
            base_url: ESP32-CAM base URL (default: "http://localhost:5069")
                     For real ESP32: "http://192.168.33.122:81"
                     For mock: "http://localhost:8081"
        """
        self.base_url = base_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, sock_read=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def test_connection(self) -> dict:
        """Test connection to ESP32-CAM"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(f"{self.base_url}/", timeout=aiohttp.ClientTimeout(total=5)) as response:
                status = response.status
                return {
                    "connected": status == 200,
                    "status_code": status,
                    "url": self.base_url
                }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "url": self.base_url
            }
    
    async def get_status(self) -> dict:
        """Get ESP32-CAM status"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(f"{self.base_url}/status") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Status code: {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def capture_frame(self) -> bytes:
        """
        Capture single frame from ESP32-CAM
        
        Returns:
            JPEG image bytes
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        async with self.session.get(f"{self.base_url}/capture") as response:
            if response.status != 200:
                raise Exception(f"Capture failed: {response.status}")
            return await response.read()
    
    async def stream_frames(self) -> AsyncGenerator[bytes, None]:
        """
        Stream MJPEG frames from ESP32-CAM
        
        Yields:
            JPEG frame bytes
        """
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=None, sock_read=30)
            )
        
        async with self.session.get(f"{self.base_url}/stream") as response:
            if response.status != 200:
                raise Exception(f"Stream failed: {response.status}")
            
            # Read MJPEG stream
            buffer = b""
            async for chunk in response.content.iter_chunked(1024):
                buffer += chunk
                
                # Find frame boundaries
                while True:
                    start = buffer.find(b'\xff\xd8')  # JPEG start marker
                    end = buffer.find(b'\xff\xd9')    # JPEG end marker
                    
                    if start != -1 and end != -1 and end > start:
                        # Extract frame
                        frame = buffer[start:end+2]
                        buffer = buffer[end+2:]
                        yield frame
                    else:
                        break
    
    async def control(self, command: dict) -> dict:
        """
        Send control command to ESP32-CAM
        
        Args:
            command: Control command dict
                Examples:
                - {"action": "set_quality", "quality": 90}
                - {"action": "set_resolution", "resolution": "800x600"}
        
        Returns:
            Response dict
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        async with self.session.post(
            f"{self.base_url}/control",
            json=command
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": f"Control failed: {response.status}"}


# ========== Usage Examples ==========

async def example_test_connection():
    """Example: Test ESP32 connection"""
    # Default: Backend proxy at port 5069
    client = ESP32Client()  # Uses default: http://localhost:5069
    
    # Or specify URL:
    # client = ESP32Client("http://localhost:8081")  # Mock
    # client = ESP32Client("http://192.168.33.122:81")  # Real ESP32
    
    async with client:
        result = await client.test_connection()
        print(f"Connection test: {result}")

async def example_capture():
    """Example: Capture single frame"""
    async with ESP32Client() as client:  # Uses default port 5069
        frame_bytes = await client.capture_frame()
        
        # Save to file
        with open("capture.jpg", "wb") as f:
            f.write(frame_bytes)
        
        print(f"Captured {len(frame_bytes)} bytes")

async def example_stream():
    """Example: Stream frames"""
    async with ESP32Client() as client:  # Uses default port 5069
        frame_count = 0
        async for frame in client.stream_frames():
            frame_count += 1
            print(f"Frame {frame_count}: {len(frame)} bytes")
            
            # Process first 10 frames
            if frame_count >= 10:
                break

async def example_control():
    """Example: Control ESP32"""
    async with ESP32Client() as client:  # Uses default port 5069
        # Set quality
        result = await client.control({"action": "set_quality", "quality": 90})
        print(f"Control result: {result}")
        
        # Get status
        status = await client.get_status()
        print(f"Status: {status}")

if __name__ == "__main__":
    # Run examples
    print("Testing ESP32 Client...")
    asyncio.run(example_test_connection())
