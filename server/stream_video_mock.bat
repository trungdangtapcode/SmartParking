@echo off
REM Mock ESP32-CAM streaming using FFmpeg
REM Stream video file as HTTP MJPEG on port 8081

echo ========================================
echo  Mock ESP32-CAM Video Streaming
echo ========================================
echo.

REM Check if FFmpeg is installed
where ffmpeg >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] FFmpeg not found!
    echo.
    echo Download FFmpeg from: https://ffmpeg.org/download.html
    echo Or install via chocolatey: choco install ffmpeg
    echo.
    pause
    exit /b 1
)

REM Check if video file exists
set VIDEO_FILE=test_video.mp4
if not exist "%VIDEO_FILE%" (
    echo [WARNING] Video file not found: %VIDEO_FILE%
    echo.
    echo Please place a video file named "test_video.mp4" in the server folder
    echo Or edit this script to point to your video file
    echo.
    pause
    exit /b 1
)

echo [OK] FFmpeg found
echo [OK] Video file: %VIDEO_FILE%
echo.
echo Starting mock ESP32-CAM stream on http://localhost:8081/stream
echo Press Ctrl+C to stop
echo.

REM Stream video as MJPEG on port 8081
ffmpeg -re -stream_loop -1 -i "%VIDEO_FILE%" ^
    -vf "scale=640:480" ^
    -f mjpeg ^
    -q:v 5 ^
    -listen 1 ^
    http://localhost:8081/stream

pause

