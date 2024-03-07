from PyQt6 import QtWidgets, uic
import sys
import serial
import serial.tools.list_ports



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

class stageControl:
    def __init__(self):
        super(stageControl, self).__init__()
        self.ser = None
        return

    def execute_gcode(self, command):
        try:
            self.ser.write(f'{command}\r\n'.encode())
        except:
            print("ERROR: Could not execute stage command")

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
        print(x, y)
        self.execute_gcode(f'G00 X{x} Y{y}')
        return

    def set_stage_height(self, z):
        print(z)
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


app = QtWidgets.QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
window = MainUI()  # Create an instance of our class
app.exec()
