# -*- coding: utf-8 -*-
"""Scanning Magnetometer main file

This module contains all the classes for the UI such as displaying graphs and opening new windows.
It also controls connections to the different equipment such as COM port serial connections and PyVisa connections. It
also controls the flow of data between these bits of equipment and sorts out the plotting/updating and save/export of
data.
"""

from PyQt6 import QtCore, QtWidgets, uic
import pyqtgraph as pg
import os
import copy
import sys
import serial
import serial.tools.list_ports
import numpy as np
import time
import pyvisa
import zhinst.utils as utils
import zhinst.core
import data_viewer
import default_param_window
import yaml
from threading_utils import Worker, WorkerSignals, ThreadedComponent
from stage_control import StageControl
from rf_control import RfControl
from lia_control import LIAControl
from windows.fft_window import FFTGraphWindow
from windows.odmr_window import ODMRGraphWindow
from windows.scanning_window import scanningImageWindow
from ui_theme import apply_ui_polish
from paths import ui_file

# if dark theme is available then use by default
try:
    import qdarktheme

    dark_theme = True
except Exception as error:
    dark_theme = False
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
        self.fallback_config_file = os.path.join(
            self.base_dir, "configs", "default_config.yml"
        )
        self.default_parameters = self._default_config_template()
        self.config_path = {"Config_Path": {"Path": self.fallback_config_file}}
        self.odmr_graph_window = None
        self.fft_graph_window = None
        self.vector_test_window = None
        self.scan_window = None
        self.a_matrix_values = copy.deepcopy(
            self.default_parameters["RF_Params"]["A_Matrix_Values"]
        )
        uic.loadUi(ui_file("scanning_magnetometer.ui"), self)  # Load the .ui file
        apply_ui_polish(self)
        self.setMinimumSize(980, 620)
        self.setWindowTitle("Scanning Magnetometer")
        self.show()  # Show the GUI

        self.stageController = StageControl(
            self, StageOptions
        )  # stage controller class instance
        self.rfController = RfControl(self)
        self.LIAController = LIAControl(self)

        # try loading default default_config.yml to set default values if it exists in directory
        try:
            with open(self.settings_file, "r") as f:
                self.config_path = yaml.safe_load(f)
            self.load_config(
                config_file_name=self.config_path.get("Config_Path", {}).get(
                    "Path", self.fallback_config_file
                )
            )
        except Exception as error:
            print(error)
            self.load_config(config_file_name=self.fallback_config_file)

        # ------------------ UI elements are connected to their respective functions here ------------------ #
        #  stage ui controls
        self.connectStageButton.clicked.connect(
            lambda: self.stageController.connect_stage(self.comPortBox.currentText())
        )
        self.homeStageButton.clicked.connect(self.stageController.home_stage)
        self.setPositionButton.clicked.connect(
            lambda: self.stageController.set_stage_pos(
                self.xPosSpinBox.value(), self.yPosSpinBox.value()
            )
        )
        self.setStageHeightButton.clicked.connect(
            lambda: self.stageController.set_stage_height(self.zPosSpinBox.value())
        )

        self.getStagePositionButton.clicked.connect(self.stageController.get_stage_pos)
        self.actionChange_Max_Position_Values.triggered.connect(
            self.stageController.set_max_stage_position
        )
        self.actionDataViewer.triggered.connect(self.open_data_viewer)
        self.actionDefaultParameters.triggered.connect(self.open_default_param)
        self.actionLoadConfig.triggered.connect(self.load_config_button_selected)
        self.actionSaveConfig.triggered.connect(self.save_config)

        self.startScanButton.clicked.connect(self.open_scan_window)

        #  LIA ui controls
        self.connectLIAButton.clicked.connect(
            lambda: self.LIAController.thread_function(
                self.LIAController.connect_lia,
                device_id=self.LIANameBox.text(),
                device_ip=self.LIAIPBox.text(),
                err_fn=self.show_error_message,
            )
        )
        self.takeFFTButton.clicked.connect(self.open_fft_graph)

        #  RF ui controls
        self.takeODMRButton.clicked.connect(self.open_odmr_graph)
        self.connectMWSourceButton.clicked.connect(
            lambda: self.rfController.thread_function(
                self.rfController.connect_rf,
                self.MWSourceIPAddressBox.text(),
                err_fn=self.show_error_message,
            )
        )
        self.togglePwrChk.stateChanged.connect(
            lambda: self.rfController.power_on_off(self.togglePwrChk.isChecked())
        )
        self.toggleModOnOff.stateChanged.connect(
            lambda: self.rfController.mod_on_off(self.toggleModOnOff.isChecked())
        )
        self.setFreqBtn.clicked.connect(self.rfController.set_freq)
        self.setPwrBtn.clicked.connect(self.rfController.set_power)
        self.applyModParamsButton.clicked.connect(self.rfController.set_mod_params)
        self.sineWaveRadio.setChecked(True)
        self.sineWaveRadio.toggled.connect(self.rfController.change_mod_type)
        self.squareWaveRadio.setChecked(False)
        self.squareWaveRadio.toggled.connect(self.rfController.change_mod_type)
        self.toggleExtModOnOff.stateChanged.connect(
            lambda: self.rfController.ext_mod_on_off(self.toggleExtModOnOff.isChecked())
        )

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
                "RF_IP": "192.168.1.2",
            },
            "Stage_Params": {
                "Avg_Time": "0.1",
                "Dwell": "0.05",
                "X_End": "20",
                "X_Start": "10",
                "X_Step": "1",
                "Y_End": "20",
                "Y_Start": "10",
                "Y_Step": "1",
            },
            "Sweep_Params": {
                "Dwell": "3.0",
                "Points": "1000",
                "Sweep_End": "3.0",
                "Sweep_Start": "2.7",
                "Sweep_Step": "250",
                "Sweep_Type": "1",
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
                "Power_On": "False",
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
                "Time_Const": "600",
            },
        }

    def show_error_message(self, error):
        """Displays pop up error message for try and except statements. Pass Exception as "error" parameter to display
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
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
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
        """Opens the fast Fourier transform window for sensitivity measurements"""
        self.fft_graph_window = FFTGraphWindow(self)

    def open_odmr_graph(self):
        """Opens the ODMR graph window for ODMR sweeps and fitting parameters"""
        window.takeODMRButton.setEnabled(
            False
        )  # stops multiple windows being opened and causing strangness occuring
        self.odmr_graph_window = ODMRGraphWindow(self)

    def open_scan_window(self):
        """Opens the scan window which shows any feedback/vector tracking graphs as well as showing a real-time image
        of the current scan.
        """
        self.scan_window = scanningImageWindow(self)

    def open_data_viewer(self):
        self.data_viewer_window = data_viewer.DataViewer()
        return

    def set_vector_matrx(self):
        self.vector_matrix_window = VectorMatrixWindow()
        return

    def open_default_param(self):
        filepath = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select File", filter="yml (*.yml)"
        )[0]
        if not filepath:
            return
        new_settings = self.config_path
        new_settings["Config_Path"]["Path"] = str(filepath)
        with open(self.settings_file, "w") as f:
            yaml.dump(new_settings, f, default_flow_style=False)
        self.config_path = new_settings
        return

    def load_config_button_selected(self):
        filepath = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select File", filter="yml (*.yml)"
        )[0]
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
            self.LIAIPBox.setText(
                self.default_parameters["Connection_Params"]["Device_IP"]
            )
            self.LIANameBox.setText(
                self.default_parameters["Connection_Params"]["Device_ID"]
            )
            self.MWSourceIPAddressBox.setText(
                self.default_parameters["Connection_Params"]["RF_IP"]
            )

            # set stage scanning parameter values
            self.scanAveragingTimeSpinBox.setValue(
                float(self.default_parameters["Stage_Params"]["Avg_Time"])
            )
            self.scanDwellTimeSpinBox.setValue(
                float(self.default_parameters["Stage_Params"]["Dwell"])
            )
            self.xEndSpinBox.setValue(
                float(self.default_parameters["Stage_Params"]["X_End"])
            )
            self.xStartSpinBox.setValue(
                float(self.default_parameters["Stage_Params"]["X_Start"])
            )
            self.xStepSpinBox.setValue(
                float(self.default_parameters["Stage_Params"]["X_Step"])
            )
            self.yEndSpinBox.setValue(
                float(self.default_parameters["Stage_Params"]["Y_End"])
            )
            self.yStartSpinBox.setValue(
                float(self.default_parameters["Stage_Params"]["Y_Start"])
            )
            self.yStepSpinBox.setValue(
                float(self.default_parameters["Stage_Params"]["Y_Step"])
            )

            # set odmr sweep params
            self.startFreqBox.setValue(
                float(self.default_parameters["Sweep_Params"]["Sweep_Start"])
            )
            self.endFreqBox.setValue(
                float(self.default_parameters["Sweep_Params"]["Sweep_End"])
            )
            self.dwellTimeBox.setValue(
                float(self.default_parameters["Sweep_Params"]["Dwell"])
            )
            self.stepSizeBox.setValue(
                float(self.default_parameters["Sweep_Params"]["Sweep_Step"])
            )
            self.pointsBox.setValue(
                int(self.default_parameters["Sweep_Params"]["Points"])
            )
            self.sweepDefBox.setCurrentIndex(
                int(self.default_parameters["Sweep_Params"]["Sweep_Type"])
            )

            # set rf source params
            self.freqBox.setValue(float(self.default_parameters["RF_Params"]["Freq"]))
            self.pwrBox.setValue(float(self.default_parameters["RF_Params"]["Power"]))
            self.togglePwrChk.setChecked(
                eval(self.default_parameters["RF_Params"]["Power_On"])
            )
            self.modFreqSpinBox.setValue(
                float(self.default_parameters["RF_Params"]["Mod_Freq"])
            )
            self.modAmpSpinBox.setValue(
                float(self.default_parameters["RF_Params"]["Mod_Amp"])
            )

            self.toggleModOnOff.setChecked(
                eval(self.default_parameters["RF_Params"]["Mod_On"])
            )
            self.toggleExtModOnOff.setChecked(
                eval(self.default_parameters["RF_Params"]["Ext_Mod"])
            )
            self.a_matrix_values = self.default_parameters["RF_Params"][
                "A_Matrix_Values"
            ]

            freqs = []
            grads = []
            for i in self.default_parameters["RF_Params"]["Feedback_Freq_Table"][0]:
                freqs.append(float(i))
            for i in self.default_parameters["RF_Params"]["Feedback_Freq_Table"][1]:
                grads.append(float(i))
            self.scanODMRPropertiesTable.setRowCount(0)
            for row in range(len(freqs)):
                self.scanODMRPropertiesTable.insertRow(row)
                self.scanODMRPropertiesTable.setItem(
                    row, 0, QtWidgets.QTableWidgetItem(str(freqs[row]))
                )
                self.scanODMRPropertiesTable.setItem(
                    row, 1, QtWidgets.QTableWidgetItem(str(grads[row]))
                )

            # set lia params
            self.odmrAqDurBox.setValue(
                int(self.default_parameters["LIA_Params"]["Duration"])
            )
            self.odmrAqBurstDurBox.setValue(
                float(self.default_parameters["LIA_Params"]["Burst_Dur"])
            )
            self.odmrAqSampleRateBox.setValue(
                int(self.default_parameters["LIA_Params"]["Sample_Rate"])
            )
            self.scalingFactorSpinBox.setValue(
                int(self.default_parameters["LIA_Params"]["Scaling"])
            )
            self.timeConstantSpinBox.setValue(
                int(self.default_parameters["LIA_Params"]["Time_Const"])
            )
            self.rangeSelect.setCurrentIndex(
                int(self.default_parameters["LIA_Params"]["Range"])
            )
            self.harmonicOrderSelect.setCurrentIndex(
                int(self.default_parameters["LIA_Params"]["Filter_Order"])
            )
            self.fftAverageSpinBox.setValue(
                int(self.default_parameters["LIA_Params"]["FFT_Average"])
            )
            self.fftDurationSpinBox.setValue(
                int(self.default_parameters["LIA_Params"]["FFT_Duration"])
            )
            self.sampleRateSpinBox.setValue(
                int(self.default_parameters["LIA_Params"]["FFT_Sample_Rate"])
            )
            self.acCoupleCheck.setChecked(
                eval(self.default_parameters["LIA_Params"]["FFT_AC_Coupling"])
            )
            self.fiftyOhmCheck.setChecked(
                eval(self.default_parameters["LIA_Params"]["FFT_50_Ohm"])
            )
        except Exception as error:
            print(error)
        return

    def save_config(self):
        if not isinstance(self.default_parameters, dict) or not self.default_parameters:
            self.default_parameters = self._default_config_template()

        new_config = copy.deepcopy(self.default_parameters)
        # set connection default values
        new_config["Connection_Params"]["Device_IP"] = str(self.LIAIPBox.text())
        new_config["Connection_Params"]["Device_ID"] = str(self.LIANameBox.text())
        new_config["Connection_Params"]["RF_IP"] = str(self.MWSourceIPAddressBox.text())

        # set stage scanning parameter values
        new_config["Stage_Params"]["Avg_Time"] = str(
            self.scanAveragingTimeSpinBox.value()
        )
        new_config["Stage_Params"]["Dwell"] = str(self.scanDwellTimeSpinBox.value())
        new_config["Stage_Params"]["X_End"] = str(self.xEndSpinBox.value())
        new_config["Stage_Params"]["X_Start"] = str(self.xStartSpinBox.value())
        new_config["Stage_Params"]["X_Step"] = str(self.xStepSpinBox.value())
        new_config["Stage_Params"]["Y_End"] = str(self.yEndSpinBox.value())
        new_config["Stage_Params"]["Y_Start"] = str(self.yStartSpinBox.value())
        new_config["Stage_Params"]["Y_Step"] = str(self.yStepSpinBox.value())

        # set odmr sweep params
        new_config["Sweep_Params"]["Sweep_Start"] = str(self.startFreqBox.value())
        new_config["Sweep_Params"]["Sweep_End"] = str(self.endFreqBox.value())
        new_config["Sweep_Params"]["Dwell"] = str(self.dwellTimeBox.value())
        new_config["Sweep_Params"]["Sweep_Step"] = str(self.stepSizeBox.value())
        new_config["Sweep_Params"]["Points"] = str(self.pointsBox.value())
        new_config["Sweep_Params"]["Sweep_Type"] = str(self.sweepDefBox.currentIndex())

        # set rf source params
        new_config["RF_Params"]["Freq"] = str(self.freqBox.value())
        new_config["RF_Params"]["Power"] = str(self.pwrBox.value())
        new_config["RF_Params"]["Power_On"] = str(self.togglePwrChk.isChecked())
        new_config["RF_Params"]["Mod_Freq"] = str(self.modFreqSpinBox.value())
        new_config["RF_Params"]["Mod_Amp"] = str(self.modAmpSpinBox.value())
        new_config["RF_Params"]["Mod_On"] = str(self.toggleModOnOff.isChecked())
        new_config["RF_Params"]["Ext_Mod"] = str(self.toggleExtModOnOff.isChecked())
        new_config["RF_Params"]["A_Matrix_Values"] = self.a_matrix_values

        freqs = []
        grads = []
        for i in range(4):
            try:
                freqs.append(float(self.scanODMRPropertiesTable.item(i, 0).text()))
                grads.append(
                    float(self.scanODMRPropertiesTable.item(i, 1).text())
                )  # gradient used for feedback with vector
            except Exception as error:
                # if table element is empty, skip it
                print(error)
        new_config["RF_Params"]["Feedback_Freq_Table"] = [freqs, grads]

        new_config["LIA_Params"]["Duration"] = str(self.odmrAqDurBox.value())

        new_config["LIA_Params"]["Burst_Dur"] = str(self.odmrAqBurstDurBox.value())
        new_config["LIA_Params"]["Sample_Rate"] = str(self.odmrAqSampleRateBox.value())
        new_config["LIA_Params"]["Scaling"] = str(self.scalingFactorSpinBox.value())
        new_config["LIA_Params"]["Time_Const"] = str(self.timeConstantSpinBox.value())
        new_config["LIA_Params"]["Range"] = str(self.rangeSelect.currentIndex())
        new_config["LIA_Params"]["Filter_Order"] = str(
            self.harmonicOrderSelect.currentIndex()
        )
        new_config["LIA_Params"]["FFT_Average"] = str(self.odmrAqDurBox.value())
        new_config["LIA_Params"]["FFT_Duration"] = str(self.fftAverageSpinBox.value())
        new_config["LIA_Params"]["FFT_Sample_Rate"] = str(
            self.fftDurationSpinBox.value()
        )
        new_config["LIA_Params"]["FFT_AC_Coupling"] = str(
            self.acCoupleCheck.isChecked()
        )
        new_config["LIA_Params"]["FFT_50_Ohm"] = str(self.fiftyOhmCheck.isChecked())

        default_save_path = os.path.join(self.base_dir, "configs", "config.yml")
        filepath = QtWidgets.QFileDialog.getSaveFileName(
            self, "Select File", default_save_path, filter="YAML Files (*.yml *.yaml)"
        )[0]
        if not filepath:
            return
        if not filepath.lower().endswith((".yml", ".yaml")):
            filepath = f"{filepath}.yml"
        with open(filepath, "w") as f:
            yaml.dump(new_config, f, default_flow_style=False)
        self.default_parameters = new_config
        return


class VectorMatrixWindow(QtWidgets.QWidget):
    def __init__(self):
        super(VectorMatrixWindow, self).__init__()
        uic.loadUi(ui_file("vectorMatrixWindow.ui"), self)  # Load the .ui file
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
    """Debug vector test window
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
        uic.loadUi(ui_file("vectorTestWindow.ui"), self)  # Load the .ui file
        apply_ui_polish(self)
        self.show()
        self.scanning = True  # when set to false it will stop threading the function

        # configure the layout of the axes for the two graphs
        self.graphWidget.setLabel(axis="left", text="RF Frequency (GHz)")
        self.graphWidget.setLabel(axis="bottom", text="Index")
        self.graphWidget.setLabel(axis="top", text="RF Frequency Shift (GHz)")
        self.graphWidget_2.setLabel(axis="left", text="Voltage (V)")
        self.graphWidget_2.setLabel(axis="bottom", text="Index")
        self.graphWidget_2.setLabel(axis="top", text="Measured Voltage (V)")

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
                self.vector_freqs.append(
                    float(window.scanODMRPropertiesTable.item(i, 0).text())
                )
                self.vector_grads.append(
                    float(window.scanODMRPropertiesTable.item(i, 1).text())
                )  # gradient used for feedback with vector
            except:
                # if table element is empty, skip it
                pass

        # starts the multi-thread for the vector feedback - prevents other ui elements and calculations being
        # interrupted
        self.thread_function(
            self.initialise_vector_feedback,
            err_fn=window.show_error_message,
            prg_fn=self.debug_plot,
        )

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
        """Starts the vector feedback to keep adjusting the microwave frequencies for 4 ODMR peaks to allow for
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
            window.rfController.inst.write(
                "FREQ " + str(round(float(self.vector_freqs[i]) * 1e9, 12))
            )
            time.sleep(1)
            sample = window.LIAController.daq.getSample(
                "/%s/demods/0/sample" % window.LIAController.device
            )
            ini_voltage.append(sample["x"][0] * scale)
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
                window.rfController.inst.write(
                    "FREQ " + str(round(float(self.vector_freqs[i]) * 1e9, 12))
                )

                time.sleep(
                    0.08
                )  # wait for LIA to calm down after changing RF frequency before measuring voltage
                sample = window.LIAController.daq.getSample(
                    "/%s/demods/0/sample" % window.LIAController.device
                )
                voltage_now = (
                    sample["x"][0] * scale
                )  # Scale the LIA output to match the measured calib. constants.
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
                kwargs["progress_callback"].emit(
                    [res_freq_arr, dV_arr]
                )  # update the graphs
                last_emit = now
        return

    def debug_plot(self, arrs):
        """Updates the debug plots for the measured voltage and frequencies - useful to see how they change over time
        to know if the tracking has lost its lock or not, for example.

        :param arrs: Lists of the measured voltage and frequencies over time to plot to the debug graph widgets
        :return:
        """
        self.vc1.setData(arrs[0][0], pen=pg.mkPen("b"))
        self.vc2.setData(arrs[0][1], pen=pg.mkPen("g"))
        self.vc3.setData(arrs[0][2], pen=pg.mkPen("r"))
        self.vc4.setData(arrs[0][3], pen=pg.mkPen("y"))

        self.fc1.setData(arrs[1][0], pen=pg.mkPen("b"))
        self.fc2.setData(arrs[1][1], pen=pg.mkPen("g"))
        self.fc3.setData(arrs[1][2], pen=pg.mkPen("r"))
        self.fc4.setData(arrs[1][3], pen=pg.mkPen("y"))
        return

    def closeEvent(self, event):
        """this function executes when the vector debug graph window closes, used to stop thread
        :param event:
        :return:
        """
        self.scanning = False  # stops the while loop in initialise_vector_feedback and finishes/kills the thread.


class StageOptions(QtWidgets.QWidget):
    def __init__(self):
        super(
            StageOptions, self
        ).__init__()  # Call the inherited classes __init__ method
        uic.loadUi(ui_file("stage_options.ui"), self)  # Load the .ui file
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
app = QtWidgets.QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
if dark_theme:
    qdarktheme.setup_theme()
window = MainUI()  # Create an instance of our class
app.exec()
