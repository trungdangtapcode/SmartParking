"""
Mock ESP32-CAM Streaming Server
Simulates ESP32-CAM behavior for development/testing

Features:
- MJPEG streaming (/stream)
- Single frame capture (/capture)
- Video looping (simulates continuous camera feed)
- Frame index overlay for debugging (set SHOW_FRAME_ID constant)
- TIME-SYNCED MODE: All cameras show frames based on real-world time

Time Synchronization:
- Videos are assumed to start at Unix epoch 0 (1970-01-01 00:00:00)
- Current frame = (current_time_seconds % video_duration_seconds) * fps
- Multiple cameras starting at different times will show the SAME moment
- Example: Camera A starts at 10:00:00, Camera B at 10:00:10 → both show frames from same scene time

Debug Mode:
- Set SHOW_FRAME_ID = True to show frame numbers on video
- Helps verify stream synchronization and frame skipping
- Green overlay shows "Frame: X (Time: HH:MM:SS)" on each frame
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import uvicorn
import cv2
import asyncio
from pathlib import Path
from typing import Optional
import base64
import time
from datetime import datetime

app = FastAPI(
    title="Mock ESP32-CAM Server",
    description="Simulates ESP32-CAM streaming for development",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== CONFIGURATION ==========
import os
STREAM_FOLDER = Path(__file__).parent / "stream"
# Allow setting default video via environment variable
DEFAULT_VIDEO = os.environ.get("MOCK_DEFAULT_VIDEO", "test_video.mp4")
DEFAULT_FPS = 30
DEFAULT_RESOLUTION = (640, 480)  # ESP32-CAM typical resolution

# 🔍 DEBUG: Show frame index overlay on video
SHOW_FRAME_ID = False  # Set to False to disable frame index overlay

# Global video capture (to simulate persistent camera)
current_video_path: Optional[Path] = None
video_capture: Optional[cv2.VideoCapture] = None
video_total_frames: int = 0
video_fps: float = DEFAULT_FPS
video_duration: float = 0.0

# 🕐 TIME-BASED SYNCHRONIZATION
# Videos are assumed to start at Unix epoch 0 (1970-01-01 00:00:00)
EPOCH_START = 0  # Unix timestamp 0
frame_lock = asyncio.Lock()  # Thread-safe access


def get_time_synced_frame_index(total_frames: int, fps: float) -> tuple[int, float]:
    """
    Calculate which frame to show based on current real-world time.
    
    Assumes video started at Unix epoch 0 (1970-01-01 00:00:00).
    All cameras will show the same frame at the same real-world time.
    
    Args:
        total_frames: Total number of frames in the video
        fps: Video frames per second
        
    Returns:
        Tuple of (frame_index, elapsed_time_seconds)
        - frame_index: Frame index to display (0-based)
        - elapsed_time_seconds: Current time position in the synchronized timeline
    """
    current_time = time.time()  # Current Unix timestamp
    video_duration = total_frames / fps  # Total video duration in seconds
    
    # Calculate elapsed time since epoch, modulo video duration (loop video)
    elapsed_time = current_time % video_duration
    
    # Calculate frame index
    frame_idx = int(elapsed_time * fps) % total_frames
    
    return frame_idx, elapsed_time


def format_time_from_frame(frame_idx: int, fps: float) -> str:
    """Format frame index as HH:MM:SS.mmm"""
    seconds = frame_idx / fps
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

def format_time_from_seconds(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

def get_or_create_capture(video_filename: str = None) -> cv2.VideoCapture:
    """Get or create video capture (simulates ESP32 camera)"""
    global current_video_path, video_capture, video_total_frames, video_fps, video_duration
    
    if video_filename:
        video_path = STREAM_FOLDER / video_filename
        if not video_path.exists():
            video_path = Path(__file__).parent / video_filename
        if not video_path.exists():
            raise HTTPException(404, f"Video not found: {video_filename}")
    else:
        video_path = Path(__file__).parent / DEFAULT_VIDEO
        if not video_path.exists():
            raise HTTPException(404, f"Default video not found: {DEFAULT_VIDEO}")
    
    # Reuse existing capture if same video
    if video_capture and current_video_path == video_path and video_capture.isOpened():
        return video_capture
    
    # Close old capture
    if video_capture:
        video_capture.release()
    
    # Open new capture
    video_capture = cv2.VideoCapture(str(video_path))
    if not video_capture.isOpened():
        raise HTTPException(500, f"Cannot open video: {video_path.name}")
    
    current_video_path = video_path
    
    # Get video properties for time-based synchronization
    video_total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = video_capture.get(cv2.CAP_PROP_FPS) or DEFAULT_FPS
    video_duration = video_total_frames / video_fps
    
    print(f"📹 [Mock ESP32] Video loaded: {video_path.name}")
    print(f"   ├─ Total frames: {video_total_frames}")
    print(f"   ├─ FPS: {video_fps:.2f}")
    print(f"   ├─ Duration: {video_duration:.2f}s ({format_time_from_frame(video_total_frames, video_fps)})")
    print(f"   └─ Time-sync: ENABLED (synced to Unix epoch)")
    
    return video_capture

# ========== ESP32-CAM Endpoints ==========

@app.get("/")
async def root():
    """ESP32-CAM root - similar to real ESP32 web interface"""
    return {
        "device": "ESP32-CAM Mock",
        "status": "online",
        "endpoints": {
            "stream": "/stream",
            "capture": "/capture",
            "status": "/status",
            "control": "/control"
        }
    }

@app.get("/stream")
async def stream_video(
    video: str = Query(default=None, description="Video filename to stream"),
    fps: int = Query(default=DEFAULT_FPS, description="Frames per second"),
    resolution: str = Query(default="640x480", description="Resolution (WIDTHxHEIGHT)")
):
    """
    MJPEG stream endpoint - mimics ESP32-CAM /stream
    � TIME-SYNCED MODE: All clients see frames based on real-world time
    
    Videos are assumed to start at Unix epoch 0 (1970-01-01 00:00:00).
    Frame index = (current_time % video_duration) * fps
    
    This ensures multiple cameras show the SAME moment regardless of when they start.
    
    Usage:
    - http://localhost:8081/stream (default video)
    - http://localhost:8081/stream?video=parking_a.mp4
    - http://localhost:8081/stream?video=parking_a.mp4&fps=20
    """
    
    # Parse resolution
    try:
        width, height = map(int, resolution.split('x'))
        target_resolution = (width, height)
    except:
        target_resolution = DEFAULT_RESOLUTION
    
    async def generate_mjpeg_stream():
        """Generate MJPEG stream like ESP32-CAM with time synchronization"""
        
        try:
            cap = get_or_create_capture(video)
            delay = 1.0 / fps
            
            # Get video properties
            total_frames = video_total_frames
            video_fps_rate = video_fps
            
            print(f"📹 [Mock ESP32] Streaming: {current_video_path.name} @ {fps}fps")
            print(f"🕐 [Mock ESP32] Time-sync mode: ACTIVE (synced to Unix epoch)")
            if SHOW_FRAME_ID:
                print(f"🔍 [Mock ESP32] Frame ID overlay: ENABLED")
            
            while True:
                # 🕐 Calculate time-synced frame index and elapsed time
                target_frame_idx, elapsed_time = get_time_synced_frame_index(total_frames, video_fps_rate)
                
                # Seek to the calculated frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_idx)
                
                ret, frame = cap.read()
                
                # Fallback: if seeking fails, loop from start
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        continue
                
                # Resize to target resolution
                frame = cv2.resize(frame, target_resolution)
                
                # 🔍 DEBUG: Add time-synced frame index overlay
                if SHOW_FRAME_ID:
                    # Add semi-transparent background for better readability
                    overlay = frame.copy()
                    cv2.rectangle(overlay, (5, 5), (280, 80), (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
                    
                    # Add frame index text
                    cv2.putText(frame, f"Frame: {target_frame_idx}", 
                                (10, 30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 
                                0.6, 
                                (0, 255, 0),  # Green color
                                2, 
                                cv2.LINE_AA)
                    
                    # Add SYNCHRONIZED time (same across all cameras)
                    time_str = format_time_from_seconds(elapsed_time)
                    cv2.putText(frame, f"Time: {time_str}", 
                                (10, 60), 
                                cv2.FONT_HERSHEY_SIMPLEX, 
                                0.6, 
                                (0, 255, 255),  # Yellow color
                                2, 
                                cv2.LINE_AA)
                
                # Encode as JPEG (simulate ESP32-CAM compression)
                ret, buffer = cv2.imencode('.jpg', frame, [
                    cv2.IMWRITE_JPEG_QUALITY, 80  # ESP32-CAM typical quality
                ])
                
                if not ret:
                    continue
                
                # MJPEG format (same as ESP32-CAM)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + 
                       buffer.tobytes() + b'\r\n')
                
                await asyncio.sleep(delay)
                
        except Exception as e:
            print(f"❌ [Mock ESP32] Stream error: {e}")
            raise
    
    return StreamingResponse(
        generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Access-Control-Allow-Origin": "*"
        }
    )

@app.get("/capture")
async def capture_frame(
    video: str = Query(default=None, description="Video filename"),
    quality: int = Query(default=85, ge=1, le=100, description="JPEG quality"),
    show_frame_id: bool = Query(default=SHOW_FRAME_ID, description="Show frame index overlay")
):
    """
    Capture single frame - mimics ESP32-CAM /capture
    � Shows TIME-SYNCED frame (based on real-world time)
    Returns a JPEG image
    
    Usage:
    - http://localhost:8081/capture
    - http://localhost:8081/capture?video=parking_a.mp4&quality=90
    - http://localhost:8081/capture?show_frame_id=false
    """
    
    try:
        cap = get_or_create_capture(video)
        
        # 🕐 Calculate time-synced frame index and elapsed time
        target_frame_idx, elapsed_time = get_time_synced_frame_index(video_total_frames, video_fps)
        
        # Seek to the calculated frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_idx)
        
        ret, frame = cap.read()
        if not ret:
            # Try again from start
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
        
        if not ret or frame is None:
            raise HTTPException(500, "Failed to capture frame")
        
        # Resize to ESP32-CAM resolution
        frame = cv2.resize(frame, DEFAULT_RESOLUTION)
        
        # 🔍 DEBUG: Add time-synced frame index overlay
        if show_frame_id:
            # Add semi-transparent background
            overlay = frame.copy()
            cv2.rectangle(overlay, (5, 5), (280, 80), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
            
            # Add frame index text
            cv2.putText(frame, f"Frame: {target_frame_idx}", 
                        (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.6, 
                        (0, 255, 0),
                        2, 
                        cv2.LINE_AA)
            
            # Add SYNCHRONIZED time (same across all cameras)
            time_str = format_time_from_seconds(elapsed_time)
            cv2.putText(frame, f"Time: {time_str}", 
                        (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.6, 
                        (0, 255, 255),
                        2, 
                        cv2.LINE_AA)
        
        # Encode as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [
            cv2.IMWRITE_JPEG_QUALITY, quality
        ])
        
        if not ret:
            raise HTTPException(500, "Failed to encode frame")
        
        return Response(
            content=buffer.tobytes(),
            media_type="image/jpeg",
            headers={
                "Content-Disposition": "inline; filename=capture.jpg",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [Mock ESP32] Capture error: {e}")
        raise HTTPException(500, str(e))

@app.get("/status")
async def get_status():
    """Get camera status - mimics ESP32-CAM /status"""
    global video_capture, current_video_path
    
    is_streaming = video_capture is not None and video_capture.isOpened()
    
    status_data = {
        "device": "ESP32-CAM Mock",
        "status": "streaming" if is_streaming else "idle",
        "current_video": current_video_path.name if current_video_path else None,
        "resolution": f"{DEFAULT_RESOLUTION[0]}x{DEFAULT_RESOLUTION[1]}",
        "available_videos": [f.name for f in STREAM_FOLDER.glob("*.mp4")] if STREAM_FOLDER.exists() else [],
        "time_sync_mode": True,  # 🕐 Time-based synchronization enabled
        "epoch_start": EPOCH_START,
        "current_unix_time": time.time(),
    }
    
    # Add video info if streaming
    if is_streaming:
        current_frame = get_time_synced_frame_index(video_total_frames, video_fps)
        status_data.update({
            "video_total_frames": video_total_frames,
            "video_fps": video_fps,
            "video_duration": video_duration,
            "current_frame": current_frame,
            "current_time": format_time_from_frame(current_frame, video_fps),
        })
    
    return status_data

@app.post("/control")
async def control_camera(command: dict):
    """
    Control camera settings - template for real ESP32 integration
    
    Commands:
    - {"action": "start_stream", "video": "parking_a.mp4"}
    - {"action": "stop_stream"}
    - {"action": "set_quality", "quality": 90}
    - {"action": "set_resolution", "resolution": "800x600"}
    """
    
    action = command.get("action")
    
    if action == "start_stream":
        video = command.get("video")
        try:
            get_or_create_capture(video)
            return {"success": True, "message": f"Started streaming: {video or 'default'}"}
        except Exception as e:
            raise HTTPException(500, str(e))
    
    elif action == "stop_stream":
        global video_capture
        if video_capture:
            video_capture.release()
            video_capture = None
        return {"success": True, "message": "Stream stopped"}
    
    elif action == "set_quality":
        # Template for real ESP32 quality control
        quality = command.get("quality", 80)
        return {"success": True, "message": f"Quality set to {quality}"}
    
    elif action == "set_resolution":
        # Template for real ESP32 resolution control
        resolution = command.get("resolution", "640x480")
        return {"success": True, "message": f"Resolution set to {resolution}"}
    
    else:
        raise HTTPException(400, f"Unknown action: {action}")

# ========== Helper Endpoints ==========

@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "ok", "device": "ESP32-CAM Mock"}

@app.get("/videos")
async def list_available_videos():
    """List available video files for streaming"""
    if not STREAM_FOLDER.exists():
        return {"videos": [], "folder": str(STREAM_FOLDER)}
    
    videos = [
        {
            "filename": f.name,
            "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
            "url": f"http://localhost:8081/stream?video={f.name}"
        }
        for f in STREAM_FOLDER.glob("*.mp4")
    ]
    
    return {
        "folder": str(STREAM_FOLDER),
        "count": len(videos),
        "videos": videos
    }

# ========== Cleanup ==========

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global video_capture
    if video_capture:
        video_capture.release()
        print("🛑 [Mock ESP32] Video capture released")

if __name__ == "__main__":
    print("=" * 60)
    print("🎥 Mock ESP32-CAM Server")
    print("=" * 60)
    print(f"📹 Stream: http://localhost:8081/stream")
    print(f"📸 Capture: http://localhost:8081/capture")
    print(f"📊 Status: http://localhost:8081/status")
    print(f"📖 Docs: http://localhost:8081/docs")
    print("=" * 60)
    print(f"📁 Video folder: {STREAM_FOLDER}")
    print("=" * 60)
    
    uvicorn.run(
        "mock_esp32_server:app",
        host="0.0.0.0",
        port=8081,
        reload=True,
        log_level="info"
    )
