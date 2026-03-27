from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg


class DataViewerUIBuilder:
    """Programmatic UI for DataViewer with legacy-compatible widget names."""

    def setup(self, window: QtWidgets.QMainWindow):
        window.setObjectName("DataViewer")
        window.resize(1080, 760)
        window.setWindowTitle("HDF5 Data Viewer")

        window.centralwidget = QtWidgets.QWidget(window)
        window.centralwidget.setObjectName("centralwidget")
        window.setCentralWidget(window.centralwidget)

        root = QtWidgets.QVBoxLayout(window.centralwidget)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_header())

        body = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)
        root.addWidget(body, 1)

        body.addWidget(self._build_left_panel(window))
        body.addWidget(self._build_plot_panel(window))
        body.setStretchFactor(0, 2)
        body.setStretchFactor(1, 5)

        self._apply_styles(window)

    def _build_header(self):
        frame = QtWidgets.QFrame()
        frame.setObjectName("dataViewerHeader")
        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)

        title_col = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("HDF5 Data Viewer")
        title.setObjectName("dataViewerTitle")
        subtitle = QtWidgets.QLabel("Browse datasets and switch between line/image views")
        subtitle.setObjectName("dataViewerSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        layout.addLayout(title_col)
        layout.addStretch(1)

        return frame

    def _build_left_panel(self, window):
        panel = QtWidgets.QFrame()
        panel.setObjectName("dataViewerLeftPanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        window.groupBox_2 = QtWidgets.QGroupBox("Found Data Sets")
        window.groupBox_2.setObjectName("groupBox_2")
        found_layout = QtWidgets.QVBoxLayout(window.groupBox_2)
        window.fileItemList = QtWidgets.QListWidget()
        window.fileItemList.setObjectName("fileItemList")
        found_layout.addWidget(window.fileItemList)

        window.groupBox = QtWidgets.QGroupBox("Data Set Items")
        window.groupBox.setObjectName("groupBox")
        item_layout = QtWidgets.QVBoxLayout(window.groupBox)
        window.dataList = QtWidgets.QListWidget()
        window.dataList.setObjectName("dataList")
        item_layout.addWidget(window.dataList)

        window.selectPlotType = QtWidgets.QComboBox()
        window.selectPlotType.setObjectName("selectPlotType")
        window.selectPlotType.addItems(["Line Plot", "Image Plot"])

        window.frame = QtWidgets.QFrame()
        window.frame.setObjectName("frame")
        frame_layout = QtWidgets.QHBoxLayout(window.frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        window.loadH5FileButton = QtWidgets.QPushButton("Load HDF5 File")
        window.loadH5FileButton.setObjectName("loadH5FileButton")
        frame_layout.addWidget(window.loadH5FileButton)

        window.frame_2 = QtWidgets.QFrame()
        window.frame_2.setObjectName("frame_2")
        frame_layout_2 = QtWidgets.QHBoxLayout(window.frame_2)
        frame_layout_2.setContentsMargins(0, 0, 0, 0)
        window.saveImgCSVButton = QtWidgets.QPushButton("Export Image as CSV")
        window.saveImgCSVButton.setObjectName("saveImgCSVButton")
        frame_layout_2.addWidget(window.saveImgCSVButton)

        layout.addWidget(window.groupBox_2)
        layout.addWidget(window.groupBox)
        layout.addWidget(window.selectPlotType)
        layout.addWidget(window.frame)
        layout.addWidget(window.frame_2)
        layout.addStretch(1)

        return panel

    def _build_plot_panel(self, window):
        panel = QtWidgets.QFrame()
        panel.setObjectName("dataViewerPlotPanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)

        window.stackedGraphs = QtWidgets.QStackedWidget()
        window.stackedGraphs.setObjectName("stackedGraphs")

        window.lineGraph = QtWidgets.QWidget()
        window.lineGraph.setObjectName("lineGraph")
        line_layout = QtWidgets.QVBoxLayout(window.lineGraph)
        line_layout.setContentsMargins(0, 0, 0, 0)
        window.dataGraph = pg.PlotWidget()
        window.dataGraph.setObjectName("dataGraph")
        line_layout.addWidget(window.dataGraph)

        window.imageGraph = QtWidgets.QWidget()
        window.imageGraph.setObjectName("imageGraph")
        image_layout = QtWidgets.QVBoxLayout(window.imageGraph)
        image_layout.setContentsMargins(0, 0, 0, 0)
        window.imageWidget = pg.ImageView()
        window.imageWidget.setObjectName("imageWidget")
        window.imageWidget.ui.histogram.hide()
        window.imageWidget.ui.roiBtn.hide()
        window.imageWidget.ui.menuBtn.hide()
        image_layout.addWidget(window.imageWidget)

        window.stackedGraphs.addWidget(window.lineGraph)
        window.stackedGraphs.addWidget(window.imageGraph)

        layout.addWidget(window.stackedGraphs)
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
            QFrame#dataViewerHeader, QFrame#dataViewerLeftPanel, QFrame#dataViewerPlotPanel {
                background: #ffffff;
                border: 1px solid #d5dbe3;
                border-radius: 10px;
            }
            QLabel#dataViewerTitle {
                font-size: 18px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#dataViewerSubtitle {
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
            QListWidget, QComboBox {
                background: #ffffff;
                border: 1px solid #c9d3df;
                border-radius: 6px;
                padding: 4px;
                selection-background-color: #3f8fc2;
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