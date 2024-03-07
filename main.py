from PyQt6 import QtWidgets, uic
import sys

class MainUI(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('scanning_magnetometer.ui', self)  # Load the .ui file
        self.show()  # Show the GUI

class stageControl:
    def __init__(self):
        return

app = QtWidgets.QApplication(sys.argv) # Create an instance of QtWidgets.QApplication
window = MainUI() # Create an instance of our class
app.exec()