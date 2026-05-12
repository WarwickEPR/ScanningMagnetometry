from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg


class ScanningWindowUIBuilder:
    """Programmatic UI for the scanning window with legacy widget names."""

    def setup(self, window: QtWidgets.QWidget):
        window.setObjectName("ScanningWindow")
        window.resize(1360, 860)
        window.setWindowTitle("Scan Monitor")

        root = QtWidgets.QVBoxLayout(window)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_top_bar(window))

        window.scanTabWidget = QtWidgets.QTabWidget()
        window.scanTabWidget.setObjectName("scanTabWidget")
        root.addWidget(window.scanTabWidget, 1)

        window.scanMapTab = self._build_map_panel(window)
        window.scanTrackingTab = self._build_trace_panel(window)
        window.scanTabWidget.addTab(window.scanMapTab, "Maps")
        window.scanTabWidget.addTab(window.scanTrackingTab, "Tracking")

        self._apply_styles(window)

    def _build_top_bar(self, window):
        bar = QtWidgets.QFrame()
        bar.setObjectName("scanTopBar")
        layout = QtWidgets.QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QtWidgets.QLabel("Live Scan")
        title.setObjectName("scanTitle")
        subtitle = QtWidgets.QLabel("Magnetic field mapping and feedback traces")
        subtitle.setObjectName("scanSubtitle")

        title_col = QtWidgets.QVBoxLayout()
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        window.exportDataButton = QtWidgets.QPushButton("Export Data")
        window.exportDataButton.setObjectName("exportDataButton")

        window.stopScanButton = QtWidgets.QPushButton("Stop Scan")
        window.stopScanButton.setObjectName("stopScanButton")

        layout.addLayout(title_col)
        layout.addStretch(1)
        layout.addWidget(window.stopScanButton)
        layout.addWidget(window.exportDataButton)
        return bar

    def _build_map_panel(self, window):
        panel = QtWidgets.QFrame()
        panel.setObjectName("mapPanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        window.mapSubTabWidget = QtWidgets.QTabWidget()
        window.mapSubTabWidget.setObjectName("mapSubTabWidget")
        layout.addWidget(window.mapSubTabWidget, 1)

        main_card = self._image_card("Primary Map")
        window.primaryMapCard = main_card
        window.imageWidget = pg.ImageView()
        window.imageWidget.setObjectName("imageWidget")
        self._attach_image_widget(main_card, window.imageWidget)
        window.primaryMapTab = QtWidgets.QWidget()
        primary_tab_layout = QtWidgets.QVBoxLayout(window.primaryMapTab)
        primary_tab_layout.setContentsMargins(0, 0, 0, 0)
        primary_tab_layout.addWidget(main_card)
        window.mapSubTabWidget.addTab(window.primaryMapTab, "Primary")

        card2 = self._image_card("Vector Bx")
        window.vectorMapCardBx = card2
        window.imageWidget_2 = pg.ImageView()
        window.imageWidget_2.setObjectName("imageWidget_2")
        self._attach_image_widget(card2, window.imageWidget_2)
        window.vectorMapTabBx = QtWidgets.QWidget()
        bx_tab_layout = QtWidgets.QVBoxLayout(window.vectorMapTabBx)
        bx_tab_layout.setContentsMargins(0, 0, 0, 0)
        bx_tab_layout.addWidget(card2)
        window.mapSubTabWidget.addTab(window.vectorMapTabBx, "Bx")

        card3 = self._image_card("Vector By")
        window.vectorMapCardBy = card3
        window.imageWidget_3 = pg.ImageView()
        window.imageWidget_3.setObjectName("imageWidget_3")
        self._attach_image_widget(card3, window.imageWidget_3)
        window.vectorMapTabBy = QtWidgets.QWidget()
        by_tab_layout = QtWidgets.QVBoxLayout(window.vectorMapTabBy)
        by_tab_layout.setContentsMargins(0, 0, 0, 0)
        by_tab_layout.addWidget(card3)
        window.mapSubTabWidget.addTab(window.vectorMapTabBy, "By")

        card4 = self._image_card("Vector Bz")
        window.vectorMapCardBz = card4
        window.imageWidget_4 = pg.ImageView()
        window.imageWidget_4.setObjectName("imageWidget_4")
        self._attach_image_widget(card4, window.imageWidget_4)
        window.vectorMapTabBz = QtWidgets.QWidget()
        bz_tab_layout = QtWidgets.QVBoxLayout(window.vectorMapTabBz)
        bz_tab_layout.setContentsMargins(0, 0, 0, 0)
        bz_tab_layout.addWidget(card4)
        window.mapSubTabWidget.addTab(window.vectorMapTabBz, "Bz")

        return panel

    def _build_trace_panel(self, window):
        panel = QtWidgets.QFrame()
        panel.setObjectName("tracePanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        trace_card_1 = QtWidgets.QGroupBox("Frequency Tracking")
        window.frequencyTrackingCard = trace_card_1
        trace_layout_1 = QtWidgets.QVBoxLayout(trace_card_1)
        window.graphWidget = pg.PlotWidget()
        window.graphWidget.setObjectName("graphWidget")
        trace_layout_1.addWidget(window.graphWidget)

        trace_card_2 = QtWidgets.QGroupBox("Voltage Tracking")
        window.voltageTrackingCard = trace_card_2
        trace_layout_2 = QtWidgets.QVBoxLayout(trace_card_2)
        window.graphWidget_2 = pg.PlotWidget()
        window.graphWidget_2.setObjectName("graphWidget_2")
        trace_layout_2.addWidget(window.graphWidget_2)

        layout.addWidget(trace_card_1, 1)
        layout.addWidget(trace_card_2, 1)

        return panel

    @staticmethod
    def _image_card(title: str):
        card = QtWidgets.QGroupBox(title)
        card.setLayout(QtWidgets.QVBoxLayout())
        card.layout().setContentsMargins(6, 6, 6, 6)
        return card

    @staticmethod
    def _attach_image_widget(card: QtWidgets.QGroupBox, image_widget: pg.ImageView):
        image_widget.ui.histogram.hide()
        image_widget.ui.roiBtn.hide()
        image_widget.ui.menuBtn.hide()
        card.layout().addWidget(image_widget)

    @staticmethod
    def _apply_styles(window):
        window.setStyleSheet(
            """
            QWidget {
                background: #f2f5f8;
                color: #1f2937;
                font-size: 12px;
            }
            QFrame#scanTopBar, QFrame#mapPanel, QFrame#tracePanel {
                background: #ffffff;
                border: 1px solid #d5dbe3;
                border-radius: 10px;
            }
            QLabel#scanTitle {
                font-size: 18px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#scanSubtitle {
                color: #5f6b7a;
                font-size: 11px;
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
            """
        )
