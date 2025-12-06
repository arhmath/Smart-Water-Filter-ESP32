# 🌊 Smart Water Filter ESP32

Proyek sistem penyaring air cerdas berbasis ESP32 yang dapat memantau kualitas air secara real-time, mengontrol pompa, dan memberikan notifikasi alarm melalui dashboard Python dan aplikasi Blynk.

## 📋 Fitur Utama

- **Monitoring Kualitas Air Real-Time**: Mengukur TDS (Total Dissolved Solids), EC (Electrical Conductivity), dan suhu air input/output
- **Deteksi Level Air**: Menggunakan sensor ultrasonik untuk memantau tinggi air dalam tangki
- **Kontrol Pompa Otomatis**: Mengaktifkan/mematikan pompa berdasarkan kondisi air dan batas penggunaan filter
- **Sistem Alarm**: Notifikasi ketika air penuh, filter perlu diganti, atau TDS tinggi
- **Dashboard Python**: Antarmuka grafis untuk visualisasi data real-time dengan MQTT
- **Integrasi Blynk**: Kontrol dan monitoring melalui aplikasi mobile Blynk
- **Komunikasi MQTT**: Publikasi data sensor dan kontrol perangkat melalui protokol MQTT

## 🔧 Perangkat Keras yang Dibutuhkan

### Komponen Utama:
- **ESP32 Development Board** (misalnya ESP32-WROOM-32)
- **Sensor TDS/EC** (2 buah - untuk input dan output)
- **Sensor Suhu DS18B20** (2 buah - untuk input dan output)
- **Sensor Ultrasonik HC-SR04** (untuk pengukuran level air)
- **Relay Module** (untuk kontrol pompa)
- **Buzzer** (untuk alarm)
- **LED** (indikator status)
- **Power Supply** (5V/3.3V sesuai kebutuhan)

### Pin Configuration ESP32:
```
- TRIG_PIN (Ultrasonik): GPIO 13
- ECHO_PIN (Ultrasonik): GPIO 12
- RELAY_PIN (Pompa): GPIO 25
- BUZZER_PIN (Alarm): GPIO 5
- LED_PIN (Indikator): GPIO 2
- SUHU_INPUT_PIN (DS18B20): GPIO 32
- TDS_INPUT_PIN (ADC): GPIO 34
- SUHU_OUTPUT_PIN (DS18B20): GPIO 33
- TDS_OUTPUT_PIN (ADC): GPIO 35
```

## 💻 Persyaratan Software

### Untuk ESP32:
- **PlatformIO** (IDE untuk development ESP32)
- **Arduino Framework**
- **Library Dependencies**:
  - PubSubClient@^2.8
  - ArduinoJson@^6.21.3
  - DallasTemperature@^3.11.0
  - OneWire@^2.3.7
  - Blynk

### Untuk Dashboard Python:
- **Python 3.7+**
- **Required Libraries**:
  - customtkinter
  - matplotlib
  - scipy
  - paho-mqtt
  - numpy

### Aplikasi Mobile:
- **Blynk App** (Android/iOS) untuk kontrol mobile

## 🚀 Instalasi dan Setup

### 1. Setup PlatformIO
```bash
# Install PlatformIO (jika belum terinstall)
# Via VSCode Extension atau CLI

# Clone atau download project ini
cd /path/to/project

# Install dependencies
pio pkg install
```

### 2. Konfigurasi WiFi dan MQTT
Edit file `src/main.cpp`:
```cpp
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Blynk Configuration
#define BLYNK_TEMPLATE_ID "YOUR_TEMPLATE_ID"
#define BLYNK_TEMPLATE_NAME "Smart Water Filter"
#define BLYNK_AUTH_TOKEN "YOUR_AUTH_TOKEN"

// MQTT Broker (default: broker.emqx.io)
const char* mqtt_server = "broker.emqx.io";
const int mqtt_port = 1883;
```

### 3. Setup Dashboard Python
```bash
# Install Python dependencies
pip install customtkinter matplotlib scipy paho-mqtt numpy

# Jalankan dashboard
python src/dashboard_ui.py
```

### 4. Setup Blynk App
1. Download aplikasi Blynk dari Play Store/App Store
2. Buat akun baru atau login
3. Buat template baru dengan ID yang sesuai
4. Tambahkan widget untuk kontrol pompa (Button V1)
5. Tambahkan display untuk TDS (Value Display V0) dan Suhu (Value Display V1)

## ⚙️ Konfigurasi Sistem

### Parameter Kalibrasi:
```cpp
// Kalibrasi TDS
const float TDS_KVALUE = 0.25;  // Sesuaikan dengan sensor Anda

// Batas Level Air
const int JARAK_PENUH_CM = 5;   // Jarak ketika tangki penuh
const int JARAK_RENDAH_CM = 10; // Jarak ketika level rendah

// Batas TDS
const int TDS_AMBANG_BATAS = 1000; // PPM
const int MAX_USE_COUNT = 50;      // Maksimal penggunaan filter
```

### MQTT Topics:
- **Data**: `smartwater/data` - Publikasi data sensor
- **Control**: `smartwater/control` - Kontrol perintah
- **Status**: `smartwater/status` - Status sistem

## 📱 Cara Penggunaan

### 1. Upload Kode ke ESP32
```bash
# Via PlatformIO
pio run -t upload
```

### 2. Monitoring Dashboard
- Jalankan `python src/dashboard_ui.py`
- Dashboard akan otomatis connect ke MQTT broker
- Pantau data real-time: TDS, EC, Suhu, Level Air
- Kontrol pompa melalui tombol di dashboard

### 3. Kontrol via MQTT
Kirim perintah JSON ke topic `smartwater/control`:
```json
{
  "command": "START_PUMP",
  "timestamp": "2024-01-01T00:00:00"
}
```

Perintah yang tersedia:
- `START_PUMP`: Menyalakan pompa
- `STOP_PUMP`: Mematikan pompa
- `ALARM_OFF`: Mematikan alarm
- `RESET_USE_COUNT`: Reset counter penggunaan filter

### 4. Kontrol via Blynk
- Gunakan widget Button untuk kontrol pompa
- Monitor data melalui Value Display widgets

## 📊 Data yang Dipantau

### Parameter Input:
- TDS Input (PPM)
- EC Input (µS/cm)
- Suhu Input (°C)

### Parameter Output:
- TDS Output (PPM)
- EC Output (µS/cm)
- Suhu Output (°C)

### Sistem:
- Level Air (cm)
- Efisiensi Filter (%)
- Status Pompa (ON/OFF)
- Status Alarm (Active/Inactive)
- Counter Penggunaan Filter

## 🔧 Troubleshooting

### Masalah Umum:

1. **ESP32 tidak connect ke WiFi**
   - Periksa SSID dan password
   - Pastikan jangkauan WiFi cukup
   - Restart ESP32

2. **Sensor TDS tidak akurat**
   - Kalibrasi ulang nilai TDS_KVALUE
   - Pastikan probe terendam air dengan benar
   - Bersihkan elektroda sensor

3. **Dashboard tidak menerima data**
   - Periksa koneksi MQTT broker
   - Pastikan topic MQTT sesuai
   - Restart dashboard Python

4. **Pompa tidak berfungsi**
   - Periksa koneksi relay
   - Pastikan power supply cukup
   - Periksa batas penggunaan filter

5. **Blynk tidak connect**
   - Periksa AUTH_TOKEN
   - Pastikan template ID benar
   - Restart aplikasi Blynk

### Debug Mode:
Aktifkan Serial Monitor di PlatformIO untuk melihat log sistem:
```bash
pio device monitor
```

## 📈 Pengembangan dan Kontribusi

### Struktur Project:
```
Smart-Water-Filter-ESP32/
├── src/
│   ├── main.cpp          # Kode utama ESP32
│   └── dashboard_ui.py   # Dashboard Python
├── include/              # Header files
├── lib/                  # Library tambahan
├── test/                 # Unit tests
├── platformio.ini        # Konfigurasi PlatformIO
└── README.md            # Dokumentasi ini
```

### Menambah Fitur Baru:
1. Tambahkan fungsi di `main.cpp`
2. Update dashboard jika diperlukan
3. Test pada hardware
4. Update dokumentasi

## 📄 Lisensi

Proyek ini menggunakan lisensi MIT. Lihat file LICENSE untuk detail lebih lanjut.

## 🤝 Kontribusi

Kontribusi sangat diterima! Silakan buat Issue atau Pull Request untuk perbaikan dan peningkatan.

## 📞 Dukungan

Jika ada pertanyaan atau masalah:
1. Periksa bagian Troubleshooting di atas
2. Buat Issue di repository GitHub
3. Pastikan menyertakan log error dan konfigurasi sistem

---

**Catatan**: Pastikan semua sensor terhubung dengan benar dan dikalibrasi sebelum digunakan dalam produksi. Sistem ini dirancang untuk monitoring dan kontrol, namun keamanan air minum tetap menjadi prioritas utama.
