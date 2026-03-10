import time
import numpy as np
from PyQt6 import QtCore, QtWidgets, uic

from threading_utils import ThreadedComponent
from paths import ui_file
from ui_theme import apply_ui_polish


class FFTGraphWindow(QtWidgets.QWidget, ThreadedComponent):
    """Opens a new window with a log-log graph showing the FFTs taken from the LIA."""

    def __init__(self, main_window):
        super().__init__()
        super(FFTGraphWindow, self).__init__()
        self.main_window = main_window
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        uic.loadUi(ui_file("FFTGraphWindow.ui"), self)
        apply_ui_polish(self)
        self.show()
        self.samples = None
        self.fft_plot = None
        self.x = None
        self.raw_asd = None
        self.calibrated_asd = None
        self.calib_const = 1
        self.bin_resolution_hz = 1.0
        self.worker_running = False
        self._cancel_requested = False

        self.graphWidget.setLabel(axis="left", text="Power Spectral Density nT/sqrt(Hz)")
        self.graphWidget.setLabel(axis="bottom", text="Frequency Hz")

        self.fftProgressLabel = QtWidgets.QLabel("FFT Status: Idle")
        self.fftProgressLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.verticalLayout.addWidget(self.fftProgressLabel)

        self.calcSensButton.clicked.connect(
            lambda: self.calc_sens(
                freq_start=self.minFreqSpinBox.value(),
                freq_end=self.maxFreqSpinBox.value(),
                ignore_freqs=self.ignoreListFreqCheckBox.isChecked(),
            )
        )

        self.addFreqButton.clicked.connect(
            lambda: self.add_ignore_freq(
                self.freqStartSpinBox.value(), self.freqEndSpinBox.value()
            )
        )

        self.odmrGradientSpinBox.editingFinished.connect(self.update_plot_with_calibration)

        self.thread_function(self.take_fft, prg_fn=self._on_fft_progress, progress_callback=None)

    def stop_fft(self):
        self._cancel_requested = True
        self.fftProgressLabel.setText("FFT Status: Stopping...")
        daq_module = getattr(self.main_window.LIAController, "daq_module", None)
        if daq_module is not None:
            try:
                daq_module.finish()
            except Exception:
                pass
            try:
                daq_module.unsubscribe("*")
            except Exception:
                pass

    def take_fft(self, *args, **kwargs):
        self._cancel_requested = False
        self.worker_running = True
        self.main_window.LIAController.fft_sweep = True
        target_count = max(1, int(self.main_window.fftAverageSpinBox.value()))
        kwargs["progress_callback"].emit((0, target_count))
        self.samples = []
        grid_delta_values = []
        last_emit = 0.0
        cancelled = False

        try:
            self.main_window.LIAController.setup_fft()
            self.main_window.LIAController.daq_module.execute()

            while not self.main_window.LIAController.daq_module.finished():
                if self._cancel_requested:
                    cancelled = True
                    break

                data_read = self.main_window.LIAController.daq_module.read(True)
                returned_signal_paths = [signal_path.lower() for signal_path in data_read.keys()]
                for signal_path in self.main_window.LIAController.signal_paths:
                    if signal_path.lower() in returned_signal_paths:
                        for signal_burst in data_read[signal_path.lower()]:
                            self.samples.append(signal_burst["value"][0])
                            try:
                                grid_delta_values.append(float(signal_burst["header"]["gridcoldelta"]))
                            except Exception:
                                pass
                            self.main_window.LIAController.data[signal_path].append(signal_burst)
                            now = time.monotonic()
                            if now - last_emit >= 0.1:
                                kwargs["progress_callback"].emit((min(len(self.samples), target_count), target_count))
                                last_emit = now
        finally:
            daq_module = getattr(self.main_window.LIAController, "daq_module", None)
            if daq_module is not None:
                try:
                    daq_module.finish()
                except Exception:
                    pass
                try:
                    daq_module.unsubscribe("*")
                except Exception:
                    pass

            self.worker_running = False
            self.main_window.LIAController.fft_sweep = False

        if cancelled:
            kwargs["progress_callback"].emit({"state": "cancelled"})
            return

        if len(self.samples) == 0:
            kwargs["progress_callback"].emit((0, target_count))
            return

        sample_stack = np.asarray(self.samples, dtype=float)
        if sample_stack.ndim == 1:
            sample_stack = sample_stack.reshape(1, -1)

        avg_sample = np.mean(sample_stack, axis=0) * self.main_window.LIAController.scaling_Factor
        raw_asd = avg_sample * np.sqrt(self.main_window.LIAController.fft_duration)

        if len(grid_delta_values) > 0:
            bin_resolution_hz = float(np.median(grid_delta_values))
        else:
            sample_rate = float(self.main_window.sampleRateSpinBox.value())
            bin_resolution_hz = sample_rate / max(1, len(raw_asd))

        x_data = np.arange(len(raw_asd), dtype=float) * bin_resolution_hz
        kwargs["progress_callback"].emit(
            {
                "state": "result",
                "raw_asd": raw_asd,
                "x": x_data,
                "bin_resolution_hz": bin_resolution_hz,
            }
        )
        kwargs["progress_callback"].emit((target_count, target_count))

    def _on_fft_progress(self, payload):
        if isinstance(payload, dict):
            state = payload.get("state")
            if state == "cancelled":
                self.fftProgressLabel.setText("FFT Status: Cancelled")
                return
            if state == "result":
                self.raw_asd = payload.get("raw_asd")
                self.x = payload.get("x")
                self.bin_resolution_hz = float(payload.get("bin_resolution_hz", 1.0))
                self.update_plot_with_calibration()
                return
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        completed, total = payload
        completed = int(completed)
        total = int(total)
        if total <= 0:
            self.fftProgressLabel.setText("FFT Status: Idle")
            return
        if completed >= total:
            self.fftProgressLabel.setText(f"FFT Status: Complete ({total}/{total})")
        else:
            self.fftProgressLabel.setText(f"FFT Status: Running ({completed}/{total})")

    def add_ignore_freq(self, freq_start, freq_end):
        row_pos = self.ignoreFrequencyList.rowCount()
        self.ignoreFrequencyList.insertRow(row_pos)
        self.ignoreFrequencyList.setItem(
            row_pos, 0, QtWidgets.QTableWidgetItem(str(freq_start))
        )
        self.ignoreFrequencyList.setItem(
            row_pos, 1, QtWidgets.QTableWidgetItem(str(freq_end))
        )

    def calc_sens(self, freq_start=10, freq_end=100, ignore_freqs=False):
        if self.raw_asd is None or self.x is None or len(self.x) == 0:
            self.meanSensLabel.setText("--")
            return

        self.calib_const = float(self.odmrGradientSpinBox.value())
        if self.calib_const <= 0:
            self.meanSensLabel.setText("--")
            return

        self.calibrated_asd = self.raw_asd * (1 / (28e-6 * self.calib_const))
        self.dummy_data()

        f0 = float(min(freq_start, freq_end))
        f1 = float(max(freq_start, freq_end))
        mask = (self.x >= f0) & (self.x <= f1)

        if ignore_freqs:
            for row in range(self.ignoreFrequencyList.rowCount()):
                try:
                    ignore_min_freq = float(self.ignoreFrequencyList.item(row, 0).text())
                    ignore_max_freq = float(self.ignoreFrequencyList.item(row, 1).text())
                    lo = min(ignore_min_freq, ignore_max_freq)
                    hi = max(ignore_min_freq, ignore_max_freq)
                    mask &= ~((self.x >= lo) & (self.x <= hi))
                except Exception as error:
                    print(error, "This is probably fine if its a text error")

        if not np.any(mask):
            self.meanSensLabel.setText("--")
            return

        mean_sens = round(float(np.mean(self.calibrated_asd[mask])), 4)
        self.meanSensLabel.setText(str(mean_sens))

    def update_plot_with_calibration(self):
        if self.raw_asd is None:
            return
        self.calib_const = float(self.odmrGradientSpinBox.value())
        if self.calib_const > 0:
            self.calibrated_asd = self.raw_asd * (1 / (28e-6 * self.calib_const))
        else:
            self.calibrated_asd = self.raw_asd
        self.dummy_data()

    def dummy_data(self):
        if self.x is None or self.calibrated_asd is None:
            return
        try:
            self.fft_plot.clear()
        except Exception:
            pass
        self.fft_plot = self.graphWidget.plot(self.x, self.calibrated_asd)
        self.graphWidget.setLogMode(True, True)

    def closeEvent(self, event):
        if self.worker_running:
            self.stop_fft()
        if getattr(self.main_window, "fft_graph_window", None) is self:
            self.main_window.fft_graph_window = None
        event.accept()
