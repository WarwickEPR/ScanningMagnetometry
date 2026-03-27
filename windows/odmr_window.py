import time
import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets
from sklearn.linear_model import LinearRegression

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
        self.autoFitButton.setText("Select Linear Region")
        self.autoFitButton.clicked.connect(self.start_linear_region_selection)
        self.autoFitButton.setEnabled(False)
        self.autoFitAfterSweepCheckBox.hide()
        self._hide_legacy_auto_fit_controls()
        self.stopSweepButton.clicked.connect(self.stop_odmr_sweep)
        self.graphWidget.scene().sigMouseClicked.connect(self._on_plot_mouse_clicked)

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
        self.autoFitButton.setEnabled(len(self.x) >= 3)
        self._selection_mode_active = False
        self._selected_indices = []
        self.autoFitButton.setText("Select Linear Region")

    def progress_fn(self, results):
        self.y = results
        self.x = np.linspace(
            self.main_window.rfController.start_freq,
            self.main_window.rfController.stop_freq,
            self.main_window.rfController.num_points,
        )
        self.x = self.x[0 : len(self.y)]
        self.dummy_data(self.x, self.y)
        self.autoFitButton.setEnabled(False)

    def start_linear_region_selection(self):
        if self.main_window.rfController.sweeping:
            return
        if self.x is None or self.y is None or len(self.x) < 3:
            return
        self._selection_mode_active = True
        self._selected_indices = []
        self.autoFitButton.setText("Select Point 1/2")

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
        nearest_idx = int(np.argmin(np.abs(self.x - clicked_x)))
        self._selected_indices.append(nearest_idx)

        if len(self._selected_indices) == 1:
            self.autoFitButton.setText("Select Point 2/2")
            return

        idx_start, idx_end = sorted(self._selected_indices[:2])
        self._selected_indices = []
        self._selection_mode_active = False
        self.autoFitButton.setText("Select Linear Region")

        self._fit_manual_region(idx_start, idx_end)

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

        if self.linear_region_list is None:
            self.linear_region_list = []
        line_plot = self.graphWidget.plot(x_linear, predicted, pen=self._linear_region_default_pen)
        self.linear_region_list.append(line_plot)

    def closeEvent(self, event):
        self.main_window.rfController.sweeping = False
        self.worker_running = False
        self._selection_mode_active = False

    def stop_odmr_sweep(self):
        self.worker_running = False
        self._selection_mode_active = False
        self.autoFitButton.setText("Select Linear Region")

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
