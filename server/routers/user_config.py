"""
User ESP32 configuration endpoints
"""
from fastapi import APIRouter, HTTPException, Header

router = APIRouter(prefix="/api/user", tags=["User Configuration"])

# Will be set by main app
firebase_service = None

def init_router(firebase_svc):
    """Initialize router with service instances"""
    global firebase_service
    firebase_service = firebase_svc

@router.post("/esp32-config")
async def save_esp32_config(
    request: dict,
    user_id: str = Header(..., alias="X-User-ID")
):
    """
    Save user's ESP32-CAM configuration
    
    Headers:
        X-User-ID: Firebase user ID (from authentication)
    
    Body:
        {
            "esp32_url": "http://192.168.1.100:81",
            "label": "Main Entrance Camera" (optional)
        }
    """
    if not firebase_service:
        raise HTTPException(status_code=503, detail="Firebase not available")
    
    try:
        esp32_url = request.get("esp32_url")
        label = request.get("label")
        
        if not esp32_url:
            raise HTTPException(status_code=400, detail="esp32_url is required")
        
        # Validate URL format (basic check)
        if not esp32_url.startswith(("http://", "https://")):
            esp32_url = f"http://{esp32_url}"
        
        # Remove trailing slash
        esp32_url = esp32_url.rstrip('/')
        
        success = await firebase_service.save_user_esp32_config(user_id, esp32_url, label)
        
        if success:
            return {
                "success": True,
                "message": "ESP32 configuration saved",
                "esp32_url": esp32_url,
                "label": label
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error saving ESP32 config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/esp32-config")
async def get_esp32_config(user_id: str = Header(..., alias="X-User-ID")):
    """
    Get user's ESP32-CAM configuration
    
    Headers:
        X-User-ID: Firebase user ID
    """
    if not firebase_service:
        raise HTTPException(status_code=503, detail="Firebase not available")
    
    try:
        config = await firebase_service.get_user_esp32_config(user_id)
        
        if config:
            return {
                "success": True,
                "config": config
            }
        else:
            return {
                "success": True,
                "config": None,
                "message": "No configuration found. Please set up your ESP32-CAM."
            }
            
    except Exception as e:
        print(f"❌ Error getting ESP32 config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/esp32-config")
async def delete_esp32_config(user_id: str = Header(..., alias="X-User-ID")):
    """
    Delete user's ESP32-CAM configuration
    
    Headers:
        X-User-ID: Firebase user ID
    """
    if not firebase_service:
        raise HTTPException(status_code=503, detail="Firebase not available")
    
    try:
        success = await firebase_service.delete_user_esp32_config(user_id)
        
        if success:
            return {
                "success": True,
                "message": "ESP32 configuration deleted"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete configuration")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting ESP32 config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
