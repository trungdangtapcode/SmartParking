"""Simple HTTP stream viewer with YOLO detection - outputs to MJPEG server."""
import cv2
import numpy as np
import torch
from ultralytics import YOLO
import urllib.request
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

class SimpleDetectionServer:
    def __init__(self, port=8170):
        self.port = port
        self.frames = {}
        self._lock = threading.Lock()
        self._server = None
        self._running = threading.Event()
        
    def update_frame(self, name, frame_bytes):
        with self._lock:
            self.frames[name] = frame_bytes
    
    def _handler_factory(self):
        outer = self
        
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress logs
                
            def do_GET(self):
                path = self.path.lstrip("/")
                if not path or path == "index":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    body = "<html><body><h2>Detection Streams</h2><ul>"
                    for k in sorted(outer.frames.keys()):
                        body += f'<li><a href="/{k}.mjpg">{k}</a></li>'
                    body += "</ul></body></html>"
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body.encode())
                    return
                
                cam_name = path.split(".")[0]
                boundary = "--frame"
                self.send_response(200)
                self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={boundary}")
                self.end_headers()
                
                try:
                    while outer._running.is_set():
                        with outer._lock:
                            buf = outer.frames.get(cam_name)
                        if buf is None:
                            time.sleep(0.05)
                            continue
                        self.wfile.write(boundary.encode() + b"\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(buf)}\r\n\r\n".encode())
                        self.wfile.write(buf + b"\r\n")
                        time.sleep(0.001)
                except:
                    pass
        return Handler
    
    def start(self):
        self._running.set()
        self._server = ThreadingHTTPServer(("0.0.0.0", self.port), self._handler_factory())
        self._server.daemon_threads = True
        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()
        print(f"✓ Server started on http://localhost:{self.port}/")

def read_http_frame(stream, stream_bytes):
    """Read a single frame from HTTP MJPEG stream."""
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                return False, None, stream_bytes
            stream_bytes += chunk
            a = stream_bytes.find(b'\xff\xd8')
            b = stream_bytes.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = stream_bytes[a:b+2]
                stream_bytes = stream_bytes[b+2:]
                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    return True, frame, stream_bytes
    except Exception as e:
        print(f"Error: {e}")
        return False, None, stream_bytes

def main():
    print("Loading YOLO model...")
    model = YOLO('yolov8s.pt')
    model.to('cuda:0')
    print("✓ Model loaded")
    
    server = SimpleDetectionServer(port=8170)
    server.start()
    
    streams = [
        {'url': 'http://localhost:5069/stream', 'name': 'cam_1'},
        {'url': 'http://localhost:5070/stream', 'name': 'cam_2'},
    ]
    
    for s in streams:
        try:
            s['stream'] = urllib.request.urlopen(s['url'], timeout=10)
            s['bytes'] = b''
            print(f"✓ Opened {s['name']}")
        except Exception as e:
            print(f"✗ Failed {s['name']}: {e}")
            s['stream'] = None
    
    print("\nProcessing... Access http://localhost:8170/ to view")
    print("Press Ctrl+C to stop\n")
    
    frame_counts = {s['name']: 0 for s in streams}
    last_times = {s['name']: time.time() for s in streams}
    
    try:
        while True:
            for s in streams:
                if s['stream'] is None:
                    continue
                
                ret, frame, s['bytes'] = read_http_frame(s['stream'], s['bytes'])
                if not ret or frame is None:
                    continue
                
                # Detect
                results = model.predict(frame, verbose=False, device='cuda:0', conf=0.25,
                                       classes=[2, 3, 5, 7])  # car, motorcycle, bus, truck
                
                # Draw
                annotated = frame.copy()
                for box in results[0].boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    label = f"{model.names[cls]} {conf:.2f}"
                    
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 3)
                    cv2.putText(annotated, label, (x1, y1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Add info text
                det_count = len(results[0].boxes)
                cv2.putText(annotated, f"Detections: {det_count}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                
                # Encode and update
                _, buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
                server.update_frame(s['name'], buf.tobytes())
                
                # FPS
                frame_counts[s['name']] += 1
                if frame_counts[s['name']] % 30 == 0:
                    fps = 30 / (time.time() - last_times[s['name']])
                    last_times[s['name']] = time.time()
                    print(f"{s['name']}: {fps:.1f} FPS, {det_count} detections")
                    
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        for s in streams:
            if s['stream']:
                s['stream'].close()

if __name__ == "__main__":
    main()
