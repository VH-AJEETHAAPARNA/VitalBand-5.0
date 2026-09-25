/*
 * VitalBand — Wrist Patch firmware (ESP32 + MAX30102 + I2C LCD + SOS button)
 * ==========================================================================
 * Replaces the MPU6050 used in the Wokwi simulation with the real MAX30102
 * pulse-oximeter. The WIRING IS UNCHANGED: the MAX30102 is an I2C device just
 * like the MPU6050, so it sits on the same SDA/SCL pair alongside the LCD.
 * Only the address differs (MAX30102 = 0x57, MPU6050 was 0x68).
 *
 * WHAT IT DOES
 *   - Reads heart rate + SpO2 from the MAX30102
 *   - Shows them live on the I2C LCD
 *   - Sends telemetry to the VitalBand backend every 5 s
 *   - SOS button fires an INSTANT, unconditional alert (no AI, no threshold,
 *     no cooldown) — this is the deterministic safety path
 *
 * FIRST-RUN CHECKLIST
 *   1. Set WIFI_SSID / WIFI_PASSWORD
 *   2. Set BACKEND_URL (see the ngrok note below)
 *   3. Open Serial Monitor at 115200 — the boot I2C scan prints every address
 *      it finds. You should see 0x57 (MAX30102) and your LCD (0x27 or 0x3F).
 *      If the LCD address differs, set LCD_ADDR to what the scan reports.
 *
 * LIBRARIES (Arduino IDE -> Library Manager)
 *   - "SparkFun MAX3010x Pulse and Proximity Sensor Library"
 *   - "LiquidCrystal I2C" by Frank de Brabander
 *   (ESP32 board package: Boards Manager -> "esp32" by Espressif)
 */

#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <LiquidCrystal_I2C.h>

#include "MAX30105.h"          // works for MAX30102
#include "heartRate.h"         // BPM detector
#include "spo2_algorithm.h"    // Maxim SpO2 algorithm

// ─────────────────────────── CONFIGURE ME ───────────────────────────────────

const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Local backend on the same network, e.g. "http://192.168.1.50:5000"
// or an ngrok HTTPS URL, e.g. "https://abc123.ngrok-free.app"
//
// NGROK WARNING: the free tier mints a NEW random URL every restart. If posts
// suddenly fail, check whether ngrok was restarted after you last flashed.
const char* BACKEND_URL = "http://192.168.1.50:5000";

// Must match the patient card you want this band to drive on the dashboard.
const char* PATIENT_ID  = "P001";
const char* DEVICE_ID   = "wrist_01";
const char* HOSPITAL_ID = "DEFAULT_HOSP";

// ─────────────────────────── PINS ───────────────────────────────────────────
// ESP32 default I2C. Both the LCD and the MAX30102 share this one bus —
// that is why swapping MPU6050 -> MAX30102 needs no rewiring.
#define I2C_SDA        21
#define I2C_SCL        22

// Verify these two against your board. In the simulation the button goes to
// GND (hence INPUT_PULLUP) and the LED sits behind a resistor.
#define SOS_BUTTON_PIN  4
#define LED_PIN         2

// LCD geometry + address. Change to 20, 4 if you have a 20x4 module.
#define LCD_ADDR 0x27
#define LCD_COLS 16
#define LCD_ROWS 2

// ─────────────────────────── TUNING ─────────────────────────────────────────
const unsigned long SEND_INTERVAL_MS   = 5000;   // telemetry cadence
const unsigned long LCD_REFRESH_MS     = 500;
const unsigned long SOS_DEBOUNCE_MS    = 250;
const long          FINGER_THRESHOLD   = 50000;  // IR level meaning "finger on"
const byte          RATE_HISTORY       = 4;      // BPM smoothing window

// ─────────────────────────── STATE ──────────────────────────────────────────

MAX30105 particleSensor;
LiquidCrystal_I2C lcd(LCD_ADDR, LCD_COLS, LCD_ROWS);

// Beat detection
byte  rates[RATE_HISTORY];
byte  rateSpot   = 0;
long  lastBeat   = 0;
float beatsPerMinute = 0;
int   beatAvg    = 0;

// SpO2 (Maxim algorithm works on a rolling 100-sample buffer)
#define SPO2_BUFFER_LEN 100
uint32_t irBuffer[SPO2_BUFFER_LEN];
uint32_t redBuffer[SPO2_BUFFER_LEN];
int32_t  spo2          = 0;
int8_t   validSPO2     = 0;
int32_t  heartRateAlgo = 0;
int8_t   validHeartRate = 0;
int      bufferIndex   = 0;
bool     spo2Warmed    = false;

bool fingerPresent = false;

unsigned long lastSend      = 0;
unsigned long lastLcd       = 0;
volatile unsigned long lastSosPress = 0;
volatile bool sosPending = false;

// ─────────────────────────── SOS (deterministic path) ───────────────────────
// Kept as an ISR so a button press is never missed while the main loop is busy
// talking to WiFi. The ISR only sets a flag; the network call happens in loop().
void IRAM_ATTR onSosPressed() {
  unsigned long now = millis();
  if (now - lastSosPress < SOS_DEBOUNCE_MS) return;  // debounce
  lastSosPress = now;
  sosPending = true;
}

// ─────────────────────────── HELPERS ────────────────────────────────────────

void i2cScan() {
  Serial.println(F("\n--- I2C scan ---"));
  byte found = 0;
  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  device at 0x%02X", addr);
      if (addr == 0x57) Serial.print(F("   <- MAX30102"));
      if (addr == 0x27 || addr == 0x3F) Serial.print(F("   <- LCD"));
      Serial.println();
      found++;
    }
  }
  if (found == 0) {
    Serial.println(F("  NOTHING FOUND. Check SDA/SCL and that both modules have 3V3 + GND."));
  }
  Serial.println(F("----------------\n"));
}

void lcdTwoLines(const String& l1, const String& l2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(l1.substring(0, LCD_COLS));
  if (LCD_ROWS > 1) {
    lcd.setCursor(0, 1);
    lcd.print(l2.substring(0, LCD_COLS));
  }
}

void connectWiFi() {
  Serial.printf("Connecting to %s", WIFI_SSID);
  lcdTwoLines("VitalBand", "WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long deadline = millis() + 20000;
  while (WiFi.status() != WL_CONNECTED && millis() < deadline) {
    delay(400);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print(F("WiFi OK, IP: "));
    Serial.println(WiFi.localIP());
    lcdTwoLines("WiFi connected", WiFi.localIP().toString());
  } else {
    // Not fatal: vitals still show on the LCD, which is what the patient and
    // a nearby nurse can actually see. Only the dashboard misses out.
    Serial.println(F("WiFi FAILED - running offline (LCD only)"));
    lcdTwoLines("WiFi failed", "LCD-only mode");
  }
  delay(1200);
}

/*
 * One POST helper for every endpoint.
 *
 * CRITICAL ESP32 DETAIL: for an https:// target you MUST use WiFiClientSecure
 * with setInsecure() and http.begin(client, url). A plain http.begin(url)
 * against an HTTPS URL fails with -1 / "connection refused". Plain http://
 * targets use the ordinary path.
 */
bool postJson(const String& path, const String& payload) {
  if (WiFi.status() != WL_CONNECTED) return false;

  String url = String(BACKEND_URL) + path;
  HTTPClient http;
  bool ok = false;
  int code = -1;

  if (url.startsWith("https://")) {
    WiFiClientSecure secureClient;
    secureClient.setInsecure();               // no cert pinning for the demo
    if (http.begin(secureClient, url)) {
      http.addHeader("Content-Type", "application/json");
      http.setTimeout(5000);
      code = http.POST(payload);
      http.end();
    }
  } else {
    if (http.begin(url)) {
      http.addHeader("Content-Type", "application/json");
      http.setTimeout(5000);
      code = http.POST(payload);
      http.end();
    }
  }

  ok = (code > 0 && code < 400);
  Serial.printf("POST %s -> %d\n", path.c_str(), code);
  return ok;
}

void sendSos() {
  Serial.println(F("*** SOS PRESSED ***"));
  digitalWrite(LED_PIN, HIGH);
  lcdTwoLines("** SOS SENT **", "Help requested");

  String body = String("{\"device_id\":\"") + DEVICE_ID +
                "\",\"patient_id\":\"" + PATIENT_ID +
                "\",\"hospital_id\":\"" + HOSPITAL_ID + "\"}";
  postJson("/api/sos", body);

  delay(1500);
  digitalWrite(LED_PIN, LOW);
}

void sendVitals(int hr, int spo2Value) {
  String body = String("{\"device_id\":\"") + DEVICE_ID +
                "\",\"patient_id\":\"" + PATIENT_ID +
                "\",\"hospital_id\":\"" + HOSPITAL_ID +
                "\",\"heart_rate\":" + String(hr) +
                ",\"spo2\":" + String(spo2Value) +
                ",\"fall\":false,\"sos\":false}";
  postJson("/api/sensor", body);
}

// ─────────────────────────── SETUP ──────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println(F("\n\nVitalBand wrist patch booting..."));

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(SOS_BUTTON_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(SOS_BUTTON_PIN), onSosPressed, FALLING);

  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);

  lcd.init();
  lcd.backlight();
  lcdTwoLines("VitalBand", "Starting...");

  i2cScan();

  // MAX30102 on the shared bus
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println(F("MAX30102 NOT FOUND at 0x57."));
    Serial.println(F("  - check 3V3 (NOT 5V on most breakouts), GND, SDA, SCL"));
    lcdTwoLines("MAX30102 ERROR", "Check wiring");
    // Do not hang: the SOS button must keep working even with a dead sensor.
  } else {
    Serial.println(F("MAX30102 ready."));
    // 0x1F..0xFF LED power. Higher = better signal but more heat/current.
    particleSensor.setup(0x3F, 4, 2, 400, 411, 4096);
    particleSensor.setPulseAmplitudeRed(0x0A);
    particleSensor.setPulseAmplitudeIR(0x1F);
    particleSensor.setPulseAmplitudeGreen(0);   // MAX30102 has no green LED
  }

  connectWiFi();
  lcdTwoLines("Place finger", "on sensor");
}

// ─────────────────────────── LOOP ───────────────────────────────────────────

void loop() {
  // 1. SOS first, always. Nothing below may delay or suppress it.
  if (sosPending) {
    sosPending = false;
    sendSos();
  }

  // 2. Sample the sensor
  long irValue  = particleSensor.getIR();
  long redValue = particleSensor.getRed();

  bool nowPresent = (irValue > FINGER_THRESHOLD);
  if (nowPresent != fingerPresent) {
    fingerPresent = nowPresent;
    if (!fingerPresent) {
      // Reset derived values so the LCD never shows a stale BPM from the
      // last person once the finger is lifted.
      beatAvg = 0;
      beatsPerMinute = 0;
      spo2 = 0;
      validSPO2 = 0;
      bufferIndex = 0;
      spo2Warmed = false;
    }
  }

  if (fingerPresent) {
    // ── Beat detection (fast, per-sample) ──
    if (checkForBeat(irValue)) {
      long delta = millis() - lastBeat;
      lastBeat = millis();
      float bpm = 60.0 / (delta / 1000.0);

      if (bpm > 20 && bpm < 255) {
        rates[rateSpot++] = (byte)bpm;
        rateSpot %= RATE_HISTORY;
        int total = 0;
        for (byte i = 0; i < RATE_HISTORY; i++) total += rates[i];
        beatAvg = total / RATE_HISTORY;
      }
    }

    // ── SpO2 (needs a rolling 100-sample window) ──
    redBuffer[bufferIndex] = redValue;
    irBuffer[bufferIndex]  = irValue;
    bufferIndex++;

    if (bufferIndex >= SPO2_BUFFER_LEN) {
      bufferIndex = 0;
      spo2Warmed = true;
      maxim_heart_rate_and_oxygen_saturation(
        irBuffer, SPO2_BUFFER_LEN, redBuffer,
        &spo2, &validSPO2, &heartRateAlgo, &validHeartRate);
    }
  }

  particleSensor.nextSample();

  // 3. LCD refresh
  if (millis() - lastLcd >= LCD_REFRESH_MS) {
    lastLcd = millis();

    if (!fingerPresent) {
      lcdTwoLines("Place finger", "on sensor");
    } else if (!spo2Warmed && beatAvg == 0) {
      lcdTwoLines("Reading...", "Hold still");
    } else {
      String l1 = "HR:" + (beatAvg > 0 ? String(beatAvg) : String("--")) + " BPM";
      String l2 = "SpO2:" +
                  ((validSPO2 && spo2 > 0 && spo2 <= 100) ? String(spo2) : String("--")) + "%";
      lcdTwoLines(l1, l2);
    }
  }

  // 4. Telemetry
  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();
    if (fingerPresent && beatAvg > 0) {
      int spo2Out = (validSPO2 && spo2 > 0 && spo2 <= 100) ? (int)spo2 : 0;
      Serial.printf("HR=%d  SpO2=%d  IR=%ld\n", beatAvg, spo2Out, irValue);
      sendVitals(beatAvg, spo2Out);
    } else {
      Serial.printf("no finger (IR=%ld)\n", irValue);
    }
  }
}
