from PyQt6 import QtWidgets


def apply_ui_polish(widget):
    """Apply lightweight visual and usability improvements without changing UI flow."""
    widget.setStyleSheet(
        """
        QWidget {
            color: #e6e8ee;
        }
        QMainWindow, QWidget#centralwidget, QTabWidget::pane, QFrame {
            background-color: #1f232a;
        }
        QTabBar::tab {
            padding: 4px 10px;
            border: 1px solid #4b5563;
            border-bottom: none;
            background: #262b33;
            color: #d9dde7;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background: #313845;
            color: #ffffff;
        }
        QPushButton {
            background-color: #2b313b;
            border: 1px solid #6b7280;
            border-radius: 4px;
            padding: 4px 10px;
            color: #f3f4f6;
        }
        QPushButton:hover {
            background-color: #374151;
            border-color: #9ca3af;
        }
        QPushButton:pressed {
            background-color: #1f2937;
            border-color: #d1d5db;
        }
        QPushButton:disabled {
            color: #8f96a3;
            border-color: #4b5563;
            background-color: #242933;
        }
        QLabel {
            font-weight: 400;
            color: #e5e7eb;
        }
        QLineEdit,
        QComboBox,
        QSpinBox,
        QDoubleSpinBox,
        QPlainTextEdit,
        QTextEdit {
            background-color: #171a20;
            border: 1px solid #6b7280;
            border-radius: 4px;
            padding-left: 2px;
            color: #f9fafb;
            selection-background-color: #3b82f6;
            selection-color: #ffffff;
        }
        QLineEdit:focus,
        QComboBox:focus,
        QSpinBox:focus,
        QDoubleSpinBox:focus,
        QPlainTextEdit:focus,
        QTextEdit:focus {
            border: 1px solid #60a5fa;
        }
        QHeaderView::section {
            background-color: #2b313b;
            color: #f3f4f6;
            border: 1px solid #4b5563;
            padding: 4px 6px;
            font-weight: 600;
        }
        QCheckBox,
        QRadioButton {
            spacing: 6px;
            color: #e5e7eb;
        }
        QCheckBox::indicator,
        QRadioButton::indicator {
            width: 14px;
            height: 14px;
            border: 1px solid #9ca3af;
            background: #111827;
        }
        QCheckBox::indicator:checked,
        QRadioButton::indicator:checked {
            background: #60a5fa;
            border: 1px solid #bfdbfe;
        }
        QTableWidget {
            gridline-color: #4b5563;
            alternate-background-color: #252b34;
            background-color: #181c23;
            color: #f3f4f6;
            border: 1px solid #4b5563;
        }
        QMenuBar, QMenu {
            background-color: #20252d;
            color: #e5e7eb;
            border: 1px solid #4b5563;
        }
    """
    )

    for spinbox in widget.findChildren(QtWidgets.QAbstractSpinBox):
        spinbox.setKeyboardTracking(False)
        spinbox.setAccelerated(True)

    def ensure_text_fits(control, extra_width=8):
        text = control.text().replace("&", "") if hasattr(control, "text") else ""
        if not text:
            return
        metrics = control.fontMetrics()
        required_width = metrics.horizontalAdvance(text) + extra_width
        required_height = metrics.height() + 6
        width = max(control.width(), required_width)
        height = max(control.height(), required_height)
        if width != control.width() or height != control.height():
            control.resize(width, height)

    for label in widget.findChildren(QtWidgets.QLabel):
        ensure_text_fits(label, extra_width=10)

    for button in widget.findChildren(QtWidgets.QPushButton):
        ensure_text_fits(button, extra_width=16)

    for check in widget.findChildren(QtWidgets.QCheckBox):
        ensure_text_fits(check, extra_width=26)

    for radio in widget.findChildren(QtWidgets.QRadioButton):
        ensure_text_fits(radio, extra_width=26)

    for table in widget.findChildren(QtWidgets.QTableWidget):
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)

    for tab_widget in widget.findChildren(QtWidgets.QTabWidget):
        tab_widget.setDocumentMode(True)
