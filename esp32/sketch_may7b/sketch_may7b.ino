#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

const char* ssid = "xxx";
const char* password = "xxx";
const char* websocket_host = "192.168.137.xxx";
const uint16_t websocket_port = xxxx;

WebSocketsClient webSocket;

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  if (type == WStype_TEXT) {
    StaticJsonDocument<200> doc;
    DeserializationError err = deserializeJson(doc, payload);

    if (err) {
      Serial.println("JSON parse error");
      return;
    }

    if (doc.containsKey("cmd")) {
      const char* command = doc["cmd"];
      Serial.printf("Command from app: %s\n", command);

      // Acknowledge to app
      StaticJsonDocument<200> ackDoc;
      ackDoc["ack"] = command;
      String ackStr;
      serializeJson(ackDoc, ackStr);
      webSocket.sendTXT(ackStr);

      // Forward to Mega
      serializeJson(doc, Serial2);
      Serial2.println();  
    }
  }
}

void setup() {
  Serial.begin(9600);  
  Serial2.begin(9600, SERIAL_8N1, 16, 17); // rx tx 

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");

  webSocket.begin(websocket_host, websocket_port, "/");
  webSocket.onEvent(webSocketEvent);
}

void loop() {
  webSocket.loop();

  if (Serial2.available()) {
    String msg = Serial2.readStringUntil('\n');
    Serial.print("From Mega: ");
    Serial.println(msg);

    StaticJsonDocument<200> doc;
    DeserializationError err = deserializeJson(doc, msg);
    if (!err && doc.containsKey("uno_ack")) {
      webSocket.sendTXT(msg);
    } else {
      webSocket.sendTXT(msg); 
    }
  }
}
