import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
from scipy.interpolate import make_interp_spline
import paho.mqtt.client as mqtt
import json
from datetime import datetime
import threading
import time

# Konfigurasi tema
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

class DashboardApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Smart Water Filter Dashboard with MQTT")
        self.geometry("1400x900")
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # --- MQTT Configuration ---
        self.mqtt_broker = "broker.emqx.io"
        self.mqtt_port = 1883
        self.mqtt_client_id = "Dashboard_Python_" + str(int(time.time()))
        self.mqtt_client = mqtt.Client(self.mqtt_client_id)
        
        # MQTT Topics
        self.topic_data = "smartwater/data"
        self.topic_control = "smartwater/control"
        self.topic_status = "smartwater/status"
        
        # --- Color Palette ---
        self.colors = {
            'primary': '#137fec',
            'background_light': '#f6f7f8',
            'surface_light': '#FFFFFF',
            'border_light': '#E0E0E0',
            'text_dark': '#1e293b',
            'text_secondary': '#64748b',
            'status_ok': '#28A745',
            'status_warning': '#FFC107',
            'status_critical': '#DC3545',
        }
        
        # --- Font Configuration ---
        self.fonts = {
            'header': ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),
            'title_lg': ctk.CTkFont(family="Segoe UI", size=24, weight="bold"), # Ukuran Standar Baru untuk Metrik Card
            'subtitle': ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            'body': ctk.CTkFont(family="Segoe UI", size=14),
            'body_bold': ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            'small': ctk.CTkFont(family="Segoe UI", size=13),
            'small_bold': ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            'metric_large': ctk.CTkFont(family="Segoe UI", size=40, weight="bold"),
            'metric_medium': ctk.CTkFont(family="Segoe UI", size=32, weight="bold"),
        }
        
        self.configure(fg_color=self.colors['background_light'])

        # --- Data Variables ---
        self.tds_input = 0
        self.tds_output = 0
        self.ec_input = 0 
        self.ec_output = 0 
        self.temp_input = 0
        self.temp_output = 0
        self.filter_efficiency = 0 
        self.water_level = "SEDANG"
        self.jarak_cm = 0
        
        self.use_count = 0 
        self.max_uses = 50 
        
        # Status
        self.pump_on = False
        self.alarm_active = False
        self.mqtt_connected = False
        self.is_closing = False
        
        # History data untuk grafik
        self.use_count_history = []
        self.max_history = 20
        
        # --- UI Elements References ---
        self.chart_canvas = None
        self.chart_frame = None
        self.status_labels = {}
        self.metric_labels = {}
        self.status_container = None # Dipindahkan ke __init__ untuk referensi
        
        # --- Grid Configuration ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Build UI ---
        self.create_main_content_frame()
        self.update_graph_data()
        
        # --- Start MQTT Connection ---
        self.setup_mqtt()
        self.mqtt_thread = threading.Thread(target=self.connect_mqtt, daemon=True)
        self.mqtt_thread.start()
        
        # --- Start periodic UI update ---
        self.periodic_update()

    def setup_mqtt(self):
        """Setup MQTT callbacks"""
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        retry_count = 0
        max_retries = 5
        
        while not self.is_closing and retry_count < max_retries:
            try:
                print(f"🔄 Attempting to connect to MQTT broker: {self.mqtt_broker}")
                self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
                self.mqtt_client.loop_forever()
                break
            except Exception as e:
                retry_count += 1
                print(f"❌ MQTT Connection Error (Attempt {retry_count}/{max_retries}): {e}")
                self.mqtt_connected = False
                self.after(0, self.update_connection_status)
                
                if retry_count < max_retries:
                    time.sleep(5)
                else:
                    print("⚠️ Max retries reached. Please check MQTT broker.")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT"""
        if rc == 0:
            print("✅ Connected to MQTT Broker!")
            self.mqtt_connected = True
            self.mqtt_client.subscribe(self.topic_data)
            self.mqtt_client.subscribe(self.topic_status)
            print(f"✅ Subscribed to: {self.topic_data}, {self.topic_status}")
            self.after(0, self.update_connection_status)
        else:
            print(f"❌ Failed to connect, return code {rc}")
            self.mqtt_connected = False

    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT"""
        print(f"⚠️ Disconnected from MQTT Broker (RC: {rc})")
        self.mqtt_connected = False
        self.after(0, self.update_connection_status)

    def on_mqtt_message(self, client, userdata, msg):
        """Callback when message received from MQTT"""
        try:
            payload = json.loads(msg.payload.decode())
            
            if msg.topic == self.topic_data:
                # Update data dari ESP32
                self.tds_input = payload.get("tds_input", 0)
                self.tds_output = payload.get("tds_output", 0)
                self.ec_input = payload.get("ec_input", 0) 
                self.ec_output = payload.get("ec_output", 0)
                self.temp_input = payload.get("suhu_input", 0)
                self.temp_output = payload.get("suhu_output", 0)
                self.use_count = payload.get("use_count", 0) 
                self.filter_efficiency = payload.get("filter_efficiency", 0) 
                self.water_level = payload.get("water_level", "SEDANG")
                self.jarak_cm = payload.get("jarak_cm", 0)
                
                self.pump_on = payload.get("pump_on", False)
                self.alarm_active = payload.get("alarm_active", False)
                
                print(f"📊 Data received - TDS In: {self.tds_input}, EC In: {self.ec_input}, Use Count: {self.use_count}")
                
                # Update UI in main thread
                self.after(0, self.update_ui_data)
                
            elif msg.topic == self.topic_status:
                status = payload.get("status", "")
                message = payload.get("message", "")
                print(f"📢 Status Update: {status} - {message}")
                self.after(0, lambda: self.show_notification(status, message))
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
        except Exception as e:
            print(f"❌ Error parsing MQTT message: {e}")

    def publish_command(self, command):
        """Publish command ke ESP32"""
        if not self.mqtt_connected:
            self.show_notification("ERROR", "MQTT tidak terhubung!")
            print("❌ Cannot send command: MQTT not connected")
            return
            
        payload = {
            "command": command,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            result = self.mqtt_client.publish(self.topic_control, json.dumps(payload))
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"✅ Command sent successfully: {command}")
            else:
                print(f"❌ Failed to send command: {command}")
        except Exception as e:
            print(f"❌ Error sending command: {e}")

    def update_connection_status(self):
        """Update status koneksi di UI"""
        if hasattr(self, 'connection_indicator'):
            if self.mqtt_connected:
                self.connection_indicator.configure(fg_color=self.colors['status_ok'])
                self.connection_label.configure(text="Connected")
            else:
                self.connection_indicator.configure(fg_color=self.colors['status_critical'])
                self.connection_label.configure(text="Disconnected")

    def get_filter_status(self):
        """Menghitung dan mengembalikan status filter"""
        if self.use_count >= self.max_uses:
            return "GANTI FILTER", self.colors['status_critical']
        elif self.use_count >= self.max_uses * 0.8:
            return "PERINGATAN", self.colors['status_warning']
        else:
            return "NORMAL", self.colors['status_ok']

    def update_ui_data(self):
        """Update semua data di UI"""
        try:
            # --- Update metric cards ---
            
            # Update TDS/EC Input (Gabungan)
            tds_ec_in_text = f"{self.tds_input} PPM / {self.ec_input:.0f} µS/cm"
            if 'tds_ec_input' in self.metric_labels:
                self.metric_labels['tds_ec_input'].configure(text=tds_ec_in_text)
            
            # Update TDS/EC Output (Gabungan)
            tds_ec_out_text = f"{self.tds_output} PPM / {self.ec_output:.0f} µS/cm"
            if 'tds_ec_output' in self.metric_labels:
                self.metric_labels['tds_ec_output'].configure(text=tds_ec_out_text)
                
            # Update Suhu Input
            if 'temp_input' in self.metric_labels:
                self.metric_labels['temp_input'].configure(text=f"{self.temp_input:.1f}°C")

            # Update Suhu Output
            if 'temp_output' in self.metric_labels:
                self.metric_labels['temp_output'].configure(text=f"{self.temp_output:.1f}°C")
                
            # Update Filter Health
            status_text, status_color = self.get_filter_status()
            if 'filter_health' in self.metric_labels:
                self.metric_labels['filter_health'].configure(text=f"{status_text} ({self.use_count}/{self.max_uses}X)")
                
            # Update system status
            self.update_system_status()
            
            # Update use count history
            self.use_count_history.append(self.use_count)
            if len(self.use_count_history) > self.max_history:
                self.use_count_history.pop(0)
            self.update_graph_data()
        except Exception as e:
            print(f"❌ Error updating UI: {e}")

    def show_notification(self, status, message):
        """Tampilkan notifikasi popup"""
        try:
            notif_window = ctk.CTkToplevel(self)
            notif_window.title(status)
            notif_window.geometry("400x180")
            notif_window.attributes('-topmost', True)
            
            color = self.colors['status_ok'] if status == "SUCCESS" else self.colors['status_critical']
            
            ctk.CTkLabel(
                notif_window,
                text=status,
                font=self.fonts['title_lg'],
                text_color=color
            ).pack(pady=20)
            
            ctk.CTkLabel(
                notif_window,
                text=message,
                font=self.fonts['body'],
                wraplength=350
            ).pack(pady=10)
            
            ctk.CTkButton(
                notif_window,
                text="OK",
                command=notif_window.destroy,
                width=100
            ).pack(pady=15)
            
            # Auto close after 5 seconds
            self.after(5000, notif_window.destroy)
        except Exception as e:
            print(f"❌ Error showing notification: {e}")

    def periodic_update(self):
        """Periodic update untuk UI"""
        if not self.is_closing:
            self.update_connection_status()
            self.after(1000, self.periodic_update)

    def create_main_content_frame(self,):
        """Frame utama dashboard"""
        main_content_frame = ctk.CTkFrame(self, fg_color=self.colors['background_light'], corner_radius=0)
        main_content_frame.grid(row=0, column=0, sticky="nsew")
        
        container = ctk.CTkFrame(main_content_frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)
        
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=0)  # Header
        container.grid_rowconfigure(1, weight=0)  # Connection Status
        container.grid_rowconfigure(2, weight=0)  # Stats Cards
        container.grid_rowconfigure(3, weight=0)  # Control Buttons
        container.grid_rowconfigure(4, weight=1)  # Charts & Status
        
        # 1. Header
        header = ctk.CTkLabel(
            container,
            text="🌊 Smart Water Filter Dashboard",
            font=self.fonts['header'],
            text_color=self.colors['text_dark'],
            anchor="w"
        )
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        
        # 2. Connection Status
        self.create_connection_status(container)
        
        # 3. Stats Cards
        self.create_stats_cards(container)
        
        # 4. Control Buttons
        self.create_control_buttons(container)
        
        # 5. Charts & System Status
        self.create_charts_and_status(container)

    def create_connection_status(self, parent):
        """Status koneksi MQTT"""
        conn_frame = ctk.CTkFrame(parent, fg_color=self.colors['surface_light'], corner_radius=8)
        conn_frame.grid(row=1, column=0, sticky="ew", pady=(0, 24))
        
        inner = ctk.CTkFrame(conn_frame, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        
        self.connection_indicator = ctk.CTkLabel(
            inner,
            text="",
            width=12,
            height=12,
            corner_radius=6,
            fg_color=self.colors['status_critical']
        )
        self.connection_indicator.pack(side="left", padx=(0, 8))
        
        self.connection_label = ctk.CTkLabel(
            inner,
            text="Disconnected",
            font=self.fonts['body_bold'],
            text_color=self.colors['text_dark']
        )
        self.connection_label.pack(side="left", padx=(0, 16))
        
        ctk.CTkLabel(
            inner,
            text=f"Broker: {self.mqtt_broker}:{self.mqtt_port}",
            font=self.fonts['small'],
            text_color=self.colors['text_secondary']
        ).pack(side="left")

    def create_stats_cards(self, parent):
        """Stats cards untuk sensor data"""
        stats_container = ctk.CTkFrame(parent, fg_color="transparent")
        stats_container.grid(row=2, column=0, sticky="ew", pady=(0, 24))
        
        # 5 kolom
        stats_container.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="stats")
        
        stats_data = [
            # 1. TDS/EC Input (Gabungan)
            {"title": "TDS / EC Input", 
             "key": "tds_ec_input", 
             "value": f"{self.tds_input} PPM / {self.ec_input:.0f} µS/cm", 
             "icon": "💧⚡"},
             
            # 2. TDS/EC Output (Gabungan)
            {"title": "TDS / EC Output", 
             "key": "tds_ec_output", 
             "value": f"{self.tds_output} PPM / {self.ec_output:.0f} µS/cm", 
             "icon": "✨✅"},
             
            # 3. Temp Input
            {"title": "Temp Input", 
             "key": "temp_input", 
             "value": f"{self.temp_input:.1f}°C", 
             "icon": "🔥"},
             
            # 4. Temp Output
            {"title": "Temp Output", 
             "key": "temp_output", 
             "value": f"{self.temp_output:.1f}°C", 
             "icon": "🌡️"},
             
            # 5. Filter Health
            {"title": "Filter Health", 
             "key": "filter_health", 
             "value": f"NORMAL ({self.use_count}/{self.max_uses}X)", 
             "icon": "♻️"} 
        ]
        
        for i, data in enumerate(stats_data):
            self.create_stat_card(stats_container, data, i)

    def create_stat_card(self, parent, data, column):
        """Individual stat card"""
        card = ctk.CTkFrame(
            parent,
            corner_radius=16,
            fg_color=self.colors['surface_light'],
            border_width=1,
            border_color=self.colors['border_light']
        )
        card.grid(row=0, column=column, padx=6, pady=0, sticky="nsew")
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Icon + Title
        title_frame = ctk.CTkFrame(inner, fg_color="transparent")
        title_frame.pack(anchor="w", pady=(0, 4))
        
        ctk.CTkLabel(
            title_frame,
            text=data.get("icon", ""),
            font=self.fonts['body']
        ).pack(side="left", padx=(0, 4))
        
        ctk.CTkLabel(
            title_frame,
            text=data["title"],
            font=self.fonts['small'],
            text_color=self.colors['text_secondary'],
            anchor="w"
        ).pack(side="left")
        
        # Gunakan font title_lg (24px) untuk SEMUA data metrik (seperti revisi sebelumnya)
        font_size = self.fonts['title_lg'] 
            
        value_label = ctk.CTkLabel(
            inner,
            text=data["value"],
            font=font_size, 
            text_color=self.colors['text_dark'],
            anchor="w"
        )
        value_label.pack(anchor="w")
        
        self.metric_labels[data["key"]] = value_label

    def create_control_buttons(self, parent):
        """Control buttons untuk pompa, alarm, dan RESET FILTER"""
        btn_container = ctk.CTkFrame(parent, fg_color="transparent")
        btn_container.grid(row=3, column=0, sticky="ew", pady=(0, 24))
        
        # 4 kolom (3 kontrol + 1 reset filter)
        btn_container.grid_columnconfigure((0, 1, 2, 3), weight=1) 
        
        # Button Start Pump
        btn_start = ctk.CTkButton(
            btn_container,
            text="🚀 Start Pump",
            font=self.fonts['body_bold'],
            fg_color=self.colors['status_ok'],
            hover_color="#1e7e34",
            height=50,
            corner_radius=12,
            command=lambda: self.publish_command("START_PUMP")
        )
        btn_start.grid(row=0, column=0, padx=8, sticky="ew")
        
        # Button Stop Pump
        btn_stop = ctk.CTkButton(
            btn_container,
            text="🛑 Stop Pump",
            font=self.fonts['body_bold'],
            fg_color=self.colors['status_critical'],
            hover_color="#bd2130",
            height=50,
            corner_radius=12,
            command=lambda: self.publish_command("STOP_PUMP")
        )
        btn_stop.grid(row=0, column=1, padx=8, sticky="ew")
        
        # Button Turn Off Alarm
        btn_alarm = ctk.CTkButton(
            btn_container,
            text="🔕 Turn Off Alarm",
            font=self.fonts['body_bold'],
            fg_color=self.colors['status_warning'],
            hover_color="#d39e00",
            height=50,
            corner_radius=12,
            command=lambda: self.publish_command("ALARM_OFF")
        )
        btn_alarm.grid(row=0, column=2, padx=8, sticky="ew")

        # Button Reset Filter Use Count
        btn_reset = ctk.CTkButton(
            btn_container,
            text="🔄 Reset Filter Use",
            font=self.fonts['body_bold'],
            fg_color=self.colors['primary'],
            hover_color="#116bca",
            height=50,
            corner_radius=12,
            command=lambda: self.publish_command("RESET_USE_COUNT")
        )
        btn_reset.grid(row=0, column=3, padx=8, sticky="ew")


    def create_charts_and_status(self, parent):
        """Charts dan system status"""
        content_frame = ctk.CTkFrame(parent, fg_color="transparent")
        content_frame.grid(row=4, column=0, sticky="nsew")
        
        content_frame.grid_columnconfigure(0, weight=2)
        content_frame.grid_columnconfigure(1, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        
        self.create_chart_section(content_frame)
        self.create_system_status_section(content_frame)

    def create_chart_section(self, parent):
        """Section grafik"""
        chart_card = ctk.CTkFrame(
            parent,
            corner_radius=16,
            fg_color=self.colors['surface_light'],
            border_width=1,
            border_color=self.colors['border_light']
        )
        chart_card.grid(row=0, column=0, sticky="nsew", padx=(0, 24))
        chart_card.grid_columnconfigure(0, weight=1)
        chart_card.grid_rowconfigure(3, weight=1)
        
        ctk.CTkLabel(
            chart_card,
            text="📈 Filter Usage History",
            font=self.fonts['subtitle'],
            text_color=self.colors['text_dark']
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(24, 8))

        # Font untuk use count display
        self.use_display = ctk.CTkLabel(
            chart_card,
            text=f"Current Usage: {self.use_count}/{self.max_uses} times",
            font=self.fonts['metric_large'],
            text_color=self.colors['text_dark']
        )
        self.use_display.grid(row=1, column=0, sticky="w", padx=24)
        
        self.chart_frame = ctk.CTkFrame(chart_card, fg_color=self.colors['surface_light'])
        self.chart_frame.grid(row=3, column=0, sticky="nsew", padx=24, pady=(16, 24))

    def create_system_status_section(self, parent):
        """Section system status (REVISI: Menggunakan CTkScrollableFrame)"""
        status_card = ctk.CTkFrame(
            parent,
            corner_radius=16,
            fg_color=self.colors['surface_light'],
            border_width=1,
            border_color=self.colors['border_light']
        )
        status_card.grid(row=0, column=1, sticky="nsew")
        
        ctk.CTkLabel(
            status_card,
            text="⚙️ System Status",
            font=self.fonts['subtitle'],
            text_color=self.colors['text_dark'],
            anchor="w"
        ).pack(anchor="w", padx=24, pady=(24, 16))
        
        # ⭐ REVISI: Gunakan CTkScrollableFrame sebagai container utama untuk status item
        self.status_container = ctk.CTkScrollableFrame(
            status_card, 
            fg_color="transparent",
            # Atur lebar sedikit lebih besar untuk menampung scrollbar jika muncul
            width=200 
        )
        # Menggunakan .pack() untuk memastikan frame mengisi ruang yang tersisa di status_card
        self.status_container.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        
        self.update_system_status()

    def update_system_status(self):
        """Update system status display"""
        try:
            # Clear existing items in the scrollable frame
            for widget in self.status_container.winfo_children():
                widget.destroy()
            
            # Determine colors based on status
            water_color = self.colors['status_ok'] if self.water_level != "RENDAH" else self.colors['status_critical']
            pump_color = self.colors['status_ok'] if self.pump_on else self.colors['text_secondary']
            alarm_color = self.colors['status_critical'] if self.alarm_active else self.colors['status_ok']
            filter_status, filter_color = self.get_filter_status() 
            
            status_items = [
                ("💧 Water Level", self.water_level, water_color),
                ("⚡ Pump Status", "ON" if self.pump_on else "OFF", pump_color),
                ("🔔 Alarm", "ACTIVE" if self.alarm_active else "OFF", alarm_color),
                ("♻️ Filter Health", f"{filter_status} ({self.use_count}x)", filter_color), 
                ("📏 Distance", f"{self.jarak_cm} cm", self.colors['text_dark']),
                # Gabungan TDS/EC Input
                ("🌊 TDS/EC In", f"{self.tds_input} PPM / {self.ec_input:.0f} µS/cm", self.colors['text_dark']), 
                # Gabungan TDS/EC Output
                ("✨ TDS/EC Out", f"{self.tds_output} PPM / {self.ec_output:.0f} µS/cm", self.colors['text_dark']), 
                ("🔥 Temp Input", f"{self.temp_input:.1f}°C", self.colors['text_dark']), 
                ("🌡️ Temp Output", f"{self.temp_output:.1f}°C", self.colors['text_dark']), 
            ]
            
            # Populate the scrollable frame
            for label, value, color in status_items:
                frame = ctk.CTkFrame(self.status_container, fg_color="transparent")
                frame.pack(fill="x", pady=8)
                
                ctk.CTkLabel(
                    frame,
                    text=label,
                    font=self.fonts['body'],
                    text_color=self.colors['text_dark']
                ).pack(side="left")
                
                ctk.CTkLabel(
                    frame,
                    text=value,
                    font=self.fonts['body_bold'],
                    text_color=color
                ).pack(side="right")
        except Exception as e:
            print(f"❌ Error updating system status: {e}")

    def update_graph_data(self):
        """Update graph dengan data terbaru"""
        try:
            if hasattr(self, 'use_display'):
                self.use_display.configure(text=f"Current Usage: {self.use_count}/{self.max_uses} times")

            self.embed_matplotlib_graph()
        except Exception as e:
            print(f"❌ Error updating graph: {e}")

    def embed_matplotlib_graph(self):
        """Embed matplotlib graph"""
        try:
            if self.chart_canvas:
                self.chart_canvas.get_tk_widget().destroy()

            fig = Figure(figsize=(10, 4), dpi=100)
            fig.patch.set_facecolor(self.colors['surface_light'])

            ax = fig.add_subplot(111)
            ax.set_facecolor(self.colors['surface_light'])

            x_data = list(range(len(self.use_count_history)))

            # Plot Use Count History
            if self.use_count_history:
                if len(self.use_count_history) > 3:
                    x_range = np.linspace(0, len(self.use_count_history) - 1, 200)
                    k_val = min(3, len(self.use_count_history)-1) if len(self.use_count_history) > 1 else 1
                    spl = make_interp_spline(x_data, self.use_count_history, k=k_val)
                    y_smooth = spl(x_range)
                else:
                    x_range = x_data
                    y_smooth = self.use_count_history

                ax.plot(x_range, y_smooth, color=self.colors['primary'], linewidth=3, label='Filter Usage', zorder=3)
                ax.fill_between(x_range, y_smooth, 0, alpha=0.2, color=self.colors['primary'], zorder=2)

            # Legend
            ax.legend(loc='upper left', fontsize=10)

            # Teks pada sumbu X disembunyikan
            ax.set_xticks([])

            # Atur sumbu Y
            y_max = max(self.use_count_history) + 5 if self.use_count_history else self.max_uses
            ax.set_ylim(0, y_max)
            ax.tick_params(axis='y', colors=self.colors['text_secondary'])

            ax.set_ylabel("Usage Count", color=self.colors['text_dark'], fontsize=12)

            for spine in ax.spines.values():
                spine.set_visible(False)

            # Tampilkan grid untuk sumbu Y
            ax.grid(axis='y', linestyle=':', alpha=0.7)

            # Create canvas and embed in Tkinter
            self.chart_canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
            self.chart_canvas.draw()
            self.chart_canvas.get_tk_widget().pack(fill="both", expand=True)

        except Exception as e:
            print(f"❌ Error embedding matplotlib graph: {e}")


    def on_closing(self):
        """Handle window close"""
        print("\n🛑 Closing application...")
        self.is_closing = True
        
        try:
            # Stop MQTT
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("✅ MQTT disconnected")
            
            # Close matplotlib
            if hasattr(self, 'chart_canvas') and self.chart_canvas:
                self.chart_canvas.get_tk_widget().destroy()
            
            plt.close('all')
            print("✅ Matplotlib closed")
            
            # Destroy window
            self.destroy()
            print("✅ Window destroyed")
            
        except Exception as e:
            print(f"❌ Error during closing: {e}")
            self.destroy()
        finally:
            self.quit()

if __name__ == "__main__":
    try:
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  🌊 Smart Water Filter Dashboard 🌊")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        
        app = DashboardApp()
        app.mainloop()
        
    except KeyboardInterrupt:
        print("\n⚠️ Application closed by user")
    except Exception as e:
        print(f"❌ Application error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        plt.close('all')