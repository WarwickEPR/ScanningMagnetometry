from PyQt6 import QtCore, QtWidgets, uic, QtGui
import pyqtgraph as pg
import sys
import serial
import serial.tools.list_ports
import numpy as np
import time
import traceback
from sklearn.linear_model import LinearRegression
from scipy.signal import savgol_filter, find_peaks

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

        self.connectStageButton.clicked.connect(
            lambda: self.stageController.connect_stage(self.comPortBox.currentText()))
        self.homeStageButton.clicked.connect(self.stageController.home_stage)
        self.setPositionButton.clicked.connect(lambda: self.stageController.set_stage_pos(self.xPosSpinBox.value(),
                                                                                          self.yPosSpinBox.value()))
        self.setStageHeightButton.clicked.connect(
            lambda: self.stageController.set_stage_height(self.zPosSpinBox.value()))
        self.getStagePositionButton.clicked.connect(self.stageController.get_stage_pos)
        self.actionChange_Max_Position_Values.triggered.connect(self.stageController.set_max_stage_position)

        self.takeFFTButton.clicked.connect(self.stageController.open_fft_graph)
        self.takeODMRButton.clicked.connect(self.stageController.open_odmr_graph)
        self.startScanButton.clicked.connect(self.stageController.open_scan_window)

        # configure thread pool
        self.threadpool = QtCore.QThreadPool()
        print('max %d threads' % self.threadpool.maxThreadCount())

        # self.graphWidget.plot([1,2,3,4,5], [1,2,3,4,5]) #dummy data for now

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
        error_dialog.showMessage(text)
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
        self.odmr_graph_window = ODMRGraphWindow()

    def open_scan_window(self):
        self.scan_window = scanningImageWindow()

    def show_error_message(self, text):
        error_dialog = QtWidgets.QErrorMessage(window)
        error_dialog.showMessage(text)
        return


class stage_options(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
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

        self.calcSensButton.clicked.connect(lambda: self.calc_sens(freq_start=self.minFreqSpinBox.value(),
                                                                   freq_end=self.maxFreqSpinBox.value(),
                                                                   ignore_freqs=self.ignoreListFreqCheckBox.isChecked()))

        self.addFreqButton.clicked.connect(
            lambda: self.add_ignore_freq(self.freqStartSpinBox.value(), self.freqEndSpinBox.value()))

        self.odmrGradientSpinBox.valueChanged.connect(lambda: self.dummy_data("example_data\example_data_fft_dbu.csv", units="dBu",
                               calib_const=self.odmrGradientSpinBox.value()))

        self.dummy_data("example_data\example_data_fft_dbu.csv", units="dBu",
                               calib_const=self.odmrGradientSpinBox.value())  # plot dummy fft data
        self.calc_sens(freq_start=self.minFreqSpinBox.value(), freq_end=self.maxFreqSpinBox.value(),
                       ignore_freqs=self.ignoreListFreqCheckBox.isChecked())
        return

    def add_ignore_freq(self, freq_start, freq_end):
        row_pos = self.ignoreFrequencyList.rowCount()
        self.ignoreFrequencyList.insertRow(row_pos)
        self.ignoreFrequencyList.setItem(row_pos, 0, QtWidgets.QTableWidgetItem(str(freq_start)))
        self.ignoreFrequencyList.setItem(row_pos, 1, QtWidgets.QTableWidgetItem(str(freq_end)))
        return

    def calc_sens(self, freq_start=10, freq_end=100, ignore_freqs=False):
        if ignore_freqs == True:
            freq_start = freq_start / 1e3  # convert khz to hz
            freq_end = freq_end / 1e3  # convert khz to hz
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
                    ignore_min_freq = (int(self.ignoreFrequencyList.item(row, 0).text())) / 1e3
                    ignore_max_freq = (int(self.ignoreFrequencyList.item(row, 1).text())) / 1e3
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
            mean_sens = round(np.mean(self.y[mask]), 4)

            self.meanSensLabel.setText(str(mean_sens))
        else:
            mean_sens = round(np.mean(self.y), 4)
            self.meanSensLabel.setText(str(mean_sens))
        # print(mean_sens) # mean sens value

    def dummy_data(self, file_path, units="nT", calib_const=1, x_col=0, y_col=1):
        calib_const = float(calib_const)
        """plots dummy FFT data for demonstrating/debugging/feature testing"""
        arr = np.loadtxt(file_path, delimiter=',')
        self.x = arr[:, x_col]
        self.y = arr[:, y_col]
        if units == "dBu":
            # converts dBu to nT/sqrt(Hz)
            self.y = 0.775 * 10 ** (self.y / 20)
            self.y = self.y / (23e-6 * calib_const)  # convert using calib_const (assumes units of V/MHz)
        try:
            self.fft_plot.clear()
        except:
            pass
        self.fft_plot = self.graphWidget.plot(self.x, self.y)
        self.graphWidget.setLogMode(True, True)
        return

    def lorentzian_derivative(self, x, x0, gamma, A):
        return -2 * A * gamma ** 2 * (x - x0) / ((x - x0) ** 2 + gamma ** 2) ** 2


class ODMRGraphWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        super(ODMRGraphWindow, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('ODMRGraphWindow.ui', self)  # Load the .ui file
        self.show()


        #configure two y axis plot

        self.p1 = self.graphWidget.plotItem
        self.p1.setLabels(left='axis 1')

        self.p2 = pg.ViewBox()
        self.p1.showAxis('right')
        self.p1.scene().addItem(self.p2)
        self.p1.getAxis('right').linkToView(self.p2)
        self.p2.setXLink(self.p1)
        self.p1.getAxis('right').setLabel('axis2', color='#0000ff')

        self.p1.vb.sigResized.connect(self.updateViews)

        self.odmr_plot = None
        self.odmr_deriv_plot = None
        self.odmr_linear_region_plot = None
        self.linear_region_list = None
        self.MainWindow = window
        self.worker_running = False

        self.odmrRegionFitBox.valueChanged.connect(lambda: self.fit_linear_region(x_values, y,
                                                                                  self.odmrRegionFitBox.value(),
                                                                                  plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                                                                  denoise=self.smoothingCheckBox.isChecked(),
                                                                                  window_length=self.smoothWindowBox.value(),
                                                                                  polyorder=self.polyorderSpinBox.value(),
                                                                                  peak_height=self.peakHeightSpinBox.value(),
                                                                                  peak_distance=self.peakDistanceSpinBox.value(),
                                                                                  peak_prom=self.peakPromSpinBox.value(),
                                                                                  ))
        self.showDerivativeCheckbox.stateChanged.connect(lambda: self.fit_linear_region(x_values, y,
                                                                                        self.odmrRegionFitBox.value(),
                                                                                        plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                                                                        denoise=self.smoothingCheckBox.isChecked(),
                                                                                        window_length=self.smoothWindowBox.value(),
                                                                                        polyorder=self.polyorderSpinBox.value(),
                                                                                        peak_height=self.peakHeightSpinBox.value(),
                                                                                        peak_distance=self.peakDistanceSpinBox.value(),
                                                                                        peak_prom=self.peakPromSpinBox.value(),
                                                                                        ))
        self.smoothingCheckBox.stateChanged.connect(lambda: self.fit_linear_region(x_values, y,
                                                                                   self.odmrRegionFitBox.value(),
                                                                                   plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                                                                   denoise=self.smoothingCheckBox.isChecked(),
                                                                                   window_length=self.smoothWindowBox.value(),
                                                                                   polyorder=self.polyorderSpinBox.value(),
                                                                                   peak_height=self.peakHeightSpinBox.value(),
                                                                                   peak_distance=self.peakDistanceSpinBox.value(),
                                                                                   peak_prom=self.peakPromSpinBox.value(),
                                                                                   ))

        self.polyorderSpinBox.valueChanged.connect(lambda: self.fit_linear_region(x_values, y,
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
            lambda: self.fit_linear_region(x_values, y, self.odmrRegionFitBox.value(),
                                           plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                           denoise=self.smoothingCheckBox.isChecked(),
                                           window_length=self.smoothWindowBox.value(),
                                           polyorder=self.polyorderSpinBox.value(),
                                           peak_height=self.peakHeightSpinBox.value(),
                                           peak_distance=self.peakDistanceSpinBox.value(),
                                           peak_prom=self.peakPromSpinBox.value(),
                                           ))

        self.peakHeightSpinBox.valueChanged.connect(
            lambda: self.fit_linear_region(x_values, y, self.odmrRegionFitBox.value(),
                                           plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                           denoise=self.smoothingCheckBox.isChecked(),
                                           window_length=self.smoothWindowBox.value(),
                                           polyorder=self.polyorderSpinBox.value(),
                                           peak_height=self.peakHeightSpinBox.value(),
                                           peak_distance=self.peakDistanceSpinBox.value(),
                                           peak_prom=self.peakPromSpinBox.value(),
                                           ))

        self.peakHeightSpinBox.valueChanged.connect(
            lambda: self.fit_linear_region(x_values, y, self.odmrRegionFitBox.value(),
                                           plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                           denoise=self.smoothingCheckBox.isChecked(),
                                           window_length=self.smoothWindowBox.value(),
                                           polyorder=self.polyorderSpinBox.value(),
                                           peak_height=self.peakHeightSpinBox.value(),
                                           peak_distance=self.peakDistanceSpinBox.value(),
                                           peak_prom=self.peakPromSpinBox.value(),
                                           ))

        self.setODMRButton.clicked.connect(self.send_to_scan_table)

        data = np.loadtxt("example_data\example_odmr_data.csv", delimiter=",")
        x_values = data[:, 0]
        y = data[:, 1]
        # x_values = np.linspace(0, 10, 1000)  # dummy x values
        # y = (self.lorentzian_derivative(x_values, 2, 0.5, 1) + self.lorentzian_derivative(x_values, 4, 0.5, 1) +
        #      self.lorentzian_derivative(x_values, 6, 0.5, 1) + self.lorentzian_derivative(x_values, 8, 0.5, 1))
        # dummy y data
        # np.random.seed(0)  # For reproducibility
        # noise = np.random.normal(0, 0.05, len(x_values))  # Gaussian noise with mean and standard deviation
        # y += noise  # add noise
        # self.dummy_data(x_values,y)  # plot dummy odmr data

        self.fit_linear_region(x_values, y)  # find linear region of data for fitting

        # self.thing_happend()

    def thing_happend(self):
        """
        what should happen when ODMR is started, thread is created and function is passed to worker
         to start data collection.
        :return:
        """
        self.worker = Worker(self.execute_this_function)


        """connect up the results signal to print the result it emits when triggered"""
        self.worker.signals.results.connect(self.print_this)


        window.threadpool.start(self.worker)

    def execute_this_function(self):
        """this function then theoretically will trigger the LIA to start data collection when the MW sweep is started
        then once the sweep is stopped, the trigger will stop LIA aquisition and then this function collects the data and
        passes the data back to be plotted using signals and slots...haven't worked that out yet ._."""

        self.worker_running = True  # this will stop the thread when its finished or if the ODMR window closes
        x = np.linspace(0, 100, 1000)
        y = np.sin(x)
        data = []

        while self.worker_running:
            for i in range(len(x)):
                data.append(y[i])
            time.sleep(5)
            self.worker_running = False
        return x, data


    def print_this(self, x, y):
        """this then prints the result emitted from the results signal, that is returned by the function 
        'execute_this_function'"""
        self.dummy_data(x, y)
        
    def closeEvent(self, event):
        """this function executes when the ODMR graph window closes, used to stop thread but can be used for anything
        else, such as printing or saving data, clearing graphs/memory etc."""
        self.worker_running = False
        return

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

    def gaussian_derivative(self, x, mu, sigma):
        return -2 * (x - mu) * np.exp(-((x - mu) / sigma) ** 2) / (np.sqrt(np.pi) * sigma)

    def lorentzian_derivative(self, x, x0, gamma, A):
        return -2 * A * gamma ** 2 * (x - x0) / ((x - x0) ** 2 + gamma ** 2) ** 2

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

    @QtCore.pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.results.emit(result[0], result[1])
        finally:
            self.signals.finished.emit()

class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(tuple)
    results = QtCore.pyqtSignal(object, object)

app = QtWidgets.QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
if dark_theme:
    qdarktheme.setup_theme()
window = MainUI()  # Create an instance of our class
app.exec()
