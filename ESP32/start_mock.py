#!/usr/bin/env python3
"""
Quick start script for ESP32 mock server
Simpler wrapper around mock_esp32_server.py
"""

import sys
import os
from pathlib import Path

# Add ESP32 folder to Python path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Start ESP32 mock server")
    parser.add_argument("--port", type=int, default=8081, help="Server port (default: 8081)")
    parser.add_argument("--video", default=None, help="Default video file")
    parser.add_argument("--list-videos", action="store_true", help="List available videos")
    args = parser.parse_args()
    
    # Check if listing videos
    if args.list_videos:
        stream_folder = Path(__file__).parent / "stream"
        if not stream_folder.exists():
            print("📁 No stream folder found. Create ESP32/stream/ and add .mp4 files")
            return
        
        videos = list(stream_folder.glob("*.mp4"))
        if not videos:
            print("📁 No videos found in ESP32/stream/")
            print("   Add .mp4 files to ESP32/stream/ folder")
            return
        
        print(f"\n📹 Available videos in {stream_folder}:")
        for video in videos:
            size_mb = video.stat().st_size / (1024 * 1024)
            print(f"   • {video.name} ({size_mb:.2f} MB)")
        print(f"\nTotal: {len(videos)} videos")
        print(f"\nUsage: http://localhost:{args.port}/stream?video=FILENAME.mp4")
        return
    
    # Start mock server
    print("=" * 60)
    print("🎥 Starting ESP32 Mock Server")
    print("=" * 60)
    print(f"📹 Port: {args.port}")
    if args.video:
        print(f"📹 Default video: {args.video}")
        # Set environment variable for mock server
        os.environ["MOCK_DEFAULT_VIDEO"] = args.video
    print("=" * 60)
    
    # Import and run
    import uvicorn
    
    os.chdir(Path(__file__).parent)
    
    uvicorn.run(
        "mock_esp32_server:app",
        host="0.0.0.0",
        port=args.port,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
