#include <WiFi.h>
#include <WiFiUdp.h>
#include "esp_wifi.h"
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <WiFiManager.h>
#include <nvs_flash.h>
#include <nvs.h>

// === CONFIGURATION ===
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
#define SCREEN_ADDRESS 0x3C
#define RESET_BUTTON_PIN 17  // GPIO 17 for reset button
#define RESET_HOLD_TIME 3000  // 3 seconds hold to reset

// Target: 50 Packets Per Second (20ms delay)
#define PACKET_DELAY_MS 20 

Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

char pc_ip_str[16] = "192.168.1.255"; 
char port_str[6]   = "8000";

IPAddress pcIP;
int udpPort;
WiFiUDP udp;

unsigned long packetCount = 0;
int lastRSSI = 0;
unsigned long lastPacketTime = 0;

// RSSI Graph Vars
#define GRAPH_WIDTH 126
int rssiHistory[GRAPH_WIDTH];
int historyIndex = 0;

uint8_t primary;
wifi_second_chan_t secondary;
String channelStr;

// === NVS STORAGE FUNCTIONS ===
// Using NVS (Non-Volatile Storage) instead of Preferences
// NVS survives reflashing as long as "Erase Flash" is set to "No" or you don't do a full chip erase

bool loadConfigFromNVS() {
  nvs_handle_t nvs_handle;
  esp_err_t err;
  
  err = nvs_open("csi_storage", NVS_READONLY, &nvs_handle);
  if (err != ESP_OK) {
    Serial.println("NVS not found, using defaults");
    return false;
  }
  
  size_t ip_len = sizeof(pc_ip_str);
  size_t port_len = sizeof(port_str);
  
  err = nvs_get_str(nvs_handle, "pc_ip", pc_ip_str, &ip_len);
  if (err != ESP_OK) {
    Serial.println("IP not found in NVS");
    nvs_close(nvs_handle);
    return false;
  }
  
  err = nvs_get_str(nvs_handle, "pc_port", port_str, &port_len);
  if (err != ESP_OK) {
    Serial.println("Port not found in NVS");
    nvs_close(nvs_handle);
    return false;
  }
  
  nvs_close(nvs_handle);
  Serial.println("Config loaded from NVS");
  Serial.print("IP: "); Serial.println(pc_ip_str);
  Serial.print("Port: "); Serial.println(port_str);
  return true;
}

bool saveConfigToNVS(const char* ip, const char* port) {
  nvs_handle_t nvs_handle;
  esp_err_t err;
  
  err = nvs_open("csi_storage", NVS_READWRITE, &nvs_handle);
  if (err != ESP_OK) {
    Serial.println("Failed to open NVS for writing");
    return false;
  }
  
  err = nvs_set_str(nvs_handle, "pc_ip", ip);
  if (err != ESP_OK) {
    Serial.println("Failed to save IP");
    nvs_close(nvs_handle);
    return false;
  }
  
  err = nvs_set_str(nvs_handle, "pc_port", port);
  if (err != ESP_OK) {
    Serial.println("Failed to save port");
    nvs_close(nvs_handle);
    return false;
  }
  
  err = nvs_commit(nvs_handle);
  nvs_close(nvs_handle);
  
  if (err == ESP_OK) {
    Serial.println("Config saved to NVS successfully");
    return true;
  }
  
  Serial.println("Failed to commit NVS");
  return false;
}

void clearNVSConfig() {
  nvs_handle_t nvs_handle;
  esp_err_t err = nvs_open("csi_storage", NVS_READWRITE, &nvs_handle);
  if (err == ESP_OK) {
    nvs_erase_all(nvs_handle);
    nvs_commit(nvs_handle);
    nvs_close(nvs_handle);
    Serial.println("NVS cleared");
  }
}

// === BINARY PACKET STRUCTURE ===
#pragma pack(push, 1)
struct BinaryPacket {
    uint32_t timestamp;
    int8_t rssi;
    uint8_t count;
    int8_t padding[2];
    int16_t csi[128];
};
#pragma pack(pop)

void initRSSIHistory() {
  for (int i = 0; i < GRAPH_WIDTH; i++) rssiHistory[i] = -90; 
}

void addRSSIToHistory(int rssi) {
  rssiHistory[historyIndex] = rssi;
  historyIndex = (historyIndex + 1) % GRAPH_WIDTH;
}

void drawRSSIGraph(int x, int y, int width, int height) {
  display.drawRect(x, y, width, height, SH110X_WHITE);
  
  int minRSSI = rssiHistory[0]; 
  int maxRSSI = rssiHistory[0];
  for (int i = 0; i < GRAPH_WIDTH; i++) {
    if (rssiHistory[i] < minRSSI) minRSSI = rssiHistory[i];
    if (rssiHistory[i] > maxRSSI) maxRSSI = rssiHistory[i];
  }
  
  minRSSI -= 3; 
  maxRSSI += 3;
  
  if (maxRSSI - minRSSI < 8) { 
    int midpoint = (maxRSSI + minRSSI) / 2;
    minRSSI = midpoint - 4; 
    maxRSSI = midpoint + 4;
  }
  
  int prevX = -1; 
  int prevY = -1;
  for (int i = 0; i < width - 2; i++) {
    int histIdx = (historyIndex - (width - 2) + i + GRAPH_WIDTH) % GRAPH_WIDTH;
    int rssi = rssiHistory[histIdx];
    int pointHeight = map(constrain(rssi, minRSSI, maxRSSI), minRSSI, maxRSSI, 2, height - 3);
    int pointX = x + 1 + i;
    int pointY = y + height - 1 - pointHeight;
    
    if (prevX != -1) {
      display.drawLine(prevX, prevY, pointX, pointY, SH110X_WHITE);
    }
    display.drawPixel(pointX, pointY, SH110X_WHITE);
    prevX = pointX; 
    prevY = pointY;
  }
}

void updateDisplay() {
  display.clearDisplay();
  
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print("CSI STREAM");
  
  bool receiving = (millis() - lastPacketTime) < 2000;
  display.setCursor(100, 0);
  if (receiving) {
    display.print("LIVE");
  } else {
    display.print("WAIT");
  }
  
  display.setCursor(0, 9);
  display.print("PKT:");
  display.setCursor(28, 9);
  if (packetCount < 1000) {
    display.print(packetCount);
  } else if (packetCount < 10000) {
    display.print(String(packetCount / 1000.0, 1) + "k"); 
  } else {
    display.print(String(packetCount / 1000) + "k");
  }
  
  float pktRate = packetCount / ((millis() / 1000.0) + 0.001);
  display.setCursor(75, 9);
  display.print(String(pktRate, 1) + " p/s");
  
  display.drawFastHLine(0, 16, 128, SH110X_WHITE);
  
  display.setTextSize(1);
  display.setCursor(0, 18);
  display.print("RSSI:");
  
  display.setTextSize(1);
  display.setCursor(28, 18);
  display.print(lastRSSI);

  display.setTextSize(1);
  display.setCursor(48, 18);
  display.print("dBm");
  
  display.setTextSize(1);
  display.setCursor(78, 18);
  display.print("SIG:");
  
  String quality;
  if (lastRSSI > -50) quality = "EXC";
  else if (lastRSSI > -60) quality = "GOOD";
  else if (lastRSSI > -70) quality = "FAIR";
  else quality = "WEAK";
  
  display.setCursor(100, 18);
  display.print(quality);

  esp_err_t res = esp_wifi_get_channel(&primary, &secondary);
  if (res == ESP_OK) {
      channelStr = "CSI Channel:" + String(primary);
      if (secondary == WIFI_SECOND_CHAN_NONE) channelStr += " (HT20)";
      else if (secondary == WIFI_SECOND_CHAN_ABOVE) channelStr += " (HT40+)";
      else if (secondary == WIFI_SECOND_CHAN_BELOW) channelStr += " (HT40-)";
  } else {
      channelStr = "Failed to get WiFi channel";
  }

  display.setTextSize(1);
  display.setCursor(0, 27);
  display.print(channelStr);
  
  drawRSSIGraph(1, 36, 126, 27);
  
  display.display();
}

void csiCallback(void *ctx, wifi_csi_info_t *data) {
  packetCount++;
  lastPacketTime = millis();
  
  int rssi = data->rx_ctrl.rssi;
  lastRSSI = rssi;
  addRSSIToHistory(rssi);

  int count = data->len / 4; 
  if (count > 64) count = 64;
  if (count < 10) return;

  BinaryPacket pkg;
  pkg.timestamp = millis();
  pkg.rssi = rssi;
  pkg.count = (uint8_t)count;
  pkg.padding[0] = 0;
  pkg.padding[1] = 0;
  
  memcpy(pkg.csi, data->buf, count * 4);

  size_t totalLen = 8 + (count * 4);
  
  udp.beginPacket(pcIP, udpPort);
  udp.write((uint8_t*)&pkg, totalLen);
  udp.endPacket();
}

void configModeCallback(WiFiManager *myWiFiManager) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("SETUP MODE");

  display.drawFastHLine(0, 11, 128, SH110X_WHITE);
  
  display.setCursor(0, 16);
  display.setTextSize(1);
  display.println("Connect to WiFi:");
  display.setCursor(0, 27);
  display.println(myWiFiManager->getConfigPortalSSID());

  display.drawFastHLine(0, 38, 128, SH110X_WHITE);
  
  display.setCursor(0, 40);
  display.println("Open in browser:");
  display.setCursor(0, 51);
  display.println(WiFi.softAPIP().toString());
  
  display.display();
}

// NEW: Check for 3-second button hold
bool checkResetButtonHold() {
  pinMode(RESET_BUTTON_PIN, INPUT_PULLUP);
  
  if (digitalRead(RESET_BUTTON_PIN) == LOW) {
    display.clearDisplay(); 
    display.setCursor(0, 0); 
    display.println("HOLD FOR RESET...");
    display.display();
    
    unsigned long pressStart = millis();
    
    // Visual countdown
    while (digitalRead(RESET_BUTTON_PIN) == LOW) {
      unsigned long elapsed = millis() - pressStart;
      
      if (elapsed >= RESET_HOLD_TIME) {
        // Reset confirmed
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("RESETTING...");
        display.println("");
        display.println("Clearing WiFi &");
        display.println("Config data...");
        display.display();
        
        WiFiManager wm;
        wm.resetSettings();
        clearNVSConfig();
        
        delay(2000);
        ESP.restart();
        return true;
      }
      
      // Show progress bar
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("HOLD TO RESET");
      display.println("");
      
      int progress = map(elapsed, 0, RESET_HOLD_TIME, 0, 100);
      display.setCursor(0, 20);
      display.print("Progress: ");
      display.print(progress);
      display.println("%");
      
      // Progress bar
      int barWidth = map(elapsed, 0, RESET_HOLD_TIME, 0, 128);
      display.fillRect(0, 35, barWidth, 10, SH110X_WHITE);
      display.drawRect(0, 35, 128, 10, SH110X_WHITE);
      
      display.display();
      delay(50);
    }
    
    // Button released before 3 seconds
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Reset cancelled");
    display.display();
    delay(1000);
    return false;
  }
  
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("Booting ESP32...");
  Wire.begin(21, 22);
  
  // Initialize NVS
  esp_err_t err = nvs_flash_init();
  if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    // NVS partition was truncated, erase and reinit
    nvs_flash_erase();
    err = nvs_flash_init();
  }
  
  // Initialize OLED
  if(!display.begin(SCREEN_ADDRESS, true)) {
    Serial.println(F("SSD1306 allocation failed"));
    for(;;);
  }
  
  display.clearDisplay(); 
  display.setTextSize(1); 
  display.setTextColor(SH110X_WHITE);
  display.setCursor(0, 0); 
  display.println("ESP32 CSI");
  display.println("Booting..."); 
  display.display();
  delay(1000);

  // Load config from NVS (survives reflashing)
  loadConfigFromNVS();

  // Check for reset button hold
  if (checkResetButtonHold()) {
    return; // Will restart
  }

  // WiFi Manager Setup
  WiFiManager wm;
  WiFiManagerParameter c_ip("pc_ip", "PC IP Address", pc_ip_str, 16);
  WiFiManagerParameter c_port("port", "UDP Port", port_str, 6);
  wm.addParameter(&c_ip); 
  wm.addParameter(&c_port);
  wm.setAPCallback(configModeCallback);
  
  if (!wm.autoConnect("WISPR CSI-Setup")) {
    delay(3000); 
    ESP.restart();
  }

  // Save new config to NVS if changed
  if (strcmp(c_ip.getValue(), pc_ip_str) != 0 || strcmp(c_port.getValue(), port_str) != 0) {
    saveConfigToNVS(c_ip.getValue(), c_port.getValue());
    strcpy(pc_ip_str, c_ip.getValue());
    strcpy(port_str, c_port.getValue());
  }

  pcIP.fromString(pc_ip_str);
  udpPort = atoi(port_str);

  display.clearDisplay(); 
  display.setCursor(0, 0);
  display.println("WiFi Connected!");
  display.println("");
  display.print("IP: ");
  display.println(WiFi.localIP());
  display.print("Target: ");
  display.println(pcIP);
  display.display();
  delay(2000);

  // Initialize UDP
  udp.begin(udpPort);
  initRSSIHistory();
  
  // Initialize reset button pin for runtime monitoring
  pinMode(RESET_BUTTON_PIN, INPUT_PULLUP);
  Serial.println("Reset button (GPIO 17) initialized for runtime monitoring");
  
  // Initialize WiFi CSI
  // wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
  // esp_wifi_init(&cfg);
  
  wifi_csi_config_t csi_config = {
    .lltf_en = true, 
    .htltf_en = true, 
    .stbc_htltf2_en = true,
    .ltf_merge_en = true, 
    .channel_filter_en = false,
    .manu_scale = false, 
    .shift = false
  };
  esp_wifi_set_csi_config(&csi_config);
  esp_wifi_set_csi_rx_cb(csiCallback, NULL);
  esp_wifi_set_csi(true);
  
  Serial.println("CSI Monitor Ready!");
  Serial.print("Target: ");
  Serial.print(pcIP);
  Serial.print(":");
  Serial.println(udpPort);
}

unsigned long lastSend = 0;
unsigned long lastDisp = 0;
unsigned long lastResetCheck = 0;
bool resetButtonActive = false;  // Flag to pause normal display during reset

// Runtime reset check - checks periodically if button is held
void checkRuntimeReset() {
  static bool wasPressed = false;
  static unsigned long pressStart = 0;
  static unsigned long lastDisplayUpdate = 0;
  
  // Force read the pin state
  bool isPressed = (digitalRead(RESET_BUTTON_PIN) == LOW);
  
  if (isPressed && !wasPressed) {
    // Button just pressed
    pressStart = millis();
    wasPressed = true;
    resetButtonActive = true;
    lastDisplayUpdate = 0;
    Serial.println("*** RESET BUTTON PRESSED - GPIO 17 is LOW ***");
  } 
  else if (isPressed && wasPressed) {
    // Button is being held
    unsigned long elapsed = millis() - pressStart;
    
    if (elapsed >= RESET_HOLD_TIME) {
      // Reset triggered
      display.clearDisplay();
      display.setTextSize(1);
      display.setCursor(0, 0);
      display.println("RESETTING NOW!");
      display.println("");
      display.println("Clearing WiFi &");
      display.println("Config data...");
      display.display();
      
      Serial.println("*** RESET TRIGGERED - CLEARING CONFIG ***");
      
      WiFiManager wm;
      wm.resetSettings();
      clearNVSConfig();
      
      delay(2000);
      ESP.restart();
    } else {
      // Show progress on display (throttle to 100ms updates)
      if (millis() - lastDisplayUpdate >= 100) {
        lastDisplayUpdate = millis();
        
        display.clearDisplay();
        display.setTextSize(1);
        display.setCursor(0, 0);
        display.println("HOLD TO RESET");
        display.println("");
        
        int progress = map(elapsed, 0, RESET_HOLD_TIME, 0, 100);
        display.setCursor(0, 20);
        display.print("Progress: ");
        display.print(progress);
        display.println("%");
        
        // Progress bar
        int barWidth = map(elapsed, 0, RESET_HOLD_TIME, 0, 128);
        display.fillRect(0, 35, barWidth, 10, SH110X_WHITE);
        display.drawRect(0, 35, 128, 10, SH110X_WHITE);
        
        display.setCursor(0, 50);
        display.print("Time: ");
        display.print(elapsed / 1000.0, 1);
        display.print("s / 3.0s");
        
        display.display();
        
        Serial.print("Reset progress: ");
        Serial.print(progress);
        Serial.print("% (");
        Serial.print(elapsed);
        Serial.println("ms)");
      }
    }
  } 
  else if (!isPressed && wasPressed) {
    // Button released before 3 seconds
    wasPressed = false;
    resetButtonActive = false;
    Serial.println("*** RESET BUTTON RELEASED - Cancelled ***");
    
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 20);
    display.println("Reset Cancelled");
    display.display();
    delay(500);
  }
}

void loop() {
  // FAST PING (Every 20ms = ~50Hz)
  if (millis() - lastSend > PACKET_DELAY_MS) {
    lastSend = millis();
    udp.beginPacket(WiFi.gatewayIP(), udpPort);
    udp.write((uint8_t)'0');
    udp.endPacket();
  }

  // Update Display (5Hz for responsiveness) - SKIP if reset button is active
  if (!resetButtonActive && millis() - lastDisp > 200) {
    lastDisp = millis();
    updateDisplay();
  }
  
  // Check for reset button during runtime (every 50ms for better responsiveness)
  if (millis() - lastResetCheck > 50) {
    lastResetCheck = millis();
    checkRuntimeReset();
  }
  
  // WiFi watchdog
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected!");
    delay(2000); 
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Restarting...");
      ESP.restart();
    }
  }
}
