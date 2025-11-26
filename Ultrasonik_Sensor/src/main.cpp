#include <Arduino.h>
#include <math.h>  // Untuk log() dan pow()

// ============================================
// PIN CONFIGURATION
// ============================================
const int TRIG_PIN = 13;      // Ultrasonik TRIG
const int ECHO_PIN = 12;      // Ultrasonik ECHO
const int RELAY_PIN = 25;     // Relay Pompa
const int BUZZER_PIN = 23;    // Buzzer Alarm
const int LED_PIN = 2;        // LED indikator

// Sensor TDS & Thermistor NTC
const int SUHU_PIN = 34;      // ADC Suhu
const int TDS_PIN = 32;       // ADC TDS

// ============================================
// SYSTEM SETTINGS
// ============================================
const float VREF = 3.3;       // Tegangan referensi ADC ESP32
const int AD_MAX = 4095;      // Resolusi ADC ESP32
const float DEFAULT_TEMP = 30.0;

const int JARAK_PENUH_CM = 2;
const int JARAK_RENDAH_CM = 10;
const int TDS_AMBANG_BATAS = 500;  // ppm

const int RELAY_ON = HIGH;
const int RELAY_OFF = LOW;
const float EC_CONVERSION_K = 0.5; // Faktor air umum (0.5–0.7)

const unsigned long SENSOR_INTERVAL = 300;

// ============================================
// GLOBAL VARIABLES
// ============================================
bool isPumpOn = false;
bool isAlarmActive = false;
bool isLowWaterLevel = false;
bool isTdsHigh = false;

unsigned long lastSensorRead = 0;
int jarakCm = 0;

float suhuAirC = 0.0;
float ecValue = 0.0;
int tdsPpm = 0;

// ============================================
// FUNCTION: Ukur Jarak Ultrasonik
// ============================================
int ukurJarak() {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    long durasi = pulseIn(ECHO_PIN, HIGH, 30000);
    if (durasi == 0) return 400;
    int jarak = (durasi * 0.0343) / 2;
    if (jarak > 400) return 400;
    return jarak;
}

// ============================================
// FUNCTION: Baca Suhu (Thermistor NTC 10k) Steinhart–Hart
// ============================================
float bacaSuhu() {
    int analogValue = analogRead(SUHU_PIN);
    float voltage = analogValue * (VREF / AD_MAX);

    if (voltage <= 0) return DEFAULT_TEMP;

    float resistance = (VREF * 10000.0 / voltage) - 10000.0;

    const float A = 0.001129148;
    const float B = 0.000234125;
    const float C = 0.0000000876741;

    float steinhart = log(resistance / 10000.0);
    steinhart = 1.0 / (A + B * steinhart + C * steinhart * steinhart * steinhart);
    steinhart = steinhart - 273.15;

    return steinhart;
}

// ============================================
// FUNCTION: Baca TDS + EC Akurat
// ============================================
void bacaTdsDanSuhu() {
    // --- Baca Suhu ---
    suhuAirC = bacaSuhu();
    if (suhuAirC < 0 || suhuAirC > 100) suhuAirC = DEFAULT_TEMP;

    // --- Baca Tegangan TDS ---
    int analogTDS = analogRead(TDS_PIN);
    float voltage = analogTDS * VREF / AD_MAX;

    // --- Kompensasi Suhu (Basis 25°C) ---
    float compCoef = 1.0 + 0.02 * (suhuAirC - 25.0);
    float vComp = voltage / compCoef;

    // --- Hitung EC dari Tegangan ---
    ecValue = (133.42 * pow(vComp, 3)
             - 255.86 * pow(vComp, 2)
             + 857.39 * vComp);

    if (ecValue < 0) ecValue = 0;

    // --- Konversi EC ke TDS (ppm) ---
    tdsPpm = ecValue * EC_CONVERSION_K;
    if (tdsPpm < 0) tdsPpm = 0;

    // --- Status TDS ---
    isTdsHigh = (tdsPpm > TDS_AMBANG_BATAS);
}

// ============================================
// FUNCTION: Kirim Data ke PC/Python/UI
// ============================================
void kirimDataStatus() {
    Serial.print("DATA: ");
    Serial.print("Jarak:"); Serial.print(jarakCm); Serial.print(" | ");
    Serial.print("TDS:"); Serial.print(tdsPpm); Serial.print(" | ");
    Serial.print("EC:"); Serial.print(ecValue, 1); Serial.print(" | ");
    Serial.print("Suhu:"); Serial.print(suhuAirC, 1); Serial.print(" | ");
    Serial.print("Pompa:"); Serial.print(isPumpOn ? "1" : "0"); Serial.print(" | ");
    Serial.print("Alarm:"); Serial.print(isAlarmActive ? "1" : "0"); Serial.print(" | ");
    Serial.print("Level Air:");

    if (jarakCm <= JARAK_PENUH_CM && jarakCm > 0) {
        Serial.println("PENUH");
    } else if (isLowWaterLevel) {
        Serial.println("RENDAH");
    } else {
        Serial.println("SEDANG");
    }
}

// ============================================
// FUNCTION: Kontrol Pompa
// ============================================
void setPump(bool turnOn, const char* reason = "MANUAL") {
    if (turnOn != isPumpOn) {
        digitalWrite(RELAY_PIN, turnOn ? RELAY_ON : RELAY_OFF);
        digitalWrite(LED_PIN, turnOn ? HIGH : LOW);
        isPumpOn = turnOn;

        Serial.println("--- LOG DEBUG ---");
        Serial.print(turnOn ? "POMPA START (Picu: " : "POMPA STOP (Picu: ");
        Serial.print(reason);
        Serial.println(")");
        Serial.println("-----------------");
    }
}

// ============================================
// FUNCTION: Kontrol Alarm
// ============================================
void setAlarm(bool active, const char* reason = "LEVEL AIR") {
    if (active != isAlarmActive) {
        digitalWrite(BUZZER_PIN, active ? HIGH : LOW);
        isAlarmActive = active;

        Serial.println("--- LOG DEBUG ---");
        Serial.print(active ? "ALARM AKTIF: " : "ALARM MATI (Picu: ");
        Serial.print(reason);
        Serial.println(")");
        Serial.println("-----------------");
    }
}

// ============================================
// FUNCTION: Perintah Serial UI
// ============================================
void handleSerialCommand() {
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();
        command.toLowerCase();

        if (command == "1") {
            if (isTdsHigh) {
                Serial.println("REJECT: TDS high");
            } else if (isLowWaterLevel) {
                if (!isPumpOn) setPump(true, "UI START");
                else Serial.println("INFO: Pump already ON");
            } else {
                Serial.println("REJECT: Water level not low");
            }
        } else if (command == "stop") {
            if (isPumpOn) setPump(false, "UI STOP");
            else Serial.println("INFO: Pump already OFF");
        }
    }
}

// ============================================
// SETUP
// ============================================
void setup() {
    delay(500);
    Serial.begin(115200);
    Serial.println("System Booting...");

    pinMode(RELAY_PIN, OUTPUT);
    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    pinMode(BUZZER_PIN, OUTPUT);
    pinMode(LED_PIN, OUTPUT);

    digitalWrite(RELAY_PIN, RELAY_OFF);
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(LED_PIN, LOW);
    delay(800);
    Serial.println("System Ready. Sending data to UI...");
}

// ============================================
// LOOP
// ============================================
void loop() {
    unsigned long now = millis();
    handleSerialCommand();

    if (now - lastSensorRead >= SENSOR_INTERVAL) {
        lastSensorRead = now;

        jarakCm = ukurJarak();
        bacaTdsDanSuhu();
        isLowWaterLevel = (jarakCm >= JARAK_RENDAH_CM);

        kirimDataStatus();

        if (isTdsHigh) {
            if (isPumpOn) setPump(false, "Auto-Stop TDS TINGGI");
            setAlarm(true, "TDS TINGGI");
        } else if (jarakCm <= JARAK_PENUH_CM && jarakCm > 0) {
            if (isPumpOn) setPump(false, "Auto-Stop PENUH");
            setAlarm(true, "Air PENUH");
        } else {
            setAlarm(false);
        }
    }
    delay(10);
}
