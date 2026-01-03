"""
Health check and debugging endpoints
"""
from fastapi import APIRouter
import time

router = APIRouter()

# Will be set by main app
ai_service = None
firebase_service = None
ESP32_URL = None

def init_router(ai_svc, firebase_svc, esp32_url):
    """Initialize router with service instances"""
    global ai_service, firebase_service, ESP32_URL
    ai_service = ai_svc
    firebase_service = firebase_svc
    ESP32_URL = esp32_url

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "smartparking-api",
        "models_loaded": ai_service is not None,
        "firebase_connected": firebase_service is not None,
        "esp32_url": ESP32_URL
    }

@router.get("/debug/streams")
async def debug_active_streams():
    """Debug endpoint to view active streams"""
    from models.stream_tracking import active_streams
    
    streams = []
    for stream in active_streams:
        streams.append({
            "stream_id": stream.stream_id,
            "is_alive": stream.is_alive,
            "age_seconds": time.time() - stream.created_at
        })
    return {
        "active_count": len(streams),
        "streams": streams
    }
