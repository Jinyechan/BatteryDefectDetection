#include <WiFi.h>
#include "esp_camera.h"
#include <WebServer.h>
#include <HTTPClient.h>
#include <base64.h>

// WiFi 및 서버 설정 (당신의 정보 사용)
const char* ssid = "class606_2.4G";
const char* password = "sejong123";
const char* serverName = "http://10.0.66.97:5000/detect"; // Flask 서버 주소

WebServer server(81);

// 카메라 핀 설정
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

// 함수 선언
void startCameraServer();
bool initCamera();
void handleStream();

// 캡처 간격 설정
unsigned long lastCaptureTime = 0;
const unsigned long captureInterval = 1000; // 1초 간격

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true); // 디버깅 출력 활성화

  // 카메라 초기화
  if (!initCamera()) {
    Serial.println("Camera initialization failed. Restarting...");
    delay(5000);
    ESP.restart();
    return;
  }
  Serial.println("Camera initialized successfully");

  // WiFi 설정 (정적 IP 사용)
  IPAddress local_IP(10, 0, 66, 13);  // ESP32-CAM IP
  IPAddress gateway(10, 0, 66, 1);    // 게이트웨이 (라우터 IP)
  IPAddress subnet(255, 255, 255, 0); // 서브넷 마스크
  WiFi.config(local_IP, gateway, subnet);

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

  // 서버 시작
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
    while (WiFi.status() != WL_CONNECTED && retryCount < 10) {
      delay(500);
      Serial.print(".");
      retryCount++;
    }
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("WiFi reconnected");
      Serial.println(WiFi.localIP());
      Serial.printf("WiFi signal strength (RSSI): %d dBm\n", WiFi.RSSI());
    } else {
      Serial.println("WiFi reconnection failed");
      ESP.restart();
    }
  }

  // 1초 간격으로 이미지 캡처 및 전송
  unsigned long currentTime = millis();
  if (currentTime - lastCaptureTime >= captureInterval) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("이미지 캡처 실패 - Frame buffer null");
      return;
    }

    Serial.printf("이미지 크기: %u 바이트\n", fb->len);
    String encodedImage = base64::encode(fb->buf, fb->len);
    Serial.println("Base64 인코딩 완료");

    esp_camera_fb_return(fb);

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(serverName);
      http.addHeader("Content-Type", "application/json");

      String jsonData = "{\"image\": \"" + encodedImage + "\"}";
      Serial.println("HTTP POST 요청 전송 중...");

      int httpResponseCode = http.POST(jsonData);
      if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.printf("HTTP 응답 코드: %d\n", httpResponseCode);
        Serial.println("서버 응답: " + response);
      } else {
        Serial.printf("HTTP 요청 실패, 오류: %s\n", http.errorToString(httpResponseCode).c_str());
      }
      http.end();
    } else {
      Serial.println("WiFi 연결 끊김");
    }

    lastCaptureTime = currentTime;
  }
}

bool initCamera() {
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
  config.frame_size = FRAMESIZE_VGA; // 640x480
  config.jpeg_quality = 10; // 품질 낮춤 (네트워크 부하 감소)
  config.fb_count = 2; // 버퍼 2개로 안정성 향상

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    return false;
  }
  return true;
}

void startCameraServer() {
  server.on("/capture", HTTP_GET, []() {
    WiFiClient client = server.client();
    if (!client) {
      Serial.println("Client disconnected");
      return;
    }

    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed in /capture");
      client.println("HTTP/1.1 500 Internal Server Error");
      client.println("Content-Type: text/plain");
      client.println();
      client.println("Camera capture failed");
      client.stop();
      return;
    }

    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: image/jpeg");
    client.printf("Content-Length: %u\r\n", fb->len);
    client.println();
    client.write(fb->buf, fb->len);
    Serial.printf("Image sent, size: %u bytes\n", fb->len);

    esp_camera_fb_return(fb);
    client.stop();
  });

  server.on("/stream", HTTP_GET, handleStream); // 스트리밍 엔드포인트 추가

  server.onNotFound([]() {
    server.send(404, "text/plain", "Not found");
  });
}

void handleStream() {
  WiFiClient client = server.client();
  if (!client) {
    Serial.println("Client disconnected");
    return;
  }

  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: multipart/x-mixed-replace; boundary=frame");
  client.println();

  while (true) {
    if (!client.connected()) {
      Serial.println("Stream client disconnected");
      break;
    }

    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Stream capture failed");
      break;
    }

    client.print("--frame\r\n");
    client.print("Content-Type: image/jpeg\r\n");
    client.printf("Content-Length: %u\r\n", fb->len);
    client.println();
    size_t sent = client.write(fb->buf, fb->len);
    client.println();

    if (sent != fb->len) {
      Serial.println("Failed to send full frame");
      esp_camera_fb_return(fb);
      break;
    }

    esp_camera_fb_return(fb);
    delay(50); // 스트리밍 속도 조절 (네트워크 부하 감소)
  }
  client.stop();
}