# ESP32-CAM Hardware Setup Guide

## Hardware Requirements

### 1. ESP32-CAM Module
- **Recommended:** AI-Thinker ESP32-CAM
- **Chip:** ESP32-S with 4MB PSRAM
- **Camera:** OV2640 (2MP)
- **Price:** ~$10 USD

### 2. USB-to-Serial Adapter (for programming)
- FTDI FT232RL or CH340G
- 3.3V/5V selectable (set to 5V for power, 3.3V for data)
- Or use ESP32-CAM-MB (programmer board)

### 3. Power Supply
- **Required:** 5V 2A power supply
- **Important:** USB power alone may not be sufficient
- Camera draws significant current during operation

### 4. Optional Components
- MicroSD card (for local storage)
- External antenna (for better WiFi range)
- Flash LED (built-in on GPIO 4)

## Wiring Diagram

### ESP32-CAM to FTDI Adapter

```
ESP32-CAM Pin    →    FTDI Pin
─────────────────────────────────
5V               →    5V (VCC)
GND              →    GND
U0R (GPIO3)      →    TX
U0T (GPIO1)      →    RX
GPIO0            →    GND (for flashing only)
                      Remove after upload!
```

### Programming Mode vs Running Mode

**Programming Mode (Upload Code):**
```
GPIO0 → GND (connect before powering on)
Then: Power on ESP32-CAM
Upload code
Power off
Remove GPIO0-GND jumper
Power on again (Running Mode)
```

**Running Mode (Normal Operation):**
```
GPIO0 → Not connected (floating or pull-up)
```

## Step-by-Step Setup

### 1. Arduino IDE Setup

#### Install ESP32 Board Support
1. Open Arduino IDE
2. Go to `File → Preferences`
3. Add to "Additional Board Manager URLs":
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Go to `Tools → Board → Boards Manager`
5. Search "esp32"
6. Install "esp32 by Espressif Systems" (version 2.0.0+)

#### Select Board
1. `Tools → Board → ESP32 Arduino`
2. Select "AI Thinker ESP32-CAM"

#### Configure Settings
```
Board: "AI Thinker ESP32-CAM"
Upload Speed: "115200"
Flash Frequency: "80MHz"
Flash Mode: "QIO"
Partition Scheme: "Huge APP (3MB No OTA/1MB SPIFFS)"
Core Debug Level: "None" (or "Info" for debugging)
Port: Select your USB-to-Serial adapter port
```

### 2. Upload Firmware

#### Prepare ESP32-CAM
1. Connect GPIO0 to GND (programming mode)
2. Connect FTDI adapter
3. Power on ESP32-CAM (LED should light up briefly)

#### Upload Code
1. Open `esp32_cam_firmware.ino` in Arduino IDE
2. Update WiFi credentials in the code:
   ```cpp
   const char* ssid = "YOUR_WIFI_SSID";
   const char* password = "YOUR_WIFI_PASSWORD";
   ```
3. Click "Upload" button
4. Wait for upload to complete (~30 seconds)
5. You should see:
   ```
   Leaving...
   Hard resetting via RTS pin...
   ```

#### Switch to Running Mode
1. **Important:** Disconnect GPIO0 from GND
2. Press RESET button or power cycle
3. ESP32-CAM should now boot normally

### 3. Find ESP32-CAM IP Address

#### Method 1: Serial Monitor
1. Keep FTDI adapter connected
2. Open `Tools → Serial Monitor`
3. Set baud rate to `115200`
4. Press RESET button on ESP32-CAM
5. Look for output:
   ```
   ========================================
   ESP32-CAM SmartParking Firmware
   ========================================
   Initializing camera...
   ✅ Camera initialized
   Connecting to WiFi: YOUR_SSID
   ✅ WiFi connected
   📡 IP Address: 192.168.1.158
   ...
   ========================================
   📹 Stream: http://192.168.1.158:81/stream
   ...
   ```

#### Method 2: Router Admin Panel
1. Login to your router admin page
2. Look for connected devices
3. Find "espressif" or "esp32cam"
4. Note the IP address

#### Method 3: Network Scanner
```bash
# Linux/Mac
nmap -sn 192.168.1.0/24 | grep -B 2 "Espressif"

# Or use tools like Angry IP Scanner
```

### 4. Test ESP32-CAM

#### Web Browser Test
Open in browser:
```
http://192.168.1.158:81/
```

You should see:
- Device information
- Live camera stream
- API endpoints list

#### Test Individual Endpoints

**Stream:**
```
http://192.168.1.158:81/stream
```
Should show live MJPEG stream

**Capture:**
```
http://192.168.1.158:81/capture
```
Should download a single JPEG image

**Status:**
```
http://192.168.1.158:81/status
```
Should return JSON:
```json
{
  "device": "ESP32-CAM-SmartParking",
  "status": "streaming",
  "ip": "192.168.1.158",
  "ssid": "YOUR_WIFI",
  "rssi": -45,
  "uptime": 3600,
  "frames": 108000,
  "free_heap": 150000,
  "resolution": "640x480"
}
```

#### Command Line Test
```bash
# Test status
curl http://192.168.1.158:81/status

# Capture frame
curl http://192.168.1.158:81/capture -o test.jpg

# Test with Python
python ../test_esp32_connection.py
```

## Troubleshooting

### Camera Not Initializing
**Symptoms:** 
- "Camera init failed with error 0x..."
- No image in stream

**Solutions:**
1. Check PSRAM is enabled:
   - `Tools → PSRAM → "Enabled"`
2. Check board selection (must be AI-Thinker ESP32-CAM)
3. Power supply insufficient → Use 5V 2A adapter
4. Camera cable not properly connected → Reseat camera module
5. Try different partition scheme: "Huge APP (3MB No OTA)"

### Cannot Upload Code
**Symptoms:**
- "Failed to connect to ESP32"
- "Serial port not found"

**Solutions:**
1. GPIO0 must be connected to GND BEFORE powering on
2. Check FTDI connections (TX↔RX, RX↔TX)
3. Try lower upload speed: `115200` instead of `921600`
4. Install CH340G driver if using CH340G adapter
5. Try pressing RESET button while uploading

### WiFi Connection Failed
**Symptoms:**
- "WiFi connection failed" in serial monitor
- Cannot ping ESP32-CAM IP

**Solutions:**
1. Check WiFi credentials (case-sensitive!)
2. ESP32 only supports 2.4GHz WiFi (not 5GHz)
3. Check WiFi signal strength (move closer to router)
4. Disable WiFi MAC filtering on router
5. Try setting static IP in code

### Poor Video Quality
**Solutions:**
1. Adjust `jpeg_quality` in code (lower = better quality)
   ```cpp
   .jpeg_quality = 10,  // Try 8-12
   ```
2. Better lighting (camera needs good light)
3. Adjust camera position/focus
4. Change frame size:
   ```cpp
   .frame_size = FRAMESIZE_SVGA,  // Try higher resolution
   ```

### Stream Lag/Buffering
**Solutions:**
1. Reduce frame rate:
   ```cpp
   delay(50);  // Increase from 33ms to 50ms (~20 FPS)
   ```
2. Reduce resolution:
   ```cpp
   .frame_size = FRAMESIZE_QVGA,  // 320x240
   ```
3. Increase JPEG compression:
   ```cpp
   .jpeg_quality = 15,  // Increase from 12
   ```
4. Check WiFi signal strength
5. Reduce network traffic

### ESP32-CAM Resets/Reboots
**Solutions:**
1. **Most common:** Insufficient power supply
   - Use 5V 2A adapter (not USB power)
   - Add 470µF capacitor between 5V and GND
2. Disable flash LED (high power consumption)
3. Check for loose connections
4. Add heatsink to ESP32 chip

### Cannot Access from Internet
**Solutions:**
1. Port forwarding on router:
   - Forward external port to `192.168.1.158:81`
2. Use ngrok or similar tunneling service
3. Dynamic DNS service for changing IP
4. Or use our backend proxy (recommended)

## Power Consumption

### Typical Current Draw
- **Idle:** 50-80 mA
- **Streaming:** 180-250 mA
- **With Flash LED:** 300-400 mA

### Power Supply Recommendations
- **Minimum:** 5V 1A (for streaming only)
- **Recommended:** 5V 2A (for reliable operation)
- **With Flash:** 5V 2.5A+

## Camera Specifications

### OV2640 Sensor
- **Resolution:** 2MP (1600x1200)
- **Output formats:** RGB565, JPEG
- **Frame rate:** Up to 60 FPS (at QQVGA)
- **Exposure:** Auto
- **White balance:** Auto
- **Field of view:** ~66° (diagonal)

### Supported Resolutions
```
QQVGA:  160x120   (~60 FPS)
QVGA:   320x240   (~30 FPS)
VGA:    640x480   (~20 FPS) ← Recommended
SVGA:   800x600   (~15 FPS)
XGA:    1024x768  (~10 FPS)
SXGA:   1280x1024 (~5 FPS)
UXGA:   1600x1200 (~2 FPS)
```

## Next Steps

1. ✅ Hardware connected and powered
2. ✅ Firmware uploaded successfully
3. ✅ WiFi connected and streaming
4. ✅ Tested all endpoints
5. 🔄 Configure backend to use real ESP32:
   ```bash
   cd ../server
   export USE_MOCK_ESP32=false
   export ESP32_URL=http://192.168.1.158:81
   python main_fastapi.py
   ```

## References

- [ESP32-CAM Datasheet](https://github.com/raphaelbs/esp32-cam-ai-thinker)
- [Arduino-ESP32 Documentation](https://docs.espressif.com/projects/arduino-esp32/)
- [OV2640 Sensor Datasheet](https://www.uctronics.com/download/cam_module/OV2640DS.pdf)
- [ESP32 Camera Library](https://github.com/espressif/esp32-camera)
