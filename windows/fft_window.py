import numpy as np
from PyQt6 import QtWidgets, uic

from threading_utils import ThreadedComponent
from paths import ui_file
from ui_theme import apply_ui_polish


class FFTGraphWindow(QtWidgets.QWidget, ThreadedComponent):
    """Opens a new window with a log-log graph showing the FFTs taken from the LIA."""

    def __init__(self, main_window):
        super().__init__()
        super(FFTGraphWindow, self).__init__()
        self.main_window = main_window
        uic.loadUi(ui_file("FFTGraphWindow.ui"), self)
        apply_ui_polish(self)
        self.show()
        self.samples = None
        self.fft_plot = None
        self.x = None
        self.y = None
        self.scaled_y = None
        self.calib_const = 1

        self.graphWidget.setLabel(axis="left", text="Power Spectral Density nT/sqrt(Hz)")
        self.graphWidget.setLabel(axis="bottom", text="Frequency Hz")

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

        self.odmrGradientSpinBox.valueChanged.connect(
            lambda: self.dummy_data(calib_const=self.odmrGradientSpinBox.value())
        )

        self.thread_function(self.take_fft, progress_callback=None)

    def take_fft(self, *args, **kwargs):
        self.worker_running = True
        self.main_window.LIAController.fft_sweep = True
        self.main_window.LIAController.setup_fft()
        self.main_window.LIAController.daq_module.execute()
        self.samples = []

        while not self.main_window.LIAController.daq_module.finished():
            data_read = self.main_window.LIAController.daq_module.read(True)
            returned_signal_paths = [signal_path.lower() for signal_path in data_read.keys()]
            for signal_path in self.main_window.LIAController.signal_paths:
                if signal_path.lower() in returned_signal_paths:
                    for signal_burst in data_read[signal_path.lower()]:
                        self.samples.append(signal_burst["value"][0])
                        self.main_window.LIAController.data[signal_path].append(signal_burst)

        self.main_window.LIAController.daq_module.finish()
        self.main_window.LIAController.daq_module.unsubscribe("*")

        self.worker_running = False
        avg_sample = (
            (np.sum(self.samples, axis=0)) / self.main_window.LIAController.count
        ) * self.main_window.LIAController.scaling_Factor
        bin_count = len(avg_sample)
        frequencies = np.arange(0, bin_count)
        amplitude_spectral_density = (avg_sample * np.sqrt(self.main_window.LIAController.fft_duration)) * (
            1 / (28e-6 * self.calib_const)
        )
        self.y = amplitude_spectral_density
        self.scaled_y = self.y
        self.x = frequencies
        self.dummy_data(calib_const=self.calib_const)
        self.main_window.LIAController.fft_sweep = False

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
        self.calib_const = float(self.odmrGradientSpinBox.value())
        if ignore_freqs:
            ignore_freqs_range_idxs = []

            idx_min_start = np.abs(self.x - freq_start).argmin()
            idx_max_end = np.abs(self.x - freq_end).argmin()

            top_end = np.arange(0, idx_min_start + 1, 1, dtype=int)
            for i in range(len(top_end)):
                ignore_freqs_range_idxs.append(top_end[i])

            tail_end = np.arange(idx_max_end + 1, len(self.x), 1, dtype=int)
            for row in range(self.ignoreFrequencyList.rowCount()):
                try:
                    ignore_min_freq = int(self.ignoreFrequencyList.item(row, 0).text())
                    ignore_max_freq = int(self.ignoreFrequencyList.item(row, 1).text())
                    idx_min = np.abs(self.x - ignore_min_freq).argmin()
                    idx_max = (np.abs(self.x - ignore_max_freq)).argmin()
                    idx_range = np.arange(idx_min, idx_max + 1, 1, dtype=int)
                    for i in range(len(idx_range)):
                        ignore_freqs_range_idxs.append(idx_range[i])
                except Exception as error:
                    print(error, "This is probably fine if its a text error")

            for i in range(len(tail_end)):
                ignore_freqs_range_idxs.append(tail_end[i])

            mask = np.ones_like(self.x, dtype=bool)
            mask[ignore_freqs_range_idxs] = False
            mean_sens = round(np.mean(self.scaled_y[mask]), 4)
            self.meanSensLabel.setText(str(mean_sens))
        else:
            mean_sens = round(np.mean(self.scaled_y), 4)
            self.meanSensLabel.setText(str(mean_sens))

    def dummy_data(self, calib_const=1):
        self.scaled_y = self.y
        try:
            self.fft_plot.clear()
        except Exception:
            pass
        self.fft_plot = self.graphWidget.plot(self.x, self.scaled_y)
        self.graphWidget.setLogMode(True, True)
