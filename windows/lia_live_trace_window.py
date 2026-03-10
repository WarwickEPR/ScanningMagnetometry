import time
import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

from threading_utils import ThreadedComponent
from ui_theme import apply_ui_polish


class LIALiveTraceWindow(QtWidgets.QWidget, ThreadedComponent):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.running = False
        self.max_points = 1000
        self.sample_interval = 0.05
        self.time_window_seconds = 20.0

        self._x_data = []
        self._y_data = []
        self._r_data = []
        self._time_data = []

        self._build_ui()
        apply_ui_polish(self)
        self.show()

    def _build_ui(self):
        self.setWindowTitle("LIA Live Demod Time Trace")
        self.resize(950, 700)

        root_layout = QtWidgets.QVBoxLayout(self)

        button_row = QtWidgets.QHBoxLayout()
        self.startButton = QtWidgets.QPushButton("Start")
        self.stopButton = QtWidgets.QPushButton("Stop")
        self.clearButton = QtWidgets.QPushButton("Clear")
        self.timeWindowLabel = QtWidgets.QLabel("Window (s)")
        self.timeWindowSpinBox = QtWidgets.QDoubleSpinBox()
        self.timeWindowSpinBox.setDecimals(1)
        self.timeWindowSpinBox.setMinimum(2.0)
        self.timeWindowSpinBox.setMaximum(600.0)
        self.timeWindowSpinBox.setSingleStep(1.0)
        self.timeWindowSpinBox.setValue(self.time_window_seconds)
        self.statusLabel = QtWidgets.QLabel("Idle")
        self.statusLabel.setMinimumWidth(220)

        button_row.addWidget(self.startButton)
        button_row.addWidget(self.stopButton)
        button_row.addWidget(self.clearButton)
        button_row.addSpacing(8)
        button_row.addWidget(self.timeWindowLabel)
        button_row.addWidget(self.timeWindowSpinBox)
        button_row.addStretch()
        button_row.addWidget(self.statusLabel)

        self.plotX = pg.PlotWidget()
        self.plotY = pg.PlotWidget()
        self.plotR = pg.PlotWidget()

        self.plotX.setLabel("left", "Demod X (V)")
        self.plotY.setLabel("left", "Demod Y (V)")
        self.plotR.setLabel("left", "Demod R (V)")
        self.plotR.setLabel("bottom", "Time (s)")
        self.plotY.setXLink(self.plotX)
        self.plotR.setXLink(self.plotX)

        self.curveX = self.plotX.plot(pen=pg.mkPen("c", width=2))
        self.curveY = self.plotY.plot(pen=pg.mkPen("m", width=2))
        self.curveR = self.plotR.plot(pen=pg.mkPen("y", width=2))

        root_layout.addLayout(button_row)
        root_layout.addWidget(self.plotX)
        root_layout.addWidget(self.plotY)
        root_layout.addWidget(self.plotR)

        self.startButton.clicked.connect(self.start_stream)
        self.stopButton.clicked.connect(self.stop_stream)
        self.clearButton.clicked.connect(self.clear_data)
        self.timeWindowSpinBox.valueChanged.connect(self._on_time_window_changed)

        self.stopButton.setEnabled(False)

    def clear_data(self):
        self._x_data.clear()
        self._y_data.clear()
        self._r_data.clear()
        self._time_data.clear()
        self._update_curves()

    def _on_time_window_changed(self, value):
        self.time_window_seconds = float(value)
        self._update_curves()

    def start_stream(self):
        if self.running:
            return
        if not self.main_window.LIAController.LIA_connected:
            error_dialog = QtWidgets.QErrorMessage(self)
            error_dialog.showMessage("LIA is not connected.")
            return
        if self.main_window.rfController.sweeping:
            error_dialog = QtWidgets.QErrorMessage(self)
            error_dialog.showMessage("Cannot start live trace while ODMR sweep is running.")
            return
        if self.main_window.scan_window is not None and getattr(self.main_window.scan_window, "scanning", False):
            error_dialog = QtWidgets.QErrorMessage(self)
            error_dialog.showMessage("Cannot start live trace while scan is running.")
            return

        self.running = True
        self.startButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self.statusLabel.setText("Streaming...")

        self.thread_function(
            self._stream_loop,
            prg_fn=self._on_stream_data,
            err_fn=self.main_window.show_error_message,
            fin_fn=self._on_stream_finished,
        )

    def stop_stream(self):
        self.running = False
        self.statusLabel.setText("Stopping...")

    def _on_stream_finished(self, *_):
        self.running = False
        self.startButton.setEnabled(True)
        self.stopButton.setEnabled(False)
        self.statusLabel.setText("Idle")

    def _stream_loop(self, *args, **kwargs):
        lia = self.main_window.LIAController
        sample_path = f"/{lia.device}/demods/0/sample"
        t0 = time.monotonic()
        last_emit = 0.0

        while self.running:
            if self.main_window.rfController.sweeping:
                break
            if self.main_window.scan_window is not None and getattr(self.main_window.scan_window, "scanning", False):
                break

            sample = lia.daq.getSample(sample_path)
            x_val = float(sample["x"][0])
            y_val = float(sample["y"][0])
            r_val = float(np.sqrt((x_val ** 2) + (y_val ** 2)))
            t_val = time.monotonic() - t0

            self._x_data.append(x_val)
            self._y_data.append(y_val)
            self._r_data.append(r_val)
            self._time_data.append(t_val)

            max_buffer_points = max(
                1000,
                int((self.time_window_seconds / self.sample_interval) * 5),
            )
            self.max_points = max_buffer_points
            if len(self._time_data) > self.max_points:
                self._time_data.pop(0)
                self._x_data.pop(0)
                self._y_data.pop(0)
                self._r_data.pop(0)

            now = time.monotonic()
            if now - last_emit >= 0.05:
                kwargs["progress_callback"].emit(None)
                last_emit = now

            time.sleep(self.sample_interval)

    def _on_stream_data(self, _):
        self._update_curves()

    def _update_curves(self):
        if len(self._time_data) == 0:
            self.curveX.setData([], [])
            self.curveY.setData([], [])
            self.curveR.setData([], [])
            return

        t_end = self._time_data[-1]
        t_start = max(0.0, t_end - self.time_window_seconds)
        start_idx = int(np.searchsorted(self._time_data, t_start, side="left"))

        time_view = self._time_data[start_idx:]
        x_view = self._x_data[start_idx:]
        y_view = self._y_data[start_idx:]
        r_view = self._r_data[start_idx:]

        self.curveX.setData(time_view, x_view)
        self.curveY.setData(time_view, y_view)
        self.curveR.setData(time_view, r_view)
        self.plotX.setXRange(t_start, max(t_start + 0.01, t_end), padding=0.0)

    def closeEvent(self, event):
        self.stop_stream()
        event.accept()
