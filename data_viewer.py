# -*- coding: utf-8 -*-
"""HDF5 Data viewer

This is for accessing the data saved in the hdf5 files and for some surface level analysis, the user can export
selected datasets to easier to use csv or matlab files.
"""

from PyQt6 import QtWidgets
import h5py
import numpy as np
from data_viewer_ui import DataViewerUIBuilder
from ui_theme import (
    configure_pyqtgraph_defaults,
    get_plot_pen,
    style_image_view,
    style_plot_labels,
    style_plot_widget,
)


class DataViewer(QtWidgets.QMainWindow):
    def __init__(self):
        super(DataViewer, self).__init__()  # Call the inherited classes __init__ method
        self.selected_data = None
        self.f = None
        configure_pyqtgraph_defaults()
        DataViewerUIBuilder().setup(self)
        self.show()  # Show the GUI

        style_plot_widget(self.dataGraph)
        style_plot_labels(self.dataGraph, left="Value", bottom="Index")
        style_image_view(self.imageWidget)

        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)
        self.loadH5FileButton.clicked.connect(self.load_file)
        self.saveImgCSVButton.clicked.connect(self.export_image_to_csv)
        self.fileItemList.itemDoubleClicked.connect(lambda: self.select_file(self.fileItemList.currentItem()))
        self.dataList.itemDoubleClicked.connect(lambda: self.select_data(self.dataList.currentItem()))
        self.selectPlotType.currentIndexChanged.connect(
            lambda: self.change_plot_type(self.selectPlotType.currentIndex()))

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
        self.data = self.f[item.text()][()]
        for i in range(len(self.data)):
            self.dataList.addItem(str(i + 1))
        # self.dataImage.setImage(data[0,:,:])
        return

    def select_data(self, item):
        self.selected_data = self.data[int(item.text()) - 1]
        if len(self.selected_data.shape) == 1:
            #  data is 1D array, plot as line
            self.dataGraph.clear()
            self.dataGraph.plot(self.selected_data, pen=get_plot_pen(0, width=2))
        elif len(self.selected_data.shape) == 2:
            self.imageWidget.setImage(self.selected_data)
            #  array is 2D, plot as image
        return

    def change_plot_type(self, item):
        self.stackedGraphs.setCurrentIndex(item)
        return

    def export_image_to_csv(self):
        if type(self.imageWidget.image) is np.ndarray:
            filepath = QtWidgets.QFileDialog.getSaveFileName(self, 'Select File', filter="CSV (*.csv)")[0]
            np.savetxt(filepath, self.imageWidget.image, delimiter=',')
            return
        else:
            error_dialog = QtWidgets.QErrorMessage(self)
            error_dialog.showMessage("No Image Selected To Export")
        return
