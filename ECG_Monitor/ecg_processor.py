"""
ECG Signal Processor
--------------------
Batch-mode processing: feed in a window of raw ADC samples, get back the
filtered waveform, R-peak locations, and BPM estimate.

Pipeline:
  ADC --> volts --> 60 Hz notch --> 0.5-40 Hz bandpass   (display waveform)
                                --> Pan-Tompkins --> R-peaks --> BPM

Designed to be called ~1 Hz from a UI with 5-10 seconds of data per call.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.signal import butter, sosfiltfilt, iirnotch, filtfilt, find_peaks


@dataclass
class ECGResult:
    voltage: np.ndarray                           # raw ADC -> volts
    filtered: np.ndarray                          # display-filtered, 0-centered, volts
    peaks: np.ndarray                             # indices of R-peaks into filtered[]
    bpm: Optional[float]                          # None if not enough peaks
    rr_intervals_ms: np.ndarray = field(          # RR intervals between detected peaks (ms)
        default_factory=lambda: np.array([])
    )


class ECGProcessor:
    """Offline/batch ECG filter + QRS detector."""

    def __init__(
        self,
        sample_rate: int = 250,
        display_band: tuple = (0.5, 40.0),        # display filter (Hz)
        qrs_band: tuple = (5.0, 15.0),            # Pan-Tompkins bandpass (Hz)
        notch_hz: float = 60.0,                   # power-line freq (Taiwan = 60 Hz)
        notch_q: float = 30.0,                    # notch Q (higher = narrower)
        refractory_ms: int = 250,                 # min distance between R-peaks
        integration_ms: int = 150,                # Pan-Tompkins MA window
        bpm_window: int = 10,                     # use last N RRs for BPM
        voltage_ref: float = 5.0,                 # ADC reference voltage
        adc_bits: int = 10,                       # Arduino UNO = 10-bit
    ):
        self.fs = sample_rate
        self.vref = voltage_ref
        self.adc_max = (1 << adc_bits) - 1
        self.refractory_samples = int(refractory_ms * sample_rate / 1000)
        self.bpm_window = bpm_window

        nyq = sample_rate / 2

        # Display-quality bandpass: 4th order Butterworth (SOS for numerical stability)
        self._display_sos = butter(
            4, [display_band[0] / nyq, display_band[1] / nyq],
            btype="band", output="sos"
        )

        # QRS-emphasizing bandpass for Pan-Tompkins
        self._qrs_sos = butter(
            2, [qrs_band[0] / nyq, qrs_band[1] / nyq],
            btype="band", output="sos"
        )

        # Power-line notch (IIR)
        self._notch_b, self._notch_a = iirnotch(notch_hz / nyq, notch_q)

        # Pan-Tompkins moving-average window (samples)
        self._pt_window = max(1, int(integration_ms * sample_rate / 1000))

        # QRS refinement: R-peak in raw signal sits near integrated peak
        self._refine_window = max(1, int(0.08 * sample_rate))  # +/- 80 ms

    # ------------------------------------------------------------
    def process(self, adc_values) -> ECGResult:
        """Process a batch of ADC samples. Returns an ECGResult."""
        adc = np.asarray(adc_values, dtype=np.float64)

        # Need >= 1 second for stable filter response
        if len(adc) < self.fs:
            return ECGResult(
                voltage=adc * self.vref / self.adc_max,
                filtered=np.zeros_like(adc),
                peaks=np.array([], dtype=int),
                bpm=None,
            )

        # ADC -> volts
        volts = adc * self.vref / self.adc_max

        # Notch 60 Hz -> bandpass for display (zero-phase via forward-backward)
        notched = filtfilt(self._notch_b, self._notch_a, volts)
        filtered = sosfiltfilt(self._display_sos, notched)

        # Pan-Tompkins R-peak detection
        peaks = self._detect_r_peaks(filtered)

        # BPM from RR intervals
        bpm, rr_ms = self._estimate_bpm(peaks)

        return ECGResult(
            voltage=volts,
            filtered=filtered,
            peaks=peaks,
            bpm=bpm,
            rr_intervals_ms=rr_ms,
        )

    # ------------------------------------------------------------
    def _detect_r_peaks(self, signal: np.ndarray) -> np.ndarray:
        """Pan-Tompkins simplified: BP -> diff -> square -> MA -> threshold + refine."""
        # 1) QRS bandpass (5-15 Hz emphasizes QRS energy)
        bp = sosfiltfilt(self._qrs_sos, signal)

        # 2) Derivative -- emphasizes the steep slope of the QRS
        diff = np.diff(bp, prepend=bp[0])

        # 3) Squaring -- non-linear amplification, all-positive
        squared = diff * diff

        # 4) Moving-window integration -- turns spike into broad envelope
        kernel = np.ones(self._pt_window) / self._pt_window
        integrated = np.convolve(squared, kernel, mode="same")

        # 5) Adaptive threshold: 40% of the 99th percentile of integrated.
        #    Percentile is outlier-robust (unlike mean + k*std).
        p99 = float(np.percentile(integrated, 99))
        if p99 <= 0:
            return np.array([], dtype=int)
        threshold = 0.4 * p99

        peaks_int, _ = find_peaks(
            integrated,
            height=threshold,
            distance=self.refractory_samples,
        )

        # 6) Refine: integration smears/delays the peak; search +/- 80 ms in the
        #    filtered signal for the actual R-peak (local max).
        refined = []
        n = len(signal)
        w = self._refine_window
        for p in peaks_int:
            lo = max(0, p - w)
            hi = min(n, p + w)
            if hi > lo:
                refined.append(lo + int(np.argmax(signal[lo:hi])))

        return np.array(refined, dtype=int)

    # ------------------------------------------------------------
    def _estimate_bpm(self, peaks: np.ndarray):
        """Median BPM from last N RR intervals. Returns (bpm_or_None, rr_ms_array)."""
        if len(peaks) < 2:
            return None, np.array([])

        recent = peaks[-self.bpm_window:] if len(peaks) > self.bpm_window else peaks
        rr_samples = np.diff(recent)
        rr_seconds = rr_samples / self.fs
        rr_ms = rr_seconds * 1000.0

        # Physiological range: 30-220 BPM -> RR 273 ms to 2000 ms
        valid = rr_seconds[(rr_seconds > 60.0 / 220) & (rr_seconds < 60.0 / 30)]
        if len(valid) == 0:
            return None, rr_ms

        bpm = 60.0 / float(np.median(valid))
        return bpm, rr_ms
