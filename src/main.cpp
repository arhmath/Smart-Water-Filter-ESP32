#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <math.h>

// ⭐ PUSTAKA DS18B20
#include <OneWire.h>
#include <DallasTemperature.h>

// ============================================
// WIFI & MQTT CONFIGURATION
// ============================================
const char* ssid = "arshaez";
const char* password = "arham1304";

// ⭐ GANTI DARI BROKER PUBLIK KE BLINK (Anda harus menginstal Blynk ESP32 Library)
#define BLYNK_TEMPLATE_ID "TMPL6a4Z3d3aC"
#define BLYNK_TEMPLATE_NAME "Smart Water Filter"
#define BLYNK_AUTH_TOKEN "lIeWudgNmA2qSJXR2POCY0Dqqu72IAfi"

// Gunakan Blynk Library dan hapus PubSubClient
#include <BlynkSimpleEsp32.h> // ⭐ TAMBAH PUSTAKA BLYNK

const char* mqtt_server = "broker.emqx.io";
const int mqtt_port = 1883;
const char* mqtt_client_id = "SmartFilter_ESP32_A1";

// MQTT Topics
const char* topic_data = "smartwater/data";
const char* topic_control = "smartwater/control";
const char* topic_status = "smartwater/status";

WiFiClient espClient;
PubSubClient mqtt(espClient);

// ============================================
// PIN CONFIGURATION
// ============================================
const int TRIG_PIN = 13;
const int ECHO_PIN = 12;
const int RELAY_PIN = 25;
const int BUZZER_PIN = 5;
const int LED_PIN = 2;

// ⭐ PIN SUHU DS18B20 (Digital Pins)
const int SUHU_INPUT_PIN = 32;       // Pin Digital untuk DS18B20 Input
const int TDS_INPUT_PIN = 34;        // ADC1_CH6 (TDS tetap ADC)

const int SUHU_OUTPUT_PIN = 33;      // Pin Digital untuk DS18B20 Output
const int TDS_OUTPUT_PIN = 35;       // ADC1_CH7 (TDS tetap ADC)

// ============================================
// DS18B20 OBJECTS
// ============================================
OneWire oneWireInput(SUHU_INPUT_PIN);
DallasTemperature sensorInput(&oneWireInput);

OneWire oneWireOutput(SUHU_OUTPUT_PIN);
DallasTemperature sensorOutput(&oneWireOutput);

// ============================================
// SYSTEM SETTINGS
// ============================================
const float VREF = 3.3;
const int AD_MAX = 4095;
const float DEFAULT_TEMP = 25.0;

const int JARAK_PENUH_CM = 5;
const int JARAK_RENDAH_CM = 10;
const int TDS_AMBANG_BATAS = 1000;
const int MAX_USE_COUNT = 50;

const int RELAY_ON = HIGH;
const int RELAY_OFF = LOW;

// ⭐ KALIBRASI TDS - SESUAIKAN DENGAN SENSOR ANDA
const float TDS_KVALUE = 0.25;  // Faktor kalibrasi (0.5 untuk sensor TDS standar)

// ⭐ INTERVAL DIKURANGI DARI 3000ms MENJADI 1000ms
const unsigned long SENSOR_INTERVAL = 1000;
const unsigned long MQTT_PUBLISH_INTERVAL = 1000;
const unsigned long MQTT_RECONNECT_INTERVAL = 10000;

// ⭐ DS18B20 TIME (UNTUK NON-BLOCKING DELAY)
// 10-bit resolution = 187ms, 12-bit = 750ms
const unsigned long TEMP_CONVERSION_TIME_MS = 200; // 10-bit res + buffer

// ⭐ DELAY TDS SETELAH PUMP CHANGE UNTUK MENGURANGI NOISE
const unsigned long TDS_STABILIZE_DELAY_MS = 3000; // 3 detik setelah pompa berubah

const unsigned long TDS_DELAY_AFTER_PUMP_ON = 5000;   // 5 detik delay setelah pump ON
const unsigned long TDS_DELAY_AFTER_PUMP_OFF = 3000;  // 3 detik delay setelah pump OFF
// ============================================
// GLOBAL VARIABLES
// ============================================
bool isPumpOn = false;
bool isAlarmActive = false;
bool isLowWaterLevel = false;
bool isTdsHighInput = false;
bool isTdsHighOutput = false;
bool mqttConnected = false;

unsigned long lastSensorRead = 0;
unsigned long lastMqttPublish = 0;
unsigned long lastMqttReconnect = 0;
unsigned long lastTempRequest = 0; // Untuk non-blocking temp read
unsigned long lastPumpChange = 0; // Track waktu perubahan pompa untuk delay TDS

int jarakCm = 0;

float suhuInputC = 0.0;
float ecInputValue = 0.0;
int tdsInputPpm = 0;

float suhuOutputC = 0.0;
float ecOutputValue = 0.0;
int tdsOutputPpm = 0;

float filterEfficiency = 0.0;
int useCount = 0;

int rawAdcTdsInput = 0;
int rawAdcTdsOutput = 0;

bool isProbeInputInWater = false;
bool isProbeOutputInWater = false;

int lastValidTdsInput = 0;
int lastValidTdsOutput = 0;
float lastValidEcInput = 0.0;
float lastValidEcOutput = 0.0;

const int ADC_MIN_WATER = 150;
const int ADC_MAX_WATER = 3900;
const int TDS_MAX_VALID = 1500;
bool tdsReadingStable = true;
// ============================================
// FUNCTION PROTOTYPES
// ============================================
void publishStatus(String status, String message);
void setPump(bool turnOn, const char* reason);
void setAlarm(bool active, const char* reason);
void mqtt_callback(char* topic, byte* payload, unsigned int length);
void reconnect_mqtt();
void publishSensorData();
int ukurJarak();
float bacaSuhuNonBlocking(DallasTemperature* sensor, const char* label);
void bacaTDS(int tdsPin, float suhu, float &ecValue, int &tdsPpm, int &rawAdc, bool &isInWater, int &lastValidTds, float &lastValidEc);
void bacaSemuaSensor();

// ============================================
// WIFI CONNECTION (Unchanged)
// ============================================
void setup_wifi() {
    delay(10);
    Serial.println();
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.print("Connecting to WiFi: ");
    Serial.println(ssid);

    WiFi.disconnect(true);
    delay(1000);
    WiFi.mode(WIFI_STA);

    Serial.print("MAC Address: ");
    Serial.println(WiFi.macAddress());
    
    WiFi.begin(ssid, password);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");

        if (attempts % 5 == 0 && attempts > 0) {
            Serial.println();
            Serial.print("Status: ");
            Serial.print(WiFi.status());
            Serial.print(" | Try: ");
            Serial.print(attempts);
            Serial.print("/30");
        }
        attempts++;
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("✓ WiFi Connected!");
        Serial.print("IP: ");
        Serial.println(WiFi.localIP());
        Serial.print("RSSI: ");
        Serial.print(WiFi.RSSI());
        Serial.println(" dBm");
    } else {
        Serial.println("✗ WiFi Failed!");
        Serial.print("Status: ");
        Serial.println(WiFi.status());
    }
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━");
}

// ============================================
// MQTT CALLBACK (Unchanged)
// ============================================
void mqtt_callback(char* topic, byte* payload, unsigned int length) {
    String message = "";
    for (unsigned int i = 0; i < length; i++) {
        message += (char)payload[i];
    }

    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.println("📨 MQTT Received");
    Serial.print("Topic: ");
    Serial.println(topic);
    Serial.print("Message: ");
    Serial.println(message);
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    StaticJsonDocument<200> doc;
    DeserializationError error = deserializeJson(doc, message);

    if (error) {
        Serial.print("✗ JSON Error: ");
        Serial.println(error.c_str());
        return;
    }

    String command = doc["command"].as<String>();

    if (command == "START_PUMP") {
        if (isTdsHighOutput || useCount >= MAX_USE_COUNT) {
            Serial.println("✗ REJECT: Filter limit/TDS tinggi!");
            publishStatus("REJECT", "Ganti filter, batas pemakaian/TDS tinggi");
        } else if (jarakCm <= JARAK_PENUH_CM && jarakCm > 0) {
            Serial.println("✗ REJECT: Water level penuh");
            publishStatus("REJECT", "Water level penuh, tidak perlu diisi");
        } else {
            setPump(true, "MQTT Command");
            publishStatus("SUCCESS", "Pompa diaktifkan");
        }
    } 
    else if (command == "STOP_PUMP") {
        setPump(false, "MQTT Command");
        publishStatus("SUCCESS", "Pompa dimatikan");
    } 
    else if (command == "ALARM_OFF") {
        setAlarm(false, "MQTT Command");
        publishStatus("SUCCESS", "Alarm dimatikan");
    } 
    else if (command == "RESET_USE_COUNT") {
        useCount = 0;
        publishStatus("SUCCESS", "Filter use count direset");
        Serial.println("✓ Use Count Reset to 0!");
    } 
    else {
        Serial.print("✗ Unknown command: ");
        Serial.println(command);
    }
}

// ============================================
// MQTT RECONNECT (Unchanged)
// ============================================
void reconnect_mqtt() {
    unsigned long now = millis();

    if (now - lastMqttReconnect < MQTT_RECONNECT_INTERVAL) {
        return;
    }

    lastMqttReconnect = now;

    if (!mqtt.connected() && WiFi.status() == WL_CONNECTED) {
        Serial.print("🔄 MQTT Connecting... ");

        if (mqtt.connect(mqtt_client_id)) {
            Serial.println("✓ OK!");
            mqttConnected = true;
            mqtt.subscribe(topic_control);
            Serial.print("✓ Subscribed: ");
            Serial.println(topic_control);

            publishStatus("ONLINE", "ESP32 Connected");
        } else {
            Serial.print("✗ Failed rc=");
            Serial.println(mqtt.state());
            mqttConnected = false;
        }
    }
}

// ============================================
// PUBLISH STATUS (Unchanged)
// ============================================
void publishStatus(String status, String message) {
    if (!mqtt.connected()) return;

    StaticJsonDocument<200> doc;
    doc["status"] = status;
    doc["message"] = message;
    doc["timestamp"] = millis();

    char buffer[256];
    serializeJson(doc, buffer);

    if (mqtt.publish(topic_status, buffer)) {
        Serial.println("✓ Status sent");
    }
}

// ============================================
// PUBLISH SENSOR DATA (Unchanged)
// ============================================
void publishSensorData() {
    if (!mqtt.connected()) return;

    StaticJsonDocument<512> doc;

    doc["jarak_cm"] = jarakCm;
    doc["tds_input"] = tdsInputPpm;
    doc["ec_input"] = ecInputValue;
    doc["suhu_input"] = suhuInputC;
    doc["tds_output"] = tdsOutputPpm;
    doc["ec_output"] = ecOutputValue;
    doc["suhu_output"] = suhuOutputC;
    doc["filter_efficiency"] = filterEfficiency;

    doc["use_count"] = useCount;

    doc["probe_input_in_water"] = isProbeInputInWater;
    doc["probe_output_in_water"] = isProbeOutputInWater;

    doc["pump_on"] = isPumpOn;
    doc["alarm_active"] = isAlarmActive;
    doc["low_water"] = isLowWaterLevel;
    doc["tds_high_input"] = isTdsHighInput;
    doc["tds_high_output"] = isTdsHighOutput;

    if (jarakCm <= JARAK_PENUH_CM && jarakCm > 0)
        doc["water_level"] = "PENUH";
    else if (isLowWaterLevel)
        doc["water_level"] = "RENDAH";
    else
        doc["water_level"] = "SEDANG";

    doc["timestamp"] = millis();

    char buffer[512];
    serializeJson(doc, buffer);

    if (mqtt.publish(topic_data, buffer)) {
        Serial.println("✓ Data published");
    }
}

BLYNK_WRITE(V1) { 
    int pumpState = param.asInt();
    String command = pumpState ? "START_PUMP" : "STOP_PUMP";

    Serial.print("Blynk Command Received: ");
    Serial.println(command);

    if (command == "START_PUMP") {
        if (isTdsHighOutput || useCount >= MAX_USE_COUNT) {
            setAlarm(true, "Filter Limit/TDS tinggi");
        } else if (jarakCm <= JARAK_PENUH_CM && jarakCm > 0) {
            setAlarm(true, "Water level penuh");
        } else {
            setPump(true, "Blynk Command");
        }
    } else if (command == "STOP_PUMP") {
        setPump(false, "Blynk Command");
    }
}

// ============================================
// ULTRASONIC SENSOR (Unchanged)
// ============================================
int ukurJarak() {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    unsigned long durasi = pulseIn(ECHO_PIN, HIGH, 30000);
    if (durasi == 0) return 400;

    int jarak = (int)((durasi * 0.0343) / 2.0);
    if (jarak > 400) return 400;

    return jarak;
}

// ============================================
// ⭐ SUHU SENSOR DS18B20 - NON-BLOCKING
// ============================================
float bacaSuhuNonBlocking(DallasTemperature* sensor, const char* label) {
    float tempC = sensor->getTempCByIndex(0);

    // Diagnostik
    if (tempC == DEVICE_DISCONNECTED_C || tempC == -127.0) {
        Serial.print(" ❌ SUHU ");
        Serial.print(label);
        Serial.println(": SENSOR DS18B20 TIDAK TERHUBUNG/BELUM SIAP!");
        return DEFAULT_TEMP; // Gunakan suhu terakhir yang valid atau default
    }

    if (tempC < -50.0 || tempC > 120.0) {
        Serial.print("   ️ SUHU ");
        Serial.print(label);
        Serial.print(": Pembacaan aneh (");
        Serial.print(tempC, 1);
        Serial.println("°C). Gunakan default.");
        return DEFAULT_TEMP;
    }

    return tempC;
}

// ============================================
// ⭐ TDS SENSOR - OPTIMIZED DELAY
// ============================================
void bacaTDS(int tdsPin, float suhu, float &ecValue, int &tdsPpm, int &rawAdc, bool &isInWater, int &lastValidTds, float &lastValidEc) {
    
    // ⭐ CEGAH PEMBACAAN JIKA PUMP BARU SAJA BERUBAH
    unsigned long timeSincePumpChange = millis() - lastPumpChange;
    
    if (!tdsReadingStable) {
        unsigned long delayRequired = isPumpOn ? TDS_DELAY_AFTER_PUMP_ON : TDS_DELAY_AFTER_PUMP_OFF;
        
        if (timeSincePumpChange < delayRequired) {
            Serial.printf("  ⏳ TDS STABILIZING... (%lu/%lu ms)\n", 
                         timeSincePumpChange, delayRequired);
            // Gunakan nilai terakhir yang valid
            tdsPpm = lastValidTds;
            ecValue = lastValidEc;
            return;
        } else {
            tdsReadingStable = true;
            Serial.println("  ✅ TDS STABLE - Mulai pembacaan");
        }
    }
    
    // ⭐ SET ATENUASI PER-PIN
    analogSetPinAttenuation(tdsPin, ADC_11db);
    pinMode(tdsPin, INPUT);
    delay(20);

    // ⭐ BUANG PEMBACAAN AWAL (WARMUP)
    for (int i = 0; i < 10; i++) {
        analogRead(tdsPin);
        delay(3);
    }

    // ⭐ SAMPLING DENGAN OUTLIER REJECTION
    const int totalSamples = 50;
    const int validSamples = 30;
    int readings[totalSamples];
    
    for (int i = 0; i < totalSamples; i++) {
        readings[i] = analogRead(tdsPin);
        delay(5);
    }
    
    // Sort untuk median filter
    for (int i = 0; i < totalSamples - 1; i++) {
        for (int j = i + 1; j < totalSamples; j++) {
            if (readings[i] > readings[j]) {
                int temp = readings[i];
                readings[i] = readings[j];
                readings[j] = temp;
            }
        }
    }
    
    // Ambil median (buang 10 terendah & 10 tertinggi)
    long sum = 0;
    int startIdx = (totalSamples - validSamples) / 2;
    for (int i = startIdx; i < startIdx + validSamples; i++) {
        sum += readings[i];
    }
    rawAdc = sum / validSamples;
    
    // ⭐ JIKA PUMP MENYALA, TAMBAHKAN EXTRA VALIDATION
    if (isPumpOn) {
        float mean = rawAdc;
        float variance = 0;
        for (int i = startIdx; i < startIdx + validSamples; i++) {
            variance += pow(readings[i] - mean, 2);
        }
        float stdDev = sqrt(variance / validSamples);
        
        if (stdDev > 150) {
            Serial.printf("  ⚠️ HIGH NOISE (SD=%.1f) - Using last valid\n", stdDev);
            tdsPpm = lastValidTds;
            ecValue = lastValidEc;
            return;
        }
    }
    
    float voltage = rawAdc * (VREF / (float)AD_MAX);

    Serial.print("  [Pin ");
    Serial.print(tdsPin);
    Serial.print("] ADC=");
    Serial.print(rawAdc);
    Serial.print(" (");
    Serial.print(voltage, 3);
    Serial.print("V)");
    
    if (isPumpOn) Serial.print(" [PUMP ON]");

    // Deteksi probe terendam atau tidak
    if (rawAdc >= ADC_MAX_WATER) {
        Serial.println(" ❌ PROBE KERING/SHORT (ADC MAX)!");
        isInWater = false;
        tdsPpm = lastValidTds;
        ecValue = lastValidEc;
        return;
    }

    if (rawAdc <= ADC_MIN_WATER) {
        Serial.println(" ⚠️ PROBE BELUM TERENDAM AIR (ADC MIN)!");
        isInWater = false;
        tdsPpm = 0;
        ecValue = 0;
        lastValidTds = 0;
        lastValidEc = 0;
        return;
    }

    isInWater = true;

    // Temperature compensation
    float tempCoefficient = 1.0 + 0.02 * (suhu - 25.0);
    float voltageCompensated = voltage / tempCoefficient;

    // Hitung TDS
    float tdsValue = (133.42 * voltageCompensated * voltageCompensated * voltageCompensated
                     - 255.86 * voltageCompensated * voltageCompensated
                     + 857.39 * voltageCompensated) * TDS_KVALUE;

    // ⭐ VALIDASI PERUBAHAN DRASTIS
    if (lastValidTds > 0) {
        float changePercent = abs(tdsValue - lastValidTds) / (float)lastValidTds * 100.0;
        
        if (changePercent > 50.0 && isPumpOn) {
            Serial.printf(" ⚠️ ANOMALY (%.0f%% change) - Using last valid\n", changePercent);
            tdsPpm = lastValidTds;
            ecValue = lastValidEc;
            return;
        }
    }

    // Limit TDS
    if (tdsValue < 0) tdsValue = 0;
    if (tdsValue > TDS_MAX_VALID) {
        Serial.print(" ⚠️ TDS TERLALU TINGGI (");
        Serial.print(tdsValue, 0);
        Serial.println(" PPM) - Gunakan nilai terakhir");
        tdsPpm = lastValidTds;
        ecValue = lastValidEc;
        return;
    }

    tdsPpm = (int)tdsValue;

    // Hitung EC dari TDS
    ecValue = tdsValue / 0.64;

    if (ecValue < 0) ecValue = 0;
    if (ecValue > 3200) ecValue = 3200;

    lastValidTds = tdsPpm;
    lastValidEc = ecValue;

    Serial.print(" ✅ TDS=");
    Serial.print(tdsPpm);
    Serial.print(" PPM | EC=");
    Serial.print(ecValue, 1);
    Serial.println(" µS/cm");
}

// ============================================
// READ ALL SENSORS
// ============================================
void bacaSemuaSensor() {
    unsigned long now = millis();

    Serial.println("\n━━━━━━━━━ READING SENSORS ━━━━━━━━━");

    // ⭐ TEMPERATURE
    if (now - lastTempRequest >= TEMP_CONVERSION_TIME_MS) {
        Serial.println("🌡️  Temperature (GET)...");
        
        suhuInputC = bacaSuhuNonBlocking(&sensorInput, "INPUT");
        suhuOutputC = bacaSuhuNonBlocking(&sensorOutput, "OUTPUT");
        
        Serial.printf("  Input: %.1f°C | Output: %.1f°C\n", suhuInputC, suhuOutputC);

        sensorInput.requestTemperatures();
        sensorOutput.requestTemperatures();
        lastTempRequest = now;
        Serial.println("  (Requested next temp conversion...)");
    } else {
        Serial.println("🌡️  Temperature (WAITING)...");
    }

    // ⭐ TDS INPUT - TAMBAHKAN BAGIAN INI!
    Serial.println("\n💧 TDS Input...");
    bacaTDS(TDS_INPUT_PIN, suhuInputC, ecInputValue, tdsInputPpm, rawAdcTdsInput, 
            isProbeInputInWater, lastValidTdsInput, lastValidEcInput);
    
    if (isProbeInputInWater) {
        isTdsHighInput = (tdsInputPpm > TDS_AMBANG_BATAS);
    } else {
        Serial.println("  ℹ️ Input probe tidak terendam - TDS=0");
        isTdsHighInput = false;
    }


    // ⭐ TDS OUTPUT - Dengan delay dan deteksi probe terendam
    if (now - lastPumpChange >= TDS_STABILIZE_DELAY_MS) {
        Serial.println("\n✨ TDS Output...");
        bacaTDS(TDS_OUTPUT_PIN, suhuOutputC, ecOutputValue, tdsOutputPpm, rawAdcTdsOutput,
                isProbeOutputInWater, lastValidTdsOutput, lastValidEcOutput);
        
        if (isProbeOutputInWater) {
            isTdsHighOutput = (tdsOutputPpm > TDS_AMBANG_BATAS);
        } else {
            Serial.println("  ℹ️ Output probe tidak terendam - TDS=0");
            isTdsHighOutput = false;
        }
    } else {
        Serial.printf("\n✨ TDS Output (STABILIZING: %lu ms remaining)...\n", 
                      TDS_STABILIZE_DELAY_MS - (now - lastPumpChange));
        
        // Gunakan nilai terakhir yang valid saat stabilizing
        tdsOutputPpm = lastValidTdsOutput;
        ecOutputValue = lastValidEcOutput;
        isTdsHighOutput = false;
    }

    // ⭐ FILTER EFFICIENCY - Hitung jika kedua sensor mendeteksi air
    if (isProbeInputInWater && isProbeOutputInWater && tdsInputPpm > 10) {
        filterEfficiency = ((float)(tdsInputPpm - tdsOutputPpm) / (float)tdsInputPpm) * 100.0;
        filterEfficiency = constrain(filterEfficiency, 0, 100);
    } else {
        filterEfficiency = 0;
        Serial.println("  ℹ️ Filter efficiency = 0 (probe tidak terendam semua)");
    }

    // ULTRASONIC
    jarakCm = ukurJarak();
    isLowWaterLevel = (jarakCm >= JARAK_RENDAH_CM);
    delay(50);
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
}

// ============================================
// PUMP CONTROL (Updated for TDS stabilization)
// ============================================
void setPump(bool turnOn, const char* reason) {
    if (turnOn == isPumpOn) {
        return;
    }

    bool prevPump = isPumpOn;

    digitalWrite(RELAY_PIN, turnOn ? RELAY_ON : RELAY_OFF);
    digitalWrite(LED_PIN, turnOn ? HIGH : LOW);

    if (!turnOn && prevPump) {
        useCount++;
        Serial.printf("♻️ USE COUNT: %d/%d\n", useCount, MAX_USE_COUNT);
    }

    isPumpOn = turnOn;
    lastPumpChange = millis();
    
    // ⭐ SET FLAG BAHWA TDS BELUM STABIL
    tdsReadingStable = false;

    Serial.print(turnOn ? "⚡ PUMP ON: " : "🛑 PUMP OFF: ");
    Serial.println(reason);
    
    if (turnOn) {
        Serial.printf("   ⏳ TDS akan distabilkan dalam %lu ms\n", TDS_DELAY_AFTER_PUMP_ON);
    } else {
        Serial.printf("   ⏳ TDS akan distabilkan dalam %lu ms\n", TDS_DELAY_AFTER_PUMP_OFF);
    }
}

// ============================================
// ALARM CONTROL (Unchanged)
// ============================================
void setAlarm(bool active, const char* reason) {
    if (active == isAlarmActive) {
        return;
    }

    digitalWrite(BUZZER_PIN, active ? HIGH : LOW);
    isAlarmActive = active;

    Serial.print(active ? "🔔 ALARM ON: " : "🔕 ALARM OFF: ");
    Serial.println(reason);
}

// ============================================
// SETUP
// ============================================
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.println("      🌊 Smart Water Filter System 🌊");
    Serial.println("        Version 4.1 - Realtime");
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.println();

    // Setup pins
    pinMode(RELAY_PIN, OUTPUT);
    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    pinMode(BUZZER_PIN, OUTPUT);
    pinMode(LED_PIN, OUTPUT);

    digitalWrite(RELAY_PIN, RELAY_OFF);
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(LED_PIN, LOW);

    // ⭐ INIT DS18B20
    Serial.println("🔧 Initializing DS18B20...");
    sensorInput.begin();
    sensorOutput.begin();
    
    // ⭐ SET RESOLUSI 10-bit UNTUK KONVERSI LEBIH CEPAT (187ms)
    sensorInput.setResolution(10);
    sensorOutput.setResolution(10);
    
    Serial.print("  Input sensors found: ");
    Serial.println(sensorInput.getDeviceCount());
    Serial.print("  Output sensors found: ");
    Serial.println(sensorOutput.getDeviceCount());
    Serial.println();
    
    // Minta konversi pertama
    sensorInput.requestTemperatures();
    sensorOutput.requestTemperatures();
    lastTempRequest = millis(); // Catat waktu permintaan pertama

    // Setup ADC
    analogSetAttenuation(ADC_11db);
    analogReadResolution(12);

    // Warm up ADC (Unchanged)
    Serial.println("🔧 Warming up ADC...");
    for (int i = 0; i < 30; i++) {
        analogRead(TDS_INPUT_PIN);
        analogRead(TDS_OUTPUT_PIN);
        delay(10);
    }
    Serial.println("✓ ADC ready\n");

    // Pin info (Unchanged)
    Serial.println("📌 Pin Configuration:");
    Serial.printf("  TDS Input (ADC):     GPIO%d\n", TDS_INPUT_PIN);
    Serial.printf("  TDS Output (ADC):    GPIO%d\n", TDS_OUTPUT_PIN);
    Serial.printf("  Temp Input (1-Wire): GPIO%d\n", SUHU_INPUT_PIN);
    Serial.printf("  Temp Output (1-Wire): GPIO%d\n", SUHU_OUTPUT_PIN);
    Serial.println();

    // Test ADC (Unchanged)
    Serial.println("🧪 Testing TDS ADC...");
    int test1 = analogRead(TDS_INPUT_PIN);
    int test2 = analogRead(TDS_OUTPUT_PIN);
    Serial.printf("  Pin %d (TDS In):  %d (%.2fV)\n", TDS_INPUT_PIN, test1, test1 * VREF / AD_MAX);
    Serial.printf("  Pin %d (TDS Out): %d (%.2fV)\n", TDS_OUTPUT_PIN, test2, test2 * VREF / AD_MAX);

    if (test1 >= 4000 || test2 >= 4000) {
        Serial.println("\n  ️  ️  ️ WARNING: Sensor TDS tidak terhubung!");
    }
    Serial.println();

    setup_wifi();
    Serial.println("⏳ Delay 3 detik untuk stabilitas sensor awal...");
    delay(3000);

    bacaSemuaSensor();
    Serial.println("✓ Pembacaan sensor awal selesai.");

    // ⭐ KONEKSI BLYNK
    Blynk.begin(BLYNK_AUTH_TOKEN, ssid, password, "blynk.cloud", 80); // Gunakan server Blynk default

    // Setup MQTT (Unchanged)
    mqtt.setServer(mqtt_server, mqtt_port);
    mqtt.setCallback(mqtt_callback);
    mqtt.setBufferSize(512);

    Serial.println("\n✓ System Ready!");
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
}

// ============================================
// MAIN LOOP
// ============================================
void loop() {
    unsigned long now = millis();

    // ⭐ JALANKAN KLIEN BLYNK
    Blynk.run();

    // WiFi check (Unchanged)
    static unsigned long lastWiFiCheck = 0;
    if (now - lastWiFiCheck >= 10000) {
        lastWiFiCheck = now;

        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("   WiFi Lost - Reconnecting...");
            setup_wifi();
        }
    }

    // MQTT (Unchanged)
    if (WiFi.status() == WL_CONNECTED) {
        if (!mqtt.connected()) {
            reconnect_mqtt();
        } else {
            mqtt.loop();
        }
    }

    // Read sensors
    if (now - lastSensorRead >= SENSOR_INTERVAL) {
        lastSensorRead = now;

        bacaSemuaSensor();

        // Summary
        Serial.println("\n╔══════════════ SUMMARY ══════════════╗");
        Serial.printf("║ Temp:  In=%.1f°C | Out=%.1f°C     ║\n", suhuInputC, suhuOutputC);
        Serial.printf("║ TDS:   In=%4d | Out=%4d PPM    ║\n", tdsInputPpm, tdsOutputPpm);
        Serial.printf("║ EC:    In=%4.0f | Out=%4.0f µS/cm║\n", ecInputValue, ecOutputValue);
        Serial.printf("║ Probe: In=%s | Out=%s      ║\n", 
                      isProbeInputInWater ? "WATER✓" : "DRY✗  ",
                      isProbeOutputInWater ? "WATER✓" : "DRY✗  ");
        Serial.printf("║ Distance: %d cm %-16s║\n", jarakCm,
                      jarakCm <= JARAK_PENUH_CM ? "(PENUH)" :
                      isLowWaterLevel ? "(RENDAH)" : "(SEDANG)");
        Serial.printf("║ Filter: %d/%d x | Eff: %.1f%%     ║\n", useCount, MAX_USE_COUNT, filterEfficiency);
        Serial.printf("║ Pump: %s | Stable: %s        ║\n", 
                      isPumpOn ? "ON " : "OFF", 
                      tdsReadingStable ? "YES" : "NO ");
        Serial.println("╚═════════════════════════════════════╝\n");

        // Auto control
        if (isTdsHighOutput || useCount >= MAX_USE_COUNT) {
            if (isPumpOn) setPump(false, "Filter Limit/TDS Tinggi");
        } else if (jarakCm <= JARAK_PENUH_CM && jarakCm > 0) {
            if (isPumpOn) setPump(false, "Tangki Penuh");
        }

        if (jarakCm <= JARAK_PENUH_CM && jarakCm > 0) {
            setAlarm(true, "Tangki Penuh");
        } else {
            setAlarm(false, "Normal");
        }
    }

    // Publish to MQTT
    if (now - lastMqttPublish >= MQTT_PUBLISH_INTERVAL) {
        lastMqttPublish = now;
        if (mqtt.connected()) {
            publishSensorData();
        }

        // ⭐ TAMBAHAN: MENGIRIM DATA KE BLYNK
        if (Blynk.connected()) {
            // Contoh mengirim TDS Output ke Virtual Pin V0 di Blynk
            Blynk.virtualWrite(V0, tdsOutputPpm);
            Blynk.virtualWrite(V1, suhuOutputC);
            // ... Tambahkan pin virtual lainnya sesuai kebutuhan
        }
    }

    delay(10);
}
