import time
import traceback
import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets, uic

from threading_utils import ThreadedComponent
from paths import ui_file
from ui_theme import apply_ui_polish
from analysis.odmr_fit import compute_odmr_linear_regions


class ODMRGraphWindow(QtWidgets.QWidget, ThreadedComponent):
    def __init__(self, main_window, *args, **kwargs):
        super(ODMRGraphWindow, self).__init__(*args, **kwargs)
        self.main_window = main_window

        uic.loadUi(ui_file("ODMRGraphWindow.ui"), self)
        apply_ui_polish(self)
        self.show()

        self.p1 = self.graphWidget.plotItem
        self.p1.setLabels(left="Voltage (V)")
        self.p1.setLabels(bottom="Frequency (GHz)")

        self.p2 = pg.ViewBox()
        self.p1.showAxis("right")
        self.p1.scene().addItem(self.p2)
        self.p1.getAxis("right").linkToView(self.p2)
        self.p2.setXLink(self.p1)
        self.p1.getAxis("right").setLabel("dV/df (V/MHz)", color="#0000ff")
        self.p1.vb.sigResized.connect(self.updateViews)

        self.odmr_plot = None
        self.odmr_deriv_plot = None
        self.odmr_linear_region_plot = None
        self.linear_region_list = None
        self.worker_running = False
        self.x = None
        self.y = None
        self._hovered_linear_row = None
        self._linear_region_default_pen = pg.mkPen(color=(255, 0, 0), width=5)
        self._linear_region_hover_pen = pg.mkPen(color=(255, 215, 0), width=7)

        self.linearRegionTable.setMouseTracking(True)
        self.linearRegionTable.viewport().setMouseTracking(True)
        self.linearRegionTable.cellEntered.connect(self.on_linear_region_table_hover)
        self.linearRegionTable.viewport().installEventFilter(self)

        self.odmrRegionFitBox.valueChanged.connect(self._fit_from_ui)
        self.showDerivativeCheckbox.stateChanged.connect(self._fit_from_ui)
        self.smoothingCheckBox.stateChanged.connect(self._fit_from_ui)
        self.polyorderSpinBox.valueChanged.connect(self._fit_from_ui)
        self.smoothWindowBox.valueChanged.connect(self._fit_from_ui)
        self.peakHeightSpinBox.valueChanged.connect(self._fit_from_ui)
        self.peakDistanceSpinBox.valueChanged.connect(self._fit_from_ui)
        self.peakPromSpinBox.valueChanged.connect(self._fit_from_ui)

        self.setODMRButton.clicked.connect(self.send_to_scan_table)
        self.autoFitButton.clicked.connect(self.run_auto_fit)
        self.stopSweepButton.clicked.connect(self.stop_odmr_sweep)

        self.thread_function(
            self.main_window.rfController.setup_sweep,
            self.main_window.startFreqBox.value(),
            self.main_window.endFreqBox.value(),
            self.main_window.pointsBox.value(),
            self.main_window.dwellTimeBox.value(),
            self.main_window.stepSizeBox.value(),
            self.main_window.odmrSweepContinous.isChecked(),
            fin_fn=self.execute_this_function,
            prg_fn=self.progress_fn,
            err_fn=self.main_window.show_error_message,
            progress_callback=None,
        )

    def _fit_from_ui(self):
        self.fit_linear_region(
            self.x,
            self.y,
            self.odmrRegionFitBox.value(),
            plot_derivative=self.showDerivativeCheckbox.isChecked(),
            denoise=self.smoothingCheckBox.isChecked(),
            window_length=self.smoothWindowBox.value(),
            polyorder=self.polyorderSpinBox.value(),
            peak_height=self.peakHeightSpinBox.value(),
            peak_distance=self.peakDistanceSpinBox.value(),
            peak_prom=self.peakPromSpinBox.value(),
        )

    def execute_this_function(self, *args, **kwargs):
        self.main_window.takeODMRButton.setEnabled(True)
        self.worker_running = False
        self.y = self.main_window.rfController.samples

        self.x = np.linspace(
            self.main_window.rfController.start_freq,
            self.main_window.rfController.stop_freq,
            self.main_window.rfController.num_points,
        )
        self.x = self.x[0 : len(self.y)]
        self.dummy_data(self.x, self.y)
        if self.autoFitAfterSweepCheckBox.isChecked():
            self.run_auto_fit()

    def progress_fn(self, results):
        self.y = results
        self.x = np.linspace(
            self.main_window.rfController.start_freq,
            self.main_window.rfController.stop_freq,
            self.main_window.rfController.num_points,
        )
        self.x = self.x[0 : len(self.y)]
        self.dummy_data(self.x, self.y)

    def run_auto_fit(self):
        if self.main_window.rfController.sweeping:
            return
        if self.x is None or self.y is None or len(self.y) < 7:
            return
        self.fit_linear_region(
            self.x,
            self.y,
            self.odmrRegionFitBox.value(),
            plot_derivative=self.showDerivativeCheckbox.isChecked(),
            denoise=self.smoothingCheckBox.isChecked(),
            window_length=self.smoothWindowBox.value(),
            polyorder=self.polyorderSpinBox.value(),
            peak_height=0,
            peak_distance=0,
            peak_prom=0,
            force=True,
        )

    def closeEvent(self, event):
        self.main_window.rfController.sweeping = False
        self.worker_running = False

    def stop_odmr_sweep(self):
        self.worker_running = False

    def updateViews(self):
        self.p2.setGeometry(self.p1.vb.sceneBoundingRect())
        self.p2.linkedViewChanged(self.p1.vb, self.p2.XAxis)

    def eventFilter(self, obj, event):
        if obj is self.linearRegionTable.viewport() and event.type() == QtCore.QEvent.Type.Leave:
            self.clear_linear_region_hover()
        return super().eventFilter(obj, event)

    def clear_linear_region_hover(self):
        if self._hovered_linear_row is None:
            return
        row = self._hovered_linear_row
        if self.linear_region_list is not None and 0 <= row < len(self.linear_region_list):
            self.linear_region_list[row].setPen(self._linear_region_default_pen)
        self._hovered_linear_row = None

    def on_linear_region_table_hover(self, row, _column):
        if self.linear_region_list is None or row < 0 or row >= len(self.linear_region_list):
            self.clear_linear_region_hover()
            return
        if self._hovered_linear_row == row:
            return
        self.clear_linear_region_hover()
        self.linear_region_list[row].setPen(self._linear_region_hover_pen)
        self._hovered_linear_row = row

    def dummy_data(self, x, y):
        try:
            self.odmr_plot.clear()
        except:
            pass
        pen = pg.mkPen(style=QtCore.Qt.PenStyle.DashLine)
        self.odmr_plot = self.graphWidget.plot(x, y, pen=pen)
        self.updateViews()

    def fit_linear_region(
        self,
        x,
        y,
        linear_region_width=50,
        window_length=50,
        polyorder=3,
        peak_height=-5,
        peak_distance=100,
        peak_prom=5,
        plot_derivative=False,
        denoise=False,
        force=False,
    ):
        try:
            if self.main_window.rfController.sweeping and not force:
                return
            if x is None or y is None:
                return

            fit_result = compute_odmr_linear_regions(
                x=x,
                y=y,
                linear_region_width=linear_region_width,
                window_length=window_length,
                polyorder=polyorder,
                peak_height=peak_height,
                peak_distance=peak_distance,
                peak_prom=peak_prom,
                denoise=denoise,
                use_positive_gradients=self.usePositiveGradientsCheckBox.isChecked(),
            )
            if fit_result is None:
                return

            y_for_fit = fit_result["y_for_fit"]
            derivative = fit_result["derivative"]
            regions = fit_result["regions"]
            prominences = fit_result["prominences"]

            try:
                self.odmr_plot.clear()
                self.dummy_data(fit_result["x"], y_for_fit)
            except:
                self.dummy_data(fit_result["x"], y_for_fit)

            try:
                for line in self.linear_region_list:
                    line.clear()
            except:
                pass

            self.linear_region_list = []
            self.linearRegionTable.setRowCount(0)
            auto_selected_rows = []

            for row_idx, region in enumerate(regions):
                self.odmr_linear_region_plot = self.graphWidget.plot(
                    region["x_linear"], region["predicted"], pen=self._linear_region_default_pen
                )
                self.linear_region_list.append(self.odmr_linear_region_plot)

                self.linearRegionTable.insertRow(row_idx)
                self.linearRegionTable.setItem(
                    row_idx,
                    0,
                    QtWidgets.QTableWidgetItem(str(round(region["center_freq"], 9))),
                )
                self.linearRegionTable.setItem(
                    row_idx,
                    1,
                    QtWidgets.QTableWidgetItem(str(round(region["slope"], 9))),
                )

                checkbox = QtWidgets.QCheckBox()
                prominence_threshold = 0.5 * float(np.median(prominences)) if len(prominences) > 0 else 0
                auto_select = bool(
                    (region["prominence"] >= prominence_threshold) and (region["r_squared"] >= 0.75)
                )
                checkbox.setChecked(auto_select)
                if auto_select:
                    auto_selected_rows.append(row_idx)
                checkbox.setToolTip(
                    f"Prominence: {region['prominence']:.3e}\nR²: {region['r_squared']:.3f}\nAuto-selected: {auto_select}"
                )
                self.linearRegionTable.setCellWidget(row_idx, 2, checkbox)

            self.clear_linear_region_hover()

            if self.linearRegionTable.rowCount() > 0 and len(auto_selected_rows) == 0:
                strongest_row = int(np.argmax(prominences)) if len(prominences) > 0 else 0
                strongest_row = min(strongest_row, self.linearRegionTable.rowCount() - 1)
                self.linearRegionTable.cellWidget(strongest_row, 2).setChecked(True)

            if plot_derivative:
                try:
                    self.p2.removeItem(self.odmr_deriv_plot)
                except:
                    pass
                pen = pg.mkPen(color=(0, 255, 0), style=QtCore.Qt.PenStyle.DashDotLine)
                self.odmr_deriv_plot = pg.PlotCurveItem(fit_result["x"], derivative, pen=pen)
                self.p2.addItem(self.odmr_deriv_plot)
            else:
                try:
                    self.p2.removeItem(self.odmr_deriv_plot)
                except:
                    pass

        except Exception:
            print(traceback.format_exc())

        self.updateViews()

    def send_to_scan_table(self):
        freqs = []
        grads = []
        for row in range(self.linearRegionTable.rowCount()):
            if self.linearRegionTable.cellWidget(row, 2).isChecked():
                freqs.append(float(self.linearRegionTable.item(row, 0).text()))
                grads.append(float(self.linearRegionTable.item(row, 1).text()))

        self.main_window.scanODMRPropertiesTable.setRowCount(0)
        for row in range(len(freqs)):
            self.main_window.scanODMRPropertiesTable.insertRow(row)
            self.main_window.scanODMRPropertiesTable.setItem(
                row, 0, QtWidgets.QTableWidgetItem(str(round(freqs[row], 3)))
            )
            self.main_window.scanODMRPropertiesTable.setItem(
                row, 1, QtWidgets.QTableWidgetItem(str(round(grads[row], 3)))
            )
