from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg
from ui_theme import configure_pyqtgraph_defaults, get_plot_pen, style_plot_labels, style_plot_widget


class LIALiveTraceWindowUIBuilder:
    """Programmatic UI builder for LIA live trace window."""

    def setup(self, window: QtWidgets.QWidget):
        configure_pyqtgraph_defaults()
        window.setObjectName("LIALiveTraceWindow")
        window.setWindowTitle("LIA Live Demod Time Trace")
        window.resize(980, 720)

        root_layout = QtWidgets.QVBoxLayout(window)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        header = QtWidgets.QFrame()
        header.setObjectName("liaHeader")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title_col = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("LIA Live Demod Trace")
        title.setObjectName("liaTitle")
        subtitle = QtWidgets.QLabel("Realtime X, Y and R demod channels")
        subtitle.setObjectName("liaSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        header_layout.addLayout(title_col)
        header_layout.addStretch(1)

        root_layout.addWidget(header)

        controls_card = QtWidgets.QFrame()
        controls_card.setObjectName("liaControlsCard")
        button_row = QtWidgets.QHBoxLayout(controls_card)
        button_row.setContentsMargins(10, 8, 10, 8)
        button_row.setSpacing(8)

        window.startButton = QtWidgets.QPushButton("Start")
        window.stopButton = QtWidgets.QPushButton("Stop")
        window.clearButton = QtWidgets.QPushButton("Clear")
        window.timeWindowLabel = QtWidgets.QLabel("Window (s)")
        window.timeWindowSpinBox = QtWidgets.QDoubleSpinBox()
        window.timeWindowSpinBox.setDecimals(1)
        window.timeWindowSpinBox.setMinimum(2.0)
        window.timeWindowSpinBox.setMaximum(600.0)
        window.timeWindowSpinBox.setSingleStep(1.0)
        window.timeWindowSpinBox.setValue(window.time_window_seconds)
        window.statusLabel = QtWidgets.QLabel("Idle")
        window.statusLabel.setMinimumWidth(220)

        button_row.addWidget(window.startButton)
        button_row.addWidget(window.stopButton)
        button_row.addWidget(window.clearButton)
        button_row.addSpacing(8)
        button_row.addWidget(window.timeWindowLabel)
        button_row.addWidget(window.timeWindowSpinBox)
        button_row.addStretch()
        button_row.addWidget(window.statusLabel)

        root_layout.addWidget(controls_card)

        plot_stack = QtWidgets.QFrame()
        plot_stack.setObjectName("liaPlotStack")
        plot_layout = QtWidgets.QVBoxLayout(plot_stack)
        plot_layout.setContentsMargins(10, 10, 10, 10)
        plot_layout.setSpacing(8)

        window.plotX = pg.PlotWidget()
        window.plotY = pg.PlotWidget()
        window.plotR = pg.PlotWidget()

        style_plot_widget(window.plotX)
        style_plot_widget(window.plotY)
        style_plot_widget(window.plotR)
        style_plot_labels(window.plotX, left="Demod X (V)")
        style_plot_labels(window.plotY, left="Demod Y (V)")
        style_plot_labels(window.plotR, left="Demod R (V)", bottom="Time (s)")
        window.plotY.setXLink(window.plotX)
        window.plotR.setXLink(window.plotX)

        window.curveX = window.plotX.plot(pen=get_plot_pen(0, width=2))
        window.curveY = window.plotY.plot(pen=get_plot_pen(4, width=2))
        window.curveR = window.plotR.plot(pen=get_plot_pen(6, width=2))

        plot_layout.addWidget(window.plotX)
        plot_layout.addWidget(window.plotY)
        plot_layout.addWidget(window.plotR)
        root_layout.addWidget(plot_stack, 1)

        window.startButton.clicked.connect(window.start_stream)
        window.stopButton.clicked.connect(window.stop_stream)
        window.clearButton.clicked.connect(window.clear_data)
        window.timeWindowSpinBox.valueChanged.connect(window._on_time_window_changed)
        window.stopButton.setEnabled(False)

        self._apply_styles(window)

    @staticmethod
    def _apply_styles(window):
        window.setStyleSheet(
            """
            QWidget {
                background: #f2f5f8;
                color: #1f2937;
                font-size: 12px;
            }
            QFrame#liaHeader, QFrame#liaControlsCard, QFrame#liaPlotStack {
                background: #ffffff;
                border: 1px solid #d5dbe3;
                border-radius: 10px;
            }
            QLabel#liaTitle {
                font-size: 18px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#liaSubtitle {
                color: #5f6b7a;
                font-size: 11px;
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
            QDoubleSpinBox {
                background: #ffffff;
                border: 1px solid #c9d3df;
                border-radius: 6px;
                padding: 4px;
            }
            """
        )
