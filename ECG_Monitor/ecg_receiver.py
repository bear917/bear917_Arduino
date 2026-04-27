"""
ECG Serial Receiver
-------------------
Background-threaded serial reader for the Arduino ECG firmware.

Features:
  - Non-blocking: serial I/O runs in a daemon thread; UI/DSP consume via get_latest()
  - Sync recovery: re-aligns on 0xAA 0x55 if the byte stream gets misaligned
  - Drop detection via 8-bit rolling counter
  - Timestamp reconstruction: uniform 1/sample_rate spacing, immune to USB jitter
  - Thread-safe ring buffer (collections.deque + Lock)

Packet format (5 bytes, matches ecg_firmware.ino):
    [0xAA] [0x55] [counter] [adc_lo] [adc_hi]
"""

import collections
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import serial


PACKET_SIZE = 5
SYNC_1 = 0xAA
SYNC_2 = 0x55


@dataclass
class ReceiverStatus:
    connected: bool = False
    running: bool = False
    total_samples: int = 0
    dropped_samples: int = 0
    buffer_fill: int = 0
    rate_hz: float = 0.0          # measured arrival rate (samples/sec over last window)
    uptime_s: float = 0.0
    last_error: Optional[str] = None


class ECGReceiver:
    """Background serial reader with ring buffer and timestamp reconstruction."""

    def __init__(
        self,
        port: str,
        baud: int = 250000,
        sample_rate: int = 250,
        buffer_seconds: float = 30.0,
    ):
        self.port = port
        self.baud = baud
        self.sample_rate = sample_rate
        self.buffer_size = int(sample_rate * buffer_seconds)

        # Ring buffer of (timestamp_s, adc_value) pairs
        self._buffer: collections.deque = collections.deque(maxlen=self.buffer_size)
        self._lock = threading.Lock()

        # Thread control
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Serial handle
        self._ser: Optional[serial.Serial] = None

        # Reconstruction state
        self._t0: Optional[float] = None     # host time of first received sample
        self._sample_index: int = 0           # total samples "seen" (including dropped)
        self._last_counter: Optional[int] = None
        self._dropped: int = 0

        # Rate measurement (exponential moving average over arrival times)
        self._recent_arrivals: collections.deque = collections.deque(maxlen=250)

        self._last_error: Optional[str] = None

    # -------------------- public API --------------------
    def connect(self) -> None:
        """Open the serial port. Call before start()."""
        self._ser = serial.Serial(self.port, self.baud, timeout=0.1)
        # Arduino UNO auto-resets on DTR assertion; wait for bootloader
        time.sleep(2.0)
        self._ser.reset_input_buffer()

    def start(self) -> None:
        """Start the background reader thread."""
        if self._ser is None or not self._ser.is_open:
            raise RuntimeError("connect() must be called before start()")
        if self._thread and self._thread.is_alive():
            return  # already running

        self._stop_event.clear()
        self._reset_state()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the reader thread and close the serial port."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception as e:
                self._last_error = f"close: {e}"

    def get_latest(self, n: int) -> List[Tuple[float, int]]:
        """Return the last n (timestamp, adc) samples. If fewer exist, returns all."""
        with self._lock:
            if n >= len(self._buffer):
                return list(self._buffer)
            # deque slicing requires list conversion
            return list(self._buffer)[-n:]

    def snapshot(self) -> List[Tuple[float, int]]:
        """Return a full copy of the current buffer."""
        with self._lock:
            return list(self._buffer)

    def clear_buffer(self) -> None:
        with self._lock:
            self._buffer.clear()

    def get_status(self) -> ReceiverStatus:
        connected = self._ser is not None and self._ser.is_open
        running = self._thread is not None and self._thread.is_alive()

        # Rate = true long-term sample rate (samples / uptime).
        # Note: do NOT compute from deque span — USB bursts make the span
        # shorter than wall time and inflate the apparent rate.
        uptime = (time.perf_counter() - self._t0) if self._t0 else 0.0
        rate = (self._sample_index / uptime) if uptime > 0.5 else 0.0

        with self._lock:
            fill = len(self._buffer)

        return ReceiverStatus(
            connected=connected,
            running=running,
            total_samples=self._sample_index,
            dropped_samples=self._dropped,
            buffer_fill=fill,
            rate_hz=rate,
            uptime_s=uptime,
            last_error=self._last_error,
        )

    # -------------------- internals --------------------
    def _reset_state(self) -> None:
        self._t0 = None
        self._sample_index = 0
        self._last_counter = None
        self._dropped = 0
        self._recent_arrivals.clear()
        self._last_error = None
        with self._lock:
            self._buffer.clear()

    def _read_loop(self) -> None:
        """Continuously read from serial, parse packets, append to buffer."""
        buf = bytearray()

        while not self._stop_event.is_set():
            try:
                # Read whatever is available (blocks up to timeout)
                chunk = self._ser.read(256)
            except serial.SerialException as e:
                self._last_error = f"read: {e}"
                break
            except Exception as e:
                self._last_error = f"read-unexpected: {e}"
                break

            if chunk:
                buf.extend(chunk)

            # Parse as many complete packets as possible
            while len(buf) >= PACKET_SIZE:
                if buf[0] == SYNC_1 and buf[1] == SYNC_2:
                    counter = buf[2]
                    adc = buf[3] | (buf[4] << 8)
                    del buf[:PACKET_SIZE]
                    self._handle_sample(counter, adc)
                else:
                    # Sync lost — search forward for next 0xAA 0x55
                    idx = buf.find(bytes([SYNC_1, SYNC_2]), 1)
                    if idx < 0:
                        # Keep only the last byte (might be start of sync)
                        del buf[:-1]
                        break
                    del buf[:idx]

    def _handle_sample(self, counter: int, adc: int) -> None:
        now = time.perf_counter()

        # Drop detection via 8-bit rolling counter
        if self._last_counter is None:
            # First sample establishes timestamp origin
            self._t0 = now
            self._sample_index = 0
        else:
            gap = (counter - self._last_counter) & 0xFF
            if gap == 0:
                # Duplicate counter — shouldn't happen from firmware; skip
                return
            if gap > 1:
                # We lost (gap - 1) samples somewhere (rare at this bandwidth)
                self._dropped += gap - 1
                self._sample_index += gap - 1

        self._last_counter = counter

        # Reconstruct timestamp: perfectly uniform spacing at nominal rate
        t = self._t0 + self._sample_index / self.sample_rate
        self._sample_index += 1

        with self._lock:
            self._buffer.append((t, adc))

        self._recent_arrivals.append(now)

    # -------------------- context manager sugar --------------------
    def __enter__(self):
        self.connect()
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()


# -------------------- quick demo / smoke test --------------------
if __name__ == "__main__":
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else "COM3"

    print(f"Connecting to {port} ...")
    with ECGReceiver(port=port) as rx:
        print("Running. Press Ctrl+C to stop.\n")
        print(f"{'time':>6} | {'samples':>8} | {'dropped':>7} | {'rate':>7} | {'last_adc':>8}")
        print("-" * 55)

        try:
            for i in range(20):
                time.sleep(1.0)
                st = rx.get_status()
                last = rx.get_latest(1)
                last_adc = last[-1][1] if last else None
                print(
                    f"{st.uptime_s:6.1f} | "
                    f"{st.total_samples:8d} | "
                    f"{st.dropped_samples:7d} | "
                    f"{st.rate_hz:6.1f}  | "
                    f"{last_adc if last_adc is not None else '---':>8}"
                )
        except KeyboardInterrupt:
            print("\nStopping...")
