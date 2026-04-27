"""
ECG Monitor UI (PyQt5)
----------------------
PyQt5 + pyqtgraph front-end for the ECG acquisition system.

Architecture:
  - ECGReceiver runs in its own background thread (already does)
  - QTimer pulls data into the UI on two cadences:
      * 33 ms  -> waveform redraw (~30 FPS)
      * 1000 ms -> processing (filter + R-peaks + BPM) and stats refresh
  - Pull model (instead of Qt signals from worker thread): simpler, no
    cross-thread signal plumbing, and the receiver stays UI-agnostic.

Run:
    python ecg_ui.py
"""

import sys
from enum import Enum
from typing import Optional

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets
from serial.tools import list_ports

from ecg_receiver import ECGReceiver
from ecg_processor import ECGProcessor


# --------------------------------------------------------------------
SAMPLE_RATE = 250
DISPLAY_SECONDS = 10                  # Rolling window shown on the plot
BAUD_RATE = 250000
WAVEFORM_FPS_MS = 33                  # ~30 FPS plot redraw
PROCESSING_INTERVAL_MS = 1000         # 1 Hz BPM / R-peak update


class State(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    RUNNING = "running"
    ERROR = "error"


class ECGMonitor(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECG Monitor")
        self.resize(1100, 700)

        # ---- model state ----
        self.receiver: Optional[ECGReceiver] = None
        self.processor = ECGProcessor(sample_rate=SAMPLE_RATE, notch_hz=60.0)
        self.state = State.DISCONNECTED
        self.last_peaks_idx = np.array([], dtype=int)
        self.last_filtered = np.array([])

        self._build_ui()
        self._refresh_ports()

        # Two timers running while connected
        self._waveform_timer = QtCore.QTimer(self)
        self._waveform_timer.timeout.connect(self._update_waveform)

        self._processing_timer = QtCore.QTimer(self)
        self._processing_timer.timeout.connect(self._update_processing)

    # ================================================================
    #                            UI BUILD
    # ================================================================
    def _build_ui(self):
        # Use a dark-friendly background regardless of system theme
        pg.setConfigOption("background", "#101418")
        pg.setConfigOption("foreground", "#d0d4d8")
        pg.setConfigOption("antialias", True)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ---------- top: connection controls ----------
        ctl = QtWidgets.QHBoxLayout()
        ctl.addWidget(QtWidgets.QLabel("COM Port:"))

        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setMinimumWidth(180)
        ctl.addWidget(self.port_combo)

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_ports)
        ctl.addWidget(self.refresh_btn)

        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect)
        ctl.addWidget(self.connect_btn)

        self.disconnect_btn = QtWidgets.QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.disconnect_btn.setEnabled(False)
        ctl.addWidget(self.disconnect_btn)

        ctl.addStretch(1)
        root.addLayout(ctl)

        # ---------- middle: BPM + status panel ----------
        info = QtWidgets.QHBoxLayout()

        # BPM tile
        bpm_box = QtWidgets.QFrame()
        bpm_box.setFrameShape(QtWidgets.QFrame.StyledPanel)
        bpm_layout = QtWidgets.QVBoxLayout(bpm_box)
        bpm_label = QtWidgets.QLabel("BPM")
        bpm_label.setStyleSheet("color: #888; font-size: 12px;")
        self.bpm_value = QtWidgets.QLabel("--")
        self.bpm_value.setStyleSheet(
            "color: #ff5577; font-size: 64px; font-weight: bold;"
        )
        self.bpm_value.setAlignment(QtCore.Qt.AlignCenter)
        bpm_layout.addWidget(bpm_label)
        bpm_layout.addWidget(self.bpm_value)
        bpm_box.setMinimumWidth(220)
        info.addWidget(bpm_box)

        # Status tile
        status_box = QtWidgets.QFrame()
        status_box.setFrameShape(QtWidgets.QFrame.StyledPanel)
        sl = QtWidgets.QGridLayout(status_box)
        self.status_state = QtWidgets.QLabel("● Disconnected")
        self.status_state.setStyleSheet("color: #888; font-size: 16px;")
        self.status_rate = QtWidgets.QLabel("Rate: -- Hz")
        self.status_samples = QtWidgets.QLabel("Samples: 0")
        self.status_drops = QtWidgets.QLabel("Drops: 0")
        self.status_buffer = QtWidgets.QLabel("Buffer: 0")
        sl.addWidget(self.status_state,   0, 0, 1, 2)
        sl.addWidget(self.status_rate,    1, 0)
        sl.addWidget(self.status_samples, 1, 1)
        sl.addWidget(self.status_drops,   2, 0)
        sl.addWidget(self.status_buffer,  2, 1)
        info.addWidget(status_box, stretch=1)

        root.addLayout(info)

        # ---------- bottom: waveform plot ----------
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("bottom", "Time", units="s")
        self.plot_widget.setLabel("left", "Amplitude", units="V")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.setMouseEnabled(x=False, y=True)  # X is auto-rolling
        self.plot_widget.setXRange(0, DISPLAY_SECONDS, padding=0)

        # Two curves: filtered waveform + R-peak markers
        self.waveform_curve = self.plot_widget.plot(
            pen=pg.mkPen("#5fdfff", width=1.5)
        )
        self.peak_scatter = pg.ScatterPlotItem(
            size=10, pen=pg.mkPen("#ff3355", width=1.5),
            brush=pg.mkBrush(255, 51, 85, 180), symbol="o"
        )
        self.plot_widget.addItem(self.peak_scatter)

        root.addWidget(self.plot_widget, stretch=1)

        # Status bar at the very bottom
        self.statusBar().showMessage("Ready")

    # ================================================================
    #                       CONNECTION HANDLERS
    # ================================================================
    def _refresh_ports(self):
        current = self.port_combo.currentText()
        self.port_combo.clear()
        ports = list_ports.comports()
        if not ports:
            self.port_combo.addItem("(no ports found)")
            self.connect_btn.setEnabled(False)
            return
        for p in ports:
            label = f"{p.device} - {p.description}"
            self.port_combo.addItem(label, p.device)
        # Try to restore previous selection
        idx = self.port_combo.findText(current)
        if idx >= 0:
            self.port_combo.setCurrentIndex(idx)
        self.connect_btn.setEnabled(True)

    def _selected_port(self) -> Optional[str]:
        return self.port_combo.currentData()

    def _on_connect(self):
        port = self._selected_port()
        if not port:
            self._set_error("No COM port selected")
            return

        self._set_state(State.CONNECTING)
        QtWidgets.QApplication.processEvents()  # Refresh UI before blocking

        try:
            self.receiver = ECGReceiver(
                port=port, baud=BAUD_RATE, sample_rate=SAMPLE_RATE,
                buffer_seconds=DISPLAY_SECONDS + 5,
            )
            self.receiver.connect()      # blocks ~2s for Arduino auto-reset
            self.receiver.start()
        except Exception as e:
            self.receiver = None
            self._set_error(f"Connect failed: {e}")
            return

        self._set_state(State.RUNNING)
        self._waveform_timer.start(WAVEFORM_FPS_MS)
        self._processing_timer.start(PROCESSING_INTERVAL_MS)

    def _on_disconnect(self):
        self._waveform_timer.stop()
        self._processing_timer.stop()
        if self.receiver:
            try:
                self.receiver.stop()
            except Exception as e:
                self.statusBar().showMessage(f"Disconnect error: {e}")
            self.receiver = None
        self.bpm_value.setText("--")
        self.waveform_curve.setData([], [])
        self.peak_scatter.setData([], [])
        self._set_state(State.DISCONNECTED)

    def _set_error(self, msg: str):
        self.statusBar().showMessage(msg)
        self.status_state.setText("● Error")
        self.status_state.setStyleSheet("color: #ff5555; font-size: 16px;")
        self._set_state(State.ERROR)

    def _set_state(self, state: State):
        self.state = state
        if state == State.DISCONNECTED:
            self.status_state.setText("● Disconnected")
            self.status_state.setStyleSheet("color: #888; font-size: 16px;")
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.port_combo.setEnabled(True)
            self.refresh_btn.setEnabled(True)
            self.statusBar().showMessage("Ready")
        elif state == State.CONNECTING:
            self.status_state.setText("● Connecting...")
            self.status_state.setStyleSheet("color: #ffaa33; font-size: 16px;")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(False)
            self.port_combo.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.statusBar().showMessage("Connecting...")
        elif state == State.RUNNING:
            self.status_state.setText("● Running")
            self.status_state.setStyleSheet("color: #55dd77; font-size: 16px;")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.port_combo.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.statusBar().showMessage(f"Connected to {self._selected_port()}")
        elif state == State.ERROR:
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.port_combo.setEnabled(True)
            self.refresh_btn.setEnabled(True)

    # ================================================================
    #                        UPDATE CALLBACKS
    # ================================================================
    def _update_waveform(self):
        """Fast path: redraw the rolling waveform (~30 FPS)."""
        if not self.receiver:
            return

        n = SAMPLE_RATE * DISPLAY_SECONDS
        data = self.receiver.get_latest(n)
        if not data:
            return

        n_have = len(data)
        _, adcs = zip(*data)
        adcs = np.asarray(adcs, dtype=np.float64)

        # If processor has a recent filtered snapshot of similar length, plot
        # that for a clean trace. Otherwise fall back to raw volts (during
        # the first second before the processor has run).
        if len(self.last_filtered) == n_have:
            y = self.last_filtered
            peaks_idx = self.last_peaks_idx
        else:
            y = adcs * (5.0 / 1023.0) - 2.5      # raw volts, centered
            peaks_idx = np.array([], dtype=int)

        # X axis: place samples so the latest point sits at DISPLAY_SECONDS
        x = np.arange(n_have) / SAMPLE_RATE
        x = x - (x[-1] - DISPLAY_SECONDS) if x[-1] > DISPLAY_SECONDS else x

        self.waveform_curve.setData(x, y)
        if len(peaks_idx) > 0:
            self.peak_scatter.setData(x[peaks_idx], y[peaks_idx])
        else:
            self.peak_scatter.setData([], [])

    def _update_processing(self):
        """Slow path: run filter + R-peak + BPM, refresh stats."""
        if not self.receiver:
            return

        # Status panel
        st = self.receiver.get_status()
        self.status_rate.setText(f"Rate: {st.rate_hz:.1f} Hz")
        self.status_samples.setText(f"Samples: {st.total_samples}")
        self.status_drops.setText(f"Drops: {st.dropped_samples}")
        self.status_buffer.setText(f"Buffer: {st.buffer_fill}")

        # Run processing on the visible window
        n = SAMPLE_RATE * DISPLAY_SECONDS
        data = self.receiver.get_latest(n)
        if len(data) < SAMPLE_RATE:        # need at least 1 s for filters
            return

        _, adcs = zip(*data)
        result = self.processor.process(np.asarray(adcs))

        self.last_filtered = result.filtered
        self.last_peaks_idx = result.peaks

        if result.bpm is not None:
            self.bpm_value.setText(f"{result.bpm:.0f}")
        else:
            self.bpm_value.setText("--")

    # ================================================================
    #                          SHUTDOWN
    # ================================================================
    def closeEvent(self, ev: QtGui.QCloseEvent):
        # Make sure the background serial thread is stopped before window dies
        self._waveform_timer.stop()
        self._processing_timer.stop()
        if self.receiver:
            try:
                self.receiver.stop()
            except Exception:
                pass
        ev.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")          # Consistent look across Win/Mac/Linux
    win = ECGMonitor()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
