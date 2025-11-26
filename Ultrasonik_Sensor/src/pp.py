"""
monitor_tds_ec.py
Aplikasi monitoring TDS/EC/Suhu berbasis Tkinter yang membaca baris serial
dengan format:
DATA: Jarak:7 | TDS:320 | EC:640.0 | Suhu:27.3 | Pompa:0 | Alarm:0 | Level Air:SEDANG

Fitur:
- Connect ke serial port (pyserial) atau gunakan simulator
- Parse data, tampilkan nilai numerik & status
- Realtime plot TDS, EC, Suhu (matplotlib)
- Log tampilan, save CSV, clear log
- Kirim perintah '1' (start) atau 'stop' ke device
- Atur faktor konversi EC↔TDS
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading, queue, time, csv, re, sys
import random
from collections import deque
from datetime import datetime

# Optional dependencies (if not installed, app still runs in simulator)
try:
    import serial
    from serial.tools import list_ports
    SERIAL_AVAILABLE = True
except Exception:
    SERIAL_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

# ----------------------------
# Configuration / constants
# ----------------------------
POLL_INTERVAL_MS = 200          # update UI interval
SERIAL_BAUDRATE = 115200
MAX_POINTS = 300                # points to show in graphs
DEFAULT_EC_K = 0.5              # default conversion factor

# Regex to parse the incoming DATA line robustly
DATA_RE = re.compile(
    r"DATA:.*?Jarak: *([\d\.]+).*?TDS: *([\d\.]+).*?EC: *([\d\.]+).*?Suhu: *([\d\.]+).*?Pompa: *([01]).*?Alarm: *([01]).*?Level Air: *([A-Z]+)",
    re.IGNORECASE
)

# ----------------------------
# Serial Reader Thread
# ----------------------------
class SerialReader(threading.Thread):
    def __init__(self, port=None, baud=SERIAL_BAUDRATE, q=None, simulate=False):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.q = q or queue.Queue()
        self.simulate = simulate
        self._stop = threading.Event()
        self.ser = None

    def stop(self):
        self._stop.set()
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    def run(self):
        if self.simulate or not SERIAL_AVAILABLE:
            self._simulate_loop()
            return

        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
        except Exception as e:
            # push an error message and exit
            self.q.put(("__error__", f"Could not open {self.port}: {e}"))
            return

        # read loop
        while not self._stop.is_set():
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if line:
                    self.q.put(("__line__", line))
            except Exception as e:
                self.q.put(("__error__", f"Serial read error: {e}"))
                break

        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    def _simulate_loop(self):
        """Simulate periodic DATA lines for testing without hardware."""
        while not self._stop.is_set():
            # simulate realistic values with some random walk
            jarak = random.randint(1, 40)
            tds = max(0, int(200 + random.gauss(0, 10)))
            ec = round(tds / DEFAULT_EC_K, 1)
            suhu = round(25 + random.gauss(0, 0.8), 1)
            pompa = random.choice([0, 1]) if jarak >= 20 else 0
            alarm = 1 if (tds > 550 or jarak <= 2) else 0
            level = "PENUH" if jarak <= 2 else ("RENDAH" if jarak >= 10 else "SEDANG")
            line = f"DATA: Jarak:{jarak} | TDS:{tds} | EC:{ec} | Suhu:{suhu} | Pompa:{pompa} | Alarm:{alarm} | Level Air:{level}"
            self.q.put(("__line__", line))
            time.sleep(0.5)

# ----------------------------
# Parser function
# ----------------------------
def parse_data_line(line):
    """
    Parse the incoming DATA line and return a dict or None.
    """
    m = DATA_RE.search(line)
    if not m:
        return None
    try:
        return {
            "timestamp": datetime.now(),
            "jarak": float(m.group(1)),
            "tds": float(m.group(2)),
            "ec": float(m.group(3)),
            "suhu": float(m.group(4)),
            "pompa": int(m.group(5)),
            "alarm": int(m.group(6)),
            "level": m.group(7).upper()
        }
    except Exception:
        return None

# ----------------------------
# Main Application (Tkinter)
# ----------------------------
class MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TDS/EC Monitor")
        self.root.geometry("1100x700")

        self.queue = queue.Queue()
        self.reader = None
        self.simulate_mode = True if not SERIAL_AVAILABLE else False

        # Data deques for plotting
        self.times = deque(maxlen=MAX_POINTS)
        self.tds_data = deque(maxlen=MAX_POINTS)
        self.ec_data = deque(maxlen=MAX_POINTS)
        self.suhu_data = deque(maxlen=MAX_POINTS)

        # last parsed values
        self.last_values = {}

        # conversion factor (editable)
        self.ec_k = tk.DoubleVar(value=DEFAULT_EC_K)

        # create UI
        self._create_widgets()

        # periodic UI update
        self.root.after(POLL_INTERVAL_MS, self._periodic_update)

    # ----------------------------
    # UI Construction
    # ----------------------------
    def _create_widgets(self):
        # Top frame: controls
        top = ttk.Frame(self.root, padding=6)
        top.pack(side="top", fill="x")

        # Serial port selection (if pyserial available)
        port_lbl = ttk.Label(top, text="Port:")
        port_lbl.grid(row=0, column=0, sticky="w")

        self.port_cb = ttk.Combobox(top, width=15, values=self._list_serial_ports())
        self.port_cb.grid(row=0, column=1, padx=4)
        if SERIAL_AVAILABLE and self.port_cb['values']:
            self.port_cb.set(self.port_cb['values'][0])

        self.connect_btn = ttk.Button(top, text="Connect", command=self.toggle_connect)
        self.connect_btn.grid(row=0, column=2, padx=4)

        self.sim_chk = tk.BooleanVar(value=self.simulate_mode)
        self.sim_btn = ttk.Checkbutton(top, text="Simulator", variable=self.sim_chk, command=self._on_toggle_sim)
        self.sim_btn.grid(row=0, column=3, padx=4)

        ttk.Label(top, text="Baud:").grid(row=0, column=4, sticky="w", padx=(10,0))
        self.baud_entry = ttk.Entry(top, width=8)
        self.baud_entry.insert(0, str(SERIAL_BAUDRATE))
        self.baud_entry.grid(row=0, column=5, padx=4)

        ttk.Label(top, text="EC↔TDS K:").grid(row=0, column=6, sticky="w", padx=(10,0))
        self.k_entry = ttk.Entry(top, width=6, textvariable=self.ec_k)
        self.k_entry.grid(row=0, column=7, padx=4)

        ttk.Button(top, text="Save Log CSV", command=self.save_csv).grid(row=0, column=8, padx=6)
        ttk.Button(top, text="Clear Log", command=self.clear_log).grid(row=0, column=9, padx=6)

        # Middle frame: numeric displays and buttons
        mid = ttk.Frame(self.root, padding=6)
        mid.pack(side="top", fill="x")

        # Numeric panel
        panel = ttk.Frame(mid)
        panel.pack(side="left", fill="y", padx=6, pady=6)

        # labels dictionary
        self.value_labels = {}
        metrics = [("Jarak (cm)", "jarak"), ("TDS (ppm)", "tds"), ("EC (µS/cm)", "ec"),
                   ("Suhu (°C)", "suhu"), ("Pompa", "pompa"), ("Alarm", "alarm"), ("Level Air", "level")]
        r = 0
        for text, key in metrics:
            lbl = ttk.Label(panel, text=text + ":", font=("Helvetica", 10))
            lbl.grid(row=r, column=0, sticky="w", pady=2)
            val = ttk.Label(panel, text="—", font=("Helvetica", 12, "bold"))
            val.grid(row=r, column=1, sticky="w", padx=8)
            self.value_labels[key] = val
            r += 1

        # Control buttons to send commands
        controls = ttk.Frame(panel, padding=(0,10))
        controls.grid(row=r, column=0, columnspan=2, pady=(10,0))
        ttk.Button(controls, text="Send '1' (START)", command=lambda: self.send_command("1")).grid(row=0, column=0, padx=4)
        ttk.Button(controls, text="Send 'stop'", command=lambda: self.send_command("stop")).grid(row=0, column=1, padx=4)

        # Right: plots
        plot_frame = ttk.Frame(mid)
        plot_frame.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        if MATPLOTLIB_AVAILABLE:
            self.fig = Figure(figsize=(7,4), dpi=100)
            self.ax_tds = self.fig.add_subplot(311)
            self.ax_ec  = self.fig.add_subplot(312)
            self.ax_suhu = self.fig.add_subplot(313)

            self.ax_tds.set_ylabel("TDS (ppm)")
            self.ax_ec.set_ylabel("EC (µS/cm)")
            self.ax_suhu.set_ylabel("Suhu (°C)")
            self.ax_suhu.set_xlabel("Waktu (s)")

            self.line_tds, = self.ax_tds.plot([], [], label="TDS")
            self.line_ec, = self.ax_ec.plot([], [], label="EC")
            self.line_suhu, = self.ax_suhu.plot([], [], label="Suhu")

            self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
        else:
            # fallback: show message
            ttk.Label(plot_frame, text="Matplotlib tidak tersedia.\nGrafik akan dinonaktifkan.",
                      foreground="red").pack(padx=10, pady=10)

        # Bottom: log text
        bottom = ttk.Frame(self.root, padding=6)
        bottom.pack(side="bottom", fill="both", expand=True)

        ttk.Label(bottom, text="Log:").pack(anchor="w")
        self.log_text = tk.Text(bottom, height=10, wrap="none")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

    # ----------------------------
    # Serial / simulator control
    # ----------------------------
    def _on_toggle_sim(self):
        self.simulate_mode = bool(self.sim_chk.get())

    def _list_serial_ports(self):
        if not SERIAL_AVAILABLE:
            return []
        ports = [p.device for p in list_ports.comports()]
        return ports

    def toggle_connect(self):
        if self.reader and self.reader.is_alive():
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        # start reader thread
        simulate = bool(self.sim_chk.get()) or not SERIAL_AVAILABLE
        port = None
        if not simulate:
            port = self.port_cb.get().strip()
            if not port:
                messagebox.showwarning("Port missing", "Pilih port serial atau aktifkan Simulator.")
                return
        try:
            baud = int(self.baud_entry.get().strip())
        except Exception:
            baud = SERIAL_BAUDRATE

        self.reader = SerialReader(port=port, baud=baud, q=self.queue, simulate=simulate)
        self.reader.start()
        self.connect_btn.config(text="Disconnect")
        self.log(f"Connected (simulate={simulate}, port={port}, baud={baud})")

    def _disconnect(self):
        if self.reader:
            self.reader.stop()
            self.reader = None
        self.connect_btn.config(text="Connect")
        self.log("Disconnected.")

    # ----------------------------
    # Send command to serial (if available)
    # ----------------------------
    def send_command(self, cmd):
        if self.reader and self.reader.ser and getattr(self.reader.ser, "is_open", False):
            try:
                self.reader.ser.write((cmd + "\n").encode())
                self.log(f"Sent: {cmd}")
            except Exception as e:
                self.log(f"Failed sending: {e}")
        else:
            # in simulator or disconnected, just log
            self.log(f"(No serial) Command not sent: {cmd}")

    # ----------------------------
    # Update loop: process queue & refresh plots/UI
    # ----------------------------
    def _periodic_update(self):
        try:
            while True:
                tag, payload = self.queue.get_nowait()
                if tag == "__line__":
                    line = payload
                    self.log(f"RX: {line}")
                    parsed = parse_data_line(line)
                    if parsed:
                        self._update_values(parsed)
                elif tag == "__error__":
                    self.log(f"ERROR: {payload}")
                else:
                    # unknown
                    self.log(f"MSG: {payload}")
        except queue.Empty:
            pass

        # update plots
        self._refresh_plots()

        # reschedule
        self.root.after(POLL_INTERVAL_MS, self._periodic_update)

    def _update_values(self, parsed):
        # apply EC↔TDS factor if user changed factor: ensure we show consistent pair
        k = float(self.ec_k.get() or DEFAULT_EC_K)
        # if the incoming EC and TDS disagree with factor significantly, we trust incoming EC, and update tds using k.
        # This lets user tune conversion factor but preserves sensor EC reading.
        parsed_ec = parsed["ec"]
        parsed_tds = parsed["tds"]
        # compute tds_from_ec to keep consistent
        tds_from_ec = parsed_ec * k
        # choose averaged value to smooth minor mismatch
        parsed["ec"] = parsed_ec
        parsed["tds"] = (parsed_tds + tds_from_ec) / 2.0

        self.last_values = parsed

        # update numeric labels
        self._set_label("jarak", f"{parsed['jarak']:.1f}")
        self._set_label("tds", f"{parsed['tds']:.1f}")
        self._set_label("ec", f"{parsed['ec']:.1f}")
        self._set_label("suhu", f"{parsed['suhu']:.1f}")
        self._set_label("pompa", "ON" if parsed['pompa'] else "OFF")
        self._set_label("alarm", "YES" if parsed['alarm'] else "NO")
        self._set_label("level", parsed['level'])

        # append to plot buffers
        t = parsed["timestamp"].strftime("%H:%M:%S")
        self.times.append(t)
        self.tds_data.append(parsed["tds"])
        self.ec_data.append(parsed["ec"])
        self.suhu_data.append(parsed["suhu"])

    def _set_label(self, key, text):
        if key in self.value_labels:
            self.value_labels[key].config(text=text)

    def _refresh_plots(self):
        if not MATPLOTLIB_AVAILABLE:
            return
        # x-axis: convert times to index or simple list
        xs = list(range(len(self.times)))

        # update each line
        self.line_tds.set_data(xs, list(self.tds_data))
        self.line_ec.set_data(xs, list(self.ec_data))
        self.line_suhu.set_data(xs, list(self.suhu_data))

        # autoscale
        def rescale(ax, data):
            if len(data) == 0:
                return
            ax.relim()
            ax.autoscale_view()

        rescale(self.ax_tds, self.tds_data)
        rescale(self.ax_ec, self.ec_data)
        rescale(self.ax_suhu, self.suhu_data)

        # set x-limits
        self.ax_tds.set_xlim(0, max(10, len(xs)))
        self.ax_ec.set_xlim(0, max(10, len(xs)))
        self.ax_suhu.set_xlim(0, max(10, len(xs)))

        # redraw
        self.canvas.draw_idle()

    # ----------------------------
    # Logging utilities
    # ----------------------------
    def log(self, text):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] {text}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def save_csv(self):
        if not self.times:
            messagebox.showinfo("No data", "No data to save.")
            return

        filename = filedialog.asksaveasfilename(defaultextension=".csv",
                                                filetypes=[("CSV files","*.csv"), ("All files","*.*")])
        if not filename:
            return

        # collect rows from stored lists (we stored only numeric buffers; we also keep last_values timestamp string)
        # We'll write time, tds, ec, suhu, jarak, last labels for pompa/alarm/level
        with open(filename, "w", newline="") as f:
            csvw = csv.writer(f)
            csvw.writerow(["time", "tds_ppm", "ec_uS_cm", "suhu_C", "jarak_cm", "pompa", "alarm", "level"])
            # we don't store all states for every point, so use the existing buffers length and last_values for non-available fields
            for i in range(len(self.times)):
                time_str = self.times[i]
                tds = self.tds_data[i] if i < len(self.tds_data) else ""
                ec = self.ec_data[i] if i < len(self.ec_data) else ""
                suhu = self.suhu_data[i] if i < len(self.suhu_data) else ""
                jarak = self.last_values.get("jarak", "")
                pompa = self.last_values.get("pompa", "")
                alarm = self.last_values.get("alarm", "")
                level = self.last_values.get("level", "")
                csvw.writerow([time_str, tds, ec, suhu, jarak, pompa, alarm, level])

        messagebox.showinfo("Saved", f"Log saved to {filename}")

    def clear_log(self):
        if messagebox.askyesno("Clear log", "Clear log and buffers?"):
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
            self.times.clear()
            self.tds_data.clear()
            self.ec_data.clear()
            self.suhu_data.clear()
            self.last_values = {}
            # reset numeric labels
            for k in self.value_labels:
                self.value_labels[k].config(text="—")
            if MATPLOTLIB_AVAILABLE:
                self._refresh_plots()

# ----------------------------
# Run app
# ----------------------------
def main():
    root = tk.Tk()
    app = MonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root, app))
    root.mainloop()

def on_closing(root, app):
    if messagebox.askokcancel("Quit", "Close application?"):
        if app.reader:
            app.reader.stop()
        root.destroy()

if __name__ == "__main__":
    main()
