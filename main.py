# -*- coding: utf-8 -*-
"""Scanning Magnetometer main file

This module contains all the classes for the UI such as displaying graphs and opening new windows.
It also controls connections to the different equipment such as COM port serial connections and PyVisa connections. It
also controls the flow of data between these bits of equipment and sorts out the plotting/updating and save/export of
data.
"""

from PyQt6 import QtCore, QtWidgets, uic
import pyqtgraph as pg
import h5py
import cv2
import os
import copy
from PIL import Image
import sys
import serial
import serial.tools.list_ports
import numpy as np
import time
import traceback
import pyvisa
from sklearn.linear_model import LinearRegression
from scipy.signal import savgol_filter, find_peaks, peak_widths
import zhinst.utils as utils
import zhinst.core
import data_viewer
import default_param_window
import yaml
from threading_utils import Worker, WorkerSignals, ThreadedComponent
from stage_control import StageControl
from rf_control import RfControl
from lia_control import LIAControl
from paths import ui_file

# if dark theme is available then use by default
try:
    import qdarktheme
    dark_theme = True
except Exception as error:
    dark_theme = False


def apply_ui_polish(widget):
    """Apply lightweight visual and usability improvements without changing UI flow."""
    widget.setStyleSheet("""
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
    """)

    for spinbox in widget.findChildren(QtWidgets.QAbstractSpinBox):
        spinbox.setKeyboardTracking(False)
        spinbox.setAccelerated(True)

    def ensure_text_fits(control, extra_width=8):
        text = control.text().replace('&', '') if hasattr(control, 'text') else ''
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


class MainUI(QtWidgets.QMainWindow):
    """
    This is the main window class. All other windows with be children of this window. All class instances of
    connections to equipment are stored here as well.

    Attributes:
        stageController: stage controller class instance
        rfController: Microwave source class instance
        LIAController: Lock-In Amplifier class instance
        threadpool: QtThreadPool class instance for submitting multi-thread tasks - asynchronous processing

    """

    def __init__(self):
        super(MainUI, self).__init__()  # Call the inherited classes __init__ method
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.settings_file = os.path.join(self.base_dir, "configs", "settings.yml")
        self.fallback_config_file = os.path.join(self.base_dir, "configs", "default_config.yml")
        self.default_parameters = self._default_config_template()
        self.config_path = {'Config_Path': {'Path': self.fallback_config_file}}
        self.odmr_graph_window = None
        self.fft_graph_window = None
        self.vector_test_window = None
        self.scan_window = None
        self.a_matrix_values = copy.deepcopy(self.default_parameters['RF_Params']['A_Matrix_Values'])
        uic.loadUi(ui_file('scanning_magnetometer.ui'), self)  # Load the .ui file
        apply_ui_polish(self)
        self.setMinimumSize(980, 620)
        self.setWindowTitle("Scanning Magnetometer")
        self.show()  # Show the GUI

        self.stageController = StageControl(self, StageOptions)  # stage controller class instance
        self.rfController = RfControl(self)
        self.LIAController = LIAControl(self)

        # try loading default default_config.yml to set default values if it exists in directory
        try:
            with open(self.settings_file, "r") as f:
                self.config_path = yaml.safe_load(f)
            self.load_config(config_file_name=self.config_path.get('Config_Path', {}).get('Path', self.fallback_config_file))
        except Exception as error:
            print(error)
            self.load_config(config_file_name=self.fallback_config_file)


        # ------------------ UI elements are connected to their respective functions here ------------------ #
        #  stage ui controls
        self.connectStageButton.clicked.connect(
            lambda: self.stageController.connect_stage(self.comPortBox.currentText()))
        self.homeStageButton.clicked.connect(self.stageController.home_stage)
        self.setPositionButton.clicked.connect(lambda: self.stageController.set_stage_pos(self.xPosSpinBox.value(),
                                                                                          self.yPosSpinBox.value()))
        self.setStageHeightButton.clicked.connect(
            lambda: self.stageController.set_stage_height(self.zPosSpinBox.value()))
        
        self.getStagePositionButton.clicked.connect(self.stageController.get_stage_pos)
        self.actionChange_Max_Position_Values.triggered.connect(self.stageController.set_max_stage_position)
        self.actionDataViewer.triggered.connect(self.open_data_viewer)
        self.actionDefaultParameters.triggered.connect(self.open_default_param)
        self.actionLoadConfig.triggered.connect(self.load_config_button_selected)
        self.actionSaveConfig.triggered.connect(self.save_config)

        self.startScanButton.clicked.connect(self.open_scan_window)

        #  LIA ui controls
        self.connectLIAButton.clicked.connect(lambda: self.LIAController.thread_function(self.LIAController.connect_lia,
                                                                                         device_id=self.LIANameBox.text(),
                                                                                         device_ip=self.LIAIPBox.text(),
                                                                                         err_fn=self.show_error_message))
        self.takeFFTButton.clicked.connect(self.open_fft_graph)

        #  RF ui controls
        self.takeODMRButton.clicked.connect(self.open_odmr_graph)
        self.connectMWSourceButton.clicked.connect(
            lambda: self.rfController.thread_function(self.rfController.connect_rf,
                                                      self.MWSourceIPAddressBox.text(),
                                                      err_fn=self.show_error_message))
        self.togglePwrChk.stateChanged.connect(lambda: self.rfController.power_on_off(self.togglePwrChk.isChecked()))
        self.toggleModOnOff.stateChanged.connect(lambda: self.rfController.mod_on_off(self.toggleModOnOff.isChecked()))
        self.setFreqBtn.clicked.connect(self.rfController.set_freq)
        self.setPwrBtn.clicked.connect(self.rfController.set_power)
        self.applyModParamsButton.clicked.connect(self.rfController.set_mod_params)
        self.sineWaveRadio.setChecked(True)
        self.sineWaveRadio.toggled.connect(self.rfController.change_mod_type)
        self.squareWaveRadio.setChecked(False)
        self.squareWaveRadio.toggled.connect(self.rfController.change_mod_type)
        self.toggleExtModOnOff.stateChanged.connect(
            lambda: self.rfController.ext_mod_on_off(self.toggleExtModOnOff.isChecked()))

        self.setVectorMatrixButton.clicked.connect(self.set_vector_matrx)


        # debug buttons
        self.vectorTestButton.clicked.connect(self.vectorTest)


        try:
            ports = serial.tools.list_ports.comports()
            available_ports = []
            for port, desc, hwid in sorted(ports):
                available_ports.append("{}".format(port))
            test = self.comPortBox
            test.addItems(available_ports)
        except Exception as error:
            error_dialog = QtWidgets.QMessageBox(self)
            error_dialog.setText("ERROR: Could not populate COM port list")
            error_dialog.exec()
        # ------------------ UI ELEMENTS FINISH HERE ------------------ #

        # configure thread pool, needed to multi-threading and asynchronous processing
        self.threadpool = QtCore.QThreadPool()

        # can supress this printout to console to tell user how many threads are available - only really useful for
        # developers
        # print('max %d threads' % self.threadpool.maxThreadCount())
        return

    @staticmethod
    def _default_config_template():
        return {
            "Connection_Params": {
                "Device_ID": "dev7811",
                "Device_IP": "192.168.1.101",
                "RF_IP": "192.168.1.2"
            },
            "Stage_Params": {
                "Avg_Time": "0.1",
                "Dwell": "0.05",
                "X_End": "20",
                "X_Start": "10",
                "X_Step": "1",
                "Y_End": "20",
                "Y_Start": "10",
                "Y_Step": "1"
            },
            "Sweep_Params": {
                "Dwell": "3.0",
                "Points": "1000",
                "Sweep_End": "3.0",
                "Sweep_Start": "2.7",
                "Sweep_Step": "250",
                "Sweep_Type": "1"
            },
            "RF_Params": {
                "Ext_Mod": "False",
                "Feedback_Freq_Table": [[2.71, 2.72, 2.73, 2.74], [0.1, 0.1, 0.1, 0.1]],
                "A_Matrix_Values": [[1, 1, 1], [1, 1, 1], [1, 1, 1], [1, 1, 1]],
                "Freq": "2.75",
                "Mod_Amp": "2.8",
                "Mod_Freq": "3.05",
                "Mod_On": "True",
                "Mod_Type": "1",
                "Power": "-30",
                "Power_On": "False"
            },
            "LIA_Params": {
                "Burst_Dur": "0.005",
                "Duration": "10",
                "FFT_50_Ohm": "False",
                "FFT_AC_Coupling": "False",
                "FFT_Average": "5",
                "FFT_Duration": "1",
                "FFT_Sample_Rate": "2048",
                "Filter_Order": "7",
                "Range": "0",
                "Sample_Rate": "50",
                "Scaling": "750",
                "Time_Const": "600"
            }
        }

    def show_error_message(self, error):
        """ Displays pop up error message for try and except statements. Pass Exception as "error" parameter to display
        error to user if printing to console is not possible (i.e in a binary release.)

        :param error: Exception class - pass in the error from a try/except statement
        :return:
        """
        error_dialog = QtWidgets.QErrorMessage(self)
        error_dialog.showMessage(str(error[1]))
        return

    def closeEvent(self, event):
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Exit Scanning Magnetometer",
            "Are you sure you want to close the program?\nThis will stop and close all open windows.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )

        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            event.ignore()
            return

        for widget in QtWidgets.QApplication.topLevelWidgets():
            if widget is not self:
                widget.close()

        event.accept()
        QtWidgets.QApplication.quit()

    def vectorTest(self):
        """debug function of testing the vector measurment capabilites - should normally be disabled in the binary
        release

        :return:
        """
        self.vector_test_window = VectorTest()  # instantiate the vector test window
        return

    def open_fft_graph(self):
        """ Opens the fast Fourier transform window for sensitivity measurements"""
        self.fft_graph_window = FFTGraphWindow()

    def open_odmr_graph(self):
        """ Opens the ODMR graph window for ODMR sweeps and fitting parameters"""
        window.takeODMRButton.setEnabled(False)  # stops multiple windows being opened and causing strangness occuring
        self.odmr_graph_window = ODMRGraphWindow()

    def open_scan_window(self):
        """ Opens the scan window which shows any feedback/vector tracking graphs as well as showing a real-time image
        of the current scan.
        """
        self.scan_window = scanningImageWindow()

    def open_data_viewer(self):
        self.data_viewer_window = data_viewer.DataViewer()
        return

    def set_vector_matrx(self):
        self.vector_matrix_window = VectorMatrixWindow()
        return

    def open_default_param(self):
        filepath = QtWidgets.QFileDialog.getOpenFileName(self, 'Select File', filter="yml (*.yml)")[0]
        if not filepath:
            return
        new_settings = self.config_path
        new_settings['Config_Path']['Path'] = str(filepath)
        with open(self.settings_file, 'w') as f:
            yaml.dump(new_settings, f, default_flow_style=False)
        self.config_path = new_settings
        return

    def load_config_button_selected(self):
        filepath = QtWidgets.QFileDialog.getOpenFileName(self, 'Select File', filter="yml (*.yml)")[0]
        self.load_config(config_file_name=filepath)

    def load_config(self, config_file_name=None):
        loaded = False
        candidate_paths = []
        if config_file_name:
            candidate_paths.append(config_file_name)
        candidate_paths.append(self.fallback_config_file)
        for path in candidate_paths:
            try:
                with open(path, "r") as f:
                    params = yaml.safe_load(f) or {}
                if isinstance(params, dict) and params:
                    self.default_parameters = params
                    loaded = True
                    break
            except Exception as error:
                print(error)

        if not loaded:
            self.default_parameters = self._default_config_template()

        try:
            # set connection default values
            self.LIAIPBox.setText(self.default_parameters['Connection_Params']['Device_IP'])
            self.LIANameBox.setText(self.default_parameters['Connection_Params']['Device_ID'])
            self.MWSourceIPAddressBox.setText(self.default_parameters['Connection_Params']['RF_IP'])

            #set stage scanning parameter values
            self.scanAveragingTimeSpinBox.setValue(float(self.default_parameters['Stage_Params']['Avg_Time']))
            self.scanDwellTimeSpinBox.setValue(float(self.default_parameters['Stage_Params']['Dwell']))
            self.xEndSpinBox.setValue(float(self.default_parameters['Stage_Params']['X_End']))
            self.xStartSpinBox.setValue(float(self.default_parameters['Stage_Params']['X_Start']))
            self.xStepSpinBox.setValue(float(self.default_parameters['Stage_Params']['X_Step']))
            self.yEndSpinBox.setValue(float(self.default_parameters['Stage_Params']['Y_End']))
            self.yStartSpinBox.setValue(float(self.default_parameters['Stage_Params']['Y_Start']))
            self.yStepSpinBox.setValue(float(self.default_parameters['Stage_Params']['Y_Step']))

            # set odmr sweep params
            self.startFreqBox.setValue(float(self.default_parameters['Sweep_Params']['Sweep_Start']))
            self.endFreqBox.setValue(float(self.default_parameters['Sweep_Params']['Sweep_End']))
            self.dwellTimeBox.setValue(float(self.default_parameters['Sweep_Params']['Dwell']))
            self.stepSizeBox.setValue(float(self.default_parameters['Sweep_Params']['Sweep_Step']))
            self.pointsBox.setValue(int(self.default_parameters['Sweep_Params']['Points']))
            self.sweepDefBox.setCurrentIndex(int(self.default_parameters['Sweep_Params']['Sweep_Type']))

            #set rf source params
            self.freqBox.setValue(float(self.default_parameters['RF_Params']['Freq']))
            self.pwrBox.setValue(float(self.default_parameters['RF_Params']['Power']))
            self.togglePwrChk.setChecked(eval(self.default_parameters['RF_Params']['Power_On']))
            self.modFreqSpinBox.setValue(float(self.default_parameters['RF_Params']['Mod_Freq']))
            self.modAmpSpinBox.setValue(float(self.default_parameters['RF_Params']['Mod_Amp']))

            self.toggleModOnOff.setChecked(eval(self.default_parameters['RF_Params']['Mod_On']))
            self.toggleExtModOnOff.setChecked(eval(self.default_parameters['RF_Params']['Ext_Mod']))
            self.a_matrix_values = self.default_parameters['RF_Params']['A_Matrix_Values']



            freqs = []
            grads = []
            for i in self.default_parameters['RF_Params']['Feedback_Freq_Table'][0]:
                    freqs.append(float(i))
            for i in self.default_parameters['RF_Params']['Feedback_Freq_Table'][1]:
                    grads.append(float(i))
            self.scanODMRPropertiesTable.setRowCount(0)
            for row in range(len(freqs)):
                self.scanODMRPropertiesTable.insertRow(row)
                self.scanODMRPropertiesTable.setItem(row, 0,
                                                       QtWidgets.QTableWidgetItem(str(freqs[row])))
                self.scanODMRPropertiesTable.setItem(row, 1,
                                                       QtWidgets.QTableWidgetItem(str(grads[row])))

            # set lia params
            self.odmrAqDurBox.setValue(int(self.default_parameters['LIA_Params']['Duration']))
            self.odmrAqBurstDurBox.setValue(float(self.default_parameters['LIA_Params']['Burst_Dur']))
            self.odmrAqSampleRateBox.setValue(int(self.default_parameters['LIA_Params']['Sample_Rate']))
            self.scalingFactorSpinBox.setValue(int(self.default_parameters['LIA_Params']['Scaling']))
            self.timeConstantSpinBox.setValue(int(self.default_parameters['LIA_Params']['Time_Const']))
            self.rangeSelect.setCurrentIndex(int(self.default_parameters['LIA_Params']['Range']))
            self.harmonicOrderSelect.setCurrentIndex(int(self.default_parameters['LIA_Params']['Filter_Order']))
            self.fftAverageSpinBox.setValue(int(self.default_parameters['LIA_Params']['FFT_Average']))
            self.fftDurationSpinBox.setValue(int(self.default_parameters['LIA_Params']['FFT_Duration']))
            self.sampleRateSpinBox.setValue(int(self.default_parameters['LIA_Params']['FFT_Sample_Rate']))
            self.acCoupleCheck.setChecked(eval(self.default_parameters['LIA_Params']['FFT_AC_Coupling']))
            self.fiftyOhmCheck.setChecked(eval(self.default_parameters['LIA_Params']['FFT_50_Ohm']))
        except Exception as error:
            print(error)
        return

    def save_config(self):
        if not isinstance(self.default_parameters, dict) or not self.default_parameters:
            self.default_parameters = self._default_config_template()

        new_config = copy.deepcopy(self.default_parameters)
        # set connection default values
        new_config['Connection_Params']['Device_IP'] = str(self.LIAIPBox.text())
        new_config['Connection_Params']['Device_ID'] = str(self.LIANameBox.text())
        new_config['Connection_Params']['RF_IP'] = str(self.MWSourceIPAddressBox.text())

        #set stage scanning parameter values
        new_config['Stage_Params']['Avg_Time'] = str(self.scanAveragingTimeSpinBox.value())
        new_config['Stage_Params']['Dwell'] = str(self.scanDwellTimeSpinBox.value())
        new_config['Stage_Params']['X_End'] = str(self.xEndSpinBox.value())
        new_config['Stage_Params']['X_Start'] = str(self.xStartSpinBox.value())
        new_config['Stage_Params']['X_Step'] = str(self.xStepSpinBox.value())
        new_config['Stage_Params']['Y_End'] = str(self.yEndSpinBox.value())
        new_config['Stage_Params']['Y_Start'] = str(self.yStartSpinBox.value())
        new_config['Stage_Params']['Y_Step'] = str(self.yStepSpinBox.value())

        # set odmr sweep params
        new_config['Sweep_Params']['Sweep_Start'] = str(self.startFreqBox.value())
        new_config['Sweep_Params']['Sweep_End'] = str(self.endFreqBox.value())
        new_config['Sweep_Params']['Dwell'] = str(self.dwellTimeBox.value())
        new_config['Sweep_Params']['Sweep_Step'] = str(self.stepSizeBox.value())
        new_config['Sweep_Params']['Points'] = str(self.pointsBox.value())
        new_config['Sweep_Params']['Sweep_Type'] = str(self.sweepDefBox.currentIndex())

        # set rf source params
        new_config['RF_Params']['Freq'] = str(self.freqBox.value())
        new_config['RF_Params']['Power'] = str(self.pwrBox.value())
        new_config['RF_Params']['Power_On'] = str(self.togglePwrChk.isChecked())
        new_config['RF_Params']['Mod_Freq'] = str(self.modFreqSpinBox.value())
        new_config['RF_Params']['Mod_Amp'] = str(self.modAmpSpinBox.value())
        new_config['RF_Params']['Mod_On'] = str(self.toggleModOnOff.isChecked())
        new_config['RF_Params']['Ext_Mod'] = str(self.toggleExtModOnOff.isChecked())
        new_config['RF_Params']['A_Matrix_Values'] = self.a_matrix_values



        freqs = []
        grads = []
        for i in range(4):
            try:
                freqs.append(float(self.scanODMRPropertiesTable.item(i, 0).text()))
                grads.append(float(
                    self.scanODMRPropertiesTable.item(i, 1).text()))  # gradient used for feedback with vector
            except Exception as error:
                # if table element is empty, skip it
                print(error)
        new_config['RF_Params']['Feedback_Freq_Table'] = [freqs, grads]

        new_config['LIA_Params']['Duration'] = str(self.odmrAqDurBox.value())

        new_config['LIA_Params']['Burst_Dur'] = str(self.odmrAqBurstDurBox.value())
        new_config['LIA_Params']['Sample_Rate'] = str(self.odmrAqSampleRateBox.value())
        new_config['LIA_Params']['Scaling'] = str(self.scalingFactorSpinBox.value())
        new_config['LIA_Params']['Time_Const'] = str(self.timeConstantSpinBox.value())
        new_config['LIA_Params']['Range'] = str(self.rangeSelect.currentIndex())
        new_config['LIA_Params']['Filter_Order'] = str(self.harmonicOrderSelect.currentIndex())
        new_config['LIA_Params']['FFT_Average'] = str(self.odmrAqDurBox.value())
        new_config['LIA_Params']['FFT_Duration'] = str(self.fftAverageSpinBox.value())
        new_config['LIA_Params']['FFT_Sample_Rate'] = str(self.fftDurationSpinBox.value())
        new_config['LIA_Params']['FFT_AC_Coupling'] = str(self.acCoupleCheck.isChecked())
        new_config['LIA_Params']['FFT_50_Ohm'] = str(self.fiftyOhmCheck.isChecked())

        default_save_path = os.path.join(self.base_dir, "configs", "config.yml")
        filepath = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Select File',
            default_save_path,
            filter="YAML Files (*.yml *.yaml)"
        )[0]
        if not filepath:
            return
        if not filepath.lower().endswith(('.yml', '.yaml')):
            filepath = f"{filepath}.yml"
        with open(filepath, 'w') as f:
            yaml.dump(new_config, f, default_flow_style=False)
        self.default_parameters = new_config
        return

class VectorMatrixWindow(QtWidgets.QWidget):
    def __init__(self):
        super(VectorMatrixWindow, self).__init__()
        uic.loadUi(ui_file('vectorMatrixWindow.ui'), self)  # Load the .ui file
        apply_ui_polish(self)
        self.show()

        self.applyChangesButton.clicked.connect(self.apply_changes)

        self.df1dbx.setValue(window.a_matrix_values[0][0])
        self.df1dby.setValue(window.a_matrix_values[0][1])
        self.df1dbz.setValue(window.a_matrix_values[0][2])

        self.df2dbx.setValue(window.a_matrix_values[1][0])
        self.df2dby.setValue(window.a_matrix_values[1][1])
        self.df2dbz.setValue(window.a_matrix_values[1][2])

        self.df3dbx.setValue(window.a_matrix_values[2][0])
        self.df3dby.setValue(window.a_matrix_values[2][1])
        self.df3dbz.setValue(window.a_matrix_values[2][2])

        self.df3dbx.setValue(window.a_matrix_values[3][0])
        self.df3dby.setValue(window.a_matrix_values[3][1])
        self.df3dbz.setValue(window.a_matrix_values[3][2])

    def apply_changes(self):
        window.a_matrix_values[0][0] = float(self.df1dbx.value())
        window.a_matrix_values[0][1] = float(self.df1dby.value())
        window.a_matrix_values[0][2] = float(self.df1dbz.value())

        window.a_matrix_values[1][0] = float(self.df2dbx.value())
        window.a_matrix_values[1][1] = float(self.df2dby.value())
        window.a_matrix_values[1][2] = float(self.df2dbz.value())

        window.a_matrix_values[2][0] = float(self.df3dbx.value())
        window.a_matrix_values[2][1] = float(self.df3dby.value())
        window.a_matrix_values[2][2] = float(self.df3dbz.value())

        window.a_matrix_values[3][0] = float(self.df4dbx.value())
        window.a_matrix_values[3][1] = float(self.df4dby.value())
        window.a_matrix_values[3][2] = float(self.df4dbz.value())

class VectorTest(QtWidgets.QWidget, ThreadedComponent):
    """ Debug vector test window
    This is used for debugging and testing the vector measurement and tracking capabilities of the system. Not for use
    by the end user. The button to open this window is and will be disabled in binary releases.

    Attributes:
        graphWidget: 1D line plotting widget
        graphWidget_2: 1D line plotting widget
        vc1: pyqtgraph.PlotItem.plot() function
        vc2: pyqtgraph.PlotItem.plot() function
        vc3: pyqtgraph.PlotItem.plot() function
        vc4: pyqtgraph.PlotItem.plot() function
        fc1: pyqtgraph.PlotItem.plot() function
        fc2: pyqtgraph.PlotItem.plot() function
        fc3: pyqtgraph.PlotItem.plot() function
        fc4: pyqtgraph.PlotItem.plot() function
    """

    def __init__(self):
        # load the UI for the vector test window
        super(VectorTest, self).__init__()
        uic.loadUi(ui_file('vectorTestWindow.ui'), self)  # Load the .ui file
        apply_ui_polish(self)
        self.show()
        self.scanning = True  # when set to false it will stop threading the function

        # configure the layout of the axes for the two graphs
        self.graphWidget.setLabel(axis='left', text='RF Frequency (GHz)')
        self.graphWidget.setLabel(axis='bottom', text='Index')
        self.graphWidget.setLabel(axis='top', text='RF Frequency Shift (GHz)')
        self.graphWidget_2.setLabel(axis='left', text='Voltage (V)')
        self.graphWidget_2.setLabel(axis='bottom', text='Index')
        self.graphWidget_2.setLabel(axis='top', text='Measured Voltage (V)')

        # calls pyqtgraph.PlotItem.plot() and creates a new plot window showing the data (which to start with is empty)
        self.vc1 = self.graphWidget.plot()
        self.vc2 = self.graphWidget.plot()
        self.vc3 = self.graphWidget.plot()
        self.vc4 = self.graphWidget.plot()

        self.fc1 = self.graphWidget_2.plot()
        self.fc2 = self.graphWidget_2.plot()
        self.fc3 = self.graphWidget_2.plot()
        self.fc4 = self.graphWidget_2.plot()

        self.vector_freqs = []
        self.vector_grads = []
        for i in range(4):
            try:
                self.vector_freqs.append(float(window.scanODMRPropertiesTable.item(i, 0).text()))
                self.vector_grads.append(float(
                    window.scanODMRPropertiesTable.item(i, 1).text()))  # gradient used for feedback with vector
            except:
                # if table element is empty, skip it
                pass

        # starts the multi-thread for the vector feedback - prevents other ui elements and calculations being
        # interrupted
        self.thread_function(self.initialise_vector_feedback, err_fn=window.show_error_message, prg_fn=self.debug_plot)

        # initial starting frequencies to use for vector tracking/measurements - change these to the desired values
        # f1 = 2.7766
        # f2 = 2.7940
        # f3 = 2.8259
        # f4 = 2.8505  # GHz
        #
        # # the ODMR gradients (i.e. calibration constants or feedback "strength") for each of the respective four
        # # frequencies being used.
        # c1 = 0.3  # V/MHz
        # c2 = 0.3
        # c3 = 0.3
        # c4 = 0.3



        # # saving the sets of frequencies and their respective gradients to separate lists to iterate over later
        # self.vector_freqs = [f1, f2, f3, f4]
        # self.vector_grads = [c1, c2, c3, c4]

        return

    def initialise_vector_feedback(self, *args, **kwargs):
        """ Starts the vector feedback to keep adjusting the microwave frequencies for 4 ODMR peaks to allow for
        calculation of the magnetic field vector

        :param args:
        :param kwargs: contains the callback to emit the signal to execute the progress function given to the
                        thread_function
        :return:
        """
        ini_voltage = []

        scale = 750  # Scale set on the lock-in, the outputted data isn't scaled so need to do this manually afterward.

        #  iterate through the starting frequency list, set the RF source to that value and get the voltage value
        # this will be used as the set-point for the feedback, these are appended to list ini_voltage
        for i in range(len(self.vector_freqs)):
            window.rfController.inst.write('FREQ ' + str(round(float(self.vector_freqs[i]) * 1e9, 12)))
            time.sleep(1)
            sample = window.LIAController.daq.getSample("/%s/demods/0/sample" % window.LIAController.device)
            ini_voltage.append(sample['x'][0] * scale)
        self.feedback_started = True  # check if the feedback is on or off and stop the thread if set to false
        df_arr = [[], [], [], []]
        dV_arr = [[], [], [], []]
        res_freq_arr = [[], [], [], []]
        last_emit = 0.0
        loop = 0
        while self.scanning:
            loop += 1
            # iterate over the 4 freqs in the list and calculate the difference between the voltage now and its
            # respective set-point voltage. This difference in voltage, along with the given calib const. (V/MHz) is
            # used to calculate the field vectors.
            for i in range(len(self.vector_freqs)):
                window.rfController.inst.write('FREQ ' + str(round(float(self.vector_freqs[i]) * 1e9, 12)))

                time.sleep(0.08)  # wait for LIA to calm down after changing RF frequency before measuring voltage
                sample = window.LIAController.daq.getSample("/%s/demods/0/sample" % window.LIAController.device)
                voltage_now = sample['x'][0] * scale  # Scale the LIA output to match the measured calib. constants.
                self.dV = voltage_now - ini_voltage[i]
                self.df = (1 / self.vector_grads[i]) * (-self.dV)  # freq. shift in MHz
                self.vector_freqs[i] = self.vector_freqs[i] + self.df / 1e3
                # append results to list for plotting to graphs later
                df_arr[i].append(self.df)
                dV_arr[i].append(self.dV)
                res_freq_arr[i].append(self.vector_freqs[i])

            # if the lists get longer than 100 elements, start removing the last element before plotting - gives a
            # scrolling graph effect for longer scans, prevents excessive "bunching up" of data on the graph.
            if len(df_arr[0]) > 100:
                for i in range(len(self.vector_freqs)):
                    df_arr[i].pop(0)
                    dV_arr[i].pop(0)
                    res_freq_arr[i].pop(0)
            # trying to iterate this while loop to fast while plotting causes the software to crash -
            # needs a workaround - using a 100 ms sleep to prevent this at the moment
            time.sleep(0.1)
            now = time.monotonic()
            if now - last_emit >= 0.1:
                kwargs['progress_callback'].emit([res_freq_arr, dV_arr])  # update the graphs
                last_emit = now
        return

    def debug_plot(self, arrs):
        """ Updates the debug plots for the measured voltage and frequencies - useful to see how they change over time
        to know if the tracking has lost its lock or not, for example.

        :param arrs: Lists of the measured voltage and frequencies over time to plot to the debug graph widgets
        :return:
        """
        self.vc1.setData(arrs[0][0], pen=pg.mkPen('b'))
        self.vc2.setData(arrs[0][1], pen=pg.mkPen('g'))
        self.vc3.setData(arrs[0][2], pen=pg.mkPen('r'))
        self.vc4.setData(arrs[0][3], pen=pg.mkPen('y'))

        self.fc1.setData(arrs[1][0], pen=pg.mkPen('b'))
        self.fc2.setData(arrs[1][1], pen=pg.mkPen('g'))
        self.fc3.setData(arrs[1][2], pen=pg.mkPen('r'))
        self.fc4.setData(arrs[1][3], pen=pg.mkPen('y'))
        return

    def closeEvent(self, event):
        """this function executes when the vector debug graph window closes, used to stop thread
        :param event:
        :return:
        """
        self.scanning = False  # stops the while loop in initialise_vector_feedback and finishes/kills the thread.


class StageOptions(QtWidgets.QWidget):
    def __init__(self):
        super(StageOptions, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi(ui_file('stage_options.ui'), self)  # Load the .ui file
        apply_ui_polish(self)
        self.show()

    def apply_position_changes(self):
        return

    def apply_speed_changes(self):
        return

    def apply_acceleration_changes(self):
        return

    def apply_jerk_changes(self):
        return


class FFTGraphWindow(QtWidgets.QWidget, ThreadedComponent):
    """ Opens a new window with a log-log graph showing the FFTs taken from the LIA. This is for measuring the
    magnetometer sensitivity

    Attributes:
        fft_plot : pyqt.PlotItem
        x : x data - probably frequency
        y : y data - Power spectral density (V/sqrt(Hz))
        scaled_y : The y values after applying the scaling of the LIA
        calib_const : The V/MHz value to use when converting the measured voltage from the LIA to a nano-tesla value
        graphWidget : pyqtgraph.PlotItem

    """
    def __init__(self):
        super().__init__()
        super(FFTGraphWindow, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi(ui_file('FFTGraphWindow.ui'), self)  # Load the .ui file
        apply_ui_polish(self)
        self.show()
        self.samples = None
        self.fft_plot = None
        self.x = None
        self.y = None
        self.scaled_y = None
        self.calib_const = 1

        #Set up of UI elements
        self.graphWidget.setLabel(axis='left', text='Power Spectral Density nT/sqrt(Hz)')
        self.graphWidget.setLabel(axis='bottom', text='Frequency Hz')

        self.calcSensButton.clicked.connect(lambda: self.calc_sens(freq_start=self.minFreqSpinBox.value(),
                                                                   freq_end=self.maxFreqSpinBox.value(),
                                                                   ignore_freqs=self.ignoreListFreqCheckBox.isChecked()))

        self.addFreqButton.clicked.connect(
            lambda: self.add_ignore_freq(self.freqStartSpinBox.value(), self.freqEndSpinBox.value()))

        self.odmrGradientSpinBox.valueChanged.connect(lambda: self.dummy_data(
            calib_const=self.odmrGradientSpinBox.value()))

        # Start threading of the take_fft function
        self.thread_function(self.take_fft,
                             progress_callback=None)
        return

    def take_fft(self, *args, **kwargs):
        """ Begins setting up the LIA for measuring the signal and performing the calculations to get the
        power spectral density as well removing unwanted signals and measuring the average noise floor.

        :param args:
        :param kwargs:
        :return:
        """
        self.worker_running = True  # this will stop the thread when its finished or if the ODMR window closes
        window.LIAController.fft_sweep = True
        window.LIAController.setup_fft()
        window.LIAController.daq_module.execute()
        self.samples = []
        while not window.LIAController.daq_module.finished():
            data_read = window.LIAController.daq_module.read(True)
            returned_signal_paths = [
                signal_path.lower() for signal_path in data_read.keys()
            ]
            for signal_path in window.LIAController.signal_paths:
                if signal_path.lower() in returned_signal_paths:
                    # Loop over all the bursts for the subscribed signal. More than
                    # one burst may be returned at a time, in particular if we call
                    # read() less frequently than the burst_duration.
                    for index, signal_burst in enumerate(data_read[signal_path.lower()]):
                        self.samples.append(signal_burst['value'][0])
                        bin_resolution = signal_burst['header']['gridcoldelta']
                        window.LIAController.data[signal_path].append(signal_burst)
                else:
                    # Note: If we read before the next burst has finished, there may be no new data.
                    # No action required.
                    pass
        window.LIAController.daq_module.finish()
        window.LIAController.daq_module.unsubscribe('*')

        self.worker_running = False
        avg_sample = ((np.sum(self.samples, axis=0)) / window.LIAController.count) * window.LIAController.scaling_Factor
        bin_count = len(avg_sample)
        frequencies = np.arange(0, bin_count)
        amplitude_spectral_density = (avg_sample * np.sqrt(window.LIAController.fft_duration)) * (
                1 / (28e-6 * self.calib_const))
        self.y = amplitude_spectral_density
        self.scaled_y = self.y
        self.x = frequencies
        self.dummy_data(calib_const=self.calib_const)
        window.LIAController.fft_sweep = False
        return

    def add_ignore_freq(self, freq_start, freq_end):
        """ Will add freq. values to the "ignoreFrequencyList" which will be used to remove the signals in the
        frequency range between freq_start and freq_end. Useful when calculating the noise floor, but you want to
        ignore known signals like the 50 Hz mains signal.

        :param freq_start: (float) Ignore data from this start point
        :param freq_end:  (float) Ignore data up to this end point
        :return:
        """
        row_pos = self.ignoreFrequencyList.rowCount()
        self.ignoreFrequencyList.insertRow(row_pos)
        self.ignoreFrequencyList.setItem(row_pos, 0, QtWidgets.QTableWidgetItem(str(freq_start)))
        self.ignoreFrequencyList.setItem(row_pos, 1, QtWidgets.QTableWidgetItem(str(freq_end)))
        return

    def calc_sens(self, freq_start=10, freq_end=100, ignore_freqs=False):
        """ Uses the mean average value between the freq_start and freq_end values (in Hz). If ignore_freqs is true then
        data in the freqs range shown in the ignoreFrequencyList, is ignored when calculating the mean average.

        :param freq_start: (float) Ignore data from this start point
        :param freq_end:  (float) Ignore data up to this end point
        :param ignore_freqs: (bool) If true, ignore data between frequency ranges in the ignoreFrequencyList
        :return:
        """
        self.calib_const = float(self.odmrGradientSpinBox.value())
        if ignore_freqs == True:
            freq_start = freq_start  # convert khz to hz
            freq_end = freq_end  # convert khz to hz
            ignore_freqs_range_idxs = []

            # clip frequency data to the selected range
            idx_min_start = np.abs(self.x - freq_start).argmin()  # find closest value idx of min freq
            idx_max_end = np.abs(self.x - freq_end).argmin()  # find closest value idx of max freq

            top_end = np.arange(0, idx_min_start + 1, 1, dtype=int)
            for i in range(len(top_end)):
                ignore_freqs_range_idxs.append(top_end[i])
            tail_end = np.arange(idx_max_end + 1, len(self.x), 1, dtype=int)
            for row in range(self.ignoreFrequencyList.rowCount()):
                try:
                    ignore_min_freq = (int(self.ignoreFrequencyList.item(row, 0).text()))
                    ignore_max_freq = (int(self.ignoreFrequencyList.item(row, 1).text()))
                    idx_min = np.abs(self.x - ignore_min_freq).argmin()
                    idx_max = (np.abs(self.x - ignore_max_freq)).argmin()
                    idx_range = np.arange(idx_min, idx_max + 1, 1, dtype=int)
                    for i in range(len(idx_range)):
                        ignore_freqs_range_idxs.append(idx_range[i])
                except Exception as error:
                    # probably will fail if empty rows are left in the table, this just ignores them but will print error to console incase its another issue
                    print(error, "This is probably fine if its a text error")
                    pass
            for i in range(len(tail_end)):
                ignore_freqs_range_idxs.append(tail_end[i])

            mask = np.ones_like(self.x, dtype=bool)
            mask[ignore_freqs_range_idxs] = False
            mean_sens = round(np.mean(self.scaled_y[mask]), 4)

            self.meanSensLabel.setText(str(mean_sens))
        else:
            mean_sens = round(np.mean(self.scaled_y), 4)
            self.meanSensLabel.setText(str(mean_sens))
        # print(mean_sens) # mean sens value

    def dummy_data(self, calib_const=1):
        """ Plots the data to the FFT graph - should probably rename from "dummy_data"

        :param calib_const: (float) Used to convert from volts to tesla value
        :return:
        """
        self.scaled_y = self.y
        try:
            self.fft_plot.clear()
        except:
            pass
        self.fft_plot = self.graphWidget.plot(self.x, self.scaled_y)
        self.graphWidget.setLogMode(True, True)
        return


class ODMRGraphWindow(QtWidgets.QWidget, ThreadedComponent):
    def __init__(self, *args, **kwargs):
        super(ODMRGraphWindow, self).__init__(*args, **kwargs)  # Call the inherited classes __init__ method
        uic.loadUi(ui_file('ODMRGraphWindow.ui'), self)  # Load the .ui file
        apply_ui_polish(self)
        self.show()

        # configure two y axis plot

        self.p1 = self.graphWidget.plotItem
        self.p1.setLabels(left='Voltage (V)')
        self.p1.setLabels(bottom='Frequency (GHz)')

        self.p2 = pg.ViewBox()
        self.p1.showAxis('right')
        self.p1.scene().addItem(self.p2)
        self.p1.getAxis('right').linkToView(self.p2)
        self.p2.setXLink(self.p1)
        self.p1.getAxis('right').setLabel('dV/df (V/MHz)', color='#0000ff')

        self.p1.vb.sigResized.connect(self.updateViews)

        self.odmr_plot = None
        self.odmr_deriv_plot = None
        self.odmr_cont = None
        self.odmr_linear_region_plot = None
        self.linear_region_list = None
        self.MainWindow = window
        self.worker_running = False
        self.x = None
        self.y = None
        self._last_fit_time = 0.0
        self._hovered_linear_row = None
        self._linear_region_default_pen = pg.mkPen(color=(255, 0, 0), width=5)
        self._linear_region_hover_pen = pg.mkPen(color=(255, 215, 0), width=7)

        self.linearRegionTable.setMouseTracking(True)
        self.linearRegionTable.viewport().setMouseTracking(True)
        self.linearRegionTable.cellEntered.connect(self.on_linear_region_table_hover)
        self.linearRegionTable.viewport().installEventFilter(self)

        self.odmrRegionFitBox.valueChanged.connect(lambda: self.fit_linear_region(self.x, self.y,
                                                                                  self.odmrRegionFitBox.value(),
                                                                                  plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                                                                  denoise=self.smoothingCheckBox.isChecked(),
                                                                                  window_length=self.smoothWindowBox.value(),
                                                                                  polyorder=self.polyorderSpinBox.value(),
                                                                                  peak_height=self.peakHeightSpinBox.value(),
                                                                                  peak_distance=self.peakDistanceSpinBox.value(),
                                                                                  peak_prom=self.peakPromSpinBox.value(),
                                                                                  ))
        self.showDerivativeCheckbox.stateChanged.connect(lambda: self.fit_linear_region(self.x, self.y,
                                                                                        self.odmrRegionFitBox.value(),
                                                                                        plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                                                                        denoise=self.smoothingCheckBox.isChecked(),
                                                                                        window_length=self.smoothWindowBox.value(),
                                                                                        polyorder=self.polyorderSpinBox.value(),
                                                                                        peak_height=self.peakHeightSpinBox.value(),
                                                                                        peak_distance=self.peakDistanceSpinBox.value(),
                                                                                        peak_prom=self.peakPromSpinBox.value(),
                                                                                        ))
        self.smoothingCheckBox.stateChanged.connect(lambda: self.fit_linear_region(self.x, self.y,
                                                                                   self.odmrRegionFitBox.value(),
                                                                                   plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                                                                   denoise=self.smoothingCheckBox.isChecked(),
                                                                                   window_length=self.smoothWindowBox.value(),
                                                                                   polyorder=self.polyorderSpinBox.value(),
                                                                                   peak_height=self.peakHeightSpinBox.value(),
                                                                                   peak_distance=self.peakDistanceSpinBox.value(),
                                                                                   peak_prom=self.peakPromSpinBox.value(),
                                                                                   ))

        self.polyorderSpinBox.valueChanged.connect(lambda: self.fit_linear_region(self.x, self.y,
                                                                                  self.odmrRegionFitBox.value(),
                                                                                  plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                                                                  denoise=self.smoothingCheckBox.isChecked(),
                                                                                  window_length=self.smoothWindowBox.value(),
                                                                                  polyorder=self.polyorderSpinBox.value(),
                                                                                  peak_height=self.peakHeightSpinBox.value(),
                                                                                  peak_distance=self.peakDistanceSpinBox.value(),
                                                                                  peak_prom=self.peakPromSpinBox.value(),
                                                                                  ))

        self.smoothWindowBox.valueChanged.connect(
            lambda: self.fit_linear_region(self.x, self.y, self.odmrRegionFitBox.value(),
                                           plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                           denoise=self.smoothingCheckBox.isChecked(),
                                           window_length=self.smoothWindowBox.value(),
                                           polyorder=self.polyorderSpinBox.value(),
                                           peak_height=self.peakHeightSpinBox.value(),
                                           peak_distance=self.peakDistanceSpinBox.value(),
                                           peak_prom=self.peakPromSpinBox.value(),
                                           ))

        self.peakHeightSpinBox.valueChanged.connect(
            lambda: self.fit_linear_region(self.x, self.y, self.odmrRegionFitBox.value(),
                                           plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                           denoise=self.smoothingCheckBox.isChecked(),
                                           window_length=self.smoothWindowBox.value(),
                                           polyorder=self.polyorderSpinBox.value(),
                                           peak_height=self.peakHeightSpinBox.value(),
                                           peak_distance=self.peakDistanceSpinBox.value(),
                                           peak_prom=self.peakPromSpinBox.value(),
                                           ))

        self.peakDistanceSpinBox.valueChanged.connect(
            lambda: self.fit_linear_region(self.x, self.y, self.odmrRegionFitBox.value(),
                                           plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                           denoise=self.smoothingCheckBox.isChecked(),
                                           window_length=self.smoothWindowBox.value(),
                                           polyorder=self.polyorderSpinBox.value(),
                                           peak_height=self.peakHeightSpinBox.value(),
                                           peak_distance=self.peakDistanceSpinBox.value(),
                                           peak_prom=self.peakPromSpinBox.value(),
                                           ))

        self.peakPromSpinBox.valueChanged.connect(
            lambda: self.fit_linear_region(self.x, self.y, self.odmrRegionFitBox.value(),
                                           plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                           denoise=self.smoothingCheckBox.isChecked(),
                                           window_length=self.smoothWindowBox.value(),
                                           polyorder=self.polyorderSpinBox.value(),
                                           peak_height=self.peakHeightSpinBox.value(),
                                           peak_distance=self.peakDistanceSpinBox.value(),
                                           peak_prom=self.peakPromSpinBox.value(),
                                           ))

        self.setODMRButton.clicked.connect(self.send_to_scan_table)
        self.autoFitButton.clicked.connect(self.run_auto_fit)
        self.stopSweepButton.clicked.connect(self.stop_odmr_sweep)

        self.thread_function(window.rfController.setup_sweep, window.startFreqBox.value(), window.endFreqBox.value(),
                             window.pointsBox.value(), window.dwellTimeBox.value(), window.stepSizeBox.value(),
                             window.odmrSweepContinous.isChecked(),
                             fin_fn=self.execute_this_function, prg_fn=self.progress_fn,
                             err_fn=window.show_error_message, progress_callback=None)

    def execute_this_function(self, *args, **kwargs):
        """this function then theoretically will trigger the LIA to start data collection when the MW sweep is started
        then once the sweep is stopped, the trigger will stop LIA aquisition and then this function collects the data and
        passes the data back to be plotted using signals and slots...haven't worked that out yet ._."""

        window.takeODMRButton.setEnabled(True)
        self.worker_running = False
        self.y = window.rfController.samples
        """
        although the user defines 3000 point step, there maybe a mistmatch between the number of expected points.
        To deal with this, once the sweep is done, check what the actual length of the data array is and then rematch
        the length of this to fit between the desired freq. sweep range.
        i.e if the user wants 3000 points but instead gets 2968 points, replot the data using a numpy range between
        freq. start and freq. end using 2968 points rather than 3000 points. This should make plotting more accurate.
        """
        self.x = np.linspace(window.rfController.start_freq, window.rfController.stop_freq,
                             window.rfController.num_points)
        self.x = self.x[0:len(self.y)]
        self.dummy_data(self.x, self.y)
        if self.autoFitAfterSweepCheckBox.isChecked():
            self.run_auto_fit()
        return

    def progress_fn(self, results):
        self.y = results
        self.x = np.linspace(window.rfController.start_freq, window.rfController.stop_freq,
                             window.rfController.num_points)
        self.x = self.x[0:len(self.y)]
        self.dummy_data(self.x, self.y)
        return

    def run_auto_fit(self):
        if window.rfController.sweeping:
            return
        if self.x is None or self.y is None or len(self.y) < 7:
            return
        self.fit_linear_region(self.x, self.y,
                               self.odmrRegionFitBox.value(),
                               plot_derivative=self.showDerivativeCheckbox.isChecked(),
                               denoise=self.smoothingCheckBox.isChecked(),
                               window_length=self.smoothWindowBox.value(),
                               polyorder=self.polyorderSpinBox.value(),
                               peak_height=0,
                               peak_distance=0,
                               peak_prom=0,
                               force=True)

    def print_this(self, results):
        """this then prints the result emitted from the results signal, that is returned by the function
        'execute_this_function'"""
        self.worker_running = False
        window.takeODMRButton.setEnabled(True)

    def closeEvent(self, event):
        """this function executes when the ODMR graph window closes, used to stop thread but can be used for anything
        else, such as printing or saving data, clearing graphs/memory etc."""
        window.rfController.sweeping = False
        self.worker_running = False

    def stop_odmr_sweep(self):
        self.worker_running = False

    def updateViews(self):
        ## view has resized; update auxiliary views to match
        self.p2.setGeometry(self.p1.vb.sceneBoundingRect())

        ## need to re-update linked axes since this was called
        ## incorrectly while views had different shapes.
        ## (probably this should be handled in ViewBox.resizeEvent)
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
        pen = pg.mkPen(style=QtCore.Qt.PenStyle.DashLine)
        self.odmr_plot = self.graphWidget.plot(x, y, pen=pen)
        self.updateViews()
        return

    def fit_linear_region(self, x, y, linear_region_width=50, window_length=50, polyorder=3, peak_height=-5,
                          peak_distance=100, peak_prom=5, plot_derivative=False, denoise=False, force=False):
        try:
            if window.rfController.sweeping and not force:
                return
            if x is None or y is None:
                return
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            if len(x) < 7 or len(y) < 7:
                return

            window_length = int(window_length)
            polyorder = int(polyorder)

            # enforce valid Savitzky-Golay parameters for robust auto-fitting
            max_allowed_window = len(y) if len(y) % 2 == 1 else len(y) - 1
            if max_allowed_window < 5:
                max_allowed_window = 5
            window_length = min(window_length, max_allowed_window)
            if window_length % 2 == 0:
                window_length -= 1
            window_length = max(5, window_length)
            polyorder = max(1, min(polyorder, window_length - 2))

            y_for_fit = y
            if denoise:
                y_for_fit = savgol_filter(y, window_length=window_length, polyorder=polyorder)

            try:
                self.odmr_plot.clear()
                self.dummy_data(x, y_for_fit)
            except:
                self.dummy_data(x, y_for_fit)

            linear_region_width = max(7, int(linear_region_width))
            if linear_region_width % 2 == 0:
                linear_region_width += 1

            if self.usePositiveGradientsCheckBox.isChecked():
                derivative = np.gradient(y_for_fit, x)  # take derivative of curve, find elbow or "knee" point of curve
            else:
                derivative = -1 * np.gradient(y_for_fit, x)

            # adaptive thresholds from derivative statistics to reduce manual tuning effort
            deriv_median = float(np.median(derivative))
            mad = float(np.median(np.abs(derivative - deriv_median)))
            robust_sigma = max(1e-12, 1.4826 * mad)
            auto_height = deriv_median + 2.0 * robust_sigma
            auto_prom = max(robust_sigma * 2.5, float(np.ptp(derivative)) * 0.04)
            auto_distance = max(3, int(len(x) / 120))

            detect_height = float(peak_height) if float(peak_height) > 0 else auto_height
            detect_prom = float(peak_prom) if float(peak_prom) > 0 else auto_prom
            detect_distance = int(peak_distance) if int(peak_distance) > 0 else auto_distance

            peaks, peak_props = find_peaks(
                derivative,
                height=detect_height,
                distance=detect_distance,
                prominence=detect_prom,
            )

            if len(peaks) == 0:
                peaks, peak_props = find_peaks(
                    derivative,
                    distance=max(2, detect_distance // 2),
                    prominence=max(auto_prom * 0.45, 1e-12),
                )

            if len(peaks) == 0:
                try:
                    for item in self.linear_region_list:
                        item.clear()
                except:
                    pass
                self.linearRegionTable.setRowCount(0)
                if plot_derivative:
                    try:
                        self.p2.removeItem(self.odmr_deriv_plot)
                    except:
                        pass
                    pen = pg.mkPen(color=(0, 255, 0), style=QtCore.Qt.PenStyle.DashDotLine)
                    self.odmr_deriv_plot = pg.PlotCurveItem(x, derivative, pen=pen)
                    self.p2.addItem(self.odmr_deriv_plot)
                self.updateViews()
                return

            # keep strongest peaks if many are found, then preserve left-to-right order
            prominences = peak_props.get('prominences', np.ones(len(peaks)))
            max_peaks = 24
            if len(peaks) > max_peaks:
                keep = np.argsort(prominences)[-max_peaks:]
                keep = keep[np.argsort(peaks[keep])]
                peaks = peaks[keep]
                prominences = prominences[keep]

            widths, _, _, _ = peak_widths(derivative, peaks, rel_height=0.5)

            try:
                for i in self.linear_region_list:
                    i.clear()
            except:
                pass

            self.linear_region_list = []
            self.linear_region_list_checkboxes = []
            self.linearRegionTable.setRowCount(0)
            row_idx = 0
            auto_selected_rows = []
            for i in range(len(peaks)):
                adaptive_width = max(linear_region_width, int(np.ceil(widths[i] * 1.8)))
                if adaptive_width % 2 == 0:
                    adaptive_width += 1

                # Adjust linear region parameter to control the width of the linear region
                linear_region_start = max(0, peaks[i] - adaptive_width // 2)
                linear_region_end = min(len(x) - 1, peaks[i] + adaptive_width // 2)
                # Extract data points for the linear region
                x_linear = x[linear_region_start:linear_region_end].reshape(-1, 1)
                y_linear = y_for_fit[linear_region_start:linear_region_end]
                if len(x_linear) < 3:
                    continue

                # Perform linear regression
                model = LinearRegression()
                model.fit(x_linear, y_linear)

                slope = model.coef_[0]
                intercept = model.intercept_

                prd = model.predict(x_linear)
                x_linear = x_linear.flatten()
                ss_res = float(np.sum((y_linear - prd) ** 2))
                ss_tot = float(np.sum((y_linear - np.mean(y_linear)) ** 2))
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

                pen = pg.mkPen(color=(255, 0, 0), width=5)

                self.odmr_linear_region_plot = self.graphWidget.plot(x_linear, prd, pen=self._linear_region_default_pen)
                self.linear_region_list.append(self.odmr_linear_region_plot)

                self.linearRegionTable.insertRow(row_idx)
                self.linearRegionTable.setItem(row_idx, 0,
                                               QtWidgets.QTableWidgetItem(
                                                   str(round((x_linear[0] + x_linear[-1]) / 2, 9))))
                self.linearRegionTable.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(str(round(slope, 9))))
                checkbox = QtWidgets.QCheckBox()
                prominence_threshold = 0.5 * float(np.median(prominences)) if len(prominences) > 0 else 0
                auto_select = bool((prominences[i] >= prominence_threshold) and (r_squared >= 0.75))
                checkbox.setChecked(auto_select)
                if auto_select:
                    auto_selected_rows.append(row_idx)
                checkbox.setToolTip(
                    f"Prominence: {prominences[i]:.3e}\nR²: {r_squared:.3f}\nAuto-selected: {auto_select}"
                )
                self.linearRegionTable.setCellWidget(row_idx, 2, checkbox)
                row_idx += 1

            self.clear_linear_region_hover()

            if self.linearRegionTable.rowCount() > 0 and len(auto_selected_rows) == 0:
                strongest_idx = int(np.argmax(prominences))
                strongest_row = min(strongest_idx, self.linearRegionTable.rowCount() - 1)
                self.linearRegionTable.cellWidget(strongest_row, 2).setChecked(True)

            # if plot deriviate is true, plot it else, if false, clear deriv plot.
            if plot_derivative:
                try:
                    # self.odmr_deriv_plot.clear()
                    self.p2.removeItem(self.odmr_deriv_plot)
                except:
                    pass
                pen = pg.mkPen(color=(0, 255, 0), style=QtCore.Qt.PenStyle.DashDotLine)
                # self.odmr_deriv_plot = self.graphWidget.plot(x, derivative, pen=pen)
                self.odmr_deriv_plot = pg.PlotCurveItem(x, derivative, pen=pen)
                self.p2.addItem(self.odmr_deriv_plot)
                # self.p2.setYRange(np.min(derivative), np.max(derivative))
            else:
                try:
                    # self.odmr_deriv_plot.clear()
                    self.p2.removeItem(self.odmr_deriv_plot)
                except:
                    pass

            # self.odmrGradientLabel.setText(str(round(slope,3)))
        except Exception as error:
            print(traceback.format_exc())

        self.updateViews()
        return

    def send_to_scan_table(self):
        self.table = self.linearRegionTable
        freqs = []
        grads = []
        for row in range(self.linearRegionTable.rowCount()):
            if self.linearRegionTable.cellWidget(row, 2).isChecked():
                freqs.append(float(self.linearRegionTable.item(row, 0).text()))
                grads.append(float(self.linearRegionTable.item(row, 1).text()))
        window.scanODMRPropertiesTable.setRowCount(0)
        for row in range(len(freqs)):
            window.scanODMRPropertiesTable.insertRow(row)
            window.scanODMRPropertiesTable.setItem(row, 0, QtWidgets.QTableWidgetItem(str(round(freqs[row], 3))))
            window.scanODMRPropertiesTable.setItem(row, 1, QtWidgets.QTableWidgetItem(str(round(grads[row], 3))))
        return

    def lorentzian_derivative(self, x, x0, gamma, A):
        return -2 * A * gamma ** 2 * (x - x0) / ((x - x0) ** 2 + gamma ** 2) ** 2


class scanningImageWindow(QtWidgets.QWidget, ThreadedComponent):
    def __init__(self):
        super().__init__()
        super(scanningImageWindow, self).__init__()  # Call the inherited classes __init__ method
        self.feedback_started = False
        self.res_grad = None
        self.res_freq = None
        self.dV = None
        self.df = None
        uic.loadUi(ui_file('scanningWindow.ui'), self)  # Load the .ui file
        apply_ui_polish(self)
        self.show()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.StageControl = window.stageController

        self.graphWidget.setLabel(axis='left', text='RF Frequency (GHz)')
        self.graphWidget.setLabel(axis='bottom', text='Index')
        self.graphWidget.setLabel(axis='top', text='RF Frequency Shift (GHz)')
        self.graphWidget_2.setLabel(axis='left', text='Voltage (V)')
        self.graphWidget_2.setLabel(axis='bottom', text='Index')
        self.graphWidget_2.setLabel(axis='top', text='Measured Voltage (V)')

        self.xCoords = np.arange(window.xStartSpinBox.value(),
                                 (window.xEndSpinBox.value() + window.xStepSpinBox.value()),
                                 window.xStepSpinBox.value())
        self.yCoords = np.arange(window.yStartSpinBox.value(),
                                 (window.yEndSpinBox.value() + window.xStepSpinBox.value()),
                                 window.yStepSpinBox.value())
        self.xStep = window.xStepSpinBox.value()
        self.yStep = window.yStepSpinBox.value()
        self.vector = window.vectorRadio.isChecked()
        self.feedback = window.feedbackToggle.isChecked()
        self.scan_averaging = window.scanAveragingToggle.isChecked()
        self.avg_time = window.scanAveragingTimeSpinBox.value()
        self.scanning = False

        if self.vector:
            window.feedbackToggle.setChecked(True)
            self.feedback = window.feedbackToggle.isChecked()

        self.vc1 = self.graphWidget.plot()
        self.vc2 = self.graphWidget.plot()
        self.vc3 = self.graphWidget.plot()
        self.vc4 = self.graphWidget.plot()

        self.fc1 = self.graphWidget_2.plot()
        self.fc2 = self.graphWidget_2.plot()
        self.fc3 = self.graphWidget_2.plot()
        self.fc4 = self.graphWidget_2.plot()

        self.exportDataButton.clicked.connect(self.export_data)
        # random array of data for testing
        self.test_data = np.random.random([4, 10, 10])

        if self.StageControl.stage_connected and window.rfController.rf_connected and window.LIAController.LIA_connected:
            if self.feedback or self.vector:
                if (window.scanODMRPropertiesTable.item(0, 0) is None) or (
                        window.scanODMRPropertiesTable.item(0, 1) is None):
                    error_dialog = QtWidgets.QErrorMessage(window)
                    error_dialog.showMessage(
                        "Error: If using feedback or vector, first row of freq. table can not be empty")
                    return
                else:
                    self.thread_function(self.setup_scan,
                                         err_fn=window.show_error_message,
                                         fin_fn=self.start_scan)
            else:
                self.thread_function(self.setup_scan,
                                     err_fn=window.show_error_message,
                                     fin_fn=self.start_scan)
        else:
            error_dialog = QtWidgets.QErrorMessage(window)
            error_dialog.showMessage("Error: Check printer, RF and LIA connections and try again")

    def setup_scan(self, *args, **kwargs):
        if self.feedback:
            if self.vector:
                self.vector_freqs = []
                self.vector_grads = []
                for i in range(4):
                    try:
                        self.vector_freqs.append(float(window.scanODMRPropertiesTable.item(i, 0).text()))
                        self.vector_grads.append(float(
                            window.scanODMRPropertiesTable.item(i, 1).text()))  # gradient used for feedback with vector
                    except:
                        # if table element is empty, skip it
                        pass
                    # self.vector_grads.append(0.3)
            else:
                self.res_freq = float(window.scanODMRPropertiesTable.item(0, 0).text())
                self.res_grad = float(window.scanODMRPropertiesTable.item(0, 1).text())  # gradient used for feedback

        self.StageControl.set_stage_pos(window.xStartSpinBox.value(), window.yStartSpinBox.value())
        # sleep needed to allow printer to move into its starting position - i dont know a way of checking if this move has finished programatically
        # time may need to be adjusted for slower movement/larger distances - might make this a user entered value in an option menu somewhere
        time.sleep(5)
        return

    def start_scan(self):
        self.scanning = True
        if self.feedback:
            if self.vector:
                self.thread_function(self.initialise_vector_feedback,
                                     err_fn=window.show_error_message,
                                     prg_fn=self.debug_plot)
            else:
                self.thread_function(self.initialise_feedback,
                                     err_fn=window.show_error_message,
                                     prg_fn=self.debug_plot)

        if self.vector:
            self.thread_function(self.scan_vector,
                                 scan_time=0.2,
                                 err_fn=window.show_error_message,
                                 prg_fn=self.update_plot,
                                 )
        else:
            self.thread_function(self.scan_no_vector,
                                 scan_time=float(window.scanDwellTimeSpinBox.value()),
                                 err_fn=window.show_error_message,
                                 prg_fn=self.update_plot,
                                 )
        return

    def _wait_for_feedback_start(self, timeout=10.0, poll=0.05):
        start = time.monotonic()
        while not self.feedback_started and self.scanning:
            if time.monotonic() - start >= timeout:
                error_dialog = QtWidgets.QErrorMessage(window)
                error_dialog.showMessage("Error: Feedback failed to start within timeout")
                return False
            time.sleep(poll)
        return True

    def initialise_feedback(self, *args, **kwargs):
        print("no vector feedback started")
        window.rfController.inst.write('FREQ ' + str(round(float(self.res_freq) * 1e9, 12)))
        time.sleep(1)
        sample = window.LIAController.daq.getSample("/%s/demods/0/sample" % window.LIAController.device)
        ini_voltage = sample['x'][0]
        self.feedback_started = True
        df_arr = []
        dV_arr = []
        res_freq_arr = []
        i = 0
        last_emit = 0.0
        while self.scanning:
            i += 1
            res_freq_arr.append(self.res_freq)
            sample = window.LIAController.daq.getSample("/%s/demods/0/sample" % window.LIAController.device)
            voltage_now = sample['x'][0]
            self.dV = voltage_now - ini_voltage
            self.df = (1 / self.res_grad) * (-self.dV)
            self.res_freq = self.res_freq + self.df
            window.rfController.inst.write('FREQ ' + str(round(float(self.res_freq) * 1e9, 12)))
            if len(df_arr) > 100:
                df_arr.pop(0)
                dV_arr.pop(0)
                res_freq_arr.pop(0)
            df_arr.append(self.df)
            dV_arr.append(self.dV)
            time.sleep(0.1)
            now = time.monotonic()
            if now - last_emit >= 0.1:
                kwargs['progress_callback'].emit([res_freq_arr, dV_arr])
                last_emit = now
        return

    def initialise_vector_feedback(self, *args, **kwargs):
        print('initializing vector feedback')
        ini_voltage = []
        self.ini_freq = []
        scale = 750
        self.vector_freqs_plotting = self.vector_freqs
        for i in range(len(self.vector_freqs)):
            self.ini_freq.append(self.vector_freqs[i])
            window.rfController.inst.write('FREQ ' + str(round(float(self.vector_freqs[i]) * 1e9, 12)))
            time.sleep(1)
            sample = window.LIAController.daq.getSample("/%s/demods/0/sample" % window.LIAController.device)
            ini_voltage.append(sample['x'][0] * scale)
        df_arr = [[], [], [], []]
        dV_arr = [[], [], [], []]
        res_freq_arr = [[], [], [], []]
        loop = 0
        self.feedback_started = True
        print('feedback starting')
        last_emit = 0.0
        while self.scanning:
            loop += 1
            for i in range(len(self.vector_freqs)):
                window.rfController.inst.write('FREQ ' + str(round(float(self.vector_freqs[i]) * 1e9, 12)))
                time.sleep(0.08)
                sample = window.LIAController.daq.getSample("/%s/demods/0/sample" % window.LIAController.device)
                voltage_now = sample['x'][0] * scale
                self.dV = voltage_now - ini_voltage[i]
                self.df = (1 / self.vector_grads[i]) * (-self.dV)
                self.vector_freqs[i] = self.vector_freqs[i] + self.df / 1e3
                df_arr[i].append(self.df)
                dV_arr[i].append(self.dV)
                res_freq_arr[i].append(self.vector_freqs[i])

            # makes the plot scroll so you dont clog up the graph for  long scans
            if len(df_arr[0]) > 100:
                for i in range(len(self.vector_freqs)):
                    df_arr[i].pop(0)
                    dV_arr[i].pop(0)
                    res_freq_arr[i].pop(0)
            time.sleep(0.1)
            now = time.monotonic()
            if now - last_emit >= 0.1:
                kwargs['progress_callback'].emit([res_freq_arr, dV_arr])
                last_emit = now
        return

    def scan_no_vector(self, *args, **kwargs):
        if self.feedback and not self._wait_for_feedback_start():
            return
        if self.scan_averaging:
            window.LIAController.daq.subscribe('/%s/demods/0/sample' % window.LIAController.device)
        time.sleep(3)  # let feedback settle
        scan_time = args[1]['scan_time']
        x_positions = self.xCoords
        y_positions = self.yCoords
        self.voltageArr = np.zeros([1, len(y_positions), len(x_positions)])
        self.voltageArrSTD = np.zeros([1, len(y_positions), len(x_positions)])
        self.df_arr = np.zeros([1, len(y_positions), len(x_positions)])
        last_emit = 0.0

        def emit_if_due(payload):
            nonlocal last_emit
            now = time.monotonic()
            if now - last_emit >= 0.1:
                kwargs['progress_callback'].emit(payload)
                last_emit = now
        print('The Scan has started. If the printer is not ready,'
              'exit program and increase the waiting time.')
        j = 0  # xpos
        totalSize = len(x_positions) * len(y_positions)
        for idx, y_position in enumerate(y_positions, 2):
            i = len(x_positions) - 1
            self.StageControl.set_stage_pos(x_positions[0], y_position)
            time.sleep(10)
            for x_position in x_positions:
                timeStart = time.time()
                ts = time.time()
                totalSize -= 1
                print(f'\nx = {x_position} mm, y = {y_position} mm', i, j)
                self.StageControl.set_stage_pos(x_position, y_position)
                time.sleep(scan_time)
                if self.feedback:
                    # if feedback on, get res_freq shift and return that
                    self.df_arr[0, j, i] = self.res_freq
                    emit_if_due(self.df_arr)
                else:
                    # else return current voltage instead
                    if self.scan_averaging:
                        stream = window.LIAController.daq.poll(self.avg_time, 200, 1, True)
                        sample_path = f"/{window.LIAController.device}/demods/0/sample"
                        self.voltageArr[0, j, i] = np.mean(stream[sample_path]['x'])
                        self.voltageArrSTD[0, j, i] = np.std(stream[sample_path]['x'])
                        emit_if_due(self.voltageArr)
                    else:
                        sample = window.LIAController.daq.getSample("/%s/demods/0/sample" % window.LIAController.device)
                        self.voltageArr[0, j, i] = np.sqrt(((sample['x'][0])**2 + (sample['y'][0])**2))
                        emit_if_due(self.voltageArr)
                i = i - 1
                te = time.time()
                eta = (te - ts) * totalSize
                print(time.ctime(int(timeStart + eta)))
                if self.scanning == False:
                    return
            j += 1
            # self.StageControl.set_stage_pos(x_positions[0], y_position)
            # time.sleep(4)
        print('Scan completed. Resetting printer.')
        time.sleep(1)
        self.scanning = False
        return

    def scan_vector(self, *args, **kwargs):
        print('initializing scan vector')
        if not self._wait_for_feedback_start():
            return
        print('scan vector starting')
        time.sleep(3)  # let feedback settle
        scan_time = args[1]['scan_time']
        x_positions = self.xCoords
        y_positions = self.yCoords
        self.voltageArr = np.zeros([4, len(y_positions), len(x_positions)])
        self.df_arr = np.zeros([4, len(y_positions), len(x_positions)])
        self.b_arr = np.zeros([3, len(y_positions), len(x_positions)])
        j = 0  # xpos
        A_pinv = np.linalg.pinv(np.array(window.a_matrix_values))
        totalSize = len(x_positions) * len(y_positions)
        last_emit = 0.0
        for idx, y_position in enumerate(y_positions, 2):
            i = len(x_positions) - 1
            for x_position in x_positions:
                timeStart = time.time()
                ts = time.time()
                totalSize -= 1
                self.StageControl.set_stage_pos(x_position, y_position)
                time.sleep(scan_time)
                # df_arr[0, j, i] = self.vector_freqs[0]
                for k in range(4):
                    self.df_arr[k, j, i] = self.vector_freqs[k]
                print(np.array(self.vector_freqs), np.array(self.ini_freq))
                df1, df2, df3, df4 = (np.array(self.vector_freqs) - np.array(self.ini_freq)) * 1000 # difference in freq. in MHz
                freq_col = ([[df1],
                             [df2],
                             [df3],
                             [df4]])
                B = np.dot(A_pinv, freq_col)
                for k in range(3):
                    self.b_arr[k, j, i] = B[k][0]
                now = time.monotonic()
                if now - last_emit >= 0.1:
                    kwargs['progress_callback'].emit(self.b_arr)
                    last_emit = now
                i = i - 1
                te = time.time()
                eta = (te - ts) * totalSize
                print(time.ctime(int(timeStart + eta)))
                if self.scanning == False:
                    return
            j += 1
            self.StageControl.set_stage_pos(x_positions[0], y_position)
            time.sleep(6)
        print('Scan completed. Resetting printer.')
        time.sleep(1)
        self.scanning = False
        return

    @staticmethod
    def calculate_levels(a):
        px = a.ravel()[np.flatnonzero(a)]
        k = int(len(px) * 0.05)
        if k > 0:
            px_low = np.argpartition(px, k)
            px_high = np.argpartition(px, -k)
            return px[px_low[k-1]], px[px_high[-k-1]]
        else:
            return min(px), max(px)

    def update_plot(self, image_arr):
        if self.vector:
            # self.imageWidget.setImage(image_arr[0])
            levels0 = self.calculate_levels(image_arr[0])
            levels1 = self.calculate_levels(image_arr[1])
            levels2 = self.calculate_levels(image_arr[2])
            self.imageWidget_2.setImage(image_arr[0], levels=levels0)
            self.imageWidget_3.setImage(image_arr[1], levels=levels1)
            self.imageWidget_4.setImage(image_arr[2], levels=levels2)
        else:
            levels = self.calculate_levels(image_arr)
            self.imageWidget.setImage(image_arr, levels=levels)

    def debug_plot(self, arrs):
        if self.vector:
            self.vc1.setData(arrs[0][0], pen=pg.mkPen('b'))
            self.vc2.setData(arrs[0][1], pen=pg.mkPen('g'))
            self.vc3.setData(arrs[0][2], pen=pg.mkPen('r'))
            self.vc4.setData(arrs[0][3], pen=pg.mkPen('y'))

            self.fc1.setData(arrs[1][0], pen=pg.mkPen('b'))
            self.fc2.setData(arrs[1][1], pen=pg.mkPen('g'))
            self.fc3.setData(arrs[1][2], pen=pg.mkPen('r'))
            self.fc4.setData(arrs[1][3], pen=pg.mkPen('y'))

    def export_data(self):
        folderpath = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Folder')
        date_time = time.strftime("/Scan_Data_%Y-%m-%d_%H-%M-%S", time.gmtime())
        # write images to h5 file
        try:
            df_arr_data = np.array(self.df_arr)
            voltage_arr_data = np.array(self.voltageArr)
            voltage_std_arr_data = np.array(self.voltageArrSTD)
            h5f = h5py.File(folderpath + date_time + ".h5", 'w')
            h5f.create_dataset('df_array', data=df_arr_data)
            h5f.create_dataset('voltage_array', data=voltage_arr_data)
            h5f.create_dataset('voltage_st_arrayy', data=voltage_std_arr_data)
            h5f.close()
        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(window)
            error_dialog.showMessage(str(error))

        # creates new image folder where the data is being saved
        # convert data to greyscale then export data as png images
        if not os.path.exists(folderpath + date_time + "IMAGES"):
            os.makedirs(folderpath + date_time + "IMAGES")
        for i in range(len(df_arr_data)):
            df_image = df_arr_data[i, :, :]
            voltage_image = voltage_arr_data[i, :, :]
            df_image = cv2.resize(df_image, dsize=(640, 640), interpolation=cv2.INTER_CUBIC)
            voltage_image = cv2.resize(voltage_image, dsize=(640, 640), interpolation=cv2.INTER_CUBIC)
            df_image8 = (((df_image - df_image.min()) / (df_image.max() - df_image.min())) * 255.9).astype(np.uint8)
            voltage_image8 = (((voltage_image - voltage_image.min()) / (
                    voltage_image.max() - voltage_image.min())) * 255.9).astype(np.uint8)
            df_image = Image.fromarray(df_image8)
            voltage_image = Image.fromarray(voltage_image8)

            df_image.save(folderpath + date_time + "IMAGES/" + "_IMAGE_freq_" + str(i) + ".PNG")
            voltage_image.save(folderpath + date_time + "IMAGES/" + "_IMAGE_voltage_" + str(i) + ".PNG")

        return

    def closeEvent(self, event):
        """this function executes when the vector debug graph window closes, used to stop thread
        :param event:
        :return:
        """
        self.scanning = False

app = QtWidgets.QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
if dark_theme:
    qdarktheme.setup_theme()
window = MainUI()  # Create an instance of our class
app.exec()
