// r4_kiosk.ino (UNO R4 WiFi)
// Sends hazard "self_report" to AWS HazardIngest on selection.

#include <Arduino.h>
#include <LiquidCrystal.h>
#include <WiFiS3.h>
#include <ArduinoHttpClient.h>
#include "secrets.h"   // create from secrets.h.example and DO NOT COMMIT

// ---------------- Pins (your wiring) ----------------
const int LCD_RS = 7;
const int LCD_EN = 8;
const int LCD_D4 = 9;
const int LCD_D5 = 10;
const int LCD_D6 = 11;
const int LCD_D7 = 12;
LiquidCrystal lcd(LCD_RS, LCD_EN, LCD_D4, LCD_D5, LCD_D6, LCD_D7);

const int TRIG_PIN   = 2;
const int ECHO_PIN   = 3;
const int JOY_Y      = A0;
const int JOY_SW     = 4;
const int ALERT_LED  = 13;
const int BTN_PIN    = 5;   // optional extra button (GND when pressed)

// ---------------- App constants ----------------
const float SPEED_OF_SOUND = 0.0343; // cm/µs
const int   ALERT_DISTANCE = 40;     // cm threshold
const unsigned long ALERT_DURATION = 5000;
const unsigned long LED_TOGGLE_MS  = 250;
const unsigned long SCROLL_INTERVAL = 800;
const unsigned long JOY_COOLDOWN_MS = 300;
const int THRESH_LOW = 300, THRESH_HIGH = 700;

// Location / device metadata
const char* AREA_ID       = "Ucalgary_cross";
const char* DEVICE_ID     = "kiosk-r4-01";
const char* LOCATION_NAME = "University of Calgary - Crosswalk";
const float LAT = 51.0189;
const float LON = -114.1594;

// ---------------- State machine ----------------
enum Mode { DEMO, MENU, THANKYOU };
Mode mode = DEMO;

// ---------------- Vars ----------------
unsigned long lastUltraTime = 0;
unsigned long lastLedToggle = 0;
unsigned long alertStart = 0;
unsigned long lastJoyMoveTime = 0;
unsigned long lastScrollTime = 0;
bool alertActive = false;
bool ledState = false;

int menuIndex = 0;
int lastHazard = -1;
const char* hazards[] = {
  "Pothole", "Icy surface", "Debris", "Fallen sign",
  "Construction", "Flooded", "Poor lighting", "Broken light", "Other"
};
const int HAZ_COUNT = sizeof(hazards) / sizeof(hazards[0]);
const char* scrollText = "Press joystick to report hazard.   ";
int scrollPos = 0;
unsigned long thankStart = 0;

// ---------------- Networking ----------------
WiFiSSLClient ssl;                 // TLS client (UNO R4 WiFi)
HttpClient http(ssl, AWS_HOST, AWS_PORT);

bool netReady = false;

void wifiConnect() {
  lcd.clear();
  lcd.setCursor(0,0); lcd.print("WiFi connecting");
  lcd.setCursor(0,1); lcd.print(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - t0) < 20000) {
    delay(300);
    lcd.print(".");
  }
  netReady = (WiFi.status() == WL_CONNECTED);
  lcd.clear();
  if (netReady) {
    lcd.setCursor(0,0); lcd.print("WiFi OK ");
    lcd.setCursor(0,1); lcd.print(WiFi.localIP());
  } else {
    lcd.setCursor(0,0); lcd.print("WiFi FAILED");
    lcd.setCursor(0,1); lcd.print("Offline mode");
  }
  delay(800);
}

// Basic JSON escaper (quotes/backslashes)
String jsonEscape(const char* s) {
  String out;
  while (*s) {
    char c = *s++;
    if (c == '"' || c == '\\') { out += '\\'; out += c; }
    else out += c;
  }
  return out;
}

// Low-level POST with explicit headers/body so we can add X-API-Key
bool httpPostJson(const char* path, const String& body, int& statusOut, String& respOut) {
  http.beginRequest();
  http.post(path);
  http.sendHeader("Host", AWS_HOST);
  http.sendHeader("Content-Type", "application/json");
  http.sendHeader("X-API-Key", AWS_API_KEY);
  http.sendHeader("Connection", "close");
  http.sendHeader("Content-Length", body.length());
  http.beginBody();
  http.print(body);
  http.endRequest();

  statusOut = http.responseStatusCode();
  respOut   = http.responseBody();
  return (statusOut >= 200 && statusOut < 300);
}

// POST a hazard “self_report” to HazardIngest
bool postSelfReport(const char* category) {
  if (!netReady) return false;

  // Build JSON (omit ts so backend uses server time)
  String body = "{";
  body += "\"item_type\":\"self_report\",";
  body += "\"area_id\":\"" + String(AREA_ID) + "\",";
  body += "\"source\":\"user_report\",";
  body += "\"reported_by\":\"kiosk\",";
  body += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  body += "\"report_category\":\"" + jsonEscape(category) + "\",";
  body += "\"location_name\":\"" + jsonEscape(LOCATION_NAME) + "\",";
  body += "\"lat\":" + String(LAT, 6) + ",";
  body += "\"lon\":" + String(LON, 6);
  body += "}";

  int status = 0; String resp;
  bool ok = httpPostJson(AWS_PATH, body, status, resp);

  // one quick retry if not 2xx
  if (!ok) {
    delay(400);
    ok = httpPostJson(AWS_PATH, body, status, resp);
  }

  Serial.print("[AWS] status="); Serial.print(status);
  Serial.print(" resp="); Serial.println(resp);
  return ok;
}

// ---------------- UI screens ----------------
void showDemo() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Lest we Forget.");
  lcd.setCursor(0, 1);
  lcd.print("Press joystick...");
  scrollPos = 0;
  lastScrollTime = millis();
  mode = DEMO;
}

void updateDemo(unsigned long now) {
  if (now - lastScrollTime >= SCROLL_INTERVAL) {
    lastScrollTime = now;
    lcd.setCursor(0, 1);
    for (int j = 0; j < 16; j++) {
      int idx = scrollPos + j;
      char c = (idx < (int)strlen(scrollText)) ? scrollText[idx] : ' ';
      lcd.print(c);
    }
    scrollPos++;
    if (scrollPos > (int)strlen(scrollText) - 16) {
      scrollPos = 0;
      lastScrollTime = now + 2000;
    }
  }

  if (buttonPressed() || extraButtonPressed()) {
    showMenu();
  }
}

void showMenu() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("> ");
  lcd.print(hazards[menuIndex]);
  int len = strlen(hazards[menuIndex]);
  for (int i = len + 2; i < 16; i++) lcd.print(' ');

  lcd.setCursor(0, 1);
  lcd.print("Use Joy / Press OK");
  mode = MENU;
}

void handleMenu(unsigned long now) {
  int move = readJoystick();
  if (move != 0 && (now - lastJoyMoveTime >= JOY_COOLDOWN_MS)) {
    lastJoyMoveTime = now;
    menuIndex += move;
    if (menuIndex < 0) menuIndex = 0;
    if (menuIndex >= HAZ_COUNT) menuIndex = HAZ_COUNT - 1;
    showMenu();
  }

  if (buttonPressed() || extraButtonPressed()) {
    lastHazard = menuIndex;

    lcd.clear();
    lcd.setCursor(0,0); lcd.print("Sending...");
    lcd.setCursor(0,1); lcd.print(hazards[lastHazard]);

    bool ok = postSelfReport(hazards[lastHazard]);
    if (!ok) {
      lcd.clear();
      lcd.setCursor(0,0); lcd.print("Send failed");
      lcd.setCursor(0,1); lcd.print("Try again");
      delay(1200);
    }
    showThankYou();
  }
}

void showThankYou() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Thank you!");
  lcd.setCursor(0, 1);
  lcd.print(hazards[lastHazard]);
  thankStart = millis();
  mode = THANKYOU;
}

void handleThankYou(unsigned long now) {
  if (now - thankStart > 2000) showDemo();
}

// ---------------- Utilities ----------------
long getDistanceCM() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 25000);
  if (duration == 0) return -1;
  return duration * SPEED_OF_SOUND / 2;
}

int readJoystick() {
  int val = analogRead(JOY_Y);
  if (val < THRESH_LOW)  return +1; // down
  if (val > THRESH_HIGH) return -1; // up
  return 0;
}

bool buttonPressed() {
  static bool lastState = HIGH;
  bool current = digitalRead(JOY_SW);
  bool fired = (lastState == HIGH && current == LOW);
  lastState = current;
  return fired;
}

bool extraButtonPressed() {
  static bool last = HIGH;
  bool cur = digitalRead(BTN_PIN);
  bool fired = (last == HIGH && cur == LOW);
  last = cur;
  return fired;
}

// ---------------- Setup / Loop ----------------
void setup() {
  lcd.begin(16, 2);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(JOY_SW, INPUT_PULLUP);
  pinMode(BTN_PIN, INPUT_PULLUP);
  pinMode(ALERT_LED, OUTPUT);
  digitalWrite(ALERT_LED, LOW);

  Serial.begin(115200);

  wifiConnect();
  showDemo();
}

void loop() {
  unsigned long now = millis();

  // Ultrasonic → flash LED when someone crosses
  if (now - lastUltraTime >= 100) {
    lastUltraTime = now;
    long distance = getDistanceCM();
    if (distance > 0 && distance < ALERT_DISTANCE) {
      alertActive = true;
      alertStart = now;
    }
  }
  if (alertActive) {
    if (now - lastLedToggle >= LED_TOGGLE_MS) {
      lastLedToggle = now;
      ledState = !ledState;
      digitalWrite(ALERT_LED, ledState);
    }
    if (now - alertStart >= ALERT_DURATION) {
      alertActive = false;
      digitalWrite(ALERT_LED, LOW);
    }
  }

  // UI state machine
  switch (mode) {
    case DEMO:     updateDemo(now);   break;
    case MENU:     handleMenu(now);   break;
    case THANKYOU: handleThankYou(now); break;
  }
}
