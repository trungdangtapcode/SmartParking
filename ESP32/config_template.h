/**
 * ESP32-CAM Configuration Template
 * 
 * Copy this file to config.h and update with your settings
 */

#ifndef CONFIG_H
#define CONFIG_H

// ========== WiFi Configuration ==========
// Replace with your WiFi credentials
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// ========== Network Configuration ==========
// Use static IP (optional, comment out for DHCP)
// #define USE_STATIC_IP
// #define STATIC_IP "192.168.1.158"
// #define GATEWAY "192.168.1.1"
// #define SUBNET "255.255.255.0"
// #define DNS1 "8.8.8.8"
// #define DNS2 "8.8.4.4"

// ========== Server Configuration ==========
#define HTTP_PORT 81  // HTTP server port (default 81)

// Device name (for mDNS: esp32cam.local)
#define DEVICE_NAME "esp32cam"

// ========== Camera Configuration ==========
// Frame size options:
// FRAMESIZE_QQVGA   (160x120)
// FRAMESIZE_QVGA    (320x240)
// FRAMESIZE_VGA     (640x480)   <- Recommended for SmartParking
// FRAMESIZE_SVGA    (800x600)
// FRAMESIZE_XGA     (1024x768)
// FRAMESIZE_SXGA    (1280x1024)
// FRAMESIZE_UXGA    (1600x1200)
#define CAMERA_FRAME_SIZE FRAMESIZE_VGA

// JPEG quality (10-63, lower = higher quality)
#define JPEG_QUALITY 12  // 10-15 recommended for detection

// Frame rate (milliseconds between frames)
#define FRAME_DELAY_MS 33  // ~30 FPS (1000/30 = 33ms)

// ========== Hardware Configuration ==========
// AI-Thinker ESP32-CAM pin definitions (don't change unless using different board)
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ========== Features ==========
// Enable/disable features
#define ENABLE_MDNS 1        // Enable mDNS (esp32cam.local)
#define ENABLE_OTA 0         // Enable OTA updates (not implemented yet)
#define ENABLE_SERIAL 1      // Enable serial debugging

// LED flash (GPIO 4 on AI-Thinker ESP32-CAM)
#define LED_FLASH_GPIO 4
#define ENABLE_FLASH 0       // Enable flash LED (warning: high power consumption)

// ========== Advanced Settings ==========
// Camera sensor settings (0-2, or -2 to 2 for some)
#define CAM_BRIGHTNESS 0     // -2 to 2
#define CAM_CONTRAST 0       // -2 to 2
#define CAM_SATURATION 0     // -2 to 2
#define CAM_SHARPNESS 0      // -2 to 2
#define CAM_DENOISE 0        // 0 = off, 1 = on
#define CAM_AE_LEVEL 0       // -2 to 2 (auto-exposure level)
#define CAM_GAIN_CEILING 0   // 0 to 6

// Watchdog timeout (seconds)
#define WATCHDOG_TIMEOUT 30

// ========== API Configuration ==========
// CORS (Cross-Origin Resource Sharing)
#define CORS_ORIGIN "*"  // Allow all origins (use specific domain in production)

// Authentication (optional, not implemented yet)
#define ENABLE_AUTH 0
#define API_KEY "your_secret_api_key_here"

#endif // CONFIG_H
