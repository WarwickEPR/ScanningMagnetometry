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
        self.f = None
        uic.loadUi('data_viewer.ui', self)  # Load the .ui file
        self.show()  # Show the GUI

        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)
        self.loadH5FileButton.clicked.connect(self.load_file)
        self.fileItemList.itemDoubleClicked.connect(lambda: self.select_file(self.fileItemList.currentItem()))
        self.dataList.itemDoubleClicked.connect(lambda: self.select_data(self.dataList.currentItem()))
        self.selectPlotType.currentIndexChanged.connect(lambda: self.change_plot_type(self.selectPlotType.currentIndex()))

    def load_file(self):
        """ loads a selected .h5 file and populates the list view with the different data sets available"""
        self.fileItemList.clear()
        self.dataList.clear()
        try:
            filepath = QtWidgets.QFileDialog.getOpenFileName(self, 'Select File', filter="HDF5 (*.hdf5 *.h5)")[0]
            if len(filepath) == 0:
                self.statusBar.showMessage("No File Selected")
                return
            else:
                self.statusBar.showMessage("Loading " + filepath)
            self.f = h5py.File(filepath, 'r')
            list_of_keys = list(self.f.keys())
            for i in list_of_keys:
                self.fileItemList.addItem(i)
        except Exception as ex:
            error_dialog = QtWidgets.QErrorMessage(self)
            error_dialog.showMessage(str(ex))
        return

    def select_file(self, item):
        """ when an item in the list view is double-clicked, attempt to display files within

        :param item: (QtListWidgetItem) currently select item in the list
        :return:
        """
        print("item selected", item.text())
        self.data = self.f[item.text()][()]
        for i in range(len(self.data)):
            self.dataList.addItem(str(i+1))
        # self.dataImage.setImage(data[0,:,:])
        return

    def select_data(self, item):
        # print(item.text(),type(item.text()))
        selected_data = self.data[int(item.text())-1]
        print(type(selected_data) , selected_data.shape)
        if len(selected_data.shape) == 1:
            #data is 1D array, plot as line
            self.dataGraph.plot(selected_data)
        elif len(selected_data.shape) == 2:
            self.imageWidget.setImage(selected_data)
            #array is 2D, plot as image

        # print(self.data[int(item.text()), :, :])
        # print(len(data))
        return

    def change_plot_type(self, item):
        self.stackedGraphs.setCurrentIndex(item)
        return
