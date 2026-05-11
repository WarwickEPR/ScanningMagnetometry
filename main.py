# -*- coding: utf-8 -*-
"""Scanning Magnetometer main file

This module contains all the classes for the UI such as displaying graphs and opening new windows.
It also controls connections to the different equipment such as COM port serial connections and PyVisa connections. It
also controls the flow of data between these bits of equipment and sorts out the plotting/updating and save/export of
data.
"""

from PyQt6 import QtCore, QtWidgets
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
import socket
from threading_utils import Worker, WorkerSignals, ThreadedComponent
from stage_control import StageControl
from rf_control import RfControl
from lia_control import LIAControl
from windows.fft_window import FFTGraphWindow
from windows.lia_live_trace_window import LIALiveTraceWindow
from windows.odmr_window import ODMRGraphWindow
from windows.scanning_window import scanningImageWindow
from windows.aux_windows_ui import (
    VectorMatrixWindowUIBuilder,
    VectorTestWindowUIBuilder,
    StageOptionsUIBuilder,
)
from main_window_ui import MainWindowUIBuilder
from ui_theme import configure_pyqtgraph_defaults, get_plot_pen, style_plot_labels, style_plot_widget

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
        configure_pyqtgraph_defaults()
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
        self.lia_live_trace_window = None
        self.a_matrix_values = copy.deepcopy(
            self.default_parameters["RF_Params"]["A_Matrix_Values"]
        )
        MainWindowUIBuilder().setup(self)
        self.setMinimumSize(980, 620)
        self.setWindowTitle("Scanning Magnetometer")
        self.show()  # Show the GUI
        self._discovered_lia_ids = []
        self._discovered_lia_ips = []
        self._discovered_rf_ips = []
        self._set_rf_input_mode(False)
        self.useDiscoveredRfCheck.toggled.connect(self._set_rf_input_mode)
        self._set_lia_input_mode(False)
        self.useDiscoveredLiaCheck.toggled.connect(self._set_lia_input_mode)

        self.stageController = StageControl(
            self, StageOptions
        )  # stage controller class instance
        self.rfController = RfControl(self)
        self.LIAController = LIAControl(self)
        self._set_connection_indicator("stage", "disconnected")
        self._set_connection_indicator("rf", "disconnected")
        self._set_connection_indicator("lia", "disconnected")

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

        # Device discovery is now user-triggered via button click.

        # ------------------ UI elements are connected to their respective functions here ------------------ #
        #  stage ui controls
        self.connectStageButton.clicked.connect(self.connect_stage)
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
        self.autoDiscoverDevicesButton.clicked.connect(self.auto_discover_devices)

        #  LIA ui controls
        self.connectLIAButton.clicked.connect(self.connect_lia)

        self.scalingFactorSpinBox.editingFinished.connect(self.on_lia_runtime_setting_changed)
        self.timeConstantSpinBox.editingFinished.connect(self.on_lia_runtime_setting_changed)
        self.rangeSelect.currentIndexChanged.connect(self.on_lia_runtime_setting_changed)
        self.harmonicOrderSelect.currentIndexChanged.connect(self.on_lia_runtime_setting_changed)
        self.acCoupleCheck.stateChanged.connect(self.on_lia_runtime_setting_changed)
        self.fiftyOhmCheck.stateChanged.connect(self.on_lia_runtime_setting_changed)
        self.referenceInputTypeSelect.currentIndexChanged.connect(
            self.on_lia_reference_type_changed
        )
        self.externalRefSignalPathSelect.currentIndexChanged.connect(
            self.on_lia_external_ref_signal_path_changed
        )

        self.takeFFTButton.clicked.connect(self.open_fft_graph)
        self.openLIALiveTraceButton.clicked.connect(self.open_lia_live_trace)
        self.resetAllButton.clicked.connect(self.reset_all)

        #  RF ui controls
        self.takeODMRButton.clicked.connect(self.open_odmr_graph)
        self.connectMWSourceButton.clicked.connect(self.connect_rf)
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
            # ports = serial.tools.list_ports.comports() 
            #filter to usb only, USB devices has vendor IDs, filter by vid to get only USB - more robust incase OS/naming convention changes
            ports = [p.device for p in serial.tools.list_ports.comports() if p.vid is not None]
            available_ports = []
            for port in sorted(ports):
                available_ports.append("{}".format(port))
            test = self.comPortBox
            test.addItems(available_ports)
        except Exception as error:
            error_dialog = QtWidgets.QMessageBox(self)
            error_dialog.setText(f"ERROR: Could not populate COM port list. {str(error)}")
            error_dialog.exec()
        # ------------------ UI ELEMENTS FINISH HERE ------------------ #

        # configure thread pool, needed to multi-threading and asynchronous processing
        self.threadpool = QtCore.QThreadPool()

        # can supress this printout to console to tell user how many threads are available - only really useful for
        # developers
        # print('max %d threads' % self.threadpool.maxThreadCount())
        return
    
    def auto_discover_devices(self):
        found = []
        zurich_ip = None
        zurich_id = None
        discovered_lia_ids = []
        discovered_lia_ips = []
        discovered_rf_ips = []
        rf_ip = None
        base_ip = "192.168.1."
        # print("Zurich open", self.is_port_open("192.168.1.101", port=8004, timeout=0.1))
        for i in range(1,255):
            ip = base_ip + str(i)
            # print(f"Scanning {ip} for devices...")
            if self.is_port_open(ip, timeout=0.1):  # common port for RF sources
                # self.MWSourceIPAddressBox.setText(ip)
                found.append(ip)
                # print(f"Found responsive device at {ip}")
            elif self.is_port_open(ip, port=8004, timeout=0.1):  # common port for Zurich LIAs
                lia_test = self.test_lia_connection(ip)
                if lia_test["Connected"]:
                    print(f"Found responsive Zurich LIA at {ip}")
                    discovered_lia_ips.append(ip)
                    zurich_ip = ip
                    devices = lia_test.get("Devices") or []
                    if devices:
                        discovered_lia_ids.extend(devices)
                        zurich_id = devices[0]
                    # print(f"Zurich LIA details: ID={zurich_id}, IP={zurich_ip}")

                
        # print(f"Auto-discovery complete. Found devices at: {found}")

        rm = pyvisa.ResourceManager()
        # look for agilent
        for ip in found:
            try:
                inst = rm.open_resource(f"TCPIP::{ip}::INSTR")
                idn = inst.query("*IDN?")
                print(f"Device at {ip} responded to *IDN? with: {idn}")
                if "Agilent" in idn or "Keysight" in idn or "N5171B" in idn:
                    print(f"Found compatible RF source at {ip}")
                    discovered_rf_ips.append(ip)
                    rf_ip = ip
            except:
                pass

        self._update_rf_discovered_values(device_ips=discovered_rf_ips)
        
        self._update_lia_discovered_values(
            device_ips=discovered_lia_ips, device_ids=discovered_lia_ids
        )

        if zurich_ip:
            self.LIAIPBox.setText(zurich_ip)
            if zurich_id:
                self.LIANameBox.setText(zurich_id)
        if rf_ip:
            self.MWSourceIPAddressBox.setText(rf_ip)

        return 
    
    def is_port_open(self, ip, port=5025, timeout=1):
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def _set_connection_indicator(self, prefix, state, text=None):
        dot = getattr(self, f"{prefix}ConnectionDot", None)
        label = getattr(self, f"{prefix}ConnectionLabel", None)
        if dot is None or label is None:
            return

        state = state or "disconnected"
        texts = {
            "disconnected": "Disconnected",
            "connecting": "Connecting...",
            "connected": "Connected",
            "error": "Connection failed",
        }

        dot.setProperty("connectionState", state)
        label.setProperty("connectionState", state)
        label.setText(text or texts.get(state, "Unknown"))

        style = self.style()
        style.unpolish(dot)
        style.polish(dot)
        style.unpolish(label)
        style.polish(label)
        dot.update()
        label.update()

    def _set_lia_input_mode(self, use_dropdown_values):
        use_dropdown = bool(use_dropdown_values)
        self.liaDiscoveredIdCombo.setEnabled(use_dropdown)
        self.liaDiscoveredIpCombo.setEnabled(use_dropdown)
        self.LIANameBox.setEnabled(not use_dropdown)
        self.LIAIPBox.setEnabled(not use_dropdown)

    def _set_rf_input_mode(self, use_dropdown_values):
        use_dropdown = bool(use_dropdown_values)
        self.rfDiscoveredIpCombo.setEnabled(use_dropdown)
        self.MWSourceIPAddressBox.setEnabled(not use_dropdown)

    def _update_rf_discovered_values(self, device_ips=None):
        device_ips = device_ips or []
        current_ip = self.rfDiscoveredIpCombo.currentText().strip()

        for ip in device_ips:
            ip_text = str(ip).strip()
            if not ip_text:
                continue
            if self.rfDiscoveredIpCombo.findText(ip_text) < 0:
                self.rfDiscoveredIpCombo.addItem(ip_text)

        if current_ip:
            ip_index = self.rfDiscoveredIpCombo.findText(current_ip)
            if ip_index >= 0:
                self.rfDiscoveredIpCombo.setCurrentIndex(ip_index)
        elif self.rfDiscoveredIpCombo.count() > 0:
            self.rfDiscoveredIpCombo.setCurrentIndex(0)

        self._discovered_rf_ips = [
            self.rfDiscoveredIpCombo.itemText(i)
            for i in range(self.rfDiscoveredIpCombo.count())
        ]

    def _current_rf_connection_ip(self):
        if self.useDiscoveredRfCheck.isChecked():
            ip_address = self.rfDiscoveredIpCombo.currentText().strip()
            source = "dropdown"
        else:
            ip_address = self.MWSourceIPAddressBox.text().strip()
            source = "manual"
        return ip_address, source

    def _update_lia_discovered_values(self, device_ips=None, device_ids=None):
        device_ips = device_ips or []
        device_ids = device_ids or []

        current_ip = self.liaDiscoveredIpCombo.currentText().strip()
        current_id = self.liaDiscoveredIdCombo.currentText().strip()

        for ip in device_ips:
            ip_text = str(ip).strip()
            if not ip_text:
                continue
            if self.liaDiscoveredIpCombo.findText(ip_text) < 0:
                self.liaDiscoveredIpCombo.addItem(ip_text)

        for dev_id in device_ids:
            dev_id_text = str(dev_id).strip()
            if not dev_id_text:
                continue
            if self.liaDiscoveredIdCombo.findText(dev_id_text) < 0:
                self.liaDiscoveredIdCombo.addItem(dev_id_text)

        if current_ip:
            ip_index = self.liaDiscoveredIpCombo.findText(current_ip)
            if ip_index >= 0:
                self.liaDiscoveredIpCombo.setCurrentIndex(ip_index)
        elif self.liaDiscoveredIpCombo.count() > 0:
            self.liaDiscoveredIpCombo.setCurrentIndex(0)

        if current_id:
            id_index = self.liaDiscoveredIdCombo.findText(current_id)
            if id_index >= 0:
                self.liaDiscoveredIdCombo.setCurrentIndex(id_index)
        elif self.liaDiscoveredIdCombo.count() > 0:
            self.liaDiscoveredIdCombo.setCurrentIndex(0)

        self._discovered_lia_ips = [
            self.liaDiscoveredIpCombo.itemText(i)
            for i in range(self.liaDiscoveredIpCombo.count())
        ]
        self._discovered_lia_ids = [
            self.liaDiscoveredIdCombo.itemText(i)
            for i in range(self.liaDiscoveredIdCombo.count())
        ]

    def _current_lia_connection_values(self):
        if self.useDiscoveredLiaCheck.isChecked():
            device_id = self.liaDiscoveredIdCombo.currentText().strip()
            device_ip = self.liaDiscoveredIpCombo.currentText().strip()
            source = "dropdown"
        else:
            device_id = self.LIANameBox.text().strip()
            device_ip = self.LIAIPBox.text().strip()
            source = "manual"
        return device_id, device_ip, source

    def reset_all(self):
        """Stop all running operations and reconnect all three instruments."""
        # --- stop LIA live trace ---
        self.stop_lia_live_trace()

        # --- stop and close scan window ---
        if self.scan_window is not None:
            try:
                self.scan_window.scanning = False
                self.scan_window.close()
            except Exception:
                pass
            self.scan_window = None

        # --- stop and close ODMR window ---
        if self.odmr_graph_window is not None:
            try:
                self.odmr_graph_window.worker_running = False
                self.odmr_graph_window.close()
            except Exception:
                pass
            self.odmr_graph_window = None

        # --- stop and close FFT window ---
        if self.fft_graph_window is not None:
            try:
                if getattr(self.fft_graph_window, "worker_running", False):
                    self.fft_graph_window.stop_fft()
                self.fft_graph_window.close()
            except Exception:
                pass
            self.fft_graph_window = None

        # --- stop vector test tracking if open ---
        if self.vector_test_window is not None:
            try:
                self.vector_test_window.stop_tracking()
            except Exception:
                pass

        # --- reconnect all instruments ---
        self.connect_stage()
        self.connect_rf()
        self.connect_lia()

    def connect_stage(self):
        port = self.comPortBox.currentText().strip()
        if not port:
            self._set_connection_indicator("stage", "error", "No COM port selected")
            return

        self._set_connection_indicator("stage", "connecting", f"Connecting to {port}...")
        connected = self.stageController.connect_stage(port)
        if connected:
            self._set_connection_indicator("stage", "connected", f"Connected: {port}")
        else:
            self._set_connection_indicator("stage", "error", f"Failed: {port}")

    def connect_rf(self):
        ip_address, source = self._current_rf_connection_ip()
        if not ip_address:
            if source == "dropdown":
                self._set_connection_indicator("rf", "error", "Select RF IP from dropdown")
            else:
                self._set_connection_indicator("rf", "error", "No IP address provided")
            return

        self._set_connection_indicator("rf", "connecting", f"Connecting to {ip_address}...")
        self.rfController.thread_function(
            self.rfController.connect_rf,
            ip_address,
            fin_fn=self._on_rf_connected,
            err_fn=self._on_rf_connection_error,
        )

    def _on_rf_connected(self, _result):
        ip_address, _source = self._current_rf_connection_ip()
        self._set_connection_indicator("rf", "connected", f"Connected: {ip_address}")

    def _on_rf_connection_error(self, error):
        ip_address, _source = self._current_rf_connection_ip()
        self._set_connection_indicator("rf", "error", f"Failed: {ip_address}")
        self.show_error_message(error)

    def connect_lia(self):
        device_id, device_ip, source = self._current_lia_connection_values()
        if not device_id or not device_ip:
            if source == "dropdown":
                self._set_connection_indicator(
                    "lia", "error", "Select Device ID and IP from dropdowns"
                )
            else:
                self._set_connection_indicator("lia", "error", "Device ID/IP required")
            return

        self._set_connection_indicator(
            "lia", "connecting", f"Connecting {device_id} @ {device_ip}..."
        )
        self.LIAController.thread_function(
            self.LIAController.connect_lia,
            device_id=device_id,
            device_ip=device_ip,
            fin_fn=self._on_lia_connected,
            err_fn=self._on_lia_connection_error,
        )
    
    def test_lia_connection(self, ip):
        try:
            daq = zhinst.core.ziDAQServer(ip, 8004, 6)
            ziDisc = zhinst.core.ziDiscovery()
            devices = ziDisc.findAll()
            return {"Connected": True, "Devices": devices, "Error": None}
        except Exception as error:
            return {"Connected": False, "Devices": None, "Error": str(error)}

    def _on_lia_connected(self, _result):
        device_id, _device_ip, _source = self._current_lia_connection_values()
        self._set_connection_indicator("lia", "connected", f"Connected: {device_id}")
        self.on_lia_reference_type_changed(self.referenceInputTypeSelect.currentIndex())
        self.on_lia_external_ref_signal_path_changed(
            self.externalRefSignalPathSelect.currentIndex()
        )

    def _on_lia_connection_error(self, error):
        device_id, _device_ip, _source = self._current_lia_connection_values()
        self._set_connection_indicator("lia", "error", f"Failed: {device_id}")
        self.show_error_message(error)

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
                "Ref_Input_Type": "internal",
                "Ext_Ref_Signal_Path": "8",
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
        if self.fft_graph_window is not None:
            try:
                if getattr(self.fft_graph_window, "worker_running", False):
                    self.fft_graph_window.stop_fft()
            except Exception:
                pass
            try:
                self.fft_graph_window.close()
            except Exception:
                pass
        self.fft_graph_window = FFTGraphWindow(self)

    def open_odmr_graph(self):
        """Opens the ODMR graph window for ODMR sweeps and fitting parameters"""
        self.stop_lia_live_trace()
        window.takeODMRButton.setEnabled(
            False
        )  # stops multiple windows being opened and causing strangness occuring
        self.odmr_graph_window = ODMRGraphWindow(self)

    def open_scan_window(self):
        """Opens the scan window which shows any feedback/vector tracking graphs as well as showing a real-time image
        of the current scan.
        """
        self.stop_lia_live_trace()
        self.scan_window = scanningImageWindow(self)

    def open_lia_live_trace(self):
        if (
            self.lia_live_trace_window is None
            or not self.lia_live_trace_window.isVisible()
        ):
            self.lia_live_trace_window = LIALiveTraceWindow(self)
        else:
            self.lia_live_trace_window.raise_()
            self.lia_live_trace_window.activateWindow()

    def stop_lia_live_trace(self):
        if self.lia_live_trace_window is not None:
            self.lia_live_trace_window.stop_stream()

    def open_data_viewer(self):
        self.data_viewer_window = data_viewer.DataViewer()
        return

    def on_lia_runtime_setting_changed(self):
        if not self.LIAController.LIA_connected:
            return
        self.LIAController.thread_function(
            self.LIAController.apply_runtime_settings,
            err_fn=self.show_error_message,
        )

    def on_lia_reference_type_changed(self, _index):
        reference_type = self.referenceInputTypeSelect.currentText().strip().lower()
        is_external = reference_type == "external"
        self.externalRefSignalPathSelect.setEnabled(is_external)

        if not self.LIAController.LIA_connected:
            return
        self.LIAController.thread_function(
            self.LIAController.set_reference_input_type,
            reference_type,
            err_fn=self.show_error_message,
        )

    def on_lia_external_ref_signal_path_changed(self, value):
        if self.referenceInputTypeSelect.currentText().strip().lower() != "external":
            return
        if not self.LIAController.LIA_connected:
            return
        signal_path_integer = self.externalRefSignalPathSelect.currentData()
        if signal_path_integer is None:
            return
        self.LIAController.thread_function(
            self.LIAController.set_external_reference_signal_path,
            int(signal_path_integer),
            err_fn=self.show_error_message,
        )

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
            self._update_lia_discovered_values(
                device_ips=[self.LIAIPBox.text().strip()],
                device_ids=[self.LIANameBox.text().strip()],
            )
            self.MWSourceIPAddressBox.setText(
                self.default_parameters["Connection_Params"]["RF_IP"]
            )
            self._update_rf_discovered_values(
                device_ips=[self.MWSourceIPAddressBox.text().strip()]
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

            ref_input_type = str(
                self.default_parameters["LIA_Params"].get("Ref_Input_Type", "internal")
            ).strip().lower()
            ref_index = 0 if ref_input_type == "internal" else 1
            self.referenceInputTypeSelect.setCurrentIndex(ref_index)
            ext_ref_signal_path = int(
                self.default_parameters["LIA_Params"].get("Ext_Ref_Signal_Path", 8)
            )
            ext_ref_index = self.externalRefSignalPathSelect.findData(ext_ref_signal_path)
            if ext_ref_index < 0:
                ext_ref_index = self.externalRefSignalPathSelect.findData(8)
            self.externalRefSignalPathSelect.setCurrentIndex(ext_ref_index)
            self.externalRefSignalPathSelect.setEnabled(ref_input_type == "external")
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
        rf_ip, _source = self._current_rf_connection_ip()
        new_config["Connection_Params"]["RF_IP"] = str(rf_ip)

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
        new_config["LIA_Params"]["FFT_Average"] = str(self.fftAverageSpinBox.value())
        new_config["LIA_Params"]["FFT_Duration"] = str(self.fftDurationSpinBox.value())
        new_config["LIA_Params"]["FFT_Sample_Rate"] = str(
            self.sampleRateSpinBox.value()
        )
        new_config["LIA_Params"]["FFT_AC_Coupling"] = str(
            self.acCoupleCheck.isChecked()
        )
        new_config["LIA_Params"]["FFT_50_Ohm"] = str(self.fiftyOhmCheck.isChecked())
        new_config["LIA_Params"]["Ref_Input_Type"] = str(
            self.referenceInputTypeSelect.currentText().strip().lower()
        )
        ext_ref_signal_path = self.externalRefSignalPathSelect.currentData()
        if ext_ref_signal_path is None:
            ext_ref_signal_path = 8
        new_config["LIA_Params"]["Ext_Ref_Signal_Path"] = str(
            int(ext_ref_signal_path)
        )

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
        VectorMatrixWindowUIBuilder().setup(self)
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

        self.df4dbx.setValue(window.a_matrix_values[3][0])
        self.df4dby.setValue(window.a_matrix_values[3][1])
        self.df4dbz.setValue(window.a_matrix_values[3][2])

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
        VectorTestWindowUIBuilder().setup(self)
        self.show()
        self.scanning = False  # when set to false it will stop threading the function
        self.worker_running = False
        self.feedback_started = False
        self.feedback_voltage_avg_samples = 3
        self.feedback_voltage_sample_spacing_s = 0.01
        self.max_df_step_mhz = 0.4
        self.max_tracking_offset_mhz = 25.0
        self.min_gradient_abs = 1e-6
        self.max_history_points = 100
        self.emit_interval_s = 0.1
        self.use_scaled_feedback_voltage = False
        self.deadband_voltage = 0.0
        self.enable_baseline_adaptation = False
        self.baseline_adapt_alpha = 0.0
        self.feedback_control_mode = "Proportional"
        self.pid_kp = 1.0
        self.pid_ki = 0.0
        self.pid_kd = 0.0
        self.pid_integral_limit = 5.0
        self.feedback_demod_mode = "R"
        self._load_feedback_controls()
        self._update_live_diagnostics({})
        if hasattr(self, "vectorTrackedResonanceCombo"):
            self.vectorTrackedResonanceCombo.setEnabled(False)
        if hasattr(self, "vectorTrackingModeCombo"):
            self.vectorTrackingModeCombo.currentIndexChanged.connect(
                self._on_tracking_mode_changed
            )
        if hasattr(self, "vectorStartButton"):
            self.vectorStartButton.clicked.connect(self.start_tracking)
        if hasattr(self, "vectorStopButton"):
            self.vectorStopButton.clicked.connect(self.stop_tracking)

        # configure the layout of the axes for the two graphs
        style_plot_widget(self.graphWidget)
        style_plot_widget(self.graphWidget_2)
        style_plot_labels(
            self.graphWidget,
            left="Frequency Shift (MHz)",
            bottom="Index",
            top="Relative Shift from Start",
        )
        style_plot_labels(
            self.graphWidget_2,
            left="Voltage (V)",
            bottom="Index",
            top="Measured Voltage (V)",
        )

        # calls pyqtgraph.PlotItem.plot() and creates a new plot window showing the data (which to start with is empty)
        self.vc1 = self.graphWidget.plot()
        self.vc2 = self.graphWidget.plot()
        self.vc3 = self.graphWidget.plot()
        self.vc4 = self.graphWidget.plot()

        self.fc1 = self.graphWidget_2.plot()
        self.fc2 = self.graphWidget_2.plot()
        self.fc3 = self.graphWidget_2.plot()
        self.fc4 = self.graphWidget_2.plot()

        self.vector_freqs = [None, None, None, None]
        self.vector_grads = [None, None, None, None]
        self._reload_vector_feedback_targets()

        self._on_tracking_mode_changed(0)
        self._get_active_tracking_indices(validate=True)
        self.initial_vector_freqs = list(self.vector_freqs)

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

    def _reload_vector_feedback_targets(self):
        self.vector_freqs = [None, None, None, None]
        self.vector_grads = [None, None, None, None]
        for i in range(4):
            try:
                freq_item = window.scanODMRPropertiesTable.item(i, 0)
                grad_item = window.scanODMRPropertiesTable.item(i, 1)
                if freq_item is None or grad_item is None:
                    continue
                self.vector_freqs[i] = float(freq_item.text())
                self.vector_grads[i] = float(grad_item.text())
            except Exception:
                pass

    def start_tracking(self):
        if self.worker_running:
            return

        self._reload_vector_feedback_targets()
        self._get_active_tracking_indices(validate=True)
        self.initial_vector_freqs = list(self.vector_freqs)
        self._update_live_diagnostics({})
        self.debug_plot([
            [[], [], [], []],
            [[], [], [], []],
            {"active_indices": self._get_active_tracking_indices(validate=False)},
        ])

        self.scanning = True
        self.feedback_started = False
        self.worker_running = True
        if hasattr(self, "vectorStartButton"):
            self.vectorStartButton.setEnabled(False)
        if hasattr(self, "vectorStopButton"):
            self.vectorStopButton.setEnabled(True)

        self.thread_function(
            self.initialise_vector_feedback,
            err_fn=window.show_error_message,
            prg_fn=self.debug_plot,
        )
        if hasattr(self, "worker"):
            self.worker.signals.finished.connect(self._on_tracking_finished)

    def stop_tracking(self):
        self.scanning = False
        self.feedback_started = False
        if hasattr(self, "vectorStopButton"):
            self.vectorStopButton.setEnabled(False)

    def _on_tracking_finished(self):
        self.scanning = False
        self.feedback_started = False
        self.worker_running = False
        if hasattr(self, "vectorStartButton"):
            self.vectorStartButton.setEnabled(True)
        if hasattr(self, "vectorStopButton"):
            self.vectorStopButton.setEnabled(False)

    @staticmethod
    def _sleep_with_stop_flag(instance, duration_s, chunk_s=0.01):
        end_t = time.monotonic() + max(0.0, float(duration_s))
        while time.monotonic() < end_t:
            if not instance.scanning:
                return False
            time.sleep(min(chunk_s, end_t - time.monotonic()))
        return True

    @staticmethod
    def _set_rf_frequency_ghz(rf_inst, frequency_ghz):
        rf_inst.write("FREQ " + str(round(float(frequency_ghz) * 1e9, 12)))

    def _on_tracking_mode_changed(self, _index):
        if hasattr(self, "vectorTrackedResonanceCombo"):
            single_mode = (
                hasattr(self, "vectorTrackingModeCombo")
                and self.vectorTrackingModeCombo.currentText() == "Single resonance"
            )
            self.vectorTrackedResonanceCombo.setEnabled(single_mode)

    def _get_active_tracking_indices(self, validate=False):
        mode = (
            self.vectorTrackingModeCombo.currentText()
            if hasattr(self, "vectorTrackingModeCombo")
            else "Four resonances"
        )
        available_indices = [
            i
            for i, (freq, grad) in enumerate(zip(self.vector_freqs, self.vector_grads))
            if freq is not None and grad is not None
        ]

        if not available_indices:
            if validate:
                raise ValueError("No resonance frequency/gradient pairs are available.")
            return []

        if mode == "Single resonance":
            selected_index = (
                self.vectorTrackedResonanceCombo.currentIndex()
                if hasattr(self, "vectorTrackedResonanceCombo")
                else 0
            )
            if selected_index not in available_indices:
                if validate:
                    raise ValueError(
                        f"Selected resonance {selected_index + 1} does not have a valid frequency/gradient pair."
                    )
                return []
            return [selected_index]

        if validate and len(available_indices) < 4:
            raise ValueError(
                "Four resonance mode requires 4 frequency/gradient pairs in the feedback table."
            )
        return available_indices

    def _load_feedback_controls(self):
        # Seed UI controls with current defaults and sync internal values.
        if hasattr(self, "vectorAvgSamplesSpinBox"):
            self.vectorAvgSamplesSpinBox.setValue(int(self.feedback_voltage_avg_samples))
        if hasattr(self, "vectorSampleSpacingSpinBox"):
            self.vectorSampleSpacingSpinBox.setValue(float(self.feedback_voltage_sample_spacing_s))
        if hasattr(self, "vectorMaxDfStepSpinBox"):
            self.vectorMaxDfStepSpinBox.setValue(float(self.max_df_step_mhz))
        if hasattr(self, "vectorMaxTrackingOffsetSpinBox"):
            self.vectorMaxTrackingOffsetSpinBox.setValue(float(self.max_tracking_offset_mhz))
        if hasattr(self, "vectorEmitIntervalSpinBox"):
            self.vectorEmitIntervalSpinBox.setValue(float(self.emit_interval_s))
        if hasattr(self, "vectorUseScaledFeedbackCheckBox"):
            self.vectorUseScaledFeedbackCheckBox.setChecked(
                bool(self.use_scaled_feedback_voltage)
            )
        if hasattr(self, "vectorDeadbandSpinBox"):
            self.vectorDeadbandSpinBox.setValue(float(self.deadband_voltage))
        if hasattr(self, "vectorBaselineAdaptCheckBox"):
            self.vectorBaselineAdaptCheckBox.setChecked(
                bool(self.enable_baseline_adaptation)
            )
        if hasattr(self, "vectorBaselineAdaptAlphaSpinBox"):
            self.vectorBaselineAdaptAlphaSpinBox.setValue(float(self.baseline_adapt_alpha))
        if hasattr(self, "vectorControlModeCombo"):
            self.vectorControlModeCombo.setCurrentText(str(self.feedback_control_mode))
        if hasattr(self, "vectorPidKpSpinBox"):
            self.vectorPidKpSpinBox.setValue(float(self.pid_kp))
        if hasattr(self, "vectorPidKiSpinBox"):
            self.vectorPidKiSpinBox.setValue(float(self.pid_ki))
        if hasattr(self, "vectorPidKdSpinBox"):
            self.vectorPidKdSpinBox.setValue(float(self.pid_kd))
        if hasattr(self, "vectorPidIntegralLimitSpinBox"):
            self.vectorPidIntegralLimitSpinBox.setValue(float(self.pid_integral_limit))
        if hasattr(self, "vectorDemodFeedbackModeCombo"):
            self.vectorDemodFeedbackModeCombo.setCurrentText(str(self.feedback_demod_mode))
        self._on_tracking_mode_changed(0)
        self._refresh_feedback_settings_from_ui()

    def _refresh_feedback_settings_from_ui(self):
        # Read user-adjusted control loop settings from UI.
        if hasattr(self, "vectorAvgSamplesSpinBox"):
            self.feedback_voltage_avg_samples = max(1, int(self.vectorAvgSamplesSpinBox.value()))
        if hasattr(self, "vectorSampleSpacingSpinBox"):
            self.feedback_voltage_sample_spacing_s = max(
                0.0, float(self.vectorSampleSpacingSpinBox.value())
            )
        if hasattr(self, "vectorMaxDfStepSpinBox"):
            self.max_df_step_mhz = max(1e-6, float(self.vectorMaxDfStepSpinBox.value()))
        if hasattr(self, "vectorMaxTrackingOffsetSpinBox"):
            self.max_tracking_offset_mhz = max(
                1e-6, float(self.vectorMaxTrackingOffsetSpinBox.value())
            )
        if hasattr(self, "vectorEmitIntervalSpinBox"):
            self.emit_interval_s = max(0.01, float(self.vectorEmitIntervalSpinBox.value()))
        if hasattr(self, "vectorUseScaledFeedbackCheckBox"):
            self.use_scaled_feedback_voltage = bool(
                self.vectorUseScaledFeedbackCheckBox.isChecked()
            )
        if hasattr(self, "vectorDeadbandSpinBox"):
            self.deadband_voltage = max(0.0, float(self.vectorDeadbandSpinBox.value()))
        if hasattr(self, "vectorBaselineAdaptCheckBox"):
            self.enable_baseline_adaptation = bool(
                self.vectorBaselineAdaptCheckBox.isChecked()
            )
        if hasattr(self, "vectorBaselineAdaptAlphaSpinBox"):
            self.baseline_adapt_alpha = max(
                0.0, float(self.vectorBaselineAdaptAlphaSpinBox.value())
            )
        if hasattr(self, "vectorControlModeCombo"):
            self.feedback_control_mode = str(self.vectorControlModeCombo.currentText())
        if hasattr(self, "vectorPidKpSpinBox"):
            self.pid_kp = max(0.0, float(self.vectorPidKpSpinBox.value()))
        if hasattr(self, "vectorPidKiSpinBox"):
            self.pid_ki = max(0.0, float(self.vectorPidKiSpinBox.value()))
        if hasattr(self, "vectorPidKdSpinBox"):
            self.pid_kd = max(0.0, float(self.vectorPidKdSpinBox.value()))
        if hasattr(self, "vectorPidIntegralLimitSpinBox"):
            self.pid_integral_limit = max(0.0, float(self.vectorPidIntegralLimitSpinBox.value()))
        if hasattr(self, "vectorDemodFeedbackModeCombo"):
            self.feedback_demod_mode = str(self.vectorDemodFeedbackModeCombo.currentText())

    def _compute_pid_df(self, error_mhz, index, pid_integral, pid_prev_error, pid_prev_time):
        now_t = time.monotonic()
        prev_t = pid_prev_time[index]
        dt = max(1e-3, now_t - prev_t) if prev_t is not None else 0.0

        if dt > 0.0 and self.pid_ki > 0.0:
            pid_integral[index] += error_mhz * dt
            if self.pid_integral_limit > 0.0:
                pid_integral[index] = float(
                    np.clip(pid_integral[index], -self.pid_integral_limit, self.pid_integral_limit)
                )

        derivative = 0.0
        if dt > 0.0 and pid_prev_error[index] is not None:
            derivative = (error_mhz - pid_prev_error[index]) / dt

        pid_prev_error[index] = error_mhz
        pid_prev_time[index] = now_t

        p_term = self.pid_kp * error_mhz
        i_term = self.pid_ki * pid_integral[index]
        d_term = self.pid_kd * derivative
        output = p_term + i_term + d_term
        return float(output), float(p_term), float(i_term), float(d_term)

    def _read_lia_voltage_average(self, lia_daq, lia_device, scale):
        self._refresh_feedback_settings_from_ui()
        samples = []
        demod_path = f"/{lia_device}/demods/0/sample"
        for sample_index in range(max(1, int(self.feedback_voltage_avg_samples))):
            sample = lia_daq.getSample(demod_path)
            x_val = float(sample["x"][0])
            y_val = float(sample["y"][0])
            if self.feedback_demod_mode == "X":
                signal_value = x_val
            else:
                signal_value = float(np.hypot(x_val, y_val))
            samples.append(signal_value * float(scale))
            if sample_index < int(self.feedback_voltage_avg_samples) - 1:
                if not self._sleep_with_stop_flag(
                    self, self.feedback_voltage_sample_spacing_s
                ):
                    break
        if not samples:
            raise RuntimeError("Failed to read LIA sample for vector feedback.")
        return float(np.mean(samples))

    def _update_live_diagnostics(self, diag):
        dv_values = diag.get("dV", []) if isinstance(diag, dict) else []
        df_values = diag.get("df", []) if isinstance(diag, dict) else []
        db_flags = diag.get("deadband", []) if isinstance(diag, dict) else []
        p_values = diag.get("p", []) if isinstance(diag, dict) else []
        i_values = diag.get("i", []) if isinstance(diag, dict) else []
        d_values = diag.get("d", []) if isinstance(diag, dict) else []

        dv_labels = getattr(self, "vectorDiagDvLabels", [])
        df_labels = getattr(self, "vectorDiagDfLabels", [])
        db_labels = getattr(self, "vectorDiagDbLabels", [])
        p_labels = getattr(self, "vectorDiagPLabels", [])
        i_labels = getattr(self, "vectorDiagILabels", [])
        d_labels = getattr(self, "vectorDiagDLabels", [])
        for i in range(
            min(
                4,
                len(dv_labels),
                len(df_labels),
                len(db_labels),
                len(p_labels),
                len(i_labels),
                len(d_labels),
            )
        ):
            if i < len(dv_values) and dv_values[i] is not None:
                dv_labels[i].setText(f"{float(dv_values[i]):+.4g}")
            else:
                dv_labels[i].setText("-")

            if i < len(df_values) and df_values[i] is not None:
                df_labels[i].setText(f"{float(df_values[i]):+.4g}")
            else:
                df_labels[i].setText("-")

            if i < len(db_flags):
                db_labels[i].setText("ON" if bool(db_flags[i]) else "OFF")
            else:
                db_labels[i].setText("-")

            if i < len(p_values) and p_values[i] is not None:
                p_labels[i].setText(f"{float(p_values[i]):+.4g}")
            else:
                p_labels[i].setText("-")

            if i < len(i_values) and i_values[i] is not None:
                i_labels[i].setText(f"{float(i_values[i]):+.4g}")
            else:
                i_labels[i].setText("-")

            if i < len(d_values) and d_values[i] is not None:
                d_labels[i].setText(f"{float(d_values[i]):+.4g}")
            else:
                d_labels[i].setText("-")

    def initialise_vector_feedback(self, *args, **kwargs):
        """Starts the vector feedback to keep adjusting the microwave frequencies for 4 ODMR peaks to allow for
        calculation of the magnetic field vector

        :param args:
        :param kwargs: contains the callback to emit the signal to execute the progress function given to the
                        thread_function
        :return:
        """
        rf_inst = getattr(window.rfController, "inst", None)
        lia_daq = getattr(window.LIAController, "daq", None)
        lia_device = getattr(window.LIAController, "device", None)
        if rf_inst is None:
            raise RuntimeError("RF source is not connected. Connect RF before vector test.")
        if lia_daq is None or lia_device is None:
            raise RuntimeError("LIA is not connected. Connect LIA before vector test.")

        runtime_scale = float(
            getattr(window.LIAController, "scaling_Factor", None)
            or window.scalingFactorSpinBox.value()
            or 1.0
        )
        scale = runtime_scale if self.use_scaled_feedback_voltage else 1.0
        active_indices = self._get_active_tracking_indices(validate=True)

        weak_gradient_rows = [
            str(i + 1)
            for i in active_indices
            if abs(float(self.vector_grads[i])) < max(self.min_gradient_abs, 1e-3)
        ]
        if weak_gradient_rows:
            print(
                "[VectorTest] Warning: very small gradient magnitude in rows "
                + ", ".join(weak_gradient_rows)
                + ". This can cause runaway tracking."
            )

        active_gradients = [float(self.vector_grads[i]) for i in active_indices]
        if len(active_gradients) > 1 and (
            all(g >= 0 for g in active_gradients) or all(g <= 0 for g in active_gradients)
        ):
            print(
                "[VectorTest] Warning: all gradient signs are identical. "
                "Check resonance slope sign for each tracked point."
            )
        settle_time_s = max(
            0.03,
            min(
                0.3,
                3.0 * (float(window.timeConstantSpinBox.value()) / 1e6),
            ),
        )
        ini_voltage = [None, None, None, None]

        #  iterate through the starting frequency list, set the RF source to that value and get the voltage value
        # this will be used as the set-point for the feedback, these are appended to list ini_voltage
        for i in [index for index, value in enumerate(self.vector_freqs) if value is not None]:
            if not self.scanning:
                return
            self._set_rf_frequency_ghz(rf_inst, self.vector_freqs[i])
            if not self._sleep_with_stop_flag(self, settle_time_s):
                return
            ini_voltage[i] = (
                self._read_lia_voltage_average(lia_daq, lia_device, scale)
            )
        self.feedback_started = True  # check if the feedback is on or off and stop the thread if set to false
        df_arr = [[], [], [], []]
        dV_arr = [[], [], [], []]
        res_freq_arr = [[], [], [], []]
        shift_mhz_arr = [[], [], [], []]
        latest_dv = [None, None, None, None]
        latest_df = [None, None, None, None]
        latest_db = [False for _ in range(len(self.vector_freqs))]
        latest_p = [None, None, None, None]
        latest_i = [None, None, None, None]
        latest_d = [None, None, None, None]
        pid_integral = [0.0, 0.0, 0.0, 0.0]
        pid_prev_error = [None, None, None, None]
        pid_prev_time = [None, None, None, None]
        last_emit = 0.0
        while self.scanning:
            self._refresh_feedback_settings_from_ui()
            active_indices = self._get_active_tracking_indices(validate=True)
            # iterate over the 4 freqs in the list and calculate the difference between the voltage now and its
            # respective set-point voltage. This difference in voltage, along with the given calib const. (V/MHz) is
            # used to calculate the field vectors.
            for i in range(len(self.vector_freqs)):
                if i not in active_indices:
                    latest_dv[i] = None
                    latest_df[i] = None
                    latest_db[i] = False
                    latest_p[i] = None
                    latest_i[i] = None
                    latest_d[i] = None
                    pid_prev_time[i] = None
                    pid_prev_error[i] = None
                    pid_integral[i] = 0.0
                    continue
                if not self.scanning:
                    break
                self._set_rf_frequency_ghz(rf_inst, self.vector_freqs[i])

                if not self._sleep_with_stop_flag(self, settle_time_s):
                    break

                voltage_now = self._read_lia_voltage_average(
                    lia_daq, lia_device, scale
                )
                self.dV = voltage_now - ini_voltage[i]
                gradient = float(self.vector_grads[i])
                if abs(gradient) < self.min_gradient_abs:
                    raise ValueError(
                        f"Gradient for resonance {i + 1} is too close to zero ({gradient})."
                    )

                error_mhz = (1.0 / gradient) * (-self.dV)

                if abs(self.dV) < self.deadband_voltage:
                    raw_df = 0.0
                    p_term = 0.0
                    i_term = 0.0
                    d_term = 0.0
                    latest_db[i] = True
                    pid_prev_time[i] = None
                    pid_prev_error[i] = 0.0
                else:
                    if self.feedback_control_mode == "PID":
                        raw_df, p_term, i_term, d_term = self._compute_pid_df(
                            error_mhz, i, pid_integral, pid_prev_error, pid_prev_time
                        )
                    else:
                        raw_df = error_mhz  # freq. shift in MHz
                        p_term = raw_df
                        i_term = 0.0
                        d_term = 0.0
                    latest_db[i] = False

                self.df = float(
                    np.clip(raw_df, -self.max_df_step_mhz, self.max_df_step_mhz)
                )

                candidate_freq = self.vector_freqs[i] + self.df / 1e3
                base_freq = self.initial_vector_freqs[i]
                min_freq = base_freq - (self.max_tracking_offset_mhz / 1e3)
                max_freq = base_freq + (self.max_tracking_offset_mhz / 1e3)
                self.vector_freqs[i] = float(np.clip(candidate_freq, min_freq, max_freq))

                if self.enable_baseline_adaptation and self.baseline_adapt_alpha > 0.0:
                    ini_voltage[i] = (
                        (1.0 - self.baseline_adapt_alpha) * ini_voltage[i]
                        + self.baseline_adapt_alpha * voltage_now
                    )

                # append results to list for plotting to graphs later
                df_arr[i].append(self.df)
                dV_arr[i].append(self.dV)
                res_freq_arr[i].append(self.vector_freqs[i])
                shift_mhz_arr[i].append((self.vector_freqs[i] - self.initial_vector_freqs[i]) * 1e3)
                latest_dv[i] = self.dV
                latest_df[i] = self.df
                latest_p[i] = p_term
                latest_i[i] = i_term
                latest_d[i] = d_term

            # Trim each trace independently so single-resonance mode and inactive traces can remain empty safely.
            for i in range(len(self.vector_freqs)):
                while len(df_arr[i]) > self.max_history_points:
                    df_arr[i].pop(0)
                while len(dV_arr[i]) > self.max_history_points:
                    dV_arr[i].pop(0)
                while len(res_freq_arr[i]) > self.max_history_points:
                    res_freq_arr[i].pop(0)
                while len(shift_mhz_arr[i]) > self.max_history_points:
                    shift_mhz_arr[i].pop(0)
            # trying to iterate this while loop to fast while plotting causes the software to crash -
            # needs a workaround - using a 100 ms sleep to prevent this at the moment
            if not self._sleep_with_stop_flag(self, 0.03):
                break
            now = time.monotonic()
            if now - last_emit >= self.emit_interval_s:
                kwargs["progress_callback"].emit(
                    [
                        shift_mhz_arr,
                        dV_arr,
                        {
                            "dV": list(latest_dv),
                            "df": list(latest_df),
                            "deadband": list(latest_db),
                            "p": list(latest_p),
                            "i": list(latest_i),
                            "d": list(latest_d),
                            "active_indices": list(active_indices),
                        },
                    ]
                )  # update the graphs
                last_emit = now
        return

    def debug_plot(self, arrs):
        """Updates the debug plots for the measured voltage and frequencies - useful to see how they change over time
        to know if the tracking has lost its lock or not, for example.

        :param arrs: Lists of the measured voltage and frequencies over time to plot to the debug graph widgets
        :return:
        """
        active_indices = []
        if isinstance(arrs, (list, tuple)) and len(arrs) >= 3 and isinstance(arrs[2], dict):
            active_indices = arrs[2].get("active_indices", [])

        freq_plots = [self.vc1, self.vc2, self.vc3, self.vc4]
        volt_plots = [self.fc1, self.fc2, self.fc3, self.fc4]
        for i in range(4):
            if i in active_indices:
                freq_plots[i].setData(arrs[0][i], pen=get_plot_pen(i))
                volt_plots[i].setData(arrs[1][i], pen=get_plot_pen(i))
            else:
                freq_plots[i].setData([], pen=get_plot_pen(i))
                volt_plots[i].setData([], pen=get_plot_pen(i))
        if isinstance(arrs, (list, tuple)) and len(arrs) >= 3 and isinstance(arrs[2], dict):
            self._update_live_diagnostics(arrs[2])
        return

    def closeEvent(self, event):
        """this function executes when the vector debug graph window closes, used to stop thread
        :param event:
        :return:
        """
        self.stop_tracking()  # stops the while loop in initialise_vector_feedback and finishes/kills the thread.
        event.accept()


class StageOptions(QtWidgets.QWidget):
    def __init__(self):
        super(
            StageOptions, self
        ).__init__()  # Call the inherited classes __init__ method
        StageOptionsUIBuilder().setup(self)
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
