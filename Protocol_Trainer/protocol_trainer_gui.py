import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import queue
import re


PROTOCOL_COMMAND_MAP = {
    "UART": "UART",
    "SPI Mode 0": "SPI0",
    "SPI Mode 1": "SPI1",
    "SPI Mode 2": "SPI2",
    "SPI Mode 3": "SPI3",
}

FIRMWARE_BAUD = 115200
SOFTSERIAL_MAX_BAUD = 57600
ARDUINO_RESET_DELAY = 2.0


def hex_to_ascii_display(hex_str):
    """把 'RX:' 後面的 hex 字串轉成可顯示的 ASCII。
    不可印的字元用 '.' 代替（HxD / Wireshark 風格）。"""
    out = []
    for tok in hex_str.split():
        try:
            b = int(tok, 16)
        except ValueError:
            out.append("?")
            continue
        if 0x20 <= b <= 0x7E:
            out.append(chr(b))
        else:
            out.append(".")
    return "".join(out)


class ProtocolTrainerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Arduino Protocol Trainer")
        self.root.geometry("960x680")

        self.ser = None
        self.reader_thread = None
        self.reader_stop = threading.Event()
        self.rx_queue = queue.Queue()

        self.listening = False  # GUI 端追蹤的 listen 狀態

        self._build_ui()
        self.refresh_ports()
        self.on_protocol_change()
        self.update_preview()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(50, self._drain_rx_queue)

    # ---------- UI ----------

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # --- Serial connection ---
        serial_frame = ttk.LabelFrame(frame, text="Serial Connection", padding=10)
        serial_frame.pack(fill=tk.X, pady=5)

        ttk.Label(serial_frame, text="COM Port:").pack(side=tk.LEFT)
        self.port_combo = ttk.Combobox(serial_frame, width=20, state="readonly")
        self.port_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(serial_frame, text="Refresh", command=self.refresh_ports).pack(side=tk.LEFT, padx=5)
        self.connect_btn = ttk.Button(serial_frame, text="Connect", command=self.connect_serial)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        self.disconnect_btn = ttk.Button(
            serial_frame, text="Disconnect", command=self.disconnect_serial, state="disabled"
        )
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="Disconnected")
        ttk.Label(serial_frame, textvariable=self.status_var, foreground="gray").pack(side=tk.LEFT, padx=10)

        # --- 中段用 Notebook 分 Send / Listen 兩頁 ---
        notebook = ttk.Notebook(frame)
        notebook.pack(fill=tk.X, pady=5)

        send_tab = ttk.Frame(notebook, padding=10)
        listen_tab = ttk.Frame(notebook, padding=10)
        notebook.add(send_tab, text="Send (UART / SPI)")
        notebook.add(listen_tab, text="Listen (UART RX on D9)")

        self._build_send_tab(send_tab)
        self._build_listen_tab(listen_tab)

        # --- Log ---
        log_header = ttk.Frame(frame)
        log_header.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(log_header, text="Log:").pack(side=tk.LEFT)
        ttk.Button(log_header, text="Clear", command=self.clear_log).pack(side=tk.RIGHT)

        log_frame = ttk.Frame(frame)
        log_frame.pack(fill=tk.BOTH, expand=True)

        # 用 monospace font，ASCII / HEX 兩欄對齊
        self.log_text = tk.Text(log_frame, height=18, wrap="none",
                                font=("Consolas", 10))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.tag_configure("tx",   foreground="blue")
        self.log_text.tag_configure("rx",   foreground="darkgreen")
        self.log_text.tag_configure("err",  foreground="red")
        self.log_text.tag_configure("info", foreground="gray")
        self.log_text.tag_configure("hdr",  foreground="black", font=("Consolas", 10, "bold"))

    def _build_send_tab(self, parent):
        ttk.Label(parent, text="Protocol:").grid(row=0, column=0, sticky="w")
        self.protocol_combo = ttk.Combobox(
            parent, width=15, state="readonly",
            values=list(PROTOCOL_COMMAND_MAP.keys()),
        )
        self.protocol_combo.grid(row=0, column=1, padx=5, sticky="w")
        self.protocol_combo.current(0)

        ttk.Label(parent, text="UART Baud:").grid(row=0, column=2, padx=(15, 0), sticky="w")
        self.uart_baud_combo = ttk.Combobox(
            parent, width=12, state="readonly",
            values=["9600", "19200", "38400", "57600"],
        )
        self.uart_baud_combo.grid(row=0, column=3, padx=5, sticky="w")
        self.uart_baud_combo.current(0)

        ttk.Label(parent, text="SPI Clock Hz:").grid(row=0, column=4, padx=(15, 0), sticky="w")
        self.spi_clock_combo = ttk.Combobox(
            parent, width=12, state="readonly",
            values=["100000", "250000", "1000000", "2000000"],
        )
        self.spi_clock_combo.grid(row=0, column=5, padx=5, sticky="w")
        self.spi_clock_combo.current(2)

        ttk.Label(parent, text="Payload Format:").grid(row=1, column=0, pady=(10, 0), sticky="w")
        self.format_combo = ttk.Combobox(
            parent, width=15, state="readonly",
            values=["ASCII", "HEX"],
        )
        self.format_combo.grid(row=1, column=1, pady=(10, 0), padx=5, sticky="w")
        self.format_combo.current(0)

        ttk.Label(parent, text="Payload:").grid(row=2, column=0, pady=(10, 0), sticky="w")
        self.payload_entry = ttk.Entry(parent)
        self.payload_entry.grid(row=2, column=1, columnspan=4, pady=(10, 0), padx=5, sticky="ew")

        self.send_btn = ttk.Button(parent, text="Send", command=self.send_message, state="disabled")
        self.send_btn.grid(row=2, column=5, pady=(10, 0), padx=5, sticky="ew")

        # Preview
        ttk.Label(parent, text="Preview:").grid(row=3, column=0, pady=(10, 0), sticky="w")
        self.preview_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.preview_var, foreground="navy").grid(
            row=3, column=1, columnspan=5, pady=(10, 0), padx=5, sticky="w"
        )

        parent.columnconfigure(4, weight=1)

        self.protocol_combo.bind("<<ComboboxSelected>>", self.on_protocol_change)
        self.uart_baud_combo.bind("<<ComboboxSelected>>", self.update_preview)
        self.spi_clock_combo.bind("<<ComboboxSelected>>", self.update_preview)
        self.format_combo.bind("<<ComboboxSelected>>", self.update_preview)
        self.payload_entry.bind("<KeyRelease>", self.update_preview)
        self.payload_entry.bind("<Return>", lambda e: self.send_message())

    def _build_listen_tab(self, parent):
        ttk.Label(parent, text="Listen Baud:").grid(row=0, column=0, sticky="w")
        self.listen_baud_combo = ttk.Combobox(
            parent, width=12, state="readonly",
            values=["9600", "19200", "38400", "57600"],
        )
        self.listen_baud_combo.grid(row=0, column=1, padx=5, sticky="w")
        self.listen_baud_combo.current(0)

        self.listen_btn = ttk.Button(
            parent, text="Start Listen", command=self.start_listen, state="disabled"
        )
        self.listen_btn.grid(row=0, column=2, padx=5)

        self.stop_listen_btn = ttk.Button(
            parent, text="Stop Listen", command=self.stop_listen, state="disabled"
        )
        self.stop_listen_btn.grid(row=0, column=3, padx=5)

        self.listen_status_var = tk.StringVar(value="Idle")
        ttk.Label(parent, textvariable=self.listen_status_var, foreground="gray").grid(
            row=0, column=4, padx=15, sticky="w"
        )

        info = ttk.Label(
            parent,
            text="Connect external TX to UNO D9, share GND. Frames split on 30ms silence.",
            foreground="gray",
        )
        info.grid(row=1, column=0, columnspan=5, pady=(10, 0), sticky="w")

        parent.columnconfigure(4, weight=1)

    # ---------- Port / 連線 ----------

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_names = [p.device for p in ports]

        current = self.port_combo.get()
        self.port_combo["values"] = port_names

        if current in port_names:
            self.port_combo.set(current)
        elif port_names:
            self.port_combo.current(0)
        else:
            self.port_combo.set("")

        self.log(f"COM ports refreshed: {port_names if port_names else 'none found'}", "info")

    def connect_serial(self):
        if self.ser and self.ser.is_open:
            self.log("Already connected. Disconnect first.", "info")
            return

        port = self.port_combo.get()
        if not port:
            messagebox.showerror("Error", "Please select a COM port.")
            return

        try:
            self.ser = serial.Serial(port, FIRMWARE_BAUD, timeout=0.1)
        except serial.SerialException as e:
            messagebox.showerror("Serial Error", str(e))
            self.log(f"Connection failed: {e}", "err")
            self.ser = None
            return

        self.log(f"Opening {port} @ {FIRMWARE_BAUD} bps, waiting for Arduino reset...", "info")
        self.status_var.set(f"Connected: {port}")
        self.root.after(int(ARDUINO_RESET_DELAY * 1000), self._post_connect)

    def _post_connect(self):
        if not self.ser or not self.ser.is_open:
            return

        self.reader_stop.clear()
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

        self.connect_btn.configure(state="disabled")
        self.disconnect_btn.configure(state="normal")
        self.send_btn.configure(state="normal")
        self.listen_btn.configure(state="normal")

        self.log("Ready.", "info")

    def disconnect_serial(self):
        if not self.ser or not self.ser.is_open:
            self.log("Serial is not connected.", "info")
            return

        # 如果還在 listen，先送 STOP 出去（盡力而為）
        if self.listening:
            try:
                self.ser.write(b"STOP\n")
                self.ser.flush()
            except Exception:
                pass
            self.listening = False

        self.reader_stop.set()
        if self.reader_thread is not None:
            self.reader_thread.join(timeout=0.5)
            self.reader_thread = None

        try:
            self.ser.close()
        except Exception as e:
            self.log(f"Close error: {e}", "err")

        self.ser = None

        self.connect_btn.configure(state="normal")
        self.disconnect_btn.configure(state="disabled")
        self.send_btn.configure(state="disabled")
        self.listen_btn.configure(state="disabled")
        self.stop_listen_btn.configure(state="disabled")
        self.status_var.set("Disconnected")
        self.listen_status_var.set("Idle")
        self.log("Serial disconnected.", "info")

    # ---------- 背景 reader ----------

    def _reader_loop(self):
        buf = bytearray()
        while not self.reader_stop.is_set():
            try:
                if self.ser is None or not self.ser.is_open:
                    break
                chunk = self.ser.read(128)
                if chunk:
                    buf.extend(chunk)
                    while True:
                        idx = -1
                        for i, b in enumerate(buf):
                            if b in (0x0A, 0x0D):
                                idx = i
                                break
                        if idx < 0:
                            break
                        line_bytes = bytes(buf[:idx])
                        del buf[:idx + 1]
                        if line_bytes:
                            line = line_bytes.decode("utf-8", errors="replace").strip()
                            if line:
                                self.rx_queue.put(line)
            except (serial.SerialException, OSError) as e:
                self.rx_queue.put(("__err__", f"Reader error: {e}"))
                break

    def _drain_rx_queue(self):
        try:
            while True:
                item = self.rx_queue.get_nowait()
                if isinstance(item, tuple) and item and item[0] == "__err__":
                    self.log(item[1], "err")
                else:
                    self._handle_arduino_line(item)
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self._drain_rx_queue)

    def _handle_arduino_line(self, line):
        """根據 Arduino 回傳的字串決定怎麼顯示。"""
        # RX frame：格式 "RX:48 65 6C 6C 6F"
        if line.startswith("RX:"):
            hex_part = line[3:].strip()
            ascii_part = hex_to_ascii_display(hex_part)
            self._log_rx_frame(ascii_part, hex_part)
            return

        # 一般狀態訊息（OK/ERROR/WARN/banner）
        # 如果是 LISTEN 狀態變化，順便更新 UI
        if line.startswith("OK: LISTEN started"):
            self.listening = True
            self.listen_btn.configure(state="disabled")
            self.stop_listen_btn.configure(state="normal")
            self.listen_status_var.set("Listening")
        elif line.startswith("OK: STOP"):
            self.listening = False
            self.listen_btn.configure(state="normal")
            self.stop_listen_btn.configure(state="disabled")
            self.listen_status_var.set("Idle")

        tag = "rx"
        if line.startswith("ERROR"):
            tag = "err"
        elif line.startswith("WARN"):
            tag = "err"
        self.log(f"Arduino: {line}", tag)

    def _log_rx_frame(self, ascii_part, hex_part):
        """顯示 RX frame：左 ASCII 欄、右 HEX 欄並排。"""
        # 第一次出現 frame 時，加一個欄位標題
        if not hasattr(self, "_rx_header_shown"):
            self.log_text.insert(
                tk.END,
                f"  {'ASCII':<34} | HEX\n", "hdr"
            )
            self.log_text.insert(
                tk.END,
                f"  {'-' * 34} + {'-' * 47}\n", "hdr"
            )
            self._rx_header_shown = True

        # ASCII 欄固定寬 34 個字元（對應約 32 byte payload + 一點 margin）
        ascii_col = ascii_part[:34].ljust(34)
        line = f"  {ascii_col} | {hex_part}\n"
        self.log_text.insert(tk.END, line, "rx")
        self.log_text.see(tk.END)

    # ---------- 命令組裝 ----------

    def on_protocol_change(self, event=None):
        if self.protocol_combo.get() == "UART":
            self.uart_baud_combo.configure(state="readonly")
            self.spi_clock_combo.configure(state="disabled")
        else:
            self.uart_baud_combo.configure(state="disabled")
            self.spi_clock_combo.configure(state="readonly")
        self.update_preview()

    def build_command(self):
        selected_protocol = self.protocol_combo.get()
        command_protocol = PROTOCOL_COMMAND_MAP[selected_protocol]
        if selected_protocol == "UART":
            parameter = self.uart_baud_combo.get()
        else:
            parameter = self.spi_clock_combo.get()
        payload_format = self.format_combo.get()
        payload = self.payload_entry.get()
        return f"{command_protocol},{parameter},{payload_format}:{payload}"

    def update_preview(self, event=None):
        self.preview_var.set(self.build_command())

    # ---------- 送出 / 驗證 ----------

    def validate_payload(self):
        payload_format = self.format_combo.get()
        payload = self.payload_entry.get()

        if not payload.strip():
            messagebox.showwarning("Warning", "Payload is empty.")
            return False

        if "\n" in payload or "\r" in payload:
            messagebox.showerror("Error", "Payload cannot contain newline characters.")
            return False

        if payload_format == "HEX":
            tokens = payload.split()
            if not tokens:
                messagebox.showwarning("Warning", "HEX payload is empty.")
                return False
            for token in tokens:
                t = token[2:] if token.lower().startswith("0x") else token
                if not re.fullmatch(r"[0-9a-fA-F]{1,2}", t):
                    messagebox.showerror(
                        "HEX Format Error",
                        "HEX payload must be bytes separated by spaces.\n\n"
                        "Example:\n  48 65 6C 6C 6F\n  0x48 0x65 0x6C",
                    )
                    return False
        return True

    def send_message(self):
        if not self.ser or not self.ser.is_open:
            messagebox.showerror("Error", "Serial port is not connected.")
            return
        if not self.validate_payload():
            return

        # 送出命令會讓 firmware 自動 stop listen，這邊同步更新 UI 狀態
        if self.listening:
            self.listening = False
            self.listen_btn.configure(state="normal")
            self.stop_listen_btn.configure(state="disabled")
            self.listen_status_var.set("Idle (auto-stopped)")

        command = self.build_command() + "\n"
        try:
            self.ser.write(command.encode("utf-8"))
            self.ser.flush()
            self.log(f"Sent: {command.strip()}", "tx")
        except serial.SerialException as e:
            messagebox.showerror("Serial Error", str(e))
            self.log(f"Send failed: {e}", "err")

    # ---------- Listen ----------

    def start_listen(self):
        if not self.ser or not self.ser.is_open:
            messagebox.showerror("Error", "Serial port is not connected.")
            return

        baud = self.listen_baud_combo.get()
        if not baud:
            messagebox.showwarning("Warning", "Please select a baud rate.")
            return

        cmd = f"LISTEN,{baud}\n"
        try:
            self.ser.write(cmd.encode("utf-8"))
            self.ser.flush()
            self.log(f"Sent: {cmd.strip()}", "tx")
            # 實際狀態由 Arduino 回的 "OK: LISTEN started" 更新
        except serial.SerialException as e:
            messagebox.showerror("Serial Error", str(e))
            self.log(f"Send failed: {e}", "err")

    def stop_listen(self):
        if not self.ser or not self.ser.is_open:
            return
        try:
            self.ser.write(b"STOP\n")
            self.ser.flush()
            self.log("Sent: STOP", "tx")
        except serial.SerialException as e:
            messagebox.showerror("Serial Error", str(e))
            self.log(f"Send failed: {e}", "err")

    # ---------- Log ----------

    def log(self, text, tag="info"):
        self.log_text.insert(tk.END, text + "\n", tag)
        self.log_text.see(tk.END)

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)
        if hasattr(self, "_rx_header_shown"):
            del self._rx_header_shown

    # ---------- 結束 ----------

    def on_close(self):
        try:
            if self.ser and self.ser.is_open:
                if self.listening:
                    try:
                        self.ser.write(b"STOP\n")
                        self.ser.flush()
                    except Exception:
                        pass
                self.reader_stop.set()
                if self.reader_thread is not None:
                    self.reader_thread.join(timeout=0.5)
                self.ser.close()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ProtocolTrainerGUI(root)
    root.mainloop()
