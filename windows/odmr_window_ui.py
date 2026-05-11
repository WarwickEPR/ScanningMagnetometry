from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg


class ODMRWindowUIBuilder:
    """Programmatic UI for ODMR window with legacy-compatible widget names."""

    def setup(self, window: QtWidgets.QWidget):
        window.setObjectName("ODMRGraphWindow")
        window.resize(1220, 820)
        window.setWindowTitle("ODMR Analysis")

        root = QtWidgets.QVBoxLayout(window)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_header(window))

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        splitter.addWidget(self._build_plot_panel(window))
        splitter.addWidget(self._build_table_panel(window))
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 3)

        # Legacy widgets retained so existing logic can hide/ignore them safely.
        self._create_legacy_widgets(window)
        self._apply_styles(window)

    def _build_header(self, window):
        frame = QtWidgets.QFrame()
        frame.setObjectName("odmrHeader")
        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        title_col = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("ODMR Sweep")
        title.setObjectName("odmrTitle")
        subtitle = QtWidgets.QLabel("Select two points to define linear regions")
        subtitle.setObjectName("odmrSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        window.stopSweepButton = QtWidgets.QPushButton("Stop Sweep")
        window.stopSweepButton.setObjectName("stopSweepButton")

        window.autoFitButton = QtWidgets.QPushButton("Select Linear Region")
        window.autoFitButton.setObjectName("autoFitButton")

        window.setODMRButton = QtWidgets.QPushButton("Send To Scan Table")
        window.setODMRButton.setObjectName("setODMRButton")

        layout.addLayout(title_col)
        layout.addStretch(1)
        layout.addWidget(window.stopSweepButton)
        layout.addWidget(window.autoFitButton)
        layout.addWidget(window.setODMRButton)
        return frame

    def _build_plot_panel(self, window):
        panel = QtWidgets.QFrame()
        panel.setObjectName("odmrPlotPanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)

        plot_group = QtWidgets.QGroupBox("Sweep Signal")
        plot_layout = QtWidgets.QVBoxLayout(plot_group)
        window.graphWidget = pg.PlotWidget()
        window.graphWidget.setObjectName("graphWidget")
        plot_layout.addWidget(window.graphWidget)

        layout.addWidget(plot_group)
        return panel

    def _build_table_panel(self, window):
        panel = QtWidgets.QFrame()
        panel.setObjectName("odmrTablePanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        region_group = QtWidgets.QGroupBox("Linear Regions")
        region_layout = QtWidgets.QVBoxLayout(region_group)

        window.linearRegionTable = QtWidgets.QTableWidget(0, 4)
        window.linearRegionTable.setObjectName("linearRegionTable")
        window.linearRegionTable.setHorizontalHeaderLabels(
            ["Center Freq (GHz)", "Gradient", "Use", ""]
        )
        window.linearRegionTable.horizontalHeader().setStretchLastSection(False)
        window.linearRegionTable.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        window.linearRegionTable.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        window.linearRegionTable.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        window.linearRegionTable.horizontalHeader().setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        window.linearRegionTable.verticalHeader().setVisible(False)
        window.linearRegionTable.setAlternatingRowColors(True)

        region_layout.addWidget(window.linearRegionTable)

        tips = QtWidgets.QLabel(
            "Tip: Click two points on the curve to add a linear fit region."
        )
        tips.setObjectName("odmrTips")

        layout.addWidget(region_group, 1)
        layout.addWidget(tips)
        return panel

    @staticmethod
    def _create_legacy_widgets(window):
        # Controls used by old auto-fit code paths, now hidden by odmr_window.py.
        window.odmrRegionFitBox = QtWidgets.QComboBox(window)
        window.showDerivativeCheckbox = QtWidgets.QCheckBox(window)
        window.smoothingCheckBox = QtWidgets.QCheckBox(window)
        window.polyorderSpinBox = QtWidgets.QSpinBox(window)
        window.smoothWindowBox = QtWidgets.QSpinBox(window)
        window.peakHeightSpinBox = QtWidgets.QDoubleSpinBox(window)
        window.peakDistanceSpinBox = QtWidgets.QSpinBox(window)
        window.peakPromSpinBox = QtWidgets.QDoubleSpinBox(window)
        window.usePositiveGradientsCheckBox = QtWidgets.QCheckBox(window)
        window.autoFitAfterSweepCheckBox = QtWidgets.QCheckBox(window)

        # Legacy labels referenced by name in hide helper.
        window.label = QtWidgets.QLabel(window)
        window.label_2 = QtWidgets.QLabel(window)
        window.label_4 = QtWidgets.QLabel(window)
        window.label_5 = QtWidgets.QLabel(window)
        window.label_6 = QtWidgets.QLabel(window)
        window.label_7 = QtWidgets.QLabel(window)

    @staticmethod
    def _apply_styles(window):
        window.setStyleSheet(
            """
            QWidget {
                background: #f2f5f8;
                color: #1f2937;
                font-size: 12px;
            }
            QFrame#odmrHeader, QFrame#odmrPlotPanel, QFrame#odmrTablePanel {
                background: #ffffff;
                border: 1px solid #d5dbe3;
                border-radius: 10px;
            }
            QLabel#odmrTitle {
                font-size: 18px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#odmrSubtitle {
                color: #5f6b7a;
                font-size: 11px;
            }
            QLabel#odmrTips {
                color: #4f5d6b;
                padding: 4px 2px;
            }
            QPushButton {
                background: #1f5a82;
                color: #ffffff;
                border: none;
                border-radius: 7px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1a4d6f;
            }
            QPushButton:pressed {
                background: #153f5a;
            }
            QGroupBox {
                border: 1px solid #d3dae4;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: 600;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QTableWidget {
                border: 1px solid #ccd6e1;
                border-radius: 6px;
                background: #ffffff;
                gridline-color: #dde4ec;
                alternate-background-color: #f8fafc;
            }
            QHeaderView::section {
                background: #e8edf2;
                border: none;
                border-right: 1px solid #d4dbe3;
                border-bottom: 1px solid #d4dbe3;
                padding: 5px;
                font-weight: 600;
            }
            """
        )
