import os
import time
import h5py
import cv2
import numpy as np
import pyqtgraph as pg
from PIL import Image
from PyQt6 import QtCore, QtWidgets, uic

from threading_utils import ThreadedComponent
from paths import ui_file
from ui_theme import apply_ui_polish


class scanningImageWindow(QtWidgets.QWidget, ThreadedComponent):
    def __init__(self, main_window):
        super().__init__()
        super(scanningImageWindow, self).__init__()
        self.main_window = main_window
        self.feedback_started = False
        self.res_grad = None
        self.res_freq = None
        self.dV = None
        self.df = None
        uic.loadUi(ui_file("scanningWindow.ui"), self)
        apply_ui_polish(self)
        self.show()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.StageControl = self.main_window.stageController

        self.graphWidget.setLabel(axis="left", text="RF Frequency (GHz)")
        self.graphWidget.setLabel(axis="bottom", text="Index")
        self.graphWidget.setLabel(axis="top", text="RF Frequency Shift (GHz)")
        self.graphWidget_2.setLabel(axis="left", text="Voltage (V)")
        self.graphWidget_2.setLabel(axis="bottom", text="Index")
        self.graphWidget_2.setLabel(axis="top", text="Measured Voltage (V)")

        self.xCoords = np.arange(
            self.main_window.xStartSpinBox.value(),
            (self.main_window.xEndSpinBox.value() + self.main_window.xStepSpinBox.value()),
            self.main_window.xStepSpinBox.value(),
        )
        self.yCoords = np.arange(
            self.main_window.yStartSpinBox.value(),
            (self.main_window.yEndSpinBox.value() + self.main_window.xStepSpinBox.value()),
            self.main_window.yStepSpinBox.value(),
        )
        self.xStep = self.main_window.xStepSpinBox.value()
        self.yStep = self.main_window.yStepSpinBox.value()
        self.vector = self.main_window.vectorRadio.isChecked()
        self.feedback = self.main_window.feedbackToggle.isChecked()
        self.scan_averaging = self.main_window.scanAveragingToggle.isChecked()
        self.avg_time = self.main_window.scanAveragingTimeSpinBox.value()
        self.scanning = False

        if self.vector:
            self.main_window.feedbackToggle.setChecked(True)
            self.feedback = self.main_window.feedbackToggle.isChecked()

        self.vc1 = self.graphWidget.plot()
        self.vc2 = self.graphWidget.plot()
        self.vc3 = self.graphWidget.plot()
        self.vc4 = self.graphWidget.plot()

        self.fc1 = self.graphWidget_2.plot()
        self.fc2 = self.graphWidget_2.plot()
        self.fc3 = self.graphWidget_2.plot()
        self.fc4 = self.graphWidget_2.plot()

        self.exportDataButton.clicked.connect(self.export_data)
        self.test_data = np.random.random([4, 10, 10])

        if (
            self.StageControl.stage_connected
            and self.main_window.rfController.rf_connected
            and self.main_window.LIAController.LIA_connected
        ):
            if self.feedback or self.vector:
                if (self.main_window.scanODMRPropertiesTable.item(0, 0) is None) or (
                    self.main_window.scanODMRPropertiesTable.item(0, 1) is None
                ):
                    error_dialog = QtWidgets.QErrorMessage(self.main_window)
                    error_dialog.showMessage(
                        "Error: If using feedback or vector, first row of freq. table can not be empty"
                    )
                    return
                self.thread_function(
                    self.setup_scan,
                    err_fn=self.main_window.show_error_message,
                    fin_fn=self.start_scan,
                )
            else:
                self.thread_function(
                    self.setup_scan,
                    err_fn=self.main_window.show_error_message,
                    fin_fn=self.start_scan,
                )
        else:
            error_dialog = QtWidgets.QErrorMessage(self.main_window)
            error_dialog.showMessage(
                "Error: Check printer, RF and LIA connections and try again"
            )

    def setup_scan(self, *args, **kwargs):
        if self.feedback:
            if self.vector:
                self.vector_freqs = []
                self.vector_grads = []
                for i in range(4):
                    try:
                        self.vector_freqs.append(
                            float(self.main_window.scanODMRPropertiesTable.item(i, 0).text())
                        )
                        self.vector_grads.append(
                            float(self.main_window.scanODMRPropertiesTable.item(i, 1).text())
                        )
                    except Exception:
                        pass
            else:
                self.res_freq = float(self.main_window.scanODMRPropertiesTable.item(0, 0).text())
                self.res_grad = float(self.main_window.scanODMRPropertiesTable.item(0, 1).text())

        self.StageControl.set_stage_pos(
            self.main_window.xStartSpinBox.value(), self.main_window.yStartSpinBox.value()
        )
        time.sleep(5)

    def start_scan(self):
        self.scanning = True
        if self.feedback:
            if self.vector:
                self.thread_function(
                    self.initialise_vector_feedback,
                    err_fn=self.main_window.show_error_message,
                    prg_fn=self.debug_plot,
                )
            else:
                self.thread_function(
                    self.initialise_feedback,
                    err_fn=self.main_window.show_error_message,
                    prg_fn=self.debug_plot,
                )

        if self.vector:
            self.thread_function(
                self.scan_vector,
                scan_time=0.2,
                err_fn=self.main_window.show_error_message,
                prg_fn=self.update_plot,
            )
        else:
            self.thread_function(
                self.scan_no_vector,
                scan_time=float(self.main_window.scanDwellTimeSpinBox.value()),
                err_fn=self.main_window.show_error_message,
                prg_fn=self.update_plot,
            )

    def _wait_for_feedback_start(self, timeout=10.0, poll=0.05):
        start = time.monotonic()
        while not self.feedback_started and self.scanning:
            if time.monotonic() - start >= timeout:
                error_dialog = QtWidgets.QErrorMessage(self.main_window)
                error_dialog.showMessage("Error: Feedback failed to start within timeout")
                return False
            time.sleep(poll)
        return True

    def initialise_feedback(self, *args, **kwargs):
        self.main_window.rfController.inst.write("FREQ " + str(round(float(self.res_freq) * 1e9, 12)))
        time.sleep(1)
        sample = self.main_window.LIAController.daq.getSample(
            "/%s/demods/0/sample" % self.main_window.LIAController.device
        )
        ini_voltage = sample["x"][0]
        self.feedback_started = True
        df_arr = []
        dV_arr = []
        res_freq_arr = []
        last_emit = 0.0
        while self.scanning:
            res_freq_arr.append(self.res_freq)
            sample = self.main_window.LIAController.daq.getSample(
                "/%s/demods/0/sample" % self.main_window.LIAController.device
            )
            voltage_now = sample["x"][0]
            self.dV = voltage_now - ini_voltage
            self.df = (1 / self.res_grad) * (-self.dV)
            self.res_freq = self.res_freq + self.df
            self.main_window.rfController.inst.write("FREQ " + str(round(float(self.res_freq) * 1e9, 12)))
            if len(df_arr) > 100:
                df_arr.pop(0)
                dV_arr.pop(0)
                res_freq_arr.pop(0)
            df_arr.append(self.df)
            dV_arr.append(self.dV)
            time.sleep(0.1)
            now = time.monotonic()
            if now - last_emit >= 0.1:
                kwargs["progress_callback"].emit([res_freq_arr, dV_arr])
                last_emit = now

    def initialise_vector_feedback(self, *args, **kwargs):
        ini_voltage = []
        self.ini_freq = []
        scale = 750
        self.vector_freqs_plotting = self.vector_freqs
        for i in range(len(self.vector_freqs)):
            self.ini_freq.append(self.vector_freqs[i])
            self.main_window.rfController.inst.write(
                "FREQ " + str(round(float(self.vector_freqs[i]) * 1e9, 12))
            )
            time.sleep(1)
            sample = self.main_window.LIAController.daq.getSample(
                "/%s/demods/0/sample" % self.main_window.LIAController.device
            )
            ini_voltage.append(sample["x"][0] * scale)
        df_arr = [[], [], [], []]
        dV_arr = [[], [], [], []]
        res_freq_arr = [[], [], [], []]
        self.feedback_started = True
        last_emit = 0.0
        while self.scanning:
            for i in range(len(self.vector_freqs)):
                self.main_window.rfController.inst.write(
                    "FREQ " + str(round(float(self.vector_freqs[i]) * 1e9, 12))
                )
                time.sleep(0.08)
                sample = self.main_window.LIAController.daq.getSample(
                    "/%s/demods/0/sample" % self.main_window.LIAController.device
                )
                voltage_now = sample["x"][0] * scale
                self.dV = voltage_now - ini_voltage[i]
                self.df = (1 / self.vector_grads[i]) * (-self.dV)
                self.vector_freqs[i] = self.vector_freqs[i] + self.df / 1e3
                df_arr[i].append(self.df)
                dV_arr[i].append(self.dV)
                res_freq_arr[i].append(self.vector_freqs[i])

            if len(df_arr[0]) > 100:
                for i in range(len(self.vector_freqs)):
                    df_arr[i].pop(0)
                    dV_arr[i].pop(0)
                    res_freq_arr[i].pop(0)
            time.sleep(0.1)
            now = time.monotonic()
            if now - last_emit >= 0.1:
                kwargs["progress_callback"].emit([res_freq_arr, dV_arr])
                last_emit = now

    def scan_no_vector(self, *args, **kwargs):
        if self.feedback and not self._wait_for_feedback_start():
            return
        if self.scan_averaging:
            self.main_window.LIAController.daq.subscribe(
                "/%s/demods/0/sample" % self.main_window.LIAController.device
            )
        time.sleep(3)
        scan_time = args[1]["scan_time"]
        x_positions = self.xCoords
        y_positions = self.yCoords
        self.voltageArr = np.zeros([1, len(y_positions), len(x_positions)])
        self.voltageArrSTD = np.zeros([1, len(y_positions), len(x_positions)])
        self.df_arr = np.zeros([1, len(y_positions), len(x_positions)])
        last_emit = 0.0

        def emit_if_due(payload):
            nonlocal last_emit
            now = time.monotonic()
            if now - last_emit >= 0.1:
                kwargs["progress_callback"].emit(payload)
                last_emit = now

        j = 0
        totalSize = len(x_positions) * len(y_positions)
        for _idx, y_position in enumerate(y_positions, 2):
            i = len(x_positions) - 1
            self.StageControl.set_stage_pos(x_positions[0], y_position)
            time.sleep(10)
            for x_position in x_positions:
                timeStart = time.time()
                ts = time.time()
                totalSize -= 1
                self.StageControl.set_stage_pos(x_position, y_position)
                time.sleep(scan_time)
                if self.feedback:
                    self.df_arr[0, j, i] = self.res_freq
                    emit_if_due(self.df_arr)
                else:
                    if self.scan_averaging:
                        stream = self.main_window.LIAController.daq.poll(self.avg_time, 200, 1, True)
                        sample_path = f"/{self.main_window.LIAController.device}/demods/0/sample"
                        self.voltageArr[0, j, i] = np.mean(stream[sample_path]["x"])
                        self.voltageArrSTD[0, j, i] = np.std(stream[sample_path]["x"])
                        emit_if_due(self.voltageArr)
                    else:
                        sample = self.main_window.LIAController.daq.getSample(
                            "/%s/demods/0/sample" % self.main_window.LIAController.device
                        )
                        self.voltageArr[0, j, i] = np.sqrt(((sample["x"][0]) ** 2 + (sample["y"][0]) ** 2))
                        emit_if_due(self.voltageArr)
                i = i - 1
                te = time.time()
                eta = (te - ts) * totalSize
                print(time.ctime(int(timeStart + eta)))
                if self.scanning is False:
                    return
            j += 1
        time.sleep(1)
        self.scanning = False

    def scan_vector(self, *args, **kwargs):
        if not self._wait_for_feedback_start():
            return
        time.sleep(3)
        scan_time = args[1]["scan_time"]
        x_positions = self.xCoords
        y_positions = self.yCoords
        self.voltageArr = np.zeros([4, len(y_positions), len(x_positions)])
        self.df_arr = np.zeros([4, len(y_positions), len(x_positions)])
        self.b_arr = np.zeros([3, len(y_positions), len(x_positions)])
        j = 0
        A_pinv = np.linalg.pinv(np.array(self.main_window.a_matrix_values))
        totalSize = len(x_positions) * len(y_positions)
        last_emit = 0.0
        for _idx, y_position in enumerate(y_positions, 2):
            i = len(x_positions) - 1
            for x_position in x_positions:
                timeStart = time.time()
                ts = time.time()
                totalSize -= 1
                self.StageControl.set_stage_pos(x_position, y_position)
                time.sleep(scan_time)
                for k in range(4):
                    self.df_arr[k, j, i] = self.vector_freqs[k]
                df1, df2, df3, df4 = (np.array(self.vector_freqs) - np.array(self.ini_freq)) * 1000
                freq_col = [[df1], [df2], [df3], [df4]]
                B = np.dot(A_pinv, freq_col)
                for k in range(3):
                    self.b_arr[k, j, i] = B[k][0]
                now = time.monotonic()
                if now - last_emit >= 0.1:
                    kwargs["progress_callback"].emit(self.b_arr)
                    last_emit = now
                i = i - 1
                te = time.time()
                eta = (te - ts) * totalSize
                print(time.ctime(int(timeStart + eta)))
                if self.scanning is False:
                    return
            j += 1
            self.StageControl.set_stage_pos(x_positions[0], y_position)
            time.sleep(6)
        time.sleep(1)
        self.scanning = False

    @staticmethod
    def calculate_levels(a):
        px = a.ravel()[np.flatnonzero(a)]
        k = int(len(px) * 0.05)
        if k > 0:
            px_low = np.argpartition(px, k)
            px_high = np.argpartition(px, -k)
            return px[px_low[k - 1]], px[px_high[-k - 1]]
        return min(px), max(px)

    def update_plot(self, image_arr):
        if self.vector:
            levels0 = self.calculate_levels(image_arr[0])
            levels1 = self.calculate_levels(image_arr[1])
            levels2 = self.calculate_levels(image_arr[2])
            self.imageWidget_2.setImage(image_arr[0], levels=levels0)
            self.imageWidget_3.setImage(image_arr[1], levels=levels1)
            self.imageWidget_4.setImage(image_arr[2], levels=levels2)
        else:
            levels = self.calculate_levels(image_arr)
            self.imageWidget.setImage(image_arr, levels=levels)

    def debug_plot(self, arrs):
        if self.vector:
            self.vc1.setData(arrs[0][0], pen=pg.mkPen("b"))
            self.vc2.setData(arrs[0][1], pen=pg.mkPen("g"))
            self.vc3.setData(arrs[0][2], pen=pg.mkPen("r"))
            self.vc4.setData(arrs[0][3], pen=pg.mkPen("y"))

            self.fc1.setData(arrs[1][0], pen=pg.mkPen("b"))
            self.fc2.setData(arrs[1][1], pen=pg.mkPen("g"))
            self.fc3.setData(arrs[1][2], pen=pg.mkPen("r"))
            self.fc4.setData(arrs[1][3], pen=pg.mkPen("y"))

    def export_data(self):
        folderpath = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder")
        date_time = time.strftime("/Scan_Data_%Y-%m-%d_%H-%M-%S", time.gmtime())
        try:
            df_arr_data = np.array(self.df_arr)
            voltage_arr_data = np.array(self.voltageArr)
            voltage_std_arr_data = np.array(self.voltageArrSTD)
            h5f = h5py.File(folderpath + date_time + ".h5", "w")
            h5f.create_dataset("df_array", data=df_arr_data)
            h5f.create_dataset("voltage_array", data=voltage_arr_data)
            h5f.create_dataset("voltage_st_arrayy", data=voltage_std_arr_data)
            h5f.close()
        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(self.main_window)
            error_dialog.showMessage(str(error))

        if not os.path.exists(folderpath + date_time + "IMAGES"):
            os.makedirs(folderpath + date_time + "IMAGES")
        for i in range(len(df_arr_data)):
            df_image = df_arr_data[i, :, :]
            voltage_image = voltage_arr_data[i, :, :]
            df_image = cv2.resize(df_image, dsize=(640, 640), interpolation=cv2.INTER_CUBIC)
            voltage_image = cv2.resize(voltage_image, dsize=(640, 640), interpolation=cv2.INTER_CUBIC)
            df_image8 = (((df_image - df_image.min()) / (df_image.max() - df_image.min())) * 255.9).astype(np.uint8)
            voltage_image8 = (((voltage_image - voltage_image.min()) / (voltage_image.max() - voltage_image.min())) * 255.9).astype(np.uint8)
            df_image = Image.fromarray(df_image8)
            voltage_image = Image.fromarray(voltage_image8)

            df_image.save(folderpath + date_time + "IMAGES/" + "_IMAGE_freq_" + str(i) + ".PNG")
            voltage_image.save(folderpath + date_time + "IMAGES/" + "_IMAGE_voltage_" + str(i) + ".PNG")

    def closeEvent(self, event):
        self.scanning = False
