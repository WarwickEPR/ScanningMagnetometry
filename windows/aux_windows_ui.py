from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg


class VectorMatrixWindowUIBuilder:
    """Programmatic UI builder for vector calibration matrix window."""

    def setup(self, window: QtWidgets.QWidget):
        window.setObjectName("VectorMatrixWindow")
        window.resize(460, 500)
        window.setWindowTitle("Vector Calibration Matrix")

        root = QtWidgets.QVBoxLayout(window)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        frame = QtWidgets.QFrame()
        frame.setObjectName("vectorMatrixCard")
        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QtWidgets.QLabel("Vector Calibration Matrix (MHz/T)")
        title.setObjectName("label_13")
        layout.addWidget(title)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        headers = ["dbx", "dby", "dbz"]
        for col, text in enumerate(headers):
            label = QtWidgets.QLabel(text)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(label, 0, col + 1)

        for row in range(4):
            row_label = QtWidgets.QLabel(f"df{row + 1}")
            grid.addWidget(row_label, row + 1, 0)

        window.df1dbx = self._make_spinbox()
        window.df1dby = self._make_spinbox()
        window.df1dbz = self._make_spinbox()
        window.df2dbx = self._make_spinbox()
        window.df2dby = self._make_spinbox()
        window.df2dbz = self._make_spinbox()
        window.df3dbx = self._make_spinbox()
        window.df3dby = self._make_spinbox()
        window.df3dbz = self._make_spinbox()
        window.df4dbx = self._make_spinbox()
        window.df4dby = self._make_spinbox()
        window.df4dbz = self._make_spinbox()

        window.df1dbx.setObjectName("df1dbx")
        window.df1dby.setObjectName("df1dby")
        window.df1dbz.setObjectName("df1dbz")
        window.df2dbx.setObjectName("df2dbx")
        window.df2dby.setObjectName("df2dby")
        window.df2dbz.setObjectName("df2dbz")
        window.df3dbx.setObjectName("df3dbx")
        window.df3dby.setObjectName("df3dby")
        window.df3dbz.setObjectName("df3dbz")
        window.df4dbx.setObjectName("df4dbx")
        window.df4dby.setObjectName("df4dby")
        window.df4dbz.setObjectName("df4dbz")

        spinboxes = [
            [window.df1dbx, window.df1dby, window.df1dbz],
            [window.df2dbx, window.df2dby, window.df2dbz],
            [window.df3dbx, window.df3dby, window.df3dbz],
            [window.df4dbx, window.df4dby, window.df4dbz],
        ]
        for row, row_boxes in enumerate(spinboxes, start=1):
            for col, box in enumerate(row_boxes, start=1):
                grid.addWidget(box, row, col)

        layout.addLayout(grid)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch(1)
        window.applyChangesButton = QtWidgets.QPushButton("Apply Changes")
        window.applyChangesButton.setObjectName("applyChangesButton")
        button_row.addWidget(window.applyChangesButton)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        root.addWidget(frame)
        self._apply_styles(window)

    @staticmethod
    def _make_spinbox():
        box = QtWidgets.QDoubleSpinBox()
        box.setDecimals(5)
        box.setRange(-99999999.0, 99999999.0)
        box.setSingleStep(0.25)
        box.setValue(1.0)
        return box

    @staticmethod
    def _apply_styles(window):
        window.setStyleSheet(
            """
            QWidget {
                background: #f2f5f8;
                color: #1f2937;
                font-size: 12px;
            }
            QFrame#vectorMatrixCard {
                background: #ffffff;
                border: 1px solid #d5dbe3;
                border-radius: 10px;
            }
            QLabel#label_13 {
                font-weight: 700;
                color: #111827;
                font-size: 14px;
            }
            QDoubleSpinBox {
                background: #ffffff;
                border: 1px solid #c9d3df;
                border-radius: 6px;
                padding: 4px;
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


class VectorTestWindowUIBuilder:
    """Programmatic UI builder for vector debug test plots."""

    def setup(self, window: QtWidgets.QWidget):
        window.setObjectName("VectorTestWindow")
        window.resize(760, 560)
        window.setWindowTitle("Vector Debug Plot")

        root = QtWidgets.QVBoxLayout(window)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        window.graphWidget_2 = pg.PlotWidget()
        window.graphWidget_2.setObjectName("graphWidget_2")
        window.graphWidget = pg.PlotWidget()
        window.graphWidget.setObjectName("graphWidget")

        top_card = QtWidgets.QFrame()
        top_card.setObjectName("vectorTopCard")
        top_layout = QtWidgets.QVBoxLayout(top_card)
        top_layout.setContentsMargins(8, 8, 8, 8)
        top_layout.addWidget(window.graphWidget_2)

        bottom_card = QtWidgets.QFrame()
        bottom_card.setObjectName("vectorBottomCard")
        bottom_layout = QtWidgets.QVBoxLayout(bottom_card)
        bottom_layout.setContentsMargins(8, 8, 8, 8)
        bottom_layout.addWidget(window.graphWidget)

        root.addWidget(top_card, 1)
        root.addWidget(bottom_card, 1)
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
            QFrame#vectorTopCard, QFrame#vectorBottomCard {
                background: #ffffff;
                border: 1px solid #d5dbe3;
                border-radius: 10px;
            }
            """
        )


class StageOptionsUIBuilder:
    """Programmatic UI builder for stage options window."""

    def setup(self, window: QtWidgets.QWidget):
        window.setObjectName("StageOptions")
        window.resize(700, 420)
        window.setWindowTitle("Stage Options")

        root = QtWidgets.QGridLayout(window)
        root.setContentsMargins(12, 12, 12, 12)
        root.setHorizontalSpacing(10)
        root.setVerticalSpacing(10)

        frame1 = self._build_position_frame(window)
        frame2 = self._build_speed_frame(window)
        frame3 = self._build_acceleration_frame(window)
        frame4 = self._build_jerk_frame(window)

        frame1.setObjectName("frame")
        frame2.setObjectName("frame_2")
        frame3.setObjectName("frame_3")
        frame4.setObjectName("frame_4")

        root.addWidget(frame1, 0, 0)
        root.addWidget(frame2, 0, 1)
        root.addWidget(frame4, 1, 0)
        root.addWidget(frame3, 1, 1)

        self._apply_styles(window)

    def _build_position_frame(self, window):
        frame = QtWidgets.QFrame()
        layout = QtWidgets.QFormLayout(frame)

        window.maxXSpinbox = QtWidgets.QDoubleSpinBox()
        window.maxYSpinbox = QtWidgets.QDoubleSpinBox()
        window.maxZSpinbox = QtWidgets.QDoubleSpinBox()
        window.maxXSpinbox.setObjectName("maxXSpinbox")
        window.maxYSpinbox.setObjectName("maxYSpinbox")
        window.maxZSpinbox.setObjectName("maxZSpinbox")

        window.applyPositionChangesButton = QtWidgets.QPushButton("Apply")
        window.applyPositionChangesButton.setObjectName("applyPositionChangesButton")

        layout.addRow("Max X Position (mm)", window.maxXSpinbox)
        layout.addRow("Max Y Position (mm)", window.maxYSpinbox)
        layout.addRow("Max Z Position (mm)", window.maxZSpinbox)
        layout.addRow("", window.applyPositionChangesButton)
        return frame

    def _build_speed_frame(self, window):
        frame = QtWidgets.QFrame()
        layout = QtWidgets.QFormLayout(frame)

        window.maxXSpeedSpinbox = QtWidgets.QDoubleSpinBox()
        window.maxYSpeedSpinbox = QtWidgets.QDoubleSpinBox()
        window.maxZSpeedSpinbox = QtWidgets.QDoubleSpinBox()
        window.maxXSpeedSpinbox.setObjectName("maxXSpeedSpinbox")
        window.maxYSpeedSpinbox.setObjectName("maxYSpeedSpinbox")
        window.maxZSpeedSpinbox.setObjectName("maxZSpeedSpinbox")

        window.applySpeedChangesButton = QtWidgets.QPushButton("Apply")
        window.applySpeedChangesButton.setObjectName("applySpeedChangesButton")

        layout.addRow("Max X Speed (mm/s)", window.maxXSpeedSpinbox)
        layout.addRow("Max Y Speed (mm/s)", window.maxYSpeedSpinbox)
        layout.addRow("Max Z Speed (mm/s)", window.maxZSpeedSpinbox)
        layout.addRow("", window.applySpeedChangesButton)
        return frame

    def _build_acceleration_frame(self, window):
        frame = QtWidgets.QFrame()
        layout = QtWidgets.QFormLayout(frame)

        window.maxXAccelerationSpinbox = QtWidgets.QDoubleSpinBox()
        window.maxYAccelerationSpinbox = QtWidgets.QDoubleSpinBox()
        window.maxZAccelerationSpinbox = QtWidgets.QDoubleSpinBox()
        window.maxXAccelerationSpinbox.setObjectName("maxXAccelerationSpinbox")
        window.maxYAccelerationSpinbox.setObjectName("maxYAccelerationSpinbox")
        window.maxZAccelerationSpinbox.setObjectName("maxZAccelerationSpinbox")

        window.applyAccelerationChangesButton = QtWidgets.QPushButton("Apply")
        window.applyAccelerationChangesButton.setObjectName("applyAccelerationChangesButton")

        layout.addRow("Max X Acceleration (mm/s)", window.maxXAccelerationSpinbox)
        layout.addRow("Max Y Acceleration (mm/s)", window.maxYAccelerationSpinbox)
        layout.addRow("Max Z Acceleration (mm/s)", window.maxZAccelerationSpinbox)
        layout.addRow("", window.applyAccelerationChangesButton)
        return frame

    def _build_jerk_frame(self, window):
        frame = QtWidgets.QFrame()
        layout = QtWidgets.QFormLayout(frame)

        window.doubleSpinBox_17 = QtWidgets.QDoubleSpinBox()
        window.doubleSpinBox_17.setObjectName("doubleSpinBox_17")
        window.maxYJerkSpinbox = QtWidgets.QDoubleSpinBox()
        window.maxYJerkSpinbox.setObjectName("maxYJerkSpinbox")
        window.maxZJerkSpinbox = QtWidgets.QDoubleSpinBox()
        window.maxZJerkSpinbox.setObjectName("maxZJerkSpinbox")

        # Preserve legacy odd object name from the .ui (this is a QLabel, not a spinbox).
        window.maxXJerkSpinbox = QtWidgets.QLabel("Max X Jerk (mm/s)")
        window.maxXJerkSpinbox.setObjectName("maxXJerkSpinbox")

        window.applyJerkChangesButton = QtWidgets.QPushButton("Apply")
        window.applyJerkChangesButton.setObjectName("applyJerkChangesButton")

        row = QtWidgets.QHBoxLayout()
        row.addWidget(window.maxXJerkSpinbox)
        row.addWidget(window.doubleSpinBox_17)
        layout.addRow(row)
        layout.addRow("Max Y Jerk (mm/s)", window.maxYJerkSpinbox)
        layout.addRow("Max Z Jerk (mm/s)", window.maxZJerkSpinbox)
        layout.addRow("", window.applyJerkChangesButton)
        return frame

    @staticmethod
    def _apply_styles(window):
        window.setStyleSheet(
            """
            QWidget {
                background: #f2f5f8;
                color: #1f2937;
                font-size: 12px;
            }
            QFrame#frame, QFrame#frame_2, QFrame#frame_3, QFrame#frame_4 {
                background: #ffffff;
                border: 1px solid #d5dbe3;
                border-radius: 10px;
            }
            QDoubleSpinBox {
                background: #ffffff;
                border: 1px solid #c9d3df;
                border-radius: 6px;
                padding: 4px;
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