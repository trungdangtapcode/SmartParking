"""
ESP32 hardware endpoints (snapshot, status, test)
"""
from fastapi import APIRouter, HTTPException
import aiohttp
import base64

router = APIRouter(prefix="/api/esp32", tags=["ESP32 Hardware"])

# Will be set by main app
esp32_client = None

def init_router(esp32_cli):
    """Initialize router with service instances"""
    global esp32_client
    esp32_client = esp32_cli

@router.get("/snapshot")
async def get_esp32_snapshot():
    """Capture single frame from ESP32-CAM"""
    try:
        async with esp32_client as client:
            frame_bytes = await client.capture_frame()
            image_b64 = base64.b64encode(frame_bytes).decode('utf-8')
            
            return {
                "success": True,
                "imageData": f"data:image/jpeg;base64,{image_b64}"
            }
            
    except Exception as e:
        print(f"❌ Snapshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_esp32_status():
    """Get ESP32-CAM status"""
    try:
        async with esp32_client as client:
            status = await client.get_status()
            return {"success": True, **status}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/test")
async def test_esp32_connection():
    """Test connection with ESP32-CAM"""
    try:
        async with esp32_client as client:
            result = await client.test_connection()
            return result
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "message": "Cannot connect to ESP32. Check configuration and network."
        }
