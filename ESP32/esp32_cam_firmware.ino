/**
 * ESP32-CAM Firmware for SmartParking
 * 
 * Hardware: ESP32-CAM (AI-Thinker)
 * Board: AI Thinker ESP32-CAM in Arduino IDE
 * 
 * Features:
 * - MJPEG streaming on /stream
 * - Single frame capture on /capture
 * - Camera control on /control
 * - Status endpoint on /status
 * 
 * Setup:
 * 1. Install ESP32 board support in Arduino IDE
 * 2. Select "AI Thinker ESP32-CAM" board
 * 3. Update WiFi credentials below
 * 4. Upload via USB-to-Serial adapter (GPIO0 to GND for flash mode)
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>

// ========== WiFi Configuration ==========
const char* ssid = "YOUR_WIFI_SSID";          // Change this
const char* password = "YOUR_WIFI_PASSWORD";   // Change this

// ========== Server Configuration ==========
WebServer server(81);  // Port 81 (default for ESP32-CAM)

// ========== Camera Pin Definitions (AI-Thinker ESP32-CAM) ==========
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

// ========== Camera Settings ==========
camera_config_t camera_config = {
    .pin_pwdn = PWDN_GPIO_NUM,
    .pin_reset = RESET_GPIO_NUM,
    .pin_xclk = XCLK_GPIO_NUM,
    .pin_sscb_sda = SIOD_GPIO_NUM,
    .pin_sscb_scl = SIOC_GPIO_NUM,
    
    .pin_d7 = Y9_GPIO_NUM,
    .pin_d6 = Y8_GPIO_NUM,
    .pin_d5 = Y7_GPIO_NUM,
    .pin_d4 = Y6_GPIO_NUM,
    .pin_d3 = Y5_GPIO_NUM,
    .pin_d2 = Y4_GPIO_NUM,
    .pin_d1 = Y3_GPIO_NUM,
    .pin_d0 = Y2_GPIO_NUM,
    .pin_vsync = VSYNC_GPIO_NUM,
    .pin_href = HREF_GPIO_NUM,
    .pin_pclk = PCLK_GPIO_NUM,
    
    .xclk_freq_hz = 20000000,
    .ledc_timer = LEDC_TIMER_0,
    .ledc_channel = LEDC_CHANNEL_0,
    
    .pixel_format = PIXFORMAT_JPEG,  // JPEG format for streaming
    .frame_size = FRAMESIZE_VGA,     // 640x480 (VGA)
    .jpeg_quality = 12,               // 10-63, lower means higher quality
    .fb_count = 2,                    // 2 frame buffers for smooth streaming
    .fb_location = CAMERA_FB_IN_PSRAM,
    .grab_mode = CAMERA_GRAB_LATEST
};

// ========== Global Variables ==========
bool cameraInitialized = false;
unsigned long lastFrameTime = 0;
unsigned long frameCount = 0;
String deviceName = "ESP32-CAM-SmartParking";

// ========== Setup ==========
void setup() {
    Serial.begin(115200);
    Serial.println("\n\n========================================");
    Serial.println("ESP32-CAM SmartParking Firmware");
    Serial.println("========================================");
    
    // Initialize camera
    Serial.println("Initializing camera...");
    esp_err_t err = esp_camera_init(&camera_config);
    if (err != ESP_OK) {
        Serial.printf("Camera init failed with error 0x%x\n", err);
        return;
    }
    cameraInitialized = true;
    Serial.println("✅ Camera initialized");
    
    // Camera sensor settings
    sensor_t * s = esp_camera_sensor_get();
    if (s != NULL) {
        s->set_brightness(s, 0);     // -2 to 2
        s->set_contrast(s, 0);       // -2 to 2
        s->set_saturation(s, 0);     // -2 to 2
        s->set_special_effect(s, 0); // 0 = No Effect
        s->set_whitebal(s, 1);       // 0 = disable, 1 = enable
        s->set_awb_gain(s, 1);       // 0 = disable, 1 = enable
        s->set_wb_mode(s, 0);        // 0 = auto, 1 = sunny, etc.
        s->set_exposure_ctrl(s, 1);  // 0 = disable, 1 = enable
        s->set_aec2(s, 0);           // 0 = disable, 1 = enable
        s->set_ae_level(s, 0);       // -2 to 2
        s->set_aec_value(s, 300);    // 0 to 1200
        s->set_gain_ctrl(s, 1);      // 0 = disable, 1 = enable
        s->set_agc_gain(s, 0);       // 0 to 30
        s->set_gainceiling(s, (gainceiling_t)0); // 0 to 6
        s->set_bpc(s, 0);            // 0 = disable, 1 = enable
        s->set_wpc(s, 1);            // 0 = disable, 1 = enable
        s->set_raw_gma(s, 1);        // 0 = disable, 1 = enable
        s->set_lenc(s, 1);           // 0 = disable, 1 = enable
        s->set_hmirror(s, 0);        // 0 = disable, 1 = enable
        s->set_vflip(s, 0);          // 0 = disable, 1 = enable
        s->set_dcw(s, 1);            // 0 = disable, 1 = enable
        s->set_colorbar(s, 0);       // 0 = disable, 1 = enable
    }
    
    // Connect to WiFi
    Serial.print("Connecting to WiFi: ");
    Serial.println(ssid);
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n✅ WiFi connected");
        Serial.print("📡 IP Address: ");
        Serial.println(WiFi.localIP());
        Serial.print("📡 Signal Strength: ");
        Serial.print(WiFi.RSSI());
        Serial.println(" dBm");
    } else {
        Serial.println("\n❌ WiFi connection failed!");
        return;
    }
    
    // Start mDNS (optional, for esp32cam.local)
    if (MDNS.begin("esp32cam")) {
        Serial.println("✅ mDNS responder started: esp32cam.local");
    }
    
    // Setup HTTP server routes
    server.on("/", HTTP_GET, handleRoot);
    server.on("/stream", HTTP_GET, handleStream);
    server.on("/capture", HTTP_GET, handleCapture);
    server.on("/status", HTTP_GET, handleStatus);
    server.on("/control", HTTP_POST, handleControl);
    server.onNotFound(handleNotFound);
    
    // Start server
    server.begin();
    Serial.println("✅ HTTP server started on port 81");
    Serial.println("========================================");
    Serial.println("📹 Stream: http://" + WiFi.localIP().toString() + ":81/stream");
    Serial.println("📸 Capture: http://" + WiFi.localIP().toString() + ":81/capture");
    Serial.println("📊 Status: http://" + WiFi.localIP().toString() + ":81/status");
    Serial.println("========================================");
}

// ========== Main Loop ==========
void loop() {
    server.handleClient();
    
    // Print stats every 10 seconds
    static unsigned long lastStatsTime = 0;
    if (millis() - lastStatsTime > 10000) {
        lastStatsTime = millis();
        Serial.printf("📊 Frames: %lu | Free heap: %d bytes | WiFi RSSI: %d dBm\n",
                      frameCount, ESP.getFreeHeap(), WiFi.RSSI());
    }
}

// ========== HTTP Handlers ==========

// Root page
void handleRoot() {
    String html = "<!DOCTYPE html><html><head><title>ESP32-CAM SmartParking</title>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
    html += "<style>body{font-family:Arial;margin:20px;background:#f0f0f0;}";
    html += "h1{color:#333;}.info{background:white;padding:15px;margin:10px 0;border-radius:5px;}";
    html += "img{max-width:100%;border:2px solid #333;}</style></head><body>";
    html += "<h1>📹 ESP32-CAM SmartParking</h1>";
    html += "<div class='info'>";
    html += "<p><strong>Device:</strong> " + deviceName + "</p>";
    html += "<p><strong>IP:</strong> " + WiFi.localIP().toString() + "</p>";
    html += "<p><strong>WiFi:</strong> " + String(ssid) + " (" + String(WiFi.RSSI()) + " dBm)</p>";
    html += "<p><strong>Uptime:</strong> " + String(millis() / 1000) + " seconds</p>";
    html += "<p><strong>Frames captured:</strong> " + String(frameCount) + "</p>";
    html += "</div>";
    html += "<h2>Live Stream:</h2>";
    html += "<img src='/stream' />";
    html += "<h2>API Endpoints:</h2>";
    html += "<div class='info'>";
    html += "<p>🎥 <a href='/stream'>/stream</a> - MJPEG stream</p>";
    html += "<p>📸 <a href='/capture'>/capture</a> - Single frame capture</p>";
    html += "<p>📊 <a href='/status'>/status</a> - Status (JSON)</p>";
    html += "<p>⚙️ POST /control - Control commands</p>";
    html += "</div>";
    html += "</body></html>";
    
    server.send(200, "text/html", html);
}

// MJPEG stream handler
void handleStream() {
    if (!cameraInitialized) {
        server.send(503, "text/plain", "Camera not initialized");
        return;
    }
    
    Serial.println("📹 Starting MJPEG stream...");
    
    WiFiClient client = server.client();
    
    // Send MJPEG headers
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: multipart/x-mixed-replace; boundary=frame");
    client.println("Access-Control-Allow-Origin: *");
    client.println();
    
    // Stream frames
    while (client.connected()) {
        camera_fb_t * fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("❌ Camera capture failed");
            break;
        }
        
        frameCount++;
        lastFrameTime = millis();
        
        // Send frame
        client.printf("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n", fb->len);
        client.write(fb->buf, fb->len);
        client.println();
        
        esp_camera_fb_return(fb);
        
        // Small delay to prevent overwhelming the client
        delay(33); // ~30 FPS
    }
    
    Serial.println("📹 Stream ended");
}

// Single frame capture
void handleCapture() {
    if (!cameraInitialized) {
        server.send(503, "text/plain", "Camera not initialized");
        return;
    }
    
    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb) {
        Serial.println("❌ Camera capture failed");
        server.send(500, "text/plain", "Camera capture failed");
        return;
    }
    
    frameCount++;
    lastFrameTime = millis();
    
    Serial.printf("📸 Captured frame: %d bytes\n", fb->len);
    
    // Send JPEG image
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send_P(200, "image/jpeg", (const char *)fb->buf, fb->len);
    
    esp_camera_fb_return(fb);
}

// Status endpoint (JSON)
void handleStatus() {
    String json = "{";
    json += "\"device\":\"" + deviceName + "\",";
    json += "\"status\":\"" + String(cameraInitialized ? "streaming" : "error") + "\",";
    json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
    json += "\"ssid\":\"" + String(ssid) + "\",";
    json += "\"rssi\":" + String(WiFi.RSSI()) + ",";
    json += "\"uptime\":" + String(millis() / 1000) + ",";
    json += "\"frames\":" + String(frameCount) + ",";
    json += "\"free_heap\":" + String(ESP.getFreeHeap()) + ",";
    json += "\"resolution\":\"640x480\"";
    json += "}";
    
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", json);
}

// Control endpoint (POST)
void handleControl() {
    if (!server.hasArg("plain")) {
        server.send(400, "application/json", "{\"error\":\"No body\"}");
        return;
    }
    
    String body = server.arg("plain");
    Serial.println("⚙️ Control command: " + body);
    
    // Parse simple commands (extend as needed)
    if (body.indexOf("\"action\":\"set_quality\"") >= 0) {
        // Extract quality value (simple parsing)
        int qualityIdx = body.indexOf("\"quality\":");
        if (qualityIdx >= 0) {
            int quality = body.substring(qualityIdx + 10).toInt();
            sensor_t * s = esp_camera_sensor_get();
            if (s != NULL) {
                s->set_quality(s, quality);
                server.send(200, "application/json", "{\"success\":true,\"message\":\"Quality set to " + String(quality) + "\"}");
                return;
            }
        }
    }
    
    server.send(200, "application/json", "{\"success\":true,\"message\":\"Command received\"}");
}

// 404 handler
void handleNotFound() {
    server.send(404, "text/plain", "Not Found");
}
