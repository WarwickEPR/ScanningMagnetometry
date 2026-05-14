import time
import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets
from sklearn.linear_model import LinearRegression

from analysis.odmr_fit_colin import ODMR_Fit
from threading_utils import ThreadedComponent
from ui_theme import (
    PLOT_BACKGROUND,
    PLOT_FOREGROUND,
    configure_pyqtgraph_defaults,
    get_plot_pen,
    style_plot_labels,
    style_plot_widget,
)
from windows.odmr_window_ui import ODMRWindowUIBuilder


class ODMRGraphWindow(QtWidgets.QWidget, ThreadedComponent):
    def __init__(self, main_window, *args, **kwargs):
        super(ODMRGraphWindow, self).__init__(*args, **kwargs)
        self.main_window = main_window

        configure_pyqtgraph_defaults()
        ODMRWindowUIBuilder().setup(self)
        self.show()

        style_plot_widget(self.graphWidget)
        self.p1 = self.graphWidget.plotItem
        style_plot_labels(self.graphWidget, left="Voltage (V)", bottom="Frequency (GHz)")

        self.p2 = pg.ViewBox()
        self.p1.showAxis("right")
        self.p1.scene().addItem(self.p2)
        self.p1.getAxis("right").linkToView(self.p2)
        self.p2.setXLink(self.p1)
        self.p2.setBackgroundColor(PLOT_BACKGROUND)
        right_axis = self.p1.getAxis("right")
        right_axis.setPen(pg.mkPen(PLOT_FOREGROUND, width=1))
        right_axis.setTextPen(pg.mkPen(PLOT_FOREGROUND, width=1))
        right_axis.setTickPen(pg.mkPen(PLOT_FOREGROUND, width=1))
        right_axis.setLabel("dV/df (V/MHz)", color=PLOT_FOREGROUND)
        self.p1.vb.sigResized.connect(self.updateViews)

        self.odmr_plot = None
        self.odmr_fit_plot = None
        self.odmr_deriv_plot = None
        self.odmr_linear_region_plot = None
        self.linear_region_list = None
        self.worker_running = False
        self.x = None
        self.y = None
        self._selection_mode_active = False
        self._selected_indices = []
        self._hovered_linear_row = None
        self._linear_region_default_pen = get_plot_pen(3, width=4)
        self._linear_region_hover_pen = get_plot_pen(6, width=6)

        self.linearRegionTable.setMouseTracking(True)
        self.linearRegionTable.viewport().setMouseTracking(True)
        self.linearRegionTable.cellEntered.connect(self.on_linear_region_table_hover)
        self.linearRegionTable.viewport().installEventFilter(self)

        self.setODMRButton.clicked.connect(self.send_to_scan_table)
        self.autoFitButton.setText("Auto Fit Regions")
        self.autoFitButton.clicked.connect(self.auto_fit_linear_regions)
        self.autoFitButton.setEnabled(False)
        self.autoFitAfterSweepCheckBox.hide()
        self._hide_legacy_auto_fit_controls()
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

    def _get_frequency_axis_for_len(self, target_len):
        axis = getattr(self.main_window.rfController, "frequency_axis", None)
        if axis is None or len(axis) == 0:
            points = max(2, int(getattr(self.main_window.rfController, "num_points", 2)))
            axis = np.linspace(
                self.main_window.rfController.start_freq,
                self.main_window.rfController.stop_freq,
                points,
            )
        if target_len <= len(axis):
            return axis[:target_len]
        # If data count exceeds current axis estimate, stretch to data length as fallback.
        return np.linspace(
            self.main_window.rfController.start_freq,
            self.main_window.rfController.stop_freq,
            target_len,
        )

    def execute_this_function(self, *args, **kwargs):
        self.main_window.takeODMRButton.setEnabled(True)
        self.worker_running = False
        self.y = self.main_window.rfController.samples

        self.x = self._get_frequency_axis_for_len(len(self.y))
        self.dummy_data(self.x, self.y)
        self.autoFitButton.setEnabled(len(self.x) >= 3)
        self._selection_mode_active = False
        self._selected_indices = []
        self.autoFitButton.setText("Auto Fit Regions")

    def progress_fn(self, results):
        self.y = results
        self.x = self._get_frequency_axis_for_len(len(self.y))
        self.dummy_data(self.x, self.y)
        self.autoFitButton.setEnabled(False)

    def auto_fit_linear_regions(self):
        if self.main_window.rfController.sweeping:
            return
        if self.x is None or self.y is None or len(self.x) < 3:
            return

        self.autoFitButton.setEnabled(False)
        self.autoFitButton.setText("Fitting...")
        QtWidgets.QApplication.processEvents()

        try:
            fitter = ODMR_Fit(np.asarray(self.x, dtype=float), np.asarray(self.y, dtype=float))
            resonance_frequency = fitter.find_resonances()
        except Exception as exc:
            self.autoFitButton.setText("Auto Fit Regions")
            self.autoFitButton.setEnabled(True)
            self.main_window.show_error_message(str(exc))
            return

        self._clear_linear_regions()

        if resonance_frequency is None or len(resonance_frequency) == 0:
            self.autoFitButton.setText("Auto Fit Regions")
            self.autoFitButton.setEnabled(True)
            QtWidgets.QMessageBox.information(
                self,
                "ODMR Auto Fit",
                "No resonances were detected in the current sweep.",
            )
            return

        n_added = 0
        for i, center_freq in enumerate(resonance_frequency):
            if not np.isfinite(center_freq):
                continue

            slope = float(fitter.resonance_slope[i])
            if not np.isfinite(slope):
                continue

            interval, fit_line = fitter.fitted_slope(i)
            interval = np.asarray(interval, dtype=float)
            fit_line = np.asarray(fit_line, dtype=float)
            if len(interval) < 3 or len(interval) != len(fit_line):
                continue

            row_idx = self.linearRegionTable.rowCount()
            self.linearRegionTable.insertRow(row_idx)
            self.linearRegionTable.setItem(
                row_idx,
                0,
                QtWidgets.QTableWidgetItem(str(round(float(center_freq), 9))),
            )
            self.linearRegionTable.setItem(
                row_idx,
                1,
                QtWidgets.QTableWidgetItem(str(round(slope, 9))),
            )
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(True)
            self.linearRegionTable.setCellWidget(row_idx, 2, checkbox)

            delete_button = QtWidgets.QPushButton("X")
            delete_button.setToolTip("Delete this fit")
            delete_button.setMaximumWidth(26)
            delete_button.clicked.connect(self._on_delete_linear_region_clicked)
            self.linearRegionTable.setCellWidget(row_idx, 3, delete_button)

            if self.linear_region_list is None:
                self.linear_region_list = []
            line_plot = self.graphWidget.plot(
                interval,
                fit_line,
                pen=self._linear_region_default_pen,
            )
            self.linear_region_list.append(line_plot)
            n_added += 1

        self.autoFitButton.setText("Auto Fit Regions")
        self.autoFitButton.setEnabled(True)

        if n_added == 0:
            QtWidgets.QMessageBox.information(
                self,
                "ODMR Auto Fit",
                "Detected resonances could not be converted into valid linear regions.",
            )

    def _clear_linear_regions(self):
        if self.linear_region_list is not None:
            for line_plot in self.linear_region_list:
                try:
                    self.graphWidget.removeItem(line_plot)
                except Exception:
                    try:
                        line_plot.clear()
                    except Exception:
                        pass
            self.linear_region_list = []

        self.linearRegionTable.setRowCount(0)
        self._hovered_linear_row = None

    def _hide_legacy_auto_fit_controls(self):
        legacy_widgets = [
            self.odmrRegionFitBox,
            self.showDerivativeCheckbox,
            self.smoothingCheckBox,
            self.polyorderSpinBox,
            self.smoothWindowBox,
            self.peakHeightSpinBox,
            self.peakDistanceSpinBox,
            self.peakPromSpinBox,
            self.usePositiveGradientsCheckBox,
        ]

        for widget_name in [
            "label",
            "label_2",
            "label_4",
            "label_5",
            "label_6",
            "label_7",
        ]:
            widget = getattr(self, widget_name, None)
            if widget is not None:
                legacy_widgets.append(widget)

        for widget in legacy_widgets:
            try:
                widget.hide()
            except Exception:
                pass

    def _on_plot_mouse_clicked(self, event):
        if not self._selection_mode_active:
            return
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        if self.x is None or self.y is None or len(self.x) < 3:
            self._selection_mode_active = False
            self.autoFitButton.setText("Select Linear Region")
            return

        view_pos = self.p1.vb.mapSceneToView(event.scenePos())
        clicked_x = float(view_pos.x())
        clicked_idx = int(np.argmin(np.abs(self.x - clicked_x)))
        self._selected_indices.append(clicked_idx)

        if len(self._selected_indices) == 1:
            self.autoFitButton.setText("Click second point...")
            return

        idx_start = min(self._selected_indices[0], self._selected_indices[1])
        idx_end = max(self._selected_indices[0], self._selected_indices[1])

        self._selection_mode_active = False
        self._selected_indices = []
        self.autoFitButton.setText("Select Linear Region")
        self._fit_manual_region(idx_start, idx_end)

    def _fit_from_center_click(self, center_idx):
        """Fit using nearest local max/min tips around the clicked center."""
        if self.x is None or self.y is None:
            return
        n = len(self.y)
        if n < 4:
            return

        y = np.asarray(self.y, dtype=float)

        # Light smoothing avoids noise-induced pseudo-extrema.
        kernel_size = max(3, n // 25)
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = np.ones(kernel_size, dtype=float) / float(kernel_size)
        y_smooth = np.convolve(y, kernel, mode="same")

        candidate_max = np.where(
            (y_smooth[1:-1] > y_smooth[:-2]) & (y_smooth[1:-1] >= y_smooth[2:])
        )[0] + 1
        candidate_min = np.where(
            (y_smooth[1:-1] < y_smooth[:-2]) & (y_smooth[1:-1] <= y_smooth[2:])
        )[0] + 1

        max_left = candidate_max[candidate_max < center_idx]
        max_right = candidate_max[candidate_max > center_idx]
        min_left = candidate_min[candidate_min < center_idx]
        min_right = candidate_min[candidate_min > center_idx]

        left_max_idx = int(max_left[-1]) if len(max_left) > 0 else None
        right_max_idx = int(max_right[0]) if len(max_right) > 0 else None
        left_min_idx = int(min_left[-1]) if len(min_left) > 0 else None
        right_min_idx = int(min_right[0]) if len(min_right) > 0 else None

        # Pick extrema on opposite sides of the clicked slope center according to slope direction.
        # Descending slope: max (left) -> min (right)
        # Ascending slope: min (left) -> max (right)
        local_slope = float(np.gradient(y_smooth)[center_idx])
        if local_slope <= 0:
            idx_start, idx_end = left_max_idx, right_min_idx
        else:
            idx_start, idx_end = left_min_idx, right_max_idx

        if idx_start is not None and idx_end is not None and idx_end - idx_start >= 2:
            self._fit_manual_region(idx_start, idx_end)
            return

        # Secondary fallback: nearest min/max pair if side-constrained extrema are unavailable.
        max_idx = (
            int(candidate_max[np.argmin(np.abs(candidate_max - center_idx))])
            if len(candidate_max) > 0
            else None
        )
        min_idx = (
            int(candidate_min[np.argmin(np.abs(candidate_min - center_idx))])
            if len(candidate_min) > 0
            else None
        )
        if max_idx is not None and min_idx is not None and max_idx != min_idx:
            idx_start = min(max_idx, min_idx)
            idx_end = max(max_idx, min_idx)
            if idx_end - idx_start >= 2:
                self._fit_manual_region(idx_start, idx_end)
                return

        # Fallback: use derivative sign-change bounds around click if tips are ambiguous.
        dy = np.gradient(y_smooth)
        left_idx = 0
        for i in range(center_idx - 1, 0, -1):
            if dy[i - 1] * dy[i] <= 0:
                left_idx = i
                break

        right_idx = n - 1
        for i in range(center_idx + 1, n - 1):
            if dy[i] * dy[i + 1] <= 0:
                right_idx = i
                break

        self._fit_manual_region(left_idx, right_idx)

    def _fit_manual_region(self, idx_start, idx_end):
        if self.x is None or self.y is None:
            return

        idx_start = max(0, int(idx_start))
        idx_end = min(len(self.x) - 1, int(idx_end))
        if idx_end - idx_start < 2:
            return

        x_linear = self.x[idx_start : idx_end + 1]
        y_linear = self.y[idx_start : idx_end + 1]
        if len(x_linear) < 3:
            return

        model = LinearRegression()
        model.fit(x_linear.reshape(-1, 1), y_linear)
        predicted = model.predict(x_linear.reshape(-1, 1))
        slope = float(model.coef_[0])
        center_freq = float(0.5 * (x_linear[0] + x_linear[-1]))

        row_idx = self.linearRegionTable.rowCount()
        self.linearRegionTable.insertRow(row_idx)
        self.linearRegionTable.setItem(
            row_idx,
            0,
            QtWidgets.QTableWidgetItem(str(round(center_freq, 9))),
        )
        self.linearRegionTable.setItem(
            row_idx,
            1,
            QtWidgets.QTableWidgetItem(str(round(slope, 9))),
        )
        checkbox = QtWidgets.QCheckBox()
        checkbox.setChecked(True)
        self.linearRegionTable.setCellWidget(row_idx, 2, checkbox)

        delete_button = QtWidgets.QPushButton("X")
        delete_button.setToolTip("Delete this fit")
        delete_button.setMaximumWidth(26)
        delete_button.clicked.connect(self._on_delete_linear_region_clicked)
        self.linearRegionTable.setCellWidget(row_idx, 3, delete_button)

        if self.linear_region_list is None:
            self.linear_region_list = []
        line_plot = self.graphWidget.plot(x_linear, predicted, pen=self._linear_region_default_pen)
        self.linear_region_list.append(line_plot)

    def _on_delete_linear_region_clicked(self):
        sender = self.sender()
        if sender is None:
            return

        row_to_remove = None
        for row in range(self.linearRegionTable.rowCount()):
            if self.linearRegionTable.cellWidget(row, 3) is sender:
                row_to_remove = row
                break

        if row_to_remove is None:
            return

        self._remove_linear_region_row(row_to_remove)

    def _remove_linear_region_row(self, row):
        if self.linear_region_list is not None and 0 <= row < len(self.linear_region_list):
            line_plot = self.linear_region_list.pop(row)
            try:
                self.graphWidget.removeItem(line_plot)
            except Exception:
                try:
                    line_plot.clear()
                except Exception:
                    pass

        if self._hovered_linear_row == row:
            self._hovered_linear_row = None
        elif self._hovered_linear_row is not None and self._hovered_linear_row > row:
            self._hovered_linear_row -= 1

        self.linearRegionTable.removeRow(row)

    def closeEvent(self, event):
        self.main_window.rfController.sweeping = False
        self.worker_running = False
        self._selection_mode_active = False

    def stop_odmr_sweep(self):
        self.worker_running = False
        self._selection_mode_active = False
        self.autoFitButton.setText("Auto Fit Regions")
        try:
            self.main_window.rfController.sweeping = False
        except Exception:
            pass
        self.main_window.takeODMRButton.setEnabled(True)

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
        pen = get_plot_pen(0, width=2, style=QtCore.Qt.PenStyle.DashLine)
        self.odmr_plot = self.graphWidget.plot(x, y, pen=pen)
        self.updateViews()

    def send_to_scan_table(self):
        freqs = []
        grads = []
        for row in range(self.linearRegionTable.rowCount()):
            if self.linearRegionTable.cellWidget(row, 2).isChecked():
                freqs.append(float(self.linearRegionTable.item(row, 0).text()))
                # Linear fit slope is V/GHz; scan table expects V/MHz.
                grads.append(float(self.linearRegionTable.item(row, 1).text()) / 1000.0)

        self.main_window.scanODMRPropertiesTable.setRowCount(0)
        for row in range(len(freqs)):
            self.main_window.scanODMRPropertiesTable.insertRow(row)
            self.main_window.scanODMRPropertiesTable.setItem(
                row, 0, QtWidgets.QTableWidgetItem(str(round(freqs[row], 3)))
            )
            self.main_window.scanODMRPropertiesTable.setItem(
                row, 1, QtWidgets.QTableWidgetItem(f"{grads[row]:.9f}")
            )
        self.main_window._refresh_scan_table_set_buttons()
