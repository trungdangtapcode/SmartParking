"""
Firebase API endpoints (history, detections)
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/firebase", tags=["Firebase"])

# Will be set by main app
firebase_service = None

def init_router(firebase_svc):
    """Initialize router with service instances"""
    global firebase_service
    firebase_service = firebase_svc

@router.get("/detections")
async def get_detections(limit: int = 50):
    """Get detection history from Firebase"""
    try:
        detections = await firebase_service.get_detections(limit=limit)
        return {"success": True, "detections": detections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/plates")
async def get_plate_history(limit: int = 50):
    """Get plate detection history"""
    try:
        plates = await firebase_service.get_plate_history(limit=limit)
        return {"success": True, "plates": plates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
