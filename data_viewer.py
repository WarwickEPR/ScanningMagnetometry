# -*- coding: utf-8 -*-
"""HDF5 Data viewer

This is for accessing the data saved in the hdf5 files and for some surface level analysis, the user can export
selected datasets to easier to use csv or matlab files.
"""

from PyQt6 import QtCore, QtWidgets, uic
import pyqtgraph as pg
import h5py
import numpy as np
import sys
try:
    import qdarktheme
    dark_theme = True
except Exception as error:
    dark_theme = False

class DataViewer(QtWidgets.QMainWindow):
    def __init__(self):
        super(DataViewer, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('data_viewer.ui', self)  # Load the .ui file
        self.show()  # Show the GUI

        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)
        self.loadH5FileButton.clicked.connect(self.load_file)

    def load_file(self):
        filepath = QtWidgets.QFileDialog.getOpenFileName(self, 'Select File', filter = "HDF5 (*.hdf5 *.h5)")
        print(filepath, type(filepath))
        # self.statusBar.showMessage("loaded " + filepath)
        return
