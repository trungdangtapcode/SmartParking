"""Simple HTTP stream viewer with YOLO detection - no tracking."""
import cv2
import numpy as np
import torch
from ultralytics import YOLO
import urllib.request
import time

def read_http_frame(stream, stream_bytes):
    """Read a single frame from HTTP MJPEG stream."""
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                return False, None, stream_bytes
            stream_bytes += chunk
            a = stream_bytes.find(b'\xff\xd8')  # JPEG start
            b = stream_bytes.find(b'\xff\xd9')  # JPEG end
            if a != -1 and b != -1:
                jpg = stream_bytes[a:b+2]
                stream_bytes = stream_bytes[b+2:]
                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    return True, frame, stream_bytes
    except Exception as e:
        print(f"Error reading stream: {e}")
        return False, None, stream_bytes

def main():
    # Load YOLO model
    print("Loading YOLO model...")
    model = YOLO('yolov8s.pt')
    model.to('cuda:0')
    
    # Open HTTP streams
    streams = [
        {'url': 'http://localhost:5069/stream', 'name': 'cam_1'},
        {'url': 'http://localhost:5070/stream', 'name': 'cam_2'},
    ]
    
    for s in streams:
        try:
            s['stream'] = urllib.request.urlopen(s['url'], timeout=10)
            s['bytes'] = b''
            print(f"✓ Opened {s['name']}: {s['url']}")
        except Exception as e:
            print(f"✗ Failed to open {s['name']}: {e}")
            s['stream'] = None
    
    print("\nStarting detection... Press 'q' to quit")
    
    frame_count = 0
    last_time = time.time()
    
    try:
        while True:
            for s in streams:
                if s['stream'] is None:
                    continue
                
                # Read frame
                ret, frame, s['bytes'] = read_http_frame(s['stream'], s['bytes'])
                if not ret or frame is None:
                    continue
                
                # Run detection
                results = model.predict(frame, verbose=False, device='cuda:0', conf=0.25)
                
                # Draw bounding boxes
                annotated = frame.copy()
                for box in results[0].boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    label = f"{model.names[cls]} {conf:.2f}"
                    
                    # Draw box
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(annotated, label, (x1, y1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Calculate FPS
                frame_count += 1
                if frame_count % 30 == 0:
                    fps = 30 / (time.time() - last_time)
                    last_time = time.time()
                    print(f"{s['name']}: {fps:.1f} FPS, {len(results[0].boxes)} detections")
                
                # Display
                cv2.imshow(s['name'], annotated)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        for s in streams:
            if s['stream']:
                s['stream'].close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
