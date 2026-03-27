from PyQt6 import QtWidgets


class DefaultParamWindowUIBuilder:
    """Programmatic UI builder for default parameter editor."""

    def setup(self, window: QtWidgets.QMainWindow):
        window.setObjectName("DefaultParamWindow")
        window.resize(360, 220)
        window.setWindowTitle("Default Parameters")

        window.centralwidget = QtWidgets.QWidget(window)
        window.centralwidget.setObjectName("centralwidget")
        window.setCentralWidget(window.centralwidget)

        root = QtWidgets.QVBoxLayout(window.centralwidget)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        card = QtWidgets.QFrame()
        card.setObjectName("defaultParamCard")
        form = QtWidgets.QFormLayout(card)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(8)

        window.liaDefaultIDTextBox = QtWidgets.QLineEdit()
        window.liaDefaultIDTextBox.setObjectName("liaDefaultIDTextBox")
        window.liaDefaultIPTextBox = QtWidgets.QLineEdit()
        window.liaDefaultIPTextBox.setObjectName("liaDefaultIPTextBox")
        window.RFDefaultIPTextBox = QtWidgets.QLineEdit()
        window.RFDefaultIPTextBox.setObjectName("RFDefaultIPTextBox")

        form.addRow("LIA Default ID", window.liaDefaultIDTextBox)
        form.addRow("LIA Default IP", window.liaDefaultIPTextBox)
        form.addRow("RF Control IP", window.RFDefaultIPTextBox)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch(1)
        window.applyParamsButton = QtWidgets.QPushButton("Apply")
        window.applyParamsButton.setObjectName("applyParamsButton")
        button_row.addWidget(window.applyParamsButton)
        button_row.addStretch(1)
        form.addRow(button_row)

        root.addWidget(card)
        root.addStretch(1)

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
            QFrame#defaultParamCard {
                background: #ffffff;
                border: 1px solid #d5dbe3;
                border-radius: 10px;
            }
            QLineEdit {
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