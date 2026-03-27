from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg


class FFTWindowUIBuilder:
    """Programmatic UI for the FFT window with legacy-compatible widget names."""

    def setup(self, window: QtWidgets.QWidget):
        window.setObjectName("FFTGraphWindow")
        window.resize(1180, 780)
        window.setWindowTitle("FFT Analysis")

        root = QtWidgets.QVBoxLayout(window)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_header(window))

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        plot_panel = QtWidgets.QFrame()
        plot_panel.setObjectName("fftPlotPanel")
        self.verticalLayout = QtWidgets.QVBoxLayout(plot_panel)
        self.verticalLayout.setContentsMargins(10, 10, 10, 10)
        self.verticalLayout.setSpacing(8)

        window.graphWidget = pg.PlotWidget()
        window.graphWidget.setObjectName("graphWidget")
        self.verticalLayout.addWidget(window.graphWidget, 1)

        # Keep legacy layout attribute name used by fft_window.py.
        window.verticalLayout = self.verticalLayout

        control_panel = self._build_controls(window)

        splitter.addWidget(plot_panel)
        splitter.addWidget(control_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 3)

        self._apply_styles(window)

    def _build_header(self, window):
        frame = QtWidgets.QFrame()
        frame.setObjectName("fftHeader")
        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)

        title_col = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("FFT Sweep")
        title.setObjectName("fftTitle")
        subtitle = QtWidgets.QLabel("Power spectral density and sensitivity estimator")
        subtitle.setObjectName("fftSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        layout.addLayout(title_col)
        layout.addStretch(1)

        return frame

    def _build_controls(self, window):
        panel = QtWidgets.QFrame()
        panel.setObjectName("fftControlPanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        sens_group = QtWidgets.QGroupBox("Sensitivity")
        sens_form = QtWidgets.QFormLayout(sens_group)

        window.minFreqSpinBox = QtWidgets.QDoubleSpinBox()
        window.minFreqSpinBox.setObjectName("minFreqSpinBox")
        window.minFreqSpinBox.setRange(0.0, 1e7)
        window.minFreqSpinBox.setDecimals(3)
        window.minFreqSpinBox.setValue(10.0)

        window.maxFreqSpinBox = QtWidgets.QDoubleSpinBox()
        window.maxFreqSpinBox.setObjectName("maxFreqSpinBox")
        window.maxFreqSpinBox.setRange(0.0, 1e7)
        window.maxFreqSpinBox.setDecimals(3)
        window.maxFreqSpinBox.setValue(100.0)

        window.odmrGradientSpinBox = QtWidgets.QDoubleSpinBox()
        window.odmrGradientSpinBox.setObjectName("odmrGradientSpinBox")
        window.odmrGradientSpinBox.setRange(0.0, 1e6)
        window.odmrGradientSpinBox.setDecimals(6)
        window.odmrGradientSpinBox.setValue(1.0)

        window.ignoreListFreqCheckBox = QtWidgets.QCheckBox("Ignore listed frequency ranges")
        window.ignoreListFreqCheckBox.setObjectName("ignoreListFreqCheckBox")
        window.ignoreListFreqCheckBox.setChecked(True)

        window.calcSensButton = QtWidgets.QPushButton("Calculate Sensitivity")
        window.calcSensButton.setObjectName("calcSensButton")

        window.meanSensLabel = QtWidgets.QLabel("--")
        window.meanSensLabel.setObjectName("meanSensLabel")
        mean_label = QtWidgets.QLabel("Mean Sensitivity (nT/sqrt(Hz))")

        sens_form.addRow("Min Frequency (Hz)", window.minFreqSpinBox)
        sens_form.addRow("Max Frequency (Hz)", window.maxFreqSpinBox)
        sens_form.addRow("ODMR Gradient", window.odmrGradientSpinBox)
        sens_form.addRow("", window.ignoreListFreqCheckBox)
        sens_form.addRow("", window.calcSensButton)
        sens_form.addRow(mean_label, window.meanSensLabel)

        ignore_group = QtWidgets.QGroupBox("Ignored Frequency Bands")
        ignore_layout = QtWidgets.QVBoxLayout(ignore_group)

        add_band_row = QtWidgets.QHBoxLayout()
        window.freqStartSpinBox = QtWidgets.QDoubleSpinBox()
        window.freqStartSpinBox.setObjectName("freqStartSpinBox")
        window.freqStartSpinBox.setRange(0.0, 1e7)
        window.freqStartSpinBox.setDecimals(3)
        window.freqStartSpinBox.setValue(48.0)

        window.freqEndSpinBox = QtWidgets.QDoubleSpinBox()
        window.freqEndSpinBox.setObjectName("freqEndSpinBox")
        window.freqEndSpinBox.setRange(0.0, 1e7)
        window.freqEndSpinBox.setDecimals(3)
        window.freqEndSpinBox.setValue(52.0)

        window.addFreqButton = QtWidgets.QPushButton("Add Range")
        window.addFreqButton.setObjectName("addFreqButton")

        add_band_row.addWidget(window.freqStartSpinBox)
        add_band_row.addWidget(window.freqEndSpinBox)
        add_band_row.addWidget(window.addFreqButton)

        window.ignoreFrequencyList = QtWidgets.QTableWidget(0, 2)
        window.ignoreFrequencyList.setObjectName("ignoreFrequencyList")
        window.ignoreFrequencyList.setHorizontalHeaderLabels(["Start (Hz)", "End (Hz)"])
        window.ignoreFrequencyList.horizontalHeader().setStretchLastSection(True)
        window.ignoreFrequencyList.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        window.ignoreFrequencyList.verticalHeader().setVisible(False)

        ignore_layout.addLayout(add_band_row)
        ignore_layout.addWidget(window.ignoreFrequencyList, 1)

        layout.addWidget(sens_group)
        layout.addWidget(ignore_group, 1)

        return panel

    @staticmethod
    def _apply_styles(window):
        window.setStyleSheet(
            """
            QWidget {
                background: #f2f5f8;
                color: #1f2937;
                font-size: 12px;
            }
            QFrame#fftHeader, QFrame#fftPlotPanel, QFrame#fftControlPanel {
                background: #ffffff;
                border: 1px solid #d5dbe3;
                border-radius: 10px;
            }
            QLabel#fftTitle {
                font-size: 18px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#fftSubtitle {
                color: #5f6b7a;
                font-size: 11px;
            }
            QLabel#meanSensLabel {
                font-weight: 700;
                color: #0f4c75;
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
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget {
                background: #ffffff;
                border: 1px solid #c9d3df;
                border-radius: 6px;
                padding: 4px;
                selection-background-color: #3f8fc2;
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
