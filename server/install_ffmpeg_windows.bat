@echo off
REM Script tự động thêm FFmpeg vào PATH (Windows)
REM Chạy với quyền Administrator

echo ============================================
echo  FFmpeg Installation Helper for Windows
echo ============================================
echo.

REM Kiểm tra quyền Administrator
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo [ERROR] Script nay can chay voi quyen Administrator!
    echo.
    echo Cach chay:
    echo 1. Click phai vao file nay
    echo 2. Chon "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo [OK] Running with Administrator privileges
echo.

REM Đường dẫn FFmpeg (sửa nếu cần)
set FFMPEG_SOURCE=C:\Users\hmt\Downloads\ffmpeg-8.0.1\ffmpeg-8.0.1\bin
set FFMPEG_DEST=C:\ffmpeg\bin

echo Kiem tra FFmpeg source...
if not exist "%FFMPEG_SOURCE%\ffmpeg.exe" (
    echo [ERROR] Khong tim thay ffmpeg.exe tai: %FFMPEG_SOURCE%
    echo.
    echo Vui long sua duong dan trong script nay:
    echo set FFMPEG_SOURCE=^<duong dan den folder bin cua ffmpeg^>
    echo.
    pause
    exit /b 1
)

echo [OK] Found ffmpeg.exe at: %FFMPEG_SOURCE%
echo.

REM Tạo thư mục đích
echo Tao thu muc: %FFMPEG_DEST%
if not exist "C:\ffmpeg" mkdir "C:\ffmpeg"
if not exist "%FFMPEG_DEST%" mkdir "%FFMPEG_DEST%"

REM Copy FFmpeg files
echo.
echo Copy FFmpeg files...
xcopy /Y /I "%FFMPEG_SOURCE%\*.exe" "%FFMPEG_DEST%\"
xcopy /Y /I "%FFMPEG_SOURCE%\*.dll" "%FFMPEG_DEST%\" 2>nul

if not exist "%FFMPEG_DEST%\ffmpeg.exe" (
    echo [ERROR] Copy that bai!
    pause
    exit /b 1
)

echo [OK] FFmpeg copied to: %FFMPEG_DEST%
echo.

REM Thêm vào PATH
echo Them vao System PATH...
setx /M PATH "%PATH%;%FFMPEG_DEST%" >nul 2>&1

if %errorLevel% EQU 0 (
    echo [OK] Da them vao PATH thanh cong!
) else (
    echo [WARNING] Khong the tu dong them vao PATH
    echo Vui long them thu cong: %FFMPEG_DEST%
)

echo.
echo ============================================
echo  Installation Complete!
echo ============================================
echo.
echo FFmpeg location: %FFMPEG_DEST%
echo.
echo QUAN TRONG: DONG VA MO LAI TERMINAL moi de PATH co hieu luc!
echo.
echo Test FFmpeg bang cach:
echo   1. Mo PowerShell MOI
echo   2. Chay: ffmpeg -version
echo.
pause

