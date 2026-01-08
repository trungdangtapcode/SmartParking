"""
Test ALPR functionality with a sample image
"""
import asyncio
import cv2
import base64
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from services.ai_service import AIService


async def test_alpr():
    """Test ALPR with the provided image"""
    
    # Load the test image
    image_path = "/mnt/mmlab2024nas/vund/.svn/bin/image.png"
    
    print(f"🔍 Loading test image: {image_path}")
    
    # Check if file exists
    if not Path(image_path).exists():
        print(f"❌ Error: File not found at {image_path}")
        return
    
    # Read image
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"❌ Error: Could not read image from {image_path}")
        return
    
    print(f"✅ Image loaded: {frame.shape[1]}x{frame.shape[0]} pixels")
    
    # Initialize AI service
    print("🤖 Initializing AI models...")
    ai_service = AIService()
    await ai_service.load_models()
    
    # STEP 1: Detect vehicles first
    print("\n" + "="*60)
    print("🚗 STEP 1: Detecting vehicles in frame...")
    print("="*60)
    
    vehicle_detections = await ai_service.detect_objects(
        frame=frame,
        conf_threshold=0.3,
        iou_threshold=0.45,
        use_tracking=False
    )
    
    vehicle_classes = {'car', 'truck', 'bus', 'motorcycle'}
    vehicles = [d for d in vehicle_detections if d.get('class') in vehicle_classes]
    
    print(f"📊 Found {len(vehicles)} vehicle(s)")
    for idx, vehicle in enumerate(vehicles, 1):
        print(f"   Vehicle #{idx}: {vehicle.get('class')} (conf: {vehicle.get('confidence', 0):.1%})")
    
    if len(vehicles) == 0:
        print("\n⚠️  NO VEHICLES DETECTED - Skipping ALPR (as per real system logic)")
        print("💡 ALPR only runs when vehicles are present to avoid false positives")
        return
    
    # STEP 2: Run ALPR only if vehicles present
    print("\n" + "="*60)
    print("🚗 STEP 2: Running ALPR (vehicles detected)...")
    print("="*60)
    
    # Convert to base64
    _, buffer = cv2.imencode('.jpg', frame)
    frame_b64 = base64.b64encode(buffer).decode('utf-8')
    
    # Run ALPR
    result = await ai_service.detect_plate(f"data:image/jpeg;base64,{frame_b64}")
    
    raw_plates = result.get('plates', [])
    print(f"📊 ALPR raw results: {len(raw_plates)} plate(s)")
    
    # Apply same filtering as worker
    filtered_plates = []
    for plate in raw_plates:
        text = plate.get('text', '')
        confidence = plate.get('confidence', 0)
        
        if confidence < 0.7:  # 70% threshold
            print(f"   🚫 Filtered low confidence: '{text}' ({confidence:.1%})")
            continue
        
        filtered_plates.append(plate)
    
    print(f"\n{'='*60}")
    print(f"📊 FINAL RESULTS: {len(filtered_plates)} plate(s) after filtering")
    print(f"{'='*60}")
    
    if filtered_plates:
        for idx, plate in enumerate(filtered_plates, 1):
            text = plate.get('text', '')
            confidence = plate.get('confidence', 0)
            bbox = plate.get('bbox', [])
            
            print(f"\n🎯 Plate #{idx}:")
            print(f"   Text: '{text}'")
            print(f"   Confidence: {confidence:.2%}")
            print(f"   BBox: {bbox}")
    else:
        print("\n✅ No valid plates (after filtering)")
    
    # Save annotated image
    annotated_b64 = result.get('annotatedImage', '')
    if annotated_b64.startswith('data:image/png;base64,'):
        annotated_b64 = annotated_b64.split(',')[1]
    
    annotated_bytes = base64.b64decode(annotated_b64)
    output_path = "/mnt/mmlab2024nas/vund/.svn/bin/server/test_alpr_output.jpg"
    with open(output_path, 'wb') as f:
        f.write(annotated_bytes)
    
    print(f"\n💾 Annotated image saved to: {output_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(test_alpr())
