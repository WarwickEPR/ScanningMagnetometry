from PyQt6 import QtCore, QtWidgets, uic, QtGui
import pyqtgraph as pg
import sys
import serial
import serial.tools.list_ports
import numpy as np
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

        self.connectStageButton.clicked.connect(lambda: self.stageController.connect_stage(self.comPortBox.currentText()))
        self.homeStageButton.clicked.connect(self.stageController.home_stage)
        self.setPositionButton.clicked.connect(lambda: self.stageController.set_stage_pos(self.xPosSpinBox.value(),
                                                                                          self.yPosSpinBox.value()))
        self.setStageHeightButton.clicked.connect(lambda: self.stageController.set_stage_height(self.zPosSpinBox.value()))
        self.getStagePositionButton.clicked.connect(self.stageController.get_stage_pos)
        self.actionChange_Max_Position_Values.triggered.connect(self.stageController.set_max_stage_position)


        self.takeFFTButton.clicked.connect(self.stageController.open_fft_graph)
        self.takeODMRButton.clicked.connect(self.stageController.open_odmr_grah)

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

    def open_odmr_grah(self):
        self.odmr_graph_window = ODMRGraphWindow()

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
        self.graphWidget.plot([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
        self.graphWidget.setLogMode(True, True)

        return

class ODMRGraphWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        super(ODMRGraphWindow, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('ODMRGraphWindow.ui', self)  # Load the .ui file
        self.show()

        self.odmr_plot = None
        self.odmr_deriv_plot = None
        self.odmr_linear_region_plot = None
        self.linear_region_list = None

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
                                                                                        denoise = self.smoothingCheckBox.isChecked(),
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

        self.smoothWindowBox.valueChanged.connect(lambda: self.fit_linear_region(x_values, y, self.odmrRegionFitBox.value(),
                                           plot_derivative=self.showDerivativeCheckbox.isChecked(),
                                           denoise=self.smoothingCheckBox.isChecked(),
                                           window_length=self.smoothWindowBox.value(),
                                           polyorder=self.polyorderSpinBox.value(),
                                             peak_height=self.peakHeightSpinBox.value(),
                                             peak_distance=self.peakDistanceSpinBox.value(),
                                             peak_prom=self.peakPromSpinBox.value(),
                                           ))

        self.peakHeightSpinBox.valueChanged.connect(lambda: self.fit_linear_region(x_values, y, self.odmrRegionFitBox.value(),
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

        x_values = np.linspace(0, 10, 1000) # dummy x values
        y = (self.lorentzian_derivative(x_values, 2, 0.5, 1) + self.lorentzian_derivative(x_values, 4, 0.5, 1) +
             self.lorentzian_derivative(x_values, 6, 0.5, 1) + self.lorentzian_derivative(x_values, 8, 0.5, 1))
        # dummy y data
        np.random.seed(0)  # For reproducibility
        noise = np.random.normal(0, 0.05, len(x_values))  # Gaussian noise with mean and standard deviation
        y += noise  # add noise
        # self.dummy_data(x_values,y)  # plot dummy odmr data

        self.fit_linear_region(x_values, y)  # find linear region of data for fitting

    def dummy_data(self,x,y):
        pen = pg.mkPen(style = QtCore.Qt.PenStyle.DashLine)
        self.odmr_plot = self.graphWidget.plot(x, y,pen=pen)
        return

    def gaussian_derivative(self, x, mu, sigma):
        return -2 * (x - mu) * np.exp(-((x - mu) / sigma)**2) / (np.sqrt(np.pi) * sigma)

    def lorentzian_derivative(self, x, x0, gamma, A):
        return -2 * A * gamma ** 2 * (x - x0) / ((x - x0) ** 2 + gamma ** 2) ** 2

    def fit_linear_region(self, x, y, linear_region_width=50, window_length=50, polyorder=3, peak_height = -5,
                          peak_distance = 100, peak_prom = 5, plot_derivative=False, denoise=False):
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
            peaks, _ = find_peaks(-derivative, height=peak_height, distance=peak_distance, prominence=peak_prom)

            try:
                for i in self.linear_region_list:
                    i.clear()
            except:
                pass
            self.linear_region_list = []
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

            #if plot deriviate is true, plot it else, if false, clear deriv plot.
            if plot_derivative:
                try:
                    self.odmr_deriv_plot.clear()
                except:
                    pass
                pen = pg.mkPen(color=(0, 255, 0), style=QtCore.Qt.PenStyle.DashDotLine)
                self.odmr_deriv_plot = self.graphWidget.plot(x, derivative, pen=pen)
            else:
                try:
                    self.odmr_deriv_plot.clear()
                except:
                    pass


            # self.odmrGradientLabel.setText(str(round(slope,3)))


            return

        except Exception as error:
            print(error)

app = QtWidgets.QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
if dark_theme:
    qdarktheme.setup_theme()
window = MainUI()  # Create an instance of our class
app.exec()
