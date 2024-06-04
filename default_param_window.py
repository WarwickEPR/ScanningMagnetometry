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
import default_params
import yaml


class DefaultParamWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(DefaultParamWindow, self).__init__()  # Call the inherited classes __init__ method
        self.selected_data = None
        self.f = None
        uic.loadUi('defaultParamWindow.ui', self)  # Load the .ui file
        self.show()  # Show the GUI

        # populate text boxes with current parameters
        self.load_params()

        # ui connections
        self.applyParamsButton.clicked.connect(self.set_params)

    def set_params(self):
        self.default_parameters = {
            "Device_IP" : self.liaDefaultIPTextBox.text(),
            "Device_ID" : self.liaDefaultIDTextBox.text(),
            "RF_IP" : self.RFDefaultIPTextBox.text()
        }
        print(self.default_parameters)
        with open('config.yml', 'w') as f:
            yaml.dump(self.default_parameters, f, default_flow_style=False)
        print(self.default_parameters)
        return

    def load_params(self):
        try:
            with open("config.yml", "r") as f:
                self.default_parameters = yaml.safe_load(f)
                print(self.default_parameters)
                self.liaDefaultIPTextBox.setText(self.default_parameters['Device_IP'])
                self.liaDefaultIDTextBox.setText(self.default_parameters['Device_ID'])
                self.RFDefaultIPTextBox.setText(self.default_parameters['RF_IP'])
        except Exception as error:
            print(error)
        return