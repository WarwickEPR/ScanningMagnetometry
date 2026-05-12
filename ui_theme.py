from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg


PLOT_BACKGROUND = "#f8fafc"
PLOT_FOREGROUND = "#5f6b7a"
PLOT_GRID = "#d8e1ea"
PLOT_BORDER = "#d5dbe3"
PLOT_PALETTE = [
    "#1f5a82",
    "#2ea043",
    "#e67e22",
    "#c0392b",
    "#0f8b8d",
    "#7c5cc4",
    "#d4a72c",
]


def configure_pyqtgraph_defaults():
    """Set global pyqtgraph defaults to match the app's light UI."""
    pg.setConfigOptions(
        antialias=True,
        background=PLOT_BACKGROUND,
        foreground=PLOT_FOREGROUND,
    )


def get_plot_pen(index=0, width=2, style=QtCore.Qt.PenStyle.SolidLine):
    color = PLOT_PALETTE[index % len(PLOT_PALETTE)]
    return pg.mkPen(color=color, width=width, style=style)


def style_plot_widget(plot_widget, show_grid=True):
    """Apply consistent axes, grid, and border styling to a PlotWidget."""
    plot_widget.setBackground(PLOT_BACKGROUND)
    plot_item = plot_widget.getPlotItem()
    view_box = plot_item.getViewBox()
    view_box.setBackgroundColor(PLOT_BACKGROUND)
    view_box.setBorder(pg.mkPen(PLOT_BORDER, width=1))
    if show_grid:
        plot_item.showGrid(x=True, y=True, alpha=0.35)

    axis_pen = pg.mkPen(PLOT_FOREGROUND, width=1)
    for axis_name in ("left", "bottom", "top", "right"):
        axis = plot_item.getAxis(axis_name)
        axis.setPen(axis_pen)
        axis.setTextPen(axis_pen)
        axis.setTickPen(axis_pen)


def style_plot_labels(plot_widget, **labels):
    """Apply axis labels using the shared plot foreground color."""
    label_style = {"color": PLOT_FOREGROUND, "font-size": "11pt"}
    for axis, text in labels.items():
        plot_widget.setLabel(axis=axis, text=text, **label_style)


def build_image_colormap():
    positions = [0.0, 0.18, 0.42, 0.68, 1.0]
    colors = [
        (14, 32, 52),
        (31, 90, 130),
        (44, 160, 143),
        (231, 180, 92),
        (250, 244, 230),
    ]
    return pg.ColorMap(positions, colors)


def style_image_view(image_view, show_colorbar=True):
    """Style an ImageView to match the light card layout."""
    image_view.view.setBackgroundColor(PLOT_BACKGROUND)
    image_view.view.setBorder(pg.mkPen(PLOT_BORDER, width=1))
    image_view.setColorMap(build_image_colormap())
    image_view.ui.roiBtn.hide()
    image_view.ui.menuBtn.hide()
    if show_colorbar:
        image_view.ui.histogram.show()
    else:
        image_view.ui.histogram.hide()


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
