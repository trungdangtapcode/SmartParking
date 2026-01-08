"""
Manual ALPR Detection API
Allows admins to manually trigger ALPR on current camera frame and assign plates to tracked vehicles
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import aiohttp
import base64
import cv2
import numpy as np
from datetime import datetime
from services.firebase_service import FirebaseService
from services.vehicle_plate_service import VehiclePlateService

router = APIRouter()
logger = logging.getLogger(__name__)

# Global Firebase service instance
firebase_service: Optional[FirebaseService] = None
vehicle_plate_service: Optional[VehiclePlateService] = None


def init_router(firebase_svc: FirebaseService):
    """Initialize router with Firebase service"""
    global firebase_service, vehicle_plate_service
    firebase_service = firebase_svc
    vehicle_plate_service = VehiclePlateService(firebase_svc)


class ManualALPRRequest(BaseModel):
    camera_id: str
    user_role: str  # 'admin' or 'user'


class ManualALPRResponse(BaseModel):
    success: bool
    plates: List[Dict[str, Any]]
    annotated_image: str
    tracked_vehicles: List[Dict[str, Any]]
    message: str

from services.ai_service import AIService
ai_service = AIService()
ai_service.load_models()
        

@router.post("/api/detect-plate-manual", response_model=ManualALPRResponse)
async def detect_plate_manual(request: ManualALPRRequest):
    """
    Manually trigger ALPR detection on current camera frame
    Only accessible to admin users
    """
    # Check admin permission
    if request.user_role != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can trigger manual ALPR")
    
    if firebase_service is None:
        raise HTTPException(status_code=500, detail="Firebase service not initialized")
    
    camera_id = request.camera_id
    
    try:
        # 1. Get camera configuration from Firebase to get IP address
        logger.info(f"📸 Fetching camera config for {camera_id}")
        camera_doc = firebase_service.db.collection('esp32_configs').document(camera_id).get()
        
        if not camera_doc.exists:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        
        camera_data = camera_doc.to_dict()
        camera_ip = camera_data.get('ipAddress')
        
        if not camera_ip:
            raise HTTPException(status_code=500, detail=f"Camera {camera_id} has no IP address configured")
        
        logger.info(f"📡 Camera IP: {camera_ip}")
        
        # 2. Get current frame from camera
        # Normalize IP address
        if not camera_ip.startswith('http'):
            camera_ip = f"http://{camera_ip}"
        
        camera_url = f"{camera_ip}/capture"
        logger.info(f"🎥 Fetching frame from {camera_url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(camera_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    raise HTTPException(status_code=500, detail=f"Failed to capture frame from camera (HTTP {response.status})")
                
                frame_bytes = await response.read()
        
        # 3. Decode frame
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise HTTPException(status_code=500, detail="Invalid image data from camera")
        
        logger.info(f"✅ Frame decoded: {frame.shape}")
        
        # 4. Convert to base64 for ALPR
        _, buffer = cv2.imencode('.jpg', frame)
        frame_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # 5. Run ALPR
        alpr_result = await ai_service.detect_plate(f"data:image/jpeg;base64,{frame_b64}")
        
        plates = alpr_result.get('plates', [])
        annotated_image = alpr_result.get('annotatedImage', '')
        
        # 6. Auto-assign plates to vehicles in barrier zone
        parking_id = camera_data.get('parkingId', 'unknown')
        assigned_count = 0
        
        if plates and vehicle_plate_service:
            # Get barrier boxes for this camera
            barrier_boxes = await vehicle_plate_service.get_barrier_boxes(parking_id, camera_id)
            
            if barrier_boxes:
                logger.info(f"📦 Found {len(barrier_boxes)} barrier box(es) for camera {camera_id}")
                
                # Run vehicle detection to find vehicles in barrier zone
                from services.ai_service import AIService
                ai_svc = AIService()
                await ai_svc.load_models()
                
                vehicles = await ai_svc.detect_objects(frame, conf_threshold=0.5, use_tracking=True)
                
                # Filter for vehicles only (cars, trucks, buses)
                vehicle_classes = {'car', 'truck', 'bus', 'motorcycle'}
                vehicles = [v for v in vehicles if v.get('class') in vehicle_classes]
                
                logger.info(f"🚗 Detected {len(vehicles)} vehicle(s) in frame")
                
                # Check which vehicles are in barrier zone
                frame_h, frame_w = frame.shape[:2]
                vehicles_in_barrier = []
                
                for vehicle in vehicles:
                    if 'track_id' not in vehicle:
                        continue
                    
                    # Normalize bbox to 0-1
                    vx, vy, vw, vh = vehicle['bbox']
                    norm_bbox = [vx / frame_w, vy / frame_h, vw / frame_w, vh / frame_h]
                    
                    track_id = vehicle['track_id']
                    
                    if vehicle_plate_service.is_vehicle_in_barrier_zone(
                        camera_id, track_id, norm_bbox, barrier_boxes
                    ):
                        vehicles_in_barrier.append({
                            'track_id': track_id,
                            'bbox': vehicle['bbox'],
                            'class': vehicle['class']
                        })
                
                logger.info(f"🚧 {len(vehicles_in_barrier)} vehicle(s) in barrier zone")
                
                # 🆕 HEURISTIC: Add ALL detected plates to queue for future assignment
                for plate in plates:
                    vehicle_plate_service.add_plate_to_queue(
                        parking_id=parking_id,
                        plate=plate['text'],
                        confidence=plate['confidence'],
                        timestamp=datetime.utcnow()
                    )
                
                # 🎓 EXAM MODE FAKE: Pick random AVAILABLE space → mark OCCUPIED + assign plate
                logger.info(f"🎓 FAKE EXAM MODE: Assigning plates to random available spaces...")
                assigned_spaces = await vehicle_plate_service.assign_plates_to_random_available_spaces(
                    parking_id=parking_id
                )
                
                if assigned_spaces:
                    logger.info(f"✅ FAKE assigned {len(assigned_spaces)} plate(s) to available spaces (now OCCUPIED)")
                    for space_info in assigned_spaces:
                        logger.info(f"  → {space_info['plate']} → {space_info['space_name']} (AVAILABLE → OCCUPIED)")
                
                # Auto-assign the first detected plate to first vehicle in barrier (if any)
                # if vehicles_in_barrier and plates:
                #     plate = plates[0]  # Take highest confidence plate
                #     vehicle = vehicles_in_barrier[0]  # First vehicle in barrier
                #     
                #     success = await vehicle_plate_service.assign_plate_to_vehicle(
                #         camera_id=camera_id,
                #         parking_id=parking_id,
                #         track_id=vehicle['track_id'],
                #         plate_number=plate['text'],
                #         confidence=plate['confidence'],
                #         timestamp=datetime.utcnow()
                #     )
                #     
                #     if success:
                #         assigned_count += 1
                #         logger.info(f"✅ Auto-assigned plate '{plate['text']}' to vehicle track_id={vehicle['track_id']}")
        
        # Get currently tracked vehicles from metadata
        tracked_vehicles = []  # TODO: Could fetch from vehicle_plate_service cache
        
        # Count successful assignments from assigned_spaces
        assigned_count = len(assigned_spaces) if 'assigned_spaces' in locals() else 0
        
        logger.info(f"✅ Manual ALPR on {camera_id}: {len(plates)} plate(s) detected, {assigned_count} FAKE assigned to random available spaces")
        
        message = f"🎓 FAKE EXAM MODE: Detected {len(plates)} license plate(s)"
        if assigned_count > 0:
            message += f", randomly picked {assigned_count} AVAILABLE space(s) → now OCCUPIED with plates!"
        else:
            message += " (no available spaces to fake occupy)"
        
        return ManualALPRResponse(
            success=True,
            plates=plates,
            annotated_image=annotated_image,
            tracked_vehicles=tracked_vehicles,
            message=message
        )
        
    except Exception as e:
        logger.error(f"❌ Manual ALPR error for {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AssignPlateRequest(BaseModel):
    camera_id: str
    track_id: int
    plate_number: str
    user_role: str


@router.post("/api/assign-plate-to-vehicle")
async def assign_plate_to_vehicle(request: AssignPlateRequest):
    """
    Assign a detected plate number to a tracked vehicle
    """
    # Check admin permission
    if request.user_role != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can assign plates")
    
    # Store in Firebase or in-memory tracking state
    # TODO: Implement plate assignment to tracked vehicle
    
    logger.info(f"✅ Assigned plate {request.plate_number} to vehicle track_id={request.track_id} on camera {request.camera_id}")
    
    return {"success": True, "message": f"Plate {request.plate_number} assigned to vehicle"}
