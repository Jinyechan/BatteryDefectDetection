#include <WiFi.h>
#include "esp_camera.h"
#include <WebServer.h>

const char* ssid = "class606_2.4G";
const char* password = "sejong123";

WebServer server(81);

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

void startCameraServer();

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true); // 디버깅 출력 활성화

  // 카메라 초기화
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
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
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_QVGA; // 320x240 (224x224로 리사이징은 Flask에서 처리)
  config.jpeg_quality = 30; // 품질 낮춤 (네트워크 부하 감소)
  config.fb_count = 1;

  // 카메라 초기화
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    delay(5000);
    ESP.restart(); // 초기화 실패 시 재부팅
    return;
  }
  Serial.println("Camera initialized successfully");

  // WiFi 연결
  WiFi.begin(ssid, password);
  int retryCount = 0;
  while (WiFi.status() != WL_CONNECTED && retryCount < 20) {
    delay(500);
    Serial.print(".");
    retryCount++;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Failed to connect to WiFi after 20 attempts");
    delay(5000);
    ESP.restart();
    return;
  }
  Serial.println("WiFi connected");
  Serial.println(WiFi.localIP());
  Serial.printf("WiFi signal strength (RSSI): %d dBm\n", WiFi.RSSI());

  startCameraServer();
  server.begin();
  Serial.println("Server started on port 81");
}

void loop() {
  server.handleClient();

  // WiFi 연결 상태 확인 및 재연결
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected, reconnecting...");
    WiFi.reconnect();
    int retryCount = 0;
    while (WiFi.status() != WL_CONNECTED && retryCount < 20) {
      delay(500);
      Serial.print(".");
      retryCount++;
    }
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Failed to reconnect to WiFi after 20 attempts");
      delay(5000);
      ESP.restart();
    }
    Serial.println("WiFi reconnected");
    Serial.println(WiFi.localIP());
    Serial.printf("WiFi signal strength (RSSI): %d dBm\n", WiFi.RSSI());
  }
}

void startCameraServer() {
  server.on("/stream", HTTP_GET, []() {
    WiFiClient client = server.client();
    if (!client) {
      Serial.println("Client disconnected");
      return;
    }

    // MJPEG 스트림 헤더 전송
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: multipart/x-mixed-replace; boundary=--frame");
    client.println();
    Serial.println("Client connected, starting stream");

    while (client.connected()) {
      camera_fb_t * fb = esp_camera_fb_get();
      if (!fb) {
        Serial.println("Camera capture failed");
        delay(1000);
        continue; // 프레임 캡처 실패 시 재시도
      }

      // MJPEG 스트림 형식으로 프레임 전송
      client.print("--frame\r\n");
      client.print("Content-Type: image/jpeg\r\n");
      client.printf("Content-Length: %u\r\n", fb->len);
      client.print("\r\n");
      client.write(fb->buf, fb->len);
      client.print("\r\n");
      Serial.printf("Frame sent, size: %u bytes\n", fb->len);

      esp_camera_fb_return(fb);
      delay(1000); // 프레임 간격 조정 (1초)
    }

    client.stop();
    Serial.println("Client disconnected");
  });

  server.onNotFound([]() {
    server.send(404, "text/plain", "Not found");
  });
}