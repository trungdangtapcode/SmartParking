"""
AI detection endpoints (plate detection, object tracking)
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["AI Detection"])

# Will be set by main app
ai_service = None
firebase_service = None

def init_router(ai_svc, firebase_svc):
    """Initialize router with service instances"""
    global ai_service, firebase_service
    ai_service = ai_svc
    firebase_service = firebase_svc

@router.post("/plate-detect")
async def detect_license_plate(request: dict):
    """
    Detect license plate from image
    Input: { "imageData": "data:image/jpeg;base64,..." }
    """
    try:
        image_data = request.get("imageData")
        if not image_data:
            raise HTTPException(status_code=400, detail="imageData is required")
        
        print(f"📥 Received plate detection request")
        
        result = await ai_service.detect_plate(image_data)
        
        # Save to Firebase
        if result.get("plates"):
            await firebase_service.save_plate_detection(result)
        
        print(f"✅ Detected {len(result.get('plates', []))} plates")
        return {"success": True, **result}
        
    except Exception as e:
        print(f"❌ Plate detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/object-tracking")
async def track_objects(request: dict):
    """
    Track objects in video
    Input: { "videoData": "data:video/mp4;base64,..." }
    """
    try:
        video_data = request.get("videoData")
        if not video_data:
            raise HTTPException(status_code=400, detail="videoData is required")
        
        # Optional parameters
        frame_skip = request.get("frameSkip", 1)
        conf_threshold = request.get("confThreshold", 0.25)
        iou_threshold = request.get("iouThreshold", 0.45)
        
        print(f"📥 Received tracking request")
        
        result = await ai_service.track_objects(
            video_data,
            frame_skip=frame_skip,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold
        )
        
        # Save to Firebase
        if result.get("success"):
            await firebase_service.save_tracking_result(result)
        
        print(f"✅ Tracking completed: {result.get('unique_tracks', 0)} unique tracks")
        return result
        
    except Exception as e:
        print(f"❌ Tracking error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
