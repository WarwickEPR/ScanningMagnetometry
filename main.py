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
from PIL import Image
import sys
import serial
import serial.tools.list_ports
import numpy as np
import time
import traceback
import pyvisa
from sklearn.linear_model import LinearRegression
from scipy.signal import savgol_filter, find_peaks
import zhinst.utils as utils
import zhinst.core
import data_viewer

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
        self.odmr_graph_window = None
        self.fft_graph_window = None
        self.vector_test_window = None
        self.scan_window = None
        uic.loadUi('scanning_magnetometer.ui', self)  # Load the .ui file
        self.show()  # Show the GUI

        self.stageController = StageControl()  # stage controller class instance
        self.rfController = RfControl()
        self.LIAController = LIAControl()

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

    def show_error_message(self, error):
        """ Displays pop up error message for try and except statements. Pass Exception as "error" parameter to display
        error to user if printing to console is not possible (i.e in a binary release.)

        :param error: Exception class - pass in the error from a try/except statement
        :return:
        """
        error_dialog = QtWidgets.QErrorMessage(self)
        error_dialog.showMessage(str(error[1]))
        return

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


class VectorTest(QtWidgets.QWidget):
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
        uic.loadUi('vectorTestWindow.ui', self)  # Load the .ui file
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

    def thread_function(self, fn, *args, **kwargs):
        """

        :param fn: The function you want to have running asynchronously
        :param args: any additional arguments  required, not really used here thinking about it...
        :param kwargs: Contains up to 3 functions, the finish,
                progress and error functions. These will execute for their respective function
        :return:
        """
        self.worker = Worker(fn, args, kwargs)  # Create a Worker class instance
        """connect up the results signal to execute its function when it emits when triggered, 
        the progress signal to execute during each clock cycle and the error signal to execute the error function
        if any issues occur
        """
        if 'fin_fn' in kwargs:
            self.worker.signals.results.connect(kwargs['fin_fn'])
        if 'prg_fn' in kwargs:
            self.worker.signals.progress.connect(kwargs['prg_fn'])
        if 'err_fn' in kwargs:
            self.worker.signals.error.connect(kwargs['err_fn'])
        window.threadpool.start(self.worker)  # start the thread

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
            kwargs['progress_callback'].emit([res_freq_arr, dV_arr])  # update the graphs
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


class StageControl:
    """ Controls the connection to the stage and contains the functions to operate it included the read and send gcode
    functionality

    Attributes:
        ser : serial connection instance
        stage_connected : boolean to check if a successful stage connection has been made
    """

    def __init__(self):
        super(StageControl, self).__init__()
        self.stage_options = None
        self.ser = None
        self.stage_connected = False
        return

    def execute_gcode(self, command):
        """ For sending g-codes to the stage to execute them - does not read any data coming back from the stage, use
        read_gcode for queries.

        :param command: The G-code to send to the printer e.g. G24
        :return:
        """
        try:
            self.ser.write(f'{command}\r\n'.encode())
        except:
            self.show_error_message("ERROR: Could not execute stage command")

    def read_gcode(self, command):
        """ For sending g-codes to the stage where a response is expected and reading it, e.g. getting the current
        stage position.

        :param command: The G-code to send to the printer e.g. G24
        :return:
        """
        try:
            self.ser.write(f'{command}\r\n'.encode())
            self.response = self.ser.readline()
            self.ser.readline()  # clears next line

        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(window)
            error_dialog.showMessage(str(error))
        return self.response

    def connect_stage(self, com_port, baud_rate=115200):
        """

        :param com_port: (str) the com port to connect to i.e "COM4"
        :param baud_rate: (int) the baud rate (or bit rate) of the stage
        :return:
        """
        try:
            # connect to stage code here
            self.ser = serial.Serial(port=com_port, baudrate=baud_rate)
            msg = QtWidgets.QMessageBox(window)
            msg.setText("Connected Successful to: " + str(com_port))
            msg.exec()
            self.stage_connected = True
        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(window)
            error_dialog.showMessage(str(error))
            self.stage_connected = False

    def home_stage(self):
        """ Starts the stage homing process - important to do this before starting a scan so
        x, y and z positions are correct and don't cause stage crashes

        :return:
        """
        self.execute_gcode('G28')  # home gcode
        return

    def set_stage_pos(self, x, y):
        """ Move the stage in the xy plane

        :param x: (float) desired x position
        :param y: (float) desired y position
        :return:
        """
        self.execute_gcode(f'G00 X{x} Y{y}')
        return

    def set_stage_height(self, z):
        """ Move the stage up and down

        :param z: (float) desired z position or "height"
        :return:
        """
        self.execute_gcode(f'G00 Z{z}')
        return

    def get_stage_pos(self):
        """ queries the stage to return its current x y and z coordinates. This may return inaccurate values if printer
        is not homed first

        :return:
        """
        try:
            response = self.read_gcode('M114')
            response = response.decode("utf-8").split()  # response[0] = xPos in mm, [1] = yPos, [2] = zPos
            xPos, yPos, zPos = response[0], response[1], response[2]
            print(xPos)
            window.currentXLabel.setText(xPos)
            window.currentYLabel.setText(yPos)
            window.currentHeightLabel.setText(zPos)
        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(window)
            error_dialog.showMessage(str(error))

    def set_max_stage_position(self):
        """ Opens the stage options window so the users can set the desired max parameters like position and speed.
        Useful if the stage size changes, and it needs to be limited to prevent stage crashing with the sensor head or
        with a sample etc.
        """
        self.stage_options = StageOptions()

    def show_error_message(self, text):
        error_dialog = QtWidgets.QErrorMessage(window)
        error_dialog.showMessage(text)
        return


class RfControl:
    """ Controls the connection to the RF Source - works using a pyVisa connection to the Keysight Signal Generator.
    Class has functions to changing the output frequency/power & modulation settings.

    Attributes:
        mw_power_on : (bool) Checks if the output is on or off for the RF source
        mod_on : (bool) Checks if modulation is applied to the output signal
        rf_connected : (bool) Check if a successful connection has been made to the signal generator
    """
    def __init__(self):
        super(RfControl, self).__init__()
        self.num_points = None
        self.stop_freq = None
        self.start_freq = None
        self.worker_running = None
        self.samples = None
        self.mw_power_on = False
        self.mod_on = False
        self.rf_connected = False

    def thread_function(self, fn, *args, **kwargs):
        """

        :param fn: The function you want to have running asynchronously
        :param args: any additional arguments  required, not really used here thinking about it...
        :param kwargs: Contains up to 3 functions, the finish,
                progress and error functions. These will execute for their respective function
        :return:
        """
        self.worker = Worker(fn, args, kwargs)  # Create a Worker class instance
        """connect up the results signal to execute its function when it emits when triggered, 
        the progress signal to execute during each clock cycle and the error signal to execute the error function
        if any issues occur
        """
        if 'fin_fn' in kwargs:
            self.worker.signals.results.connect(kwargs['fin_fn'])
        if 'prg_fn' in kwargs:
            self.worker.signals.progress.connect(kwargs['prg_fn'])
        if 'err_fn' in kwargs:
            self.worker.signals.error.connect(kwargs['err_fn'])
        window.threadpool.start(self.worker)  # start the thread

    def connect_rf(self, *args, **kwargs):
        """

        :param args: Contains the IP address string from the respective UI text box element
        :param kwargs:
        :return:
        """
        ip_address = args[0][0]
        self.rm = pyvisa.ResourceManager()
        ip_address = "TCPIP::" + ip_address + "::INSTR"
        self.inst = self.rm.open_resource(ip_address,
                                          query_delay = 0.1,
                                          timeout = 0.1,
                                          send_end = True)
        self.inst.read_termination = '\r\n'
        self.inst.write_termination = '\r\n'
        self.inst.chunk_size = 102400
        self.inst.write("*CLS")  # clear error bank

        self.inst.baud_rate = 115200

        window.powerLabel.setText(str(round(float(self.inst.query('POW?')), 3)))
        window.currentFreqLabel.setText(str(round(float(self.get_freq()) / 1e9, 3)))
        mod_freq, mod_amp = self.get_mod_params()
        window.modAmpLabel.setText(str(round(float(mod_amp) / 1e6, 3)))
        window.modFreqLabel.setText(str(round(float(mod_freq) / 1e3, 3)))
        #
        # gets current power state and sets on/off UI button to appropriate state
        power = int(self.inst.query("OUTP?"))
        if power == 0:
            self.mw_power_on = False
            window.togglePwrChk.setChecked(False)
        elif power == 1:
            self.mw_power_on = True
            window.togglePwrChk.setChecked(True)
        time.sleep(0.05)
        power = int(self.inst.query("OUTP?"))
        #
        # set frequency modulation on by default
        time.sleep(0.05)
        self.inst.write('FM:STAT ON')
        time.sleep(0.05)
        self.inst.write('OUTP:MOD:STAT ON')
        time.sleep(0.05)
        self.inst.write('LFO:STAT ON')
        time.sleep(0.05)
        window.toggleModOnOff.setChecked(True)
        self.rf_connected = True
        return

    def power_on_off(self, state):
        """

        :param state: (bool) State of output power on/off wanted by the user
        :return:
        """
        if state:
            self.inst.write('OUTP ON')
            self.mw_power_on = True
        elif not state:
            self.inst.write('OUTP OFF')
            self.mw_power_on = False
        return

    def set_freq(self):
        """ Set the frequency of the RF source using the value in the frequency UI box """
        self.inst.write('FREQ ' + str(round(float(window.freqBox.value()) * 1e9, 12)))
        window.currentFreqLabel.setText(str(round(float(self.get_freq()) / 1e9, 3)))

    def get_freq(self):
        """ Returns the current set output frequency """
        return self.inst.query("FREQ?")

    def set_power(self):
        """ Set the dBm power value of the output signal"""
        self.inst.write(f'POW {float(window.pwrBox.value())} dBm')
        curr_p = round(float(self.inst.query('POW?')), 3)
        window.powerLabel.setText(str(curr_p))

    def mod_on_off(self, state):
        """ Toggle the frequency modulation of the output signal on and off"""
        if state:
            self.mod_on = True
            self.inst.write('FM:STAT ON')
            self.inst.write('OUTP:MOD:STAT ON')
        elif not state:
            self.mod_on = False
            self.inst.write('FM:STAT OFF')
            self.inst.write('OUTP:MOD:STAT OFF')
        return

    def set_mod_params(self):
        """ Set the modulation frequency value and the modulation amplitude using the values in the UI elements"""
        self.inst.write(f'FM {float(window.modAmpSpinBox.value())} MHz')
        self.inst.write(f'FM:INT:FREQ {float(window.modFreqSpinBox.value())} kHz')
        mod_freq, mod_amp = self.get_mod_params()
        window.modAmpLabel.setText(str(round(float(mod_amp) / 1e6, 3)))
        window.modFreqLabel.setText(str(round(float(mod_freq) / 1e3, 3)))
        return

    def get_mod_params(self):
        """ Returns the current value of the frequency modulation frequency and modulation amplitude"""
        return self.inst.query('FM:INT:FREQ?'), self.inst.query('FM?')

    def change_mod_type(self):
        """ Toggle type of FM from square to sine wave """
        if window.squareWaveRadio.isChecked():
            self.inst.write(':FM:INT:FUNC SQU')  # set square wave fm
        elif window.sineWaveRadio.isChecked():
            self.inst.write(':FM:INT:FUNC SIN')  # set sine wave fm

    def ext_mod_on_off(self, state):
        """ Toggles whether the RF source should use its internal signal generator or an external signal for its
        frequency modulation

        :param state: (bool) True for external modulation, False for internal
        :return:
        """
        if state:
            self.inst.write(':FM:SOUR EXT')
        elif not state:
            self.inst.write(':FM:SOUR INT')
        return

    def setup_sweep(self, *args, **kwargs):
        """ Set the correct parameters for both the RF source and the LIA for performing an ODMR sweep. Parameters set
        using the respective UI text/spin/toggle box elements.

        :param args: Contains the float values from the UI elements
        :param kwargs: Contains the function to execute when the callback is emitted, this is used to update ODMR graph
        :return:
        """
        self.worker_running = True  # this will stop the thread when its finished or if the ODMR window closes
        window.LIAController.odmr_sweep = True
        self.sweeping = True
        self.start_freq = args[0][0]  # Start frequency in Hz (e.g., 1 GHz)
        self.stop_freq = args[0][1]  # Stop frequency in Hz (e.g., 2 GHz)
        self.num_points = args[0][2]  # Number of frequency points
        dwell_time = args[0][3] / 1000
        sweep_step = args[0][4]

        # Setting parameters of the RF source
        window.rfController.inst.write(':INIT:CONT OFF')  # set sweep to be continous
        window.rfController.inst.write(':TRIG:SEQ:SOUR BUS')  # sets sweep to trigger on *TRG command
        window.rfController.inst.write(
            'ROUT:CONN:TRIG1:OUTP SRun')  # sets trig out 1 on Keysight to emit pulse when sweep starts, used to trigger LIA
        window.rfController.inst.write('ROUT:CONN:TRIG2:OUTP SETT')
        window.rfController.inst.write(':SOURce:FREQuency:MODE LIST')  # set frequency mode from CW to list sweep
        window.rfController.inst.write(f':SWE:DWELL {dwell_time}')  # set dwell time
        if window.sweepDefBox.currentText() == 'Points':  # if points are used, set points
            window.rfController.inst.write(f':SWE:POINTS {self.num_points}')
        elif window.sweepDefBox.currentText() == 'Step Size':  # if step size used, set step size
            window.rfController.inst.write(f':SWE:STEP {sweep_step} kHz')
        window.rfController.inst.write(f':SOURce:FREQuency:STARt {self.start_freq} GHz')  # set start and end sweep freq
        window.rfController.inst.write(f':SOURce:FREQuency:STOP {self.stop_freq} GHz')
        window.rfController.inst.write('TSWeep')  # Prime the sweep, start sweep with *TRG command
        window.LIAController.setup_sweep()  # setup LIA for data acquisition
        window.LIAController.daq_module.execute()  # arm the acquisition (if triggering) or start aq. immediately if no trigger

        # fudge factor? found in the Zurich LIA docs & examples. No explanation given as to why but
        # think it's related to making sure the buffer is ready before starting measurements
        buffer_size = window.LIAController.daq_module.getInt("buffersize")
        time.sleep(1.2 * buffer_size)

        # Record data in a loop with timeout. Setup variables before triggering sweep
        self.samples = []
        i = 0
        j = 0
        window.rfController.inst.write('*TRG')  # trigger sweep to start
        while self.sweeping:
            data_read = window.LIAController.daq_module.read(True)  # read data
            returned_signal_paths = [signal_path.lower() for signal_path in data_read.keys()]
            for signal_path in window.LIAController.signal_paths:
                if signal_path.lower() in returned_signal_paths:
                    # Loop over all the bursts for the subscribed signal. More than
                    # one burst may be returned at a time, in particular if we call
                    # read() less frequently than the burst_duration.
                    for index, signal_burst in enumerate(data_read[signal_path.lower()]):
                        i += 1
                        self.samples.append(np.mean(signal_burst['value'][0]))
                        window.LIAController.data[signal_path].append(signal_burst)
                    kwargs['progress_callback'].emit(self.samples)
                else:
                    j += 1
                    # Note: If we read before the next burst has finished, there may be no new data.
                    # No action required.
                    pass
            if (int(window.rfController.inst.query(':STATus:OPERation:CONDition?')) & 8) == 8:  # trigger sweep to start
                pass
            else:
                if window.odmrSweepContinous.isChecked():
                    window.LIAController.daq_module.unsubscribe('*')
                    window.rfController.inst.write('TSWeep')
                    window.LIAController.setup_sweep()  # setup LIA for data acquisition
                    self.samples = []
                    window.LIAController.daq_module.execute()
                    time.sleep(1.2 * buffer_size)
                    window.rfController.inst.write('*TRG')
                    pass
                else:
                    window.LIAController.daq_module.finish()
                    self.sweeping = False
        # when sweep is finished, read any leftover data and plot
        # stop acquisition and unsubscribe from module
        window.LIAController.daq_module.unsubscribe('*')
        window.LIAController.odmr_sweep = False
        return


class LIAControl:
    """ Control connection to the Zurich Lock-in amplifier using pyvisa. Also contains the functions to measure inputs
    and outputs of the LIA as well as set various parameters. Also contains the functions to setup different
    data acquisition modules for ODMR sweeps and FFT measurements.

    Attributes:
        LIA_connected : (bool) Zurich LIA connection state
        odmr_sweep : (bool) Is an ODMR sweep currently happening?
        fft_sweep: (bool) Is an FFT sweep/acquisition currently happening?
    """
    def __init__(self):
        super(LIAControl, self).__init__()
        self.data = None
        self.clockbase = None
        self.device_id = None
        self.server_host = None
        self.scaling_Factor = None
        self.LIA_connected = False
        self.odmr_sweep = False
        self.fft_sweep = False
        return

    def thread_function(self, fn, *args, **kwargs):
        """

        :param fn: The function you want to have running asynchronously
        :param args: any additional arguments  required, not really used here thinking about it...
        :param kwargs: Contains up to 3 functions, the finish,
                progress and error functions. These will execute for their respective function
        :return:
        """
        self.worker = Worker(fn, args, kwargs)  # Create a Worker class instance
        """connect up the results signal to execute its function when it emits when triggered, 
        the progress signal to execute during each clock cycle and the error signal to execute the error function
        if any issues occur
        """
        if 'fin_fn' in kwargs:
            self.worker.signals.results.connect(kwargs['fin_fn'])
        if 'prg_fn' in kwargs:
            self.worker.signals.progress.connect(kwargs['prg_fn'])
        if 'err_fn' in kwargs:
            self.worker.signals.error.connect(kwargs['err_fn'])
        window.threadpool.start(self.worker)  # start the thread

    def connect_lia(self, *args, **kwargs):
        """

        :param args:  Contains the UI element strings of IP address for the LIA connection
        :param kwargs:
        :return:
        """
        try:
            self.server_host: str = args[1]['device_ip']  # this needs to be a user input - remove the magic number
            self.device_id = args[1]['device_id']
            server_port = 8004  # this also needs to be a user defined input
            api_level = 6  # determines how detailed returning information from the LIA is when using the API commands
            (self.daq, self.device, _) = zhinst.utils.create_api_session(
                self.device_id, api_level, server_host=self.server_host, server_port=server_port
            )
            zhinst.utils.api_server_version_check(self.daq)
            self.daq.set(f"/{self.device}/demods/0/enable", 1)  # enable the demodulation
            self.clockbase = float(self.daq.getInt(f"/{self.device}/clockbase"))  # get the clockspeed of the LIA for

            self.LIA_connected = True
        except Exception as e:
            # Probably should make this a popup message instead of console output..
            print(e)

    def setup_sweep(self):
        """ Set the parameters and arm the data acquisition module of the LIA, ready to start ODMR sweep.

        :return:
        """
        self.demod_path = f"/{self.device}/demods/0/sample"
        self.signal_paths = []
        self.signal_paths.append(self.demod_path + ".x")
        # set up sweep parameters to get data from Data Aquisition module
        self.total_duration = window.odmrAqDurBox.value()
        self.module_sampling_rate = window.odmrAqSampleRateBox.value()  # Number of points/second
        self.burst_duration = window.odmrAqBurstDurBox.value()  # Time in seconds for each data burst/segment.
        self.num_cols = int(np.ceil(self.module_sampling_rate * self.burst_duration))
        self.num_bursts = int(np.ceil(self.total_duration / self.burst_duration))
        self.daq.sync()
        # Create an instance of the Data Acquisition Module.
        self.daq_module = self.daq.dataAcquisitionModule()
        # Set the device that will be used for the trigger - this parameter must be set

        self.daq_module.set("device", self.device)
        # Configure the Data Acquisition Module.

        trigger = True  # Uses an input on TrigIn1 to trigger the start of the data acquisition
        if trigger:
            self.daq_module.set("grid/mode", 4)
            self.daq_module.set('type', 6)
            self.daq_module.set('triggernode', self.demod_path + '.TrigIn1')  # set trigger input to be TrigIn1
            self.daq_module.set("duration", self.burst_duration)
            self.daq_module.set('edge', 0)
            self.daq_module.set("count", window.pointsBox.value())
            self.daq_module.set("grid/cols", self.module_sampling_rate)
            self.daq_module.set('holdoff/time', 0.001)
            self.daq_module.set('delay', 0)
            self.daq_module.set('endless', 1)
        elif not trigger:  # Specify continuous acquisition (type=0).
            self.daq_module.set("grid/mode", 2)
            self.daq_module.set("type", 0)  # type 0 = no trigger
            self.daq_module.set("count", self.num_bursts)
            self.daq_module.set("duration", self.burst_duration)
            self.daq_module.set("grid/cols", self.num_cols)

        self.data = {}
        # A dictionary to store all the acquired data.
        for signal_path in self.signal_paths:
            print("Subscribing to ", signal_path)
            self.daq_module.subscribe(signal_path)
            self.data[signal_path] = []
        return

    def setup_fft(self):
        """ Set the parameters and arm the data acquisition module of the LIA, ready to start FFT measurement.

            :return:
        """
        self.scaling_Factor = int(window.scalingFactorSpinBox.value())
        demod_select = 0
        v_range = int(window.rangeSelect.currentText())
        imp_fifty = int(window.fiftyOhmCheck.isChecked())
        ac_coupled = int(window.acCoupleCheck.isChecked())
        in_channel = 0
        demod_index = 1
        filter_order = int(window.harmonicOrderSelect.currentText())
        time_constant = (float(window.timeConstantSpinBox.value())) / 1e6  # ~80hz
        exp_setting = [
            ["/%s/sigins/%d/ac" % (self.device, in_channel), ac_coupled],  # ac coupling on/off
            ["/%s/sigins/%d/imp50" % (self.device, in_channel), imp_fifty],  # 50 ohm impednecne on/off
            ["/%s/sigins/%d/range" % (self.device, in_channel), v_range],  # set signal in range
            ["/%s/demods/%d/enable" % (self.device, demod_index), 1],  # enable data transfer
            # set data transfer rate from demod to data server
            ["/%s/demods/%d/adcselect" % (self.device, 0), 0],  # set demodulator 1's input to signal in 1
            ["/%s/demods/%d/adcselect" % (self.device, 1), 8],  # select auxin1 as demodulator 2's input
            # set filter order to 8th order
            ["/%s/demods/%d/timeconstant" % (self.device, demod_index), time_constant],
            # sets low pass filter timeconstant ~ 3db filter freq.
            ["/%s/demods/%d/harmonic" % (self.device, demod_index), 1],  # set mod harmonic to be 1st harmonic
            ["/%s/extrefs/%d/enable" % (self.device, in_channel), 1],  # sets ext ref to be aux in 1
            ["/%s/auxouts/%d/outputselect" % (self.device, 0), demod_select],
            # set output to be demod x (0) or demod y (1)
        ]
        self.daq.set(exp_setting)
        self.daq.set(f"/{self.device}/demods/0/enable", 1)
        self.daq.set(f"/{self.device}/demods/1/enable", 1)
        self.daq.set("/%s/demods/%d/harmonic" % (self.device, demod_index), 1)
        self.daq.set("/%s/auxouts/%d/scale" % (self.device, 0), self.scaling_Factor)
        self.daq.set("/%s/demods/%d/order" % (self.device, demod_index), filter_order)

        demod_path = f"/{self.device}/demods/0/sample"
        self.signal_paths = []
        self.signal_paths.append(demod_path + ".x.fft.abs.avg")

        self.count = int(window.fftAverageSpinBox.value())
        self.fft_duration = int(window.fftDurationSpinBox.value())
        cols = int(window.sampleRateSpinBox.value())

        self.daq_module = self.daq.dataAcquisitionModule()
        self.daq_module.set("device", self.device)
        # Specify continuous acquisition (type=0).
        self.daq_module.set("type", 0)
        self.daq_module.set("grid/mode", 2)
        self.daq_module.set("count", self.count)
        self.daq_module.set("duration", self.fft_duration)
        self.daq_module.set("grid/cols", cols)

        self.data = {}
        # A dictionary to store all the acquired data.
        for signal_path in self.signal_paths:
            print("Subscribing to ", signal_path)
            self.daq_module.subscribe(signal_path)
            self.data[signal_path] = []
        return


class StageOptions(QtWidgets.QWidget):
    def __init__(self):
        super(StageOptions, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('stage_options.ui', self)  # Load the .ui file
        self.show()

    def apply_position_changes(self):
        return

    def apply_speed_changes(self):
        return

    def apply_acceleration_changes(self):
        return

    def apply_jerk_changes(self):
        return


class FFTGraphWindow(QtWidgets.QWidget):
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
        uic.loadUi('FFTGraphWindow.ui', self)  # Load the .ui file
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

    def thread_function(self, fn, *args, **kwargs):
        """

        :param fn: The function you want to have running asynchronously
        :param args: any additional arguments  required, not really used here thinking about it...
        :param kwargs: Contains up to 3 functions, the finish,
                progress and error functions. These will execute for their respective function
        :return:
        """
        self.worker = Worker(fn, args, kwargs)  # Create a Worker class instance
        """connect up the results signal to execute its function when it emits when triggered, 
        the progress signal to execute during each clock cycle and the error signal to execute the error function
        if any issues occur
        """
        if 'fin_fn' in kwargs:
            self.worker.signals.results.connect(kwargs['fin_fn'])
        if 'prg_fn' in kwargs:
            self.worker.signals.progress.connect(kwargs['prg_fn'])
        if 'err_fn' in kwargs:
            self.worker.signals.error.connect(kwargs['err_fn'])
        window.threadpool.start(self.worker)  # start the thread

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


class ODMRGraphWindow(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(ODMRGraphWindow, self).__init__(*args, **kwargs)  # Call the inherited classes __init__ method
        uic.loadUi('ODMRGraphWindow.ui', self)  # Load the .ui file
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

        self.setODMRButton.clicked.connect(self.send_to_scan_table)
        self.stopSweepButton.clicked.connect(self.stop_odmr_sweep)

        self.thread_function(window.rfController.setup_sweep, window.startFreqBox.value(), window.endFreqBox.value(),
                             window.pointsBox.value(), window.dwellTimeBox.value(), window.stepSizeBox.value(),
                             window.odmrSweepContinous.isChecked(),
                             fin_fn=self.execute_this_function, prg_fn=self.progress_fn,
                             err_fn=window.show_error_message, progress_callback=None)

    def thread_function(self, fn, *args, **kwargs):
        self.worker = Worker(fn, args, kwargs)
        """connect up the results signal to print the result it emits when triggered"""
        if 'fin_fn' in kwargs:
            self.worker.signals.results.connect(kwargs['fin_fn'])
        if 'prg_fn' in kwargs:
            self.worker.signals.progress.connect(kwargs['prg_fn'])
            self.worker.signals.progress.connect(self.progress_fn)
        if 'err_fn' in kwargs:
            self.worker.signals.error.connect(kwargs['err_fn'])
        window.threadpool.start(self.worker)

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
        return

    def progress_fn(self, results):
        self.y = results
        self.x = np.linspace(window.rfController.start_freq, window.rfController.stop_freq,
                             window.rfController.num_points)
        self.x = self.x[0:len(self.y)]
        self.dummy_data(self.x, self.y)
        return

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
                          peak_distance=100, peak_prom=5, plot_derivative=False, denoise=False):
        try:
            window_length = int(window_length)
            polyorder = int(polyorder)
            if denoise:
                y = savgol_filter(y, window_length=window_length, polyorder=polyorder)
            try:
                self.odmr_plot.clear()
                self.dummy_data(x, y)
            except:
                self.dummy_data(x, y)

            linear_region_width = int(linear_region_width)
            derivative = np.gradient(y, x)  # take derivative of curve, find elbow or "knee" point of curve
            elbow_index = np.argmin(derivative)  # find the minimum of the gradient, use that to determine linear region
            peaks, _ = find_peaks(derivative, height=peak_height, distance=peak_distance, prominence=peak_prom)

            try:
                for i in self.linear_region_list:
                    i.clear()
            except:
                pass

            self.linear_region_list = []
            self.linear_region_list_checkboxes = []
            self.linearRegionTable.setRowCount(0)
            for i in range(len(peaks)):
                # Adjust linear region parameter to control the width of the linear region
                linear_region_start = max(0, peaks[i] - linear_region_width // 2)
                linear_region_end = min(len(x) - 1, peaks[i] + linear_region_width // 2)
                # Extract data points for the linear region
                x_linear = x[linear_region_start:linear_region_end].reshape(-1, 1)
                y_linear = y[linear_region_start:linear_region_end]

                # Perform linear regression
                model = LinearRegression()
                model.fit(x_linear, y_linear)

                slope = model.coef_[0]
                intercept = model.intercept_

                prd = model.predict(x_linear)
                x_linear = x_linear.flatten()

                pen = pg.mkPen(color=(255, 0, 0), width=5)

                self.odmr_linear_region_plot = self.graphWidget.plot(x_linear, prd, pen=pen)
                self.linear_region_list.append(self.odmr_linear_region_plot)

                self.linearRegionTable.insertRow(i)
                self.linearRegionTable.setItem(i, 0,
                                               QtWidgets.QTableWidgetItem(
                                                   str(round((x_linear[0] + x_linear[-1]) / 2, 9))))
                self.linearRegionTable.setItem(i, 1, QtWidgets.QTableWidgetItem(str(round(slope, 9))))
                self.linearRegionTable.setCellWidget(i, 2, QtWidgets.QCheckBox())

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


class scanningImageWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        super(scanningImageWindow, self).__init__()  # Call the inherited classes __init__ method
        self.feedback_started = None
        self.res_grad = None
        self.res_freq = None
        self.dV = None
        self.df = None
        uic.loadUi('scanningWindow.ui', self)  # Load the .ui file
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

    def thread_function(self, fn, *args, **kwargs):
        self.worker = Worker(fn, args, kwargs)
        """connect up the results signal to print the result it emits when triggered"""
        if 'fin_fn' in kwargs:
            self.worker.signals.results.connect(kwargs['fin_fn'])
        if 'prg_fn' in kwargs:
            self.worker.signals.progress.connect(kwargs['prg_fn'])
        if 'err_fn' in kwargs:
            self.worker.signals.error.connect(kwargs['err_fn'])
        window.threadpool.start(self.worker)

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
            kwargs['progress_callback'].emit([res_freq_arr, dV_arr])
        return

    def initialise_vector_feedback(self, *args, **kwargs):
        print('initializing vector feedback')
        ini_voltage = []
        scale = 750
        for i in range(len(self.vector_freqs)):
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
            kwargs['progress_callback'].emit([res_freq_arr, dV_arr])
        return

    def scan_no_vector(self, *args, **kwargs):
        while self.feedback_started == False:
            continue
        time.sleep(3)  # let feedback settle
        scan_time = args[1]['scan_time']
        x_positions = self.xCoords
        y_positions = self.yCoords
        self.voltageArr = np.zeros([1, len(y_positions), len(x_positions)])
        self.df_arr = np.zeros([1, len(y_positions), len(x_positions)])
        print('The Scan has started. If the printer is not ready,'
              'exit program and increase the waiting time.')
        j = 0  # xpos
        totalSize = len(x_positions) * len(y_positions)
        for idx, y_position in enumerate(y_positions, 2):
            i = len(x_positions) - 1
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
                    kwargs['progress_callback'].emit(self.df_arr)
                else:
                    # else return current voltage instead
                    sample = window.LIAController.daq.getSample("/%s/demods/0/sample" % window.LIAController.device)
                    self.voltageArr[0, j, i] = sample['x'][0]
                    kwargs['progress_callback'].emit(self.voltageArr)
                i = i - 1
                te = time.time()
                eta = (te - ts) * totalSize
                print(time.ctime(int(timeStart + eta)))
            j += 1
            self.StageControl.set_stage_pos(x_positions[0], y_position)
            time.sleep(4)
        print('Scan completed. Resetting printer.')
        time.sleep(1)
        self.scanning = False
        return

    def scan_vector(self, *args, **kwargs):
        print('initializing scan vector')
        while self.feedback_started == False:
            print('waiting')
            continue
        print('scan vector starting')
        time.sleep(3)  # let feedback settle
        scan_time = args[1]['scan_time']
        x_positions = self.xCoords
        y_positions = self.yCoords
        self.voltageArr = np.zeros([4, len(y_positions), len(x_positions)])
        self.df_arr = np.zeros([4, len(y_positions), len(x_positions)])
        j = 0  # xpos
        totalSize = len(x_positions) * len(y_positions)
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
                kwargs['progress_callback'].emit(self.df_arr)
                i = i - 1
                te = time.time()
                eta = (te - ts) * totalSize
                print(time.ctime(int(timeStart + eta)))
            j += 1
            self.StageControl.set_stage_pos(x_positions[0], y_position)
            time.sleep(3)
        print('Scan completed. Resetting printer.')
        time.sleep(1)
        self.scanning = False
        return

    def update_plot(self, image_arr):
        if self.vector:
            self.imageWidget.setImage(image_arr[0])
            self.imageWidget_2.setImage(image_arr[1])
            self.imageWidget_3.setImage(image_arr[2])
            self.imageWidget_4.setImage(image_arr[3])
            # self.imageWidget.autoLevels()
        else:
            self.imageWidget.setImage(image_arr)
            # self.imageWidget.autoLevels()

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
            h5f = h5py.File(folderpath + date_time + ".h5", 'w')
            h5f.create_dataset('df_array', data=df_arr_data)
            h5f.create_dataset('voltage_array', data=voltage_arr_data)
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


class Worker(QtCore.QRunnable):
    """"worker thread"""

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        print()
        # add callback to kwargs
        self.kwargs['progress_callback'] = self.signals.progress

    @QtCore.pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.results.emit(result)
        finally:
            self.signals.finished.emit()


class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(tuple)
    results = QtCore.pyqtSignal(object)
    progress = QtCore.pyqtSignal(object)


app = QtWidgets.QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
if dark_theme:
    qdarktheme.setup_theme()
window = MainUI()  # Create an instance of our class
app.exec()
