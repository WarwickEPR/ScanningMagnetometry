import scipy.signal
from PyQt6 import QtCore, QtWidgets, uic, QtGui
import pyqtgraph as pg
import sys
import serial
import serial.tools.list_ports
import numpy as np
import time
import traceback
import pyvisa
from sklearn.linear_model import LinearRegression
from scipy.signal import savgol_filter, find_peaks, welch
from scipy.fftpack import rfft, fftfreq
import zhinst.utils as utils
import zhinst.core
from zhinst.toolkit import Session

uiclass, baseclass = pg.Qt.loadUiType("scanning_magnetometer.ui")

try:
    import qdarktheme

    dark_theme = True
except Exception as error:
    dark_theme = False


class MainUI(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('scanning_magnetometer.ui', self)  # Load the .ui file
        self.show()  # Show the GUI

        self.stageController = stageControl()  # stage controller class instance
        self.rfController = RfControl()
        self.LIAController = LIAControl()

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

        self.startScanButton.clicked.connect(self.stageController.open_scan_window)

        #  LIA ui controls
        self.connectLIAButton.clicked.connect(lambda: self.LIAController.thread_function(self.LIAController.connect_lia,
                                                                                         device_id=self.LIANameBox.text(),
                                                                                         err_fn=self.show_error_message))
        self.takeFFTButton.clicked.connect(self.stageController.open_fft_graph)

        #  RF ui controls
        self.takeODMRButton.clicked.connect(self.stageController.open_odmr_graph)
        self.connectMWSourceButton.clicked.connect(lambda: self.rfController.thread_function(self.rfController.connect_rf,
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
        self.toggleExtModOnOff.stateChanged.connect(lambda: self.rfController.ext_mod_on_off(self.toggleExtModOnOff.isChecked()))

        # configure thread pool
        self.threadpool = QtCore.QThreadPool()
        print('max %d threads' % self.threadpool.maxThreadCount())

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
        return

    def show_error_message(self, text):
        error_dialog = QtWidgets.QErrorMessage(self)
        error_dialog.showMessage(str(text[1]))
        return

class stageControl:
    def __init__(self):
        super(stageControl, self).__init__()
        self.ser = None
        return

    def execute_gcode(self, command):
        try:
            self.ser.write(f'{command}\r\n'.encode())
        except:
            self.show_error_message("ERROR: Could not execute stage command")

    def read_gcode(self, command):
        try:
            self.ser.write(f'{command}\r\n'.encode())
            response = self.ser.readline()
            self.ser.readline()  # clears next line
        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(window)
            error_dialog.showMessage(str(error))
        return response

    def connect_stage(self, com_port, baud_rate=115200):
        try:
            # connect to stage code here
            self.ser = serial.Serial(port=com_port, baudrate=baud_rate)
            msg = QtWidgets.QMessageBox(window)
            msg.setText("Connected Successful to: " + str(com_port))
            msg.exec()
        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(window)
            error_dialog.showMessage(str(error))

    def home_stage(self):
        self.execute_gcode('G28')  # home gcode
        return

    def set_stage_pos(self, x, y):
        self.execute_gcode(f'G00 X{x} Y{y}')
        return

    def set_stage_height(self, z):
        self.execute_gcode(f'G00 Z{z}')
        return

    def get_stage_pos(self):
        try:
            response = self.read_gcode('M114')

            response = response.decode("utf-8").split()  # response[0] = xPos in mm, [1] = yPos, [2] = zPos
            xPos, yPos, zPos = response[0], response[1], response[2]
            window.currentXLabel.setText(xPos)
            window.currentYLabel.setText(yPos)
            window.currentHeightLabel.setText(zPos)
        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(window)
            error_dialog.showMessage(str(error))

    def set_max_stage_position(self):
        self.stage_options = stage_options()

    def open_fft_graph(self):
        self.fft_graph_window = FFTGraphWindow()

    def open_odmr_graph(self):
        window.takeODMRButton.setEnabled(False)
        self.odmr_graph_window = ODMRGraphWindow()

    def open_scan_window(self):
        self.scan_window = scanningImageWindow()

    def show_error_message(self, text):
        error_dialog = QtWidgets.QErrorMessage(window)
        error_dialog.showMessage(text)
        return


class RfControl:
    def __init__(self):
        super(RfControl, self).__init__()
        self.mw_power_on = False
        self.mod_on = False

    def thread_function(self, fn, *args, **kwargs):
        self.worker = Worker(fn, args, kwargs)
        """connect up the results signal to print the result it emits when triggered"""
        if 'fin_fn' in kwargs:
            pass
            # self.worker.signals.results.connect(self.print_this)
        if 'prg_fn' in kwargs:
            pass
            # self.worker.signals.progress.connect(self.progress_fn)
        if 'err_fn' in kwargs:
            self.worker.signals.error.connect(kwargs['err_fn'])
        window.threadpool.start(self.worker)

    def connect_rf(self, *args, **kwargs):
        ip_address = args[0][0]
        self.rm = pyvisa.ResourceManager()
        ip_address = "TCPIP::" + ip_address + "::INSTR"
        self.inst = self.rm.open_resource(ip_address)
        self.inst.chunk_size = 102400
        self.inst.write("*CLS")  # clear error bank
        self.inst.baud_rate = 115200

        window.powerLabel.setText(str(round(float(self.inst.query('POW?')), 3)))
        window.currentFreqLabel.setText(str(round(float(self.get_freq()) / 1e9, 3)))
        mod_freq, mod_amp = self.get_mod_params()
        window.modAmpLabel.setText(str(round(float(mod_amp) / 1e6, 3)))
        window.modFreqLabel.setText(str(round(float(mod_freq) / 1e3, 3)))

        #turn power and modulation off by default
        power = int(self.inst.query("OUTP?"))
        if power == 0:
            self.mw_power_on = False
            window.togglePwrChk.setChecked(False)
        elif power == 1:
            self.mw_power_on = True
            window.togglePwrChk.setChecked(True)

        self.inst.write('FM:STAT ON')
        self.inst.write('OUTP:MOD:STAT ON')
        window.toggleModOnOff.setChecked(True)
        return

    def power_on_off(self, state):
        if state:
            self.inst.write('OUTP ON')
            self.mw_power_on = True
        elif not state:
            self.inst.write('OUTP OFF')
            self.mw_power_on = False
        return

    def set_freq(self):
        self.inst.write('FREQ ' + str(round(float(window.freqBox.value()) * 1e9, 12)))
        window.currentFreqLabel.setText(str(round(float(self.get_freq())/1e9, 3)))
        return

    def get_freq(self):
        return self.inst.query("FREQ?")

    def set_power(self):
        self.inst.write(f'POW {float(window.pwrBox.value())} dBm')
        curr_p = round(float(self.inst.query('POW?')), 3)
        window.powerLabel.setText(str(curr_p))

    def mod_on_off(self, state):
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
        self.inst.write(f'FM {float(window.modAmpSpinBox.value())} MHz')
        self.inst.write(f'FM:INT:FREQ {float(window.modFreqSpinBox.value())} kHz')
        mod_freq, mod_amp = self.get_mod_params()
        window.modAmpLabel.setText(str(round(float(mod_amp)/1e6, 3)))
        window.modFreqLabel.setText(str(round(float(mod_freq)/1e3, 3)))
        return

    def get_mod_params(self):
        return self.inst.query('FM:INT:FREQ?'), self.inst.query('FM?')

    def change_mod_type(self):
        if window.squareWaveRadio.isChecked():
            self.inst.write(':FM:INT:FUNC SQU') #set square wave fm
        elif window.sineWaveRadio.isChecked():
            self.inst.write(':FM:INT:FUNC SIN') #set sine wave fm

    def ext_mod_on_off(self, state):
        if state:
            self.inst.write(':FM:SOUR EXT')
        elif not state:
            self.inst.write(':FM:SOUR INT')
        return

    def setup_sweep(self, *args, **kwargs):
        self.worker_running = True  # this will stop the thread when its finished or if the ODMR window closes
        self.start_freq = args[0][0]  # Start frequency in Hz (e.g., 1 GHz)
        self.stop_freq = args[0][1]  # Stop frequency in Hz (e.g., 2 GHz)
        num_points = args[0][2]  # Number of frequency points
        dwell_time = args[0][3] / 1000
        sweep_step = args[0][4]

        #set trigger to output when sweep start
        window.rfController.inst.write(':TRIG:SEQ:SOUR BUS')  # sets sweep to trigger on *TRG command
        window.rfController.inst.write('ROUT:CONN:TRIG:OUTP SRun')  # sets trig out 1 on Keysight to emit pulse when sweep starts, used to trigger LIA
        window.rfController.inst.write(':SOURce:FREQuency:MODE LIST')  # set frequency mode from CW to list sweep
        window.rfController.inst.write(f':SWE:DWELL {dwell_time}')  # set dwell time
        if window.sweepDefBox.currentText() == 'Points':  # if points are used, set points
            window.rfController.inst.write(f':SWE:POINTS {num_points}')
        elif window.sweepDefBox.currentText() == 'Step Size':  # if step size used, set step size
            window.rfController.inst.write(f':SWE:STEP {sweep_step} kHz')
        window.rfController.inst.write(f':SOURce:FREQuency:STARt {self.start_freq} GHz')  # set start and end sweep freq
        window.rfController.inst.write(f':SOURce:FREQuency:STOP {self.stop_freq} GHz')
        window.rfController.inst.write('TSWeep')  # Prime the sweep, start sweep with *TRG command
        window.LIAController.setup_sweep() #setup LIA for data aquisition
        window.rfController.inst.write('*TRG')  # trigger sweep to start

        sweeping = True
        read_count = 0
        window.LIAController.daq_module.execute()
        # Record data in a loop with timeout.
        self.samples = []
        temp_x = []
        while sweeping == True:
            data_read = window.LIAController.daq_module.read(True)
            returned_signal_paths = [
                signal_path.lower() for signal_path in data_read.keys()
            ]
            progress = window.LIAController.daq_module.progress()[0]
            for signal_path in window.LIAController.signal_paths:
                if signal_path.lower() in returned_signal_paths:
                    # Loop over all the bursts for the subscribed signal. More than
                    # one burst may be returned at a time, in particular if we call
                    # read() less frequently than the burst_duration.
                    for index, signal_burst in enumerate(data_read[signal_path.lower()]):
                        self.samples.append(signal_burst['value'][0])
                        window.LIAController.data[signal_path].append(signal_burst)
                else:
                    # Note: If we read before the next burst has finished, there may be no new data.
                    # No action required.
                    pass
            if (int(window.rfController.inst.query(':STATus:OPERation:CONDition?')) & 8) == 8:  # trigger sweep to start
                # time.sleep(0.01)
                pass
            else:
                sweeping = False
        #stop aquisition and unsub from module
        window.LIAController.daq_module.finish()
        window.LIAController.daq_module.unsubscribe('*')
        return

class LIAControl:
    def __init__(self):
        super(LIAControl, self).__init__()
        return

    def thread_function(self, fn, *args, **kwargs):
        self.worker = Worker(fn, args, kwargs)
        """connect up the results signal to print the result it emits when triggered"""
        if 'fin_fn' in kwargs:
            pass
            # self.worker.signals.results.connect(self.print_this)
        if 'prg_fn' in kwargs:
            pass
            # self.worker.signals.progress.connect(self.progress_fn)
        if 'err_fn' in kwargs:
            self.worker.signals.error.connect(kwargs['err_fn'])
        window.threadpool.start(self.worker)

    def connect_lia(self, *args, **kwargs):
        self.server_host: str = "192.168.70.166"
        self.device_id = args[1]['device_id']
        server_port = 8004
        api_level = 6
        (self.daq, self.device, _) = zhinst.utils.create_api_session(
            self.device_id, api_level, server_host=self.server_host, server_port=server_port
        )
        zhinst.utils.api_server_version_check(self.daq)
        self.daq.set(f"/{self.device}/demods/0/enable", 1)
        self.clockbase = float(self.daq.getInt(f"/{self.device}/clockbase"))

        # self.demod_path = f"/{self.device}/demods/0/sample"
        # self.signal_paths = []
        # self.signal_paths.append(self.demod_path + ".x")  # The demodulator X output.
        # self.signal_paths.append(self.demod_path + ".y")

    def setup_sweep(self):
        self.demod_path = f"/{self.device}/demods/0/sample"
        self.signal_paths = []
        self.signal_paths.append(self.demod_path + ".x")
        #set up sweep parameters to get data from Data Aquisition module
        self.total_duration = window.odmrAqDurBox.value()
        self.module_sampling_rate =  window.odmrAqSampleRateBox.value() # Number of points/second
        self.burst_duration = window.odmrAqBurstDurBox.value()  # Time in seconds for each data burst/segment.
        self.num_cols = int(np.ceil(self.module_sampling_rate * self.burst_duration))
        self.num_bursts = int(np.ceil(self.total_duration /self.burst_duration))
        # Create an instance of the Data Acquisition Module.
        self.daq_module = self.daq.dataAcquisitionModule()
        # Configure the Data Acquisition Module.
        # Set the device that will be used for the trigger - this parameter must be set.
        self.daq_module.set("device", self.device)
        # Specify continuous acquisition (type=0).
        self.daq_module.set("type", 0)
        self.daq_module.set("grid/mode", 2)
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
        self.scaling_Factor = int(window.scalingFactorSpinBox.value())
        demod_select = 0
        range = int(window.rangeSelect.currentText())
        imp_fifty = int(window.fiftyOhmCheck.isChecked())
        ac_coupled = int(window.acCoupleCheck.isChecked())
        in_channel = 0
        demod_index = 1
        harmonic_order = int(window.harmonicOrderSelect.currentText())
        time_constant = float(window.timeConstantSpinBox.value())  # ~80hz
        exp_setting = [
            ["/%s/sigins/%d/ac" % (self.device, in_channel), ac_coupled],  # ac coupling on/off
            ["/%s/sigins/%d/imp50" % (self.device, in_channel), imp_fifty],  # 50 ohm impednecne on/off
            ["/%s/sigins/%d/range" % (self.device, in_channel), range],  # set signal in range
            ["/%s/demods/%d/enable" % (self.device, demod_index), 1],  # enable data transfer
            # set data transfer rate from demod to data server
            ["/%s/demods/%d/adcselect" % (self.device, 0), 0],  # set demodulator 1's input to signal in 1
            ["/%s/demods/%d/adcselect" % (self.device, 1), 8], #select auxin1 as demodulator 2's input
            ["/%s/demods/%d/order" % (self.device, demod_index), harmonic_order],  # set filter order to 8th order
            ["/%s/demods/%d/timeconstant" % (self.device, demod_index), time_constant],
            # sets low pass filter timeconstant ~ 3db filter freq.
            ["/%s/demods/%d/harmonic" % (self.device, demod_index), 1],  # set mod harmonic to be 1st harmonic
            ["/%s/extrefs/%d/enable" % (self.device, in_channel), 1],  # sets ext ref to be aux in 1
            ["/%s/auxouts/%d/outputselect" % (self.device, 0), demod_select],  # set output to be demod x (0) or demod y (1)
        ]
        self.daq.set(exp_setting)
        self.daq.set(f"/{self.device}/demods/0/enable", 1)
        self.daq.set(f"/{self.device}/demods/1/enable", 1)
        self.daq.set("/%s/auxouts/%d/scale" % (self.device, 0), self.scaling_Factor),
        clockbase = float(self.daq.getInt(f"/{self.device}/clockbase"))

        demod_path = f"/{self.device}/demods/0/sample"
        self.signal_paths = []
        self.signal_paths.append(demod_path + ".x.fft.abs.avg")

        count = int(window.fftAverageSpinBox.value())
        self.fft_duration = int(window.fftDurationSpinBox.value())
        cols = int(window.sampleRateSpinBox.value())

        self.daq_module = self.daq.dataAcquisitionModule()
        self.daq_module.set("device", self.device)
        # Specify continuous acquisition (type=0).
        self.daq_module.set("type", 0)
        self.daq_module.set("grid/mode", 2)
        self.daq_module.set("count", count)
        self.daq_module.set("duration", self.fft_duration)
        self.daq_module.set("grid/cols", cols)

        self.data = {}
        # A dictionary to store all the acquired data.
        for signal_path in self.signal_paths:
            print("Subscribing to ", signal_path)
            self.daq_module.subscribe(signal_path)
            self.data[signal_path] = []
        return

class stage_options(QtWidgets.QWidget):
    def __init__(self):
        super(stage_options, self).__init__()  # Call the inherited classes __init__ method
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
    def __init__(self):
        super().__init__()
        super(FFTGraphWindow, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('FFTGraphWindow.ui', self)  # Load the .ui file
        self.show()
        self.fft_plot = None
        self.x = None
        self.y = None
        self.scaled_y = None
        self.calib_const = 1

        self.calcSensButton.clicked.connect(lambda: self.calc_sens(freq_start=self.minFreqSpinBox.value(),
                                                                   freq_end=self.maxFreqSpinBox.value(),
                                                                   ignore_freqs=self.ignoreListFreqCheckBox.isChecked()))

        self.addFreqButton.clicked.connect(
            lambda: self.add_ignore_freq(self.freqStartSpinBox.value(), self.freqEndSpinBox.value()))

        self.odmrGradientSpinBox.valueChanged.connect(lambda: self.dummy_data(
            calib_const=self.odmrGradientSpinBox.value()))

        self.thread_function(self.take_fft,
                             progress_callback=None)


        return

    def thread_function(self, fn, *args, **kwargs):
        self.worker = Worker(fn, args, kwargs)
        """connect up the results signal to print the result it emits when triggered"""
        if 'fin_fn' in kwargs:
            pass
            # self.worker.signals.results.connect(self.print_this)
        if 'prg_fn' in kwargs:
            pass
            # self.worker.signals.progress.connect(self.progress_fn)
        if 'err_fn' in kwargs:
            self.worker.signals.error.connect(kwargs['err_fn'])
        window.threadpool.start(self.worker)

    def take_fft(self, *args, **kwargs):
        self.worker_running = True  # this will stop the thread when its finished or if the ODMR window closes
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
        avg_sample = ((np.sum(self.samples, axis=0)) / 10) * window.LIAController.scaling_Factor
        bin_count = len(avg_sample)
        frequencies = np.arange(0, bin_count)
        amplitude_spectral_density = (avg_sample * np.sqrt(window.LIAController.fft_duration)) * (1/(28e-6 * self.calib_const))
        self.y = amplitude_spectral_density
        self.scaled_y = self.y
        self.x = frequencies
        self.dummy_data(calib_const=self.calib_const)
        return

    def add_ignore_freq(self, freq_start, freq_end):
        row_pos = self.ignoreFrequencyList.rowCount()
        self.ignoreFrequencyList.insertRow(row_pos)
        self.ignoreFrequencyList.setItem(row_pos, 0, QtWidgets.QTableWidgetItem(str(freq_start)))
        self.ignoreFrequencyList.setItem(row_pos, 1, QtWidgets.QTableWidgetItem(str(freq_end)))
        return

    def calc_sens(self, freq_start=10, freq_end=100, ignore_freqs=False):
        if ignore_freqs == True:
            freq_start = freq_start  # convert khz to hz
            freq_end = freq_end # convert khz to hz
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
        self.scaled_y = self.y
        try:
            self.fft_plot.clear()
        except:
            pass
        self.fft_plot = self.graphWidget.plot(self.x, self.scaled_y)
        self.graphWidget.setLogMode(True, True)
        return

    def lorentzian_derivative(self, x, x0, gamma, A):
        return -2 * A * gamma ** 2 * (x - x0) / ((x - x0) ** 2 + gamma ** 2) ** 2


class ODMRGraphWindow(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(ODMRGraphWindow, self).__init__(*args, **kwargs)  # Call the inherited classes __init__ method
        uic.loadUi('ODMRGraphWindow.ui', self)  # Load the .ui file
        self.show()

        #configure two y axis plot

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
                             fin_fn=self.execute_this_function, prg_fn=self.progress_fn,
                             err_fn = window.show_error_message, progress_callback=None)

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
        print('sweep stop')
        self.y = window.rfController.samples
        self.y = np.concatenate(self.y).ravel()
        self.x = np.linspace(window.rfController.start_freq, window.rfController.stop_freq, len(self.y))
        self.dummy_data(self.x,self.y)
        return

    def progress_fn(self, results):
        "update progress bar of odmr sweep?"

    def print_this(self, results):
        """this then prints the result emitted from the results signal, that is returned by the function 
        'execute_this_function'"""
        self.worker_running = False
        window.takeODMRButton.setEnabled(True)
        
    def closeEvent(self, event):
        """this function executes when the ODMR graph window closes, used to stop thread but can be used for anything
        else, such as printing or saving data, clearing graphs/memory etc."""
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
                self.linearRegionTable.setItem(i, 0, QtWidgets.QTableWidgetItem(str(round(x_linear[i], 3))))
                self.linearRegionTable.setItem(i, 1, QtWidgets.QTableWidgetItem(str(round(slope, 3))))
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
            print(error)

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


class scanningImageWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        super(scanningImageWindow, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('scanningWindow.ui', self)  # Load the .ui file
        self.show()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)

        #this is just for testing purposes, do not use when plotting real data
        self.dummy_data = np.loadtxt("example_data\example_2d_scan_data.csv", ndmin=2, delimiter=",")
        self.data = np.zeros([np.size(self.dummy_data, 0), np.size(self.dummy_data, 1)])
        self.i = 0
        self.j = 0

        # self.dummy_data()
        self.timer = QtCore.QTimer(self)  # time to trigger replot of image for testing purposes,
        self.timer.setInterval(10)
        self.timer.timeout.connect(lambda: self.update_plot(self.data))
        self.timer.start()
        #  in real life the replot will be triggered when the stage moves
        #  and takes a data point

    def update_plot(self, data):
        self.data[self.i, self.j] = self.dummy_data[self.i, self.j]
        self.imageWidget.setImage(data)

        #  this is just to cylce through dummy data, not for real data use (not useful i think?)
        if self.i == np.size(self.dummy_data, 0) - 1 and self.j == np.size(self.dummy_data, 1) - 1:
            return
        if self.i == np.size(self.dummy_data, 0) - 1:
            self.i = 0
            self.j += 1
        else:
            self.i += 1
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
        #add callback to kwargs
        # self.kwargs['progress_callback'] = self.signals.progress
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
