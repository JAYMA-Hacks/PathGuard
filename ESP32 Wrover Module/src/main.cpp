#include <Arduino.h>
#include <WiFi.h>
#include "esp_camera.h"

// your helper starts the HTTP server and registers routes
// make sure app_httpd.cpp has this function:
extern void startCameraServer(void);

#include "camera_pins.h"   // uses CAMERA_MODEL_* from build_flags or board_config.h

// ---- Wi-Fi config ----
const char* WIFI_SSID = "(INSERT WIFI/HOTSPOT NAME)";
const char* WIFI_PASS = "(INSERT WIFI/HOTSPOT PASSWORD)";

// If you prefer AP mode for quick testing, comment station() block and uncomment AP() block below.

static void init_camera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;

  // These macros get set by CAMERA_MODEL_* in build_flags (or via board_config.h)
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size = FRAMESIZE_SVGA; // 800x600 to start
    config.jpeg_quality = 12;           // 10–12 is decent
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 15;
    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    for(;;) { delay(1000); }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n[PathGuard] booting...");

  init_camera();

  // ----- Wi-Fi Station mode -----
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("Connecting to %s", WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nWiFi connected, IP: %s\n", WiFi.localIP().toString().c_str());

  // // ----- OR Wi-Fi AP mode (quick test) -----
  // WiFi.mode(WIFI_AP);
  // WiFi.softAP("ESP32-CAM", "12345678");
  // Serial.printf("AP started, connect to SSID ESP32-CAM, IP: %s\n",
  //               WiFi.softAPIP().toString().c_str());

  startCameraServer();

  Serial.println("Camera HTTP server started.");
  Serial.println("Open the web UI at: http://<the-IP-shown-above>/");
  Serial.println("Stream endpoint (MJPEG): http://<IP>/stream");
}

void loop() {
  // nothing required; HTTP server runs in background tasks
  delay(100);
}
