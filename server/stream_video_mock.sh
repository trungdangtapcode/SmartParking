#!/bin/bash
# Mock ESP32-CAM streaming using FFmpeg
# Stream video file as HTTP MJPEG on port 8081

echo "========================================"
echo " Mock ESP32-CAM Video Streaming"
echo "========================================"
echo

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "[ERROR] FFmpeg not found!"
    echo
    echo "Install FFmpeg:"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  macOS: brew install ffmpeg"
    echo
    exit 1
fi

# Check if video file exists
VIDEO_FILE="test_video.mp4"
if [ ! -f "$VIDEO_FILE" ]; then
    echo "[WARNING] Video file not found: $VIDEO_FILE"
    echo
    echo "Please place a video file named 'test_video.mp4' in the server folder"
    echo "Or edit this script to point to your video file"
    echo
    exit 1
fi

echo "[OK] FFmpeg found"
echo "[OK] Video file: $VIDEO_FILE"
echo
echo "Starting mock ESP32-CAM stream on http://localhost:8081/stream"
echo "Press Ctrl+C to stop"
echo

# Stream video as MJPEG on port 8081
ffmpeg -re -stream_loop -1 -i "$VIDEO_FILE" \
    -vf "scale=640:480" \
    -f mjpeg \
    -q:v 5 \
    -listen 1 \
    http://localhost:8081/stream

