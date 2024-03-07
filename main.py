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



class stageControl(QtWidgets.QMainWindow):
    def __init__(self):
        super(stageControl, self).__init__()
        self.ser = None
        return

    def execute_gcode(self, command):
        try:
            self.ser.write(f'{command}\r\n'.encode())
        except:
            print("ERROR: Could not execute stage command")

    def connect_stage(self, com_port, baud_rate=115200):
        try:
            # connect to stage code here
            self.ser = serial.Serial(port=com_port, baudrate=baud_rate)
            msg = QtWidgets.QMessageBox(self)
            msg.setText("Connected Successful to: " + str(com_port))
            msg.exec()
        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(self)
            error_dialog.showMessage(str(error))
x
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


app = QtWidgets.QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
window = MainUI()  # Create an instance of our class
app.exec()
