import os
import time
import h5py
import cv2
import numpy as np
import pyqtgraph as pg
from scipy.ndimage import gaussian_filter
from PIL import Image
from PyQt6 import QtCore, QtWidgets

from threading_utils import ThreadedComponent
from ui_theme import (
    configure_pyqtgraph_defaults,
    get_plot_pen,
    style_image_view,
    style_plot_labels,
    style_plot_widget,
)
from windows.scanning_window_ui import ScanningWindowUIBuilder


class scanningImageWindow(QtWidgets.QWidget, ThreadedComponent):
    def __init__(self, main_window):
        super().__init__()
        super(scanningImageWindow, self).__init__()
        self.main_window = main_window
        self.feedback_started = False
        self.res_grad = None
        self.res_freq = None
        self.scalar_ini_freq = None
        self.latest_feedback_voltage = None
        self.latest_feedback_shift_mhz = None
        self.dV = None
        self.df = None
        configure_pyqtgraph_defaults()
        ScanningWindowUIBuilder().setup(self)
        self.show()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.StageControl = self.main_window.stageController

        style_plot_widget(self.graphWidget)
        style_plot_widget(self.graphWidget_2)
        style_plot_labels(
            self.graphWidget,
            left="RF Frequency (GHz)",
            bottom="Index",
            top="RF Frequency Shift (GHz)",
        )
        style_plot_labels(
            self.graphWidget_2,
            left="Voltage (V)",
            bottom="Index",
            top="Measured Voltage (V)",
        )
        style_image_view(self.imageWidget)
        style_image_view(self.imageWidget_2)
        style_image_view(self.imageWidget_3)
        style_image_view(self.imageWidget_4)

        self.xCoords = np.arange(
            self.main_window.xStartSpinBox.value(),
            (self.main_window.xEndSpinBox.value() + self.main_window.xStepSpinBox.value()),
            self.main_window.xStepSpinBox.value(),
        )
        self.yCoords = np.arange(
            self.main_window.yStartSpinBox.value(),
            (self.main_window.yEndSpinBox.value() + self.main_window.yStepSpinBox.value()),
            self.main_window.yStepSpinBox.value(),
        )
        self.xStep = self.main_window.xStepSpinBox.value()
        self.yStep = self.main_window.yStepSpinBox.value()
        self.vector = self.main_window.vectorRadio.isChecked()
        self.feedback = self.main_window.feedbackToggle.isChecked()
        self.feedback_row_index = int(
            getattr(self.main_window.feedbackRowSelect, "currentIndex", lambda: 0)()
        )
        self.scan_averaging = self.main_window.scanAveragingToggle.isChecked()
        self.avg_time = self.main_window.scanAveragingTimeSpinBox.value()
        _pattern_combo = getattr(self.main_window, "scanPatternCombo", None)
        self.serpentine = (
            _pattern_combo.currentText() == "Serpentine" if _pattern_combo is not None else False
        )
        self.scanning = False
        self.feedback_voltage_avg_samples = 3
        self.feedback_voltage_sample_spacing_s = 0.01
        self.max_df_step_mhz = 0.4
        self.max_tracking_offset_mhz = 25.0
        self.min_gradient_abs = 1e-6
        self.max_history_points = 100
        self.emit_interval_s = 0.1
        self.use_scaled_feedback_voltage = False
        self.deadband_voltage = 0.0
        self.enable_baseline_adaptation = False
        self.baseline_adapt_alpha = 0.0
        self.feedback_control_mode = "Proportional"
        self.pid_kp = 1.0
        self.pid_ki = 0.0
        self.pid_kd = 0.0
        self.pid_integral_limit = 5.0
        self.scalar_feedback_demod_mode = "X"
        self.vector_feedback_demod_mode = "R"
        self.setpoint_duration_s = 2.0
        self.total_pixels = int(len(self.xCoords) * len(self.yCoords))
        self.completed_pixels = 0
        self.scan_start_time_monotonic = None
        self.field_model = getattr(self.main_window, "odmr_fit_model", None)
        self._refresh_feedback_settings_from_ui()
        self._set_eta_label_initial()

        if self.vector:
            self.main_window.feedbackToggle.setChecked(True)
            self.feedback = self.main_window.feedbackToggle.isChecked()

        self._apply_mode_visibility()

        self.vc1 = self.graphWidget.plot()
        self.vc2 = self.graphWidget.plot()
        self.vc3 = self.graphWidget.plot()
        self.vc4 = self.graphWidget.plot()

        self.fc1 = self.graphWidget_2.plot()
        self.fc2 = self.graphWidget_2.plot()
        self.fc3 = self.graphWidget_2.plot()
        self.fc4 = self.graphWidget_2.plot()

        self.exportDataButton.clicked.connect(self.export_data)
        self.stopScanButton.clicked.connect(self.stop_scan)
        self.gaussianBlurCheck.toggled.connect(self._on_blur_setting_changed)
        self.gaussianSigmaSpinBox.valueChanged.connect(self._on_blur_setting_changed)
        self._last_plot_arr = None
        self.test_data = np.random.random([4, 10, 10])

        if (
            self.StageControl.stage_connected
            and self.main_window.rfController.rf_connected
            and self.main_window.LIAController.LIA_connected
        ):
            if self.feedback or self.vector:
                if self.vector:
                    for row in range(4):
                        freq_item = self.main_window.scanODMRPropertiesTable.item(row, 0)
                        grad_item = self.main_window.scanODMRPropertiesTable.item(row, 1)
                        if freq_item is None or grad_item is None:
                            error_dialog = QtWidgets.QErrorMessage(self.main_window)
                            error_dialog.showMessage(
                                "Error: Vector mode requires all 4 feedback rows to be populated."
                            )
                            return
                        try:
                            float(freq_item.text())
                            float(grad_item.text())
                        except Exception:
                            error_dialog = QtWidgets.QErrorMessage(self.main_window)
                            error_dialog.showMessage(
                                "Error: Vector mode feedback table contains invalid values."
                            )
                            return
                else:
                    target_row = self.feedback_row_index
                    if (
                        self.main_window.scanODMRPropertiesTable.item(target_row, 0) is None
                    ) or (
                        self.main_window.scanODMRPropertiesTable.item(target_row, 1) is None
                    ):
                        error_dialog = QtWidgets.QErrorMessage(self.main_window)
                        error_dialog.showMessage(
                            "Error: Selected feedback table entry is empty."
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
                self.res_freq = float(
                    self.main_window.scanODMRPropertiesTable.item(
                        self.feedback_row_index, 0
                    ).text()
                )
                self.res_grad = float(
                    self.main_window.scanODMRPropertiesTable.item(
                        self.feedback_row_index, 1
                    ).text()
                )

        if not self.StageControl.move_stage_pos_wait(
            self.main_window.xStartSpinBox.value(),
            self.main_window.yStartSpinBox.value(),
            use_motion_barrier=True,
        ):
            raise RuntimeError("Stage failed to reach scan start position.")

    def _move_stage_to_measurement_point(self, x_position, y_position, require_full_wait=False):
        if not self.scanning:
            return False
        if require_full_wait:
            reached_target = self.StageControl.move_stage_pos_wait(
                x_position,
                y_position,
                tolerance_mm=0.02,
                poll_s=0.01,
                settle_s=0.02,
                use_motion_barrier=True,
            )
            if not reached_target:
                raise RuntimeError(
                    f"Stage failed to reach scan position X={float(x_position):.5f}, Y={float(y_position):.5f}."
                )
        else:
            self.StageControl.set_stage_pos(x_position, y_position)
        return self.scanning

    def _apply_mode_visibility(self):
        use_tracking = bool(self.feedback or self.vector)
        use_vector_maps = bool(self.vector)

        tab_widget = getattr(self, "scanTabWidget", None)
        map_tab = getattr(self, "scanMapTab", None)
        tracking_tab = getattr(self, "scanTrackingTab", None)
        if tab_widget is not None and map_tab is not None and tracking_tab is not None:
            tracking_index = tab_widget.indexOf(tracking_tab)
            map_index = tab_widget.indexOf(map_tab)
            if tracking_index != -1:
                if hasattr(tab_widget, "setTabVisible"):
                    tab_widget.setTabVisible(tracking_index, use_tracking)
                tab_widget.setTabEnabled(tracking_index, use_tracking)
            if map_index != -1:
                tab_widget.setCurrentIndex(map_index)

        map_sub_tabs = getattr(self, "mapSubTabWidget", None)
        primary_tab = getattr(self, "primaryMapTab", None)
        bx_tab = getattr(self, "vectorMapTabBx", None)
        by_tab = getattr(self, "vectorMapTabBy", None)
        bz_tab = getattr(self, "vectorMapTabBz", None)
        if map_sub_tabs is not None:
            tab_targets = [
                (primary_tab, not use_vector_maps),
                (bx_tab, use_vector_maps),
                (by_tab, use_vector_maps),
                (bz_tab, use_vector_maps),
            ]
            for tab_widget_ref, should_show in tab_targets:
                if tab_widget_ref is None:
                    continue
                tab_index = map_sub_tabs.indexOf(tab_widget_ref)
                if tab_index == -1:
                    continue
                if hasattr(map_sub_tabs, "setTabVisible"):
                    map_sub_tabs.setTabVisible(tab_index, bool(should_show))
                map_sub_tabs.setTabEnabled(tab_index, bool(should_show))

            if use_vector_maps and bx_tab is not None:
                bx_index = map_sub_tabs.indexOf(bx_tab)
                if bx_index != -1:
                    map_sub_tabs.setCurrentIndex(bx_index)
            elif (not use_vector_maps) and primary_tab is not None:
                primary_index = map_sub_tabs.indexOf(primary_tab)
                if primary_index != -1:
                    map_sub_tabs.setCurrentIndex(primary_index)

        for widget_name in [
            "frequencyTrackingCard",
            "voltageTrackingCard",
            "graphWidget",
            "graphWidget_2",
        ]:
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setVisible(use_tracking)

        # Rename the primary map card and its sub-tab to reflect scan content
        if not use_vector_maps:
            if self.feedback:
                primary_title = "\u0394f Map (MHz)"
                tab_label = "\u0394f Map"
            else:
                primary_title = "Voltage Map (V)"
                tab_label = "Voltage Map"
            primary_card = getattr(self, "primaryMapCard", None)
            if primary_card is not None:
                primary_card.setTitle(primary_title)
            if map_sub_tabs is not None and primary_tab is not None:
                idx = map_sub_tabs.indexOf(primary_tab)
                if idx != -1:
                    map_sub_tabs.setTabText(idx, tab_label)

    @staticmethod
    def _format_duration_hms(total_seconds):
        total = max(0, int(round(float(total_seconds))))
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _set_eta_label_initial(self):
        if self.total_pixels > 0:
            self.scanEtaLabel.setText(f"ETA: estimating... (0/{self.total_pixels} px)")
        else:
            self.scanEtaLabel.setText("ETA: --")

    def _update_eta_label(self, completed, total, elapsed_s):
        completed_i = int(max(0, completed))
        total_i = int(max(1, total))
        if completed_i <= 0:
            self.scanEtaLabel.setText(f"ETA: estimating... ({completed_i}/{total_i} px)")
            return
        if completed_i >= total_i:
            total_time = self._format_duration_hms(elapsed_s)
            self.scanEtaLabel.setText(f"ETA: complete ({total_i}/{total_i} px, {total_time})")
            return
        rate = float(completed_i) / max(1e-6, float(elapsed_s))
        remaining_px = total_i - completed_i
        eta_s = remaining_px / max(1e-6, rate)
        eta_text = self._format_duration_hms(eta_s)
        self.scanEtaLabel.setText(f"ETA: {eta_text} ({completed_i}/{total_i} px)")

    def start_scan(self):
        self.scanning = True
        self.completed_pixels = 0
        self.scan_start_time_monotonic = time.monotonic()
        self._set_eta_label_initial()
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
                raise RuntimeError("Feedback failed to start within timeout")
            time.sleep(poll)
        return bool(self.feedback_started)

    def _refresh_feedback_settings_from_ui(self):
        if hasattr(self.main_window, "scanFbAvgSamplesSpinBox"):
            self.feedback_voltage_avg_samples = max(
                1, int(self.main_window.scanFbAvgSamplesSpinBox.value())
            )
        if hasattr(self.main_window, "scanFbSampleSpacingSpinBox"):
            self.feedback_voltage_sample_spacing_s = max(
                0.0, float(self.main_window.scanFbSampleSpacingSpinBox.value())
            )
        if hasattr(self.main_window, "scanFbSetpointDurationSpinBox"):
            self.setpoint_duration_s = max(
                0.1, float(self.main_window.scanFbSetpointDurationSpinBox.value())
            )
        if hasattr(self.main_window, "scanFbMaxDfStepSpinBox"):
            self.max_df_step_mhz = max(
                1e-6, float(self.main_window.scanFbMaxDfStepSpinBox.value())
            )
        if hasattr(self.main_window, "scanFbMaxTrackingOffsetSpinBox"):
            self.max_tracking_offset_mhz = max(
                1e-6, float(self.main_window.scanFbMaxTrackingOffsetSpinBox.value())
            )
        if hasattr(self.main_window, "scanFbEmitIntervalSpinBox"):
            self.emit_interval_s = max(
                0.01, float(self.main_window.scanFbEmitIntervalSpinBox.value())
            )
        if hasattr(self.main_window, "scanFbDeadbandSpinBox"):
            self.deadband_voltage = max(
                0.0, float(self.main_window.scanFbDeadbandSpinBox.value())
            )
        if hasattr(self.main_window, "scanFbControlModeCombo"):
            self.feedback_control_mode = str(
                self.main_window.scanFbControlModeCombo.currentText()
            )
        if hasattr(self.main_window, "scanFbPidKpSpinBox"):
            self.pid_kp = max(0.0, float(self.main_window.scanFbPidKpSpinBox.value()))
        if hasattr(self.main_window, "scanFbPidKiSpinBox"):
            self.pid_ki = max(0.0, float(self.main_window.scanFbPidKiSpinBox.value()))
        if hasattr(self.main_window, "scanFbPidKdSpinBox"):
            self.pid_kd = max(0.0, float(self.main_window.scanFbPidKdSpinBox.value()))
        if hasattr(self.main_window, "scanFbPidIntegralLimitSpinBox"):
            self.pid_integral_limit = max(
                0.0, float(self.main_window.scanFbPidIntegralLimitSpinBox.value())
            )
        if hasattr(self.main_window, "scanFbUseScaledCheckBox"):
            self.use_scaled_feedback_voltage = bool(
                self.main_window.scanFbUseScaledCheckBox.isChecked()
            )
        if hasattr(self.main_window, "scanFbBaselineAdaptCheckBox"):
            self.enable_baseline_adaptation = bool(
                self.main_window.scanFbBaselineAdaptCheckBox.isChecked()
            )
        if hasattr(self.main_window, "scanFbBaselineAlphaSpinBox"):
            self.baseline_adapt_alpha = max(
                0.0, float(self.main_window.scanFbBaselineAlphaSpinBox.value())
            )
        if hasattr(self.main_window, "scanFbScalarDemodModeCombo"):
            self.scalar_feedback_demod_mode = str(
                self.main_window.scanFbScalarDemodModeCombo.currentText()
            )
        if hasattr(self.main_window, "scanFbVectorDemodModeCombo"):
            self.vector_feedback_demod_mode = str(
                self.main_window.scanFbVectorDemodModeCombo.currentText()
            )

    @staticmethod
    def _sleep_with_stop_flag(instance, duration_s, chunk_s=0.01):
        end_t = time.monotonic() + max(0.0, float(duration_s))
        while time.monotonic() < end_t:
            if not instance.scanning:
                return False
            remaining = end_t - time.monotonic()
            if remaining <= 0.0:
                break
            time.sleep(min(float(chunk_s), remaining))
        return True

    @staticmethod
    def _set_rf_frequency_ghz(rf_inst, frequency_ghz):
        rf_inst.write("FREQ " + str(round(float(frequency_ghz) * 1e9, 12)))

    def _compute_pid_df(self, error_mhz, index, pid_integral, pid_prev_error, pid_prev_time):
        now_t = time.monotonic()
        prev_t = pid_prev_time[index]
        dt = max(1e-3, now_t - prev_t) if prev_t is not None else 0.0

        if dt > 0.0 and self.pid_ki > 0.0:
            pid_integral[index] += error_mhz * dt
            if self.pid_integral_limit > 0.0:
                pid_integral[index] = float(
                    np.clip(pid_integral[index], -self.pid_integral_limit, self.pid_integral_limit)
                )

        derivative = 0.0
        if dt > 0.0 and pid_prev_error[index] is not None:
            derivative = (error_mhz - pid_prev_error[index]) / dt

        pid_prev_error[index] = error_mhz
        pid_prev_time[index] = now_t

        p_term = self.pid_kp * error_mhz
        i_term = self.pid_ki * pid_integral[index]
        d_term = self.pid_kd * derivative
        output = p_term + i_term + d_term
        return float(output), float(p_term), float(i_term), float(d_term)

    def _read_lia_voltage_average(self, lia_daq, lia_device, scale, demod_mode):
        samples = []
        demod_path = f"/{lia_device}/demods/0/sample"
        for sample_index in range(max(1, int(self.feedback_voltage_avg_samples))):
            sample = lia_daq.getSample(demod_path)
            x_val = float(sample["x"][0])
            y_val = float(sample["y"][0])
            if demod_mode == "X":
                signal_value = x_val
            else:
                signal_value = float(np.hypot(x_val, y_val))
            samples.append(signal_value * float(scale))
            if sample_index < int(self.feedback_voltage_avg_samples) - 1:
                if not self._sleep_with_stop_flag(self, self.feedback_voltage_sample_spacing_s):
                    break
        if not samples:
            raise RuntimeError("Failed to read LIA sample for feedback.")
        return float(np.mean(samples))

    def _auto_zero_demod_phase(self, settle_after_s=None):
        lia_ctrl = getattr(self.main_window, "LIAController", None)
        if lia_ctrl is None:
            return False

        if settle_after_s is None:
            tc = float(self.main_window.get_lia_time_constant_seconds())
            settle_after_s = max(0.2, min(1.5, 6.0 * max(0.0, tc)))

        ok = False
        try:
            if hasattr(lia_ctrl, "auto_zero_demod_phase"):
                ok = bool(
                    lia_ctrl.auto_zero_demod_phase(
                        demod_index=0,
                        settle_s=float(settle_after_s),
                        timeout_s=3.0,
                        poll_s=0.02,
                    )
                )
            else:
                daq = getattr(lia_ctrl, "daq", None)
                dev = getattr(lia_ctrl, "device", None)
                if daq is not None and dev is not None:
                    daq.setInt(f"/{dev}/demods/0/phaseadjust", 1)
                    daq.sync()
                    ok = True
        except Exception:
            ok = False

        if ok and settle_after_s and float(settle_after_s) > 0.0:
            if not self._sleep_with_stop_flag(self, float(settle_after_s)):
                return False
        return ok

    def initialise_feedback(self, *args, **kwargs):
        self._refresh_feedback_settings_from_ui()
        rf_inst = getattr(self.main_window.rfController, "inst", None)
        lia_daq = getattr(self.main_window.LIAController, "daq", None)
        lia_device = getattr(self.main_window.LIAController, "device", None)
        if rf_inst is None:
            raise RuntimeError("RF source is not connected. Connect RF before starting feedback scan.")
        if lia_daq is None or lia_device is None:
            raise RuntimeError("LIA is not connected. Connect LIA before starting feedback scan.")

        runtime_scale = float(
            getattr(self.main_window.LIAController, "scaling_Factor", None)
            or self.main_window.scalingFactorSpinBox.value()
            or 1.0
        )
        scale = runtime_scale if self.use_scaled_feedback_voltage else 1.0
        settle_time_s = max(
            0.03,
            min(
                0.3,
                3.0 * float(self.main_window.get_lia_time_constant_seconds()),
            ),
        )

        if abs(float(self.res_grad)) < self.min_gradient_abs:
            raise ValueError(f"Selected gradient is too close to zero ({self.res_grad}).")

        self.scalar_ini_freq = float(self.res_freq)
        self._set_rf_frequency_ghz(rf_inst, self.res_freq)
        if not self._sleep_with_stop_flag(self, settle_time_s):
            return
        self._auto_zero_demod_phase()

        demod_path = f"/{lia_device}/demods/0/sample"
        setpoint_samples = []
        setpoint_end = time.monotonic() + self.setpoint_duration_s
        while time.monotonic() < setpoint_end:
            if not self.scanning:
                return
            sample = lia_daq.getSample(demod_path)
            setpoint_samples.append(float(sample["x"][0]) * float(scale))
            time.sleep(0.01)
        if not setpoint_samples:
            raise RuntimeError("Failed to acquire scalar feedback setpoint samples.")
        ini_voltage = float(np.mean(setpoint_samples))

        self.feedback_started = True
        shift_arr = []
        voltage_arr = []
        pid_integral = [0.0]
        pid_prev_error = [None]
        pid_prev_time = [None]
        last_emit = 0.0

        while self.scanning:
            self._refresh_feedback_settings_from_ui()
            self._set_rf_frequency_ghz(rf_inst, self.res_freq)
            if not self._sleep_with_stop_flag(self, settle_time_s):
                return

            voltage_now = self._read_lia_voltage_average(
                lia_daq, lia_device, scale, self.scalar_feedback_demod_mode
            )
            self.dV = voltage_now - ini_voltage
            error_mhz = (1.0 / float(self.res_grad)) * (-self.dV)

            if abs(self.dV) < self.deadband_voltage:
                raw_df = 0.0
                pid_prev_time[0] = None
                pid_prev_error[0] = 0.0
            else:
                if self.feedback_control_mode == "PID":
                    raw_df, _p_term, _i_term, _d_term = self._compute_pid_df(
                        error_mhz, 0, pid_integral, pid_prev_error, pid_prev_time
                    )
                else:
                    raw_df = error_mhz

            self.df = float(np.clip(raw_df, -self.max_df_step_mhz, self.max_df_step_mhz))
            candidate_freq = float(self.res_freq) + self.df / 1e3
            min_freq = self.scalar_ini_freq - (self.max_tracking_offset_mhz / 1e3)
            max_freq = self.scalar_ini_freq + (self.max_tracking_offset_mhz / 1e3)
            self.res_freq = float(np.clip(candidate_freq, min_freq, max_freq))
            self._set_rf_frequency_ghz(rf_inst, self.res_freq)

            if self.enable_baseline_adaptation and self.baseline_adapt_alpha > 0.0:
                ini_voltage = (
                    (1.0 - self.baseline_adapt_alpha) * ini_voltage
                    + self.baseline_adapt_alpha * voltage_now
                )

            shift_mhz = (float(self.res_freq) - float(self.scalar_ini_freq)) * 1e3
            self.latest_feedback_voltage = voltage_now
            self.latest_feedback_shift_mhz = shift_mhz
            shift_arr.append(shift_mhz)
            voltage_arr.append(voltage_now)

            while len(shift_arr) > self.max_history_points:
                shift_arr.pop(0)
            while len(voltage_arr) > self.max_history_points:
                voltage_arr.pop(0)

            if not self._sleep_with_stop_flag(self, 0.03):
                return
            now = time.monotonic()
            if now - last_emit >= self.emit_interval_s:
                kwargs["progress_callback"].emit([shift_arr, voltage_arr])
                last_emit = now

    def initialise_vector_feedback(self, *args, **kwargs):
        self._refresh_feedback_settings_from_ui()
        rf_inst = getattr(self.main_window.rfController, "inst", None)
        lia_daq = getattr(self.main_window.LIAController, "daq", None)
        lia_device = getattr(self.main_window.LIAController, "device", None)
        if rf_inst is None:
            raise RuntimeError("RF source is not connected. Connect RF before vector scan.")
        if lia_daq is None or lia_device is None:
            raise RuntimeError("LIA is not connected. Connect LIA before vector scan.")

        runtime_scale = float(
            getattr(self.main_window.LIAController, "scaling_Factor", None)
            or self.main_window.scalingFactorSpinBox.value()
            or 1.0
        )
        scale = runtime_scale if self.use_scaled_feedback_voltage else 1.0
        settle_time_s = max(
            0.03,
            min(
                0.3,
                3.0 * float(self.main_window.get_lia_time_constant_seconds()),
            ),
        )

        self.ini_freq = list(self.vector_freqs)
        ini_voltage = [None, None, None, None]
        demod_path = f"/{lia_device}/demods/0/sample"
        phase_adjust_done = False
        for i in range(len(self.vector_freqs)):
            if not self.scanning:
                return
            self._set_rf_frequency_ghz(rf_inst, self.vector_freqs[i])
            if not self._sleep_with_stop_flag(self, settle_time_s):
                return
            if (not phase_adjust_done) and i == 0:
                self._auto_zero_demod_phase()
                phase_adjust_done = True
            setpoint_samples = []
            setpoint_end = time.monotonic() + self.setpoint_duration_s
            while time.monotonic() < setpoint_end:
                if not self.scanning:
                    return
                sample = lia_daq.getSample(demod_path)
                x_val = float(sample["x"][0])
                y_val = float(sample["y"][0])
                if self.vector_feedback_demod_mode == "X":
                    setpoint_samples.append(x_val * float(scale))
                else:
                    setpoint_samples.append(float(np.hypot(x_val, y_val)) * float(scale))
                time.sleep(0.01)
            ini_voltage[i] = float(np.mean(setpoint_samples)) if setpoint_samples else 0.0

        df_arr = [[], [], [], []]
        dV_arr = [[], [], [], []]
        res_freq_arr = [[], [], [], []]
        self.feedback_started = True
        pid_integral = [0.0, 0.0, 0.0, 0.0]
        pid_prev_error = [None, None, None, None]
        pid_prev_time = [None, None, None, None]
        last_emit = 0.0
        while self.scanning:
            self._refresh_feedback_settings_from_ui()
            for i in range(len(self.vector_freqs)):
                if not self.scanning:
                    return
                self._set_rf_frequency_ghz(rf_inst, self.vector_freqs[i])
                if not self._sleep_with_stop_flag(self, settle_time_s):
                    return

                voltage_now = self._read_lia_voltage_average(
                    lia_daq, lia_device, scale, self.vector_feedback_demod_mode
                )
                self.dV = voltage_now - ini_voltage[i]
                gradient = float(self.vector_grads[i])
                if abs(gradient) < self.min_gradient_abs:
                    raise ValueError(
                        f"Gradient for resonance {i + 1} is too close to zero ({gradient})."
                    )

                error_mhz = (1.0 / gradient) * (-self.dV)
                if abs(self.dV) < self.deadband_voltage:
                    raw_df = 0.0
                    pid_prev_time[i] = None
                    pid_prev_error[i] = 0.0
                else:
                    if self.feedback_control_mode == "PID":
                        raw_df, _p_term, _i_term, _d_term = self._compute_pid_df(
                            error_mhz, i, pid_integral, pid_prev_error, pid_prev_time
                        )
                    else:
                        raw_df = error_mhz

                self.df = float(np.clip(raw_df, -self.max_df_step_mhz, self.max_df_step_mhz))
                candidate_freq = self.vector_freqs[i] + self.df / 1e3
                base_freq = self.ini_freq[i]
                min_freq = base_freq - (self.max_tracking_offset_mhz / 1e3)
                max_freq = base_freq + (self.max_tracking_offset_mhz / 1e3)
                self.vector_freqs[i] = float(np.clip(candidate_freq, min_freq, max_freq))

                if self.enable_baseline_adaptation and self.baseline_adapt_alpha > 0.0:
                    ini_voltage[i] = (
                        (1.0 - self.baseline_adapt_alpha) * ini_voltage[i]
                        + self.baseline_adapt_alpha * voltage_now
                    )

                df_arr[i].append(self.df)
                dV_arr[i].append(self.dV)
                res_freq_arr[i].append(self.vector_freqs[i])
                while len(df_arr[i]) > self.max_history_points:
                    df_arr[i].pop(0)
                while len(dV_arr[i]) > self.max_history_points:
                    dV_arr[i].pop(0)
                while len(res_freq_arr[i]) > self.max_history_points:
                    res_freq_arr[i].pop(0)

            if not self._sleep_with_stop_flag(self, 0.03):
                return
            now = time.monotonic()
            if now - last_emit >= self.emit_interval_s:
                shift_mhz_arr = [
                    [(freq - self.ini_freq[i]) * 1e3 for freq in res_freq_arr[i]]
                    for i in range(4)
                ]
                kwargs["progress_callback"].emit([shift_mhz_arr, dV_arr])
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

        j = 0
        totalSize = len(x_positions) * len(y_positions)
        total_pixels = int(totalSize)
        for row_index, y_position in enumerate(y_positions):
            # Serpentine: reverse x direction on odd rows
            if self.serpentine and row_index % 2 == 1:
                row_x = list(reversed(x_positions))
            else:
                row_x = list(x_positions)
            i_start = 0 if (self.serpentine and row_index % 2 == 1) else len(x_positions) - 1
            i_step = 1 if (self.serpentine and row_index % 2 == 1) else -1
            i = i_start
            for col_index, x_position in enumerate(row_x):
                timeStart = time.time()
                ts = time.time()
                totalSize -= 1
                require_full_wait = col_index == 0
                if not self._move_stage_to_measurement_point(
                    x_position, y_position, require_full_wait=require_full_wait
                ):
                    return
                if scan_time > 0 and not self._sleep_with_stop_flag(self, scan_time):
                    return
                if self.feedback:
                    self.df_arr[0, j, i] = (
                        self.latest_feedback_shift_mhz
                        if self.latest_feedback_shift_mhz is not None
                        else (float(self.res_freq) - float(self.scalar_ini_freq)) * 1e3
                    )
                    self.voltageArr[0, j, i] = (
                        self.latest_feedback_voltage
                        if self.latest_feedback_voltage is not None
                        else 0.0
                    )
                else:
                    if self.scan_averaging:
                        stream = self.main_window.LIAController.daq.poll(self.avg_time, 200, 1, True)
                        sample_path = f"/{self.main_window.LIAController.device}/demods/0/sample"
                        self.voltageArr[0, j, i] = np.mean(stream[sample_path]["x"])
                        self.voltageArrSTD[0, j, i] = np.std(stream[sample_path]["x"])
                    else:
                        sample = self.main_window.LIAController.daq.getSample(
                            "/%s/demods/0/sample" % self.main_window.LIAController.device
                        )
                        self.voltageArr[0, j, i] = float(sample["x"][0])
                self.completed_pixels += 1
                now_emit = time.monotonic()
                if now_emit - last_emit >= 0.1:
                    payload = {
                        "image": self.df_arr if self.feedback else self.voltageArr,
                        "completed": self.completed_pixels,
                        "total": total_pixels,
                        "elapsed_s": now_emit - (self.scan_start_time_monotonic or now_emit),
                    }
                    kwargs["progress_callback"].emit(payload)
                    last_emit = now_emit
                i += i_step
                te = time.time()
                eta = (te - ts) * totalSize
                print(time.ctime(int(timeStart + eta)))
                if self.scanning is False:
                    return
            j += 1
        kwargs["progress_callback"].emit(
            {
                "image": self.df_arr if self.feedback else self.voltageArr,
                "completed": total_pixels,
                "total": total_pixels,
                "elapsed_s": time.monotonic() - (self.scan_start_time_monotonic or time.monotonic()),
            }
        )
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
        field_model = getattr(self.main_window, "odmr_fit_model", None) or self.field_model
        A_pinv = None if field_model is not None else np.linalg.pinv(np.array(self.main_window.a_matrix_values))
        totalSize = len(x_positions) * len(y_positions)
        total_pixels = int(totalSize)
        last_emit = 0.0
        for row_index, y_position in enumerate(y_positions):
            # Serpentine: reverse x direction on odd rows
            if self.serpentine and row_index % 2 == 1:
                row_x = list(reversed(x_positions))
            else:
                row_x = list(x_positions)
            i_start = 0 if (self.serpentine and row_index % 2 == 1) else len(x_positions) - 1
            i_step = 1 if (self.serpentine and row_index % 2 == 1) else -1
            i = i_start
            for col_index, x_position in enumerate(row_x):
                timeStart = time.time()
                ts = time.time()
                totalSize -= 1
                require_full_wait = col_index == 0
                if not self._move_stage_to_measurement_point(
                    x_position, y_position, require_full_wait=require_full_wait
                ):
                    return
                if scan_time > 0 and not self._sleep_with_stop_flag(self, scan_time):
                    return
                for k in range(4):
                    self.df_arr[k, j, i] = self.vector_freqs[k]
                if field_model is not None:
                    B = np.asarray(
                        field_model.shift_to_field(
                            np.asarray(self.vector_freqs, dtype=float),
                            reference_frequencies=np.asarray(self.ini_freq, dtype=float),
                        ),
                        dtype=float,
                    ).reshape(-1)
                    for k in range(min(3, len(B))):
                        self.b_arr[k, j, i] = B[k]
                else:
                    df1, df2, df3, df4 = (np.array(self.vector_freqs) - np.array(self.ini_freq)) * 1000
                    freq_col = [[df1], [df2], [df3], [df4]]
                    B = np.dot(A_pinv, freq_col)
                    for k in range(3):
                        self.b_arr[k, j, i] = B[k][0]
                now = time.monotonic()
                self.completed_pixels += 1
                if now - last_emit >= 0.1:
                    kwargs["progress_callback"].emit(
                        {
                            "image": self.b_arr,
                            "completed": self.completed_pixels,
                            "total": total_pixels,
                            "elapsed_s": now - (self.scan_start_time_monotonic or now),
                        }
                    )
                    last_emit = now
                i += i_step
                te = time.time()
                eta = (te - ts) * totalSize
                print(time.ctime(int(timeStart + eta)))
                if self.scanning is False:
                    return
            j += 1
        kwargs["progress_callback"].emit(
            {
                "image": self.b_arr,
                "completed": total_pixels,
                "total": total_pixels,
                "elapsed_s": time.monotonic() - (self.scan_start_time_monotonic or time.monotonic()),
            }
        )
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

    def _maybe_blur(self, data_2d):
        """Return data_2d with optional Gaussian blur applied."""
        if self.gaussianBlurCheck.isChecked():
            sigma = float(self.gaussianSigmaSpinBox.value())
            return gaussian_filter(data_2d.astype(float), sigma=sigma)
        return data_2d

    def _on_blur_setting_changed(self, *_):
        """Enable/disable the sigma box and re-render the last frame immediately."""
        self.gaussianSigmaSpinBox.setEnabled(self.gaussianBlurCheck.isChecked())
        if self._last_plot_arr is not None:
            self.update_plot(self._last_plot_arr)

    @staticmethod
    def _apply_image(image_view, data, levels):
        image_view.setImage(data, levels=levels, autoHistogramRange=False)
        image_view.ui.histogram.setLevels(*levels)

    def update_plot(self, image_arr):
        completed = None
        total = None
        elapsed_s = None
        if isinstance(image_arr, dict):
            completed = image_arr.get("completed")
            total = image_arr.get("total")
            elapsed_s = image_arr.get("elapsed_s")
            image_arr = image_arr.get("image")

        if image_arr is None:
            return

        self._last_plot_arr = image_arr
        if self.vector:
            levels0 = self.calculate_levels(image_arr[0])
            levels1 = self.calculate_levels(image_arr[1])
            levels2 = self.calculate_levels(image_arr[2])
            self._apply_image(self.imageWidget_2, self._maybe_blur(image_arr[0]), levels0)
            self._apply_image(self.imageWidget_3, self._maybe_blur(image_arr[1]), levels1)
            self._apply_image(self.imageWidget_4, self._maybe_blur(image_arr[2]), levels2)
        else:
            levels = self.calculate_levels(image_arr)
            self._apply_image(self.imageWidget, self._maybe_blur(image_arr), levels)

        if completed is not None and total is not None and elapsed_s is not None:
            self._update_eta_label(completed, total, elapsed_s)

    def debug_plot(self, arrs):
        if self.vector:
            self.vc1.setData(arrs[0][0], pen=get_plot_pen(0))
            self.vc2.setData(arrs[0][1], pen=get_plot_pen(1))
            self.vc3.setData(arrs[0][2], pen=get_plot_pen(2))
            self.vc4.setData(arrs[0][3], pen=get_plot_pen(3))

            self.fc1.setData(arrs[1][0], pen=get_plot_pen(0))
            self.fc2.setData(arrs[1][1], pen=get_plot_pen(1))
            self.fc3.setData(arrs[1][2], pen=get_plot_pen(2))
            self.fc4.setData(arrs[1][3], pen=get_plot_pen(3))
        else:
            self.vc1.setData(arrs[0], pen=get_plot_pen(0))
            self.vc2.setData([])
            self.vc3.setData([])
            self.vc4.setData([])

            self.fc1.setData(arrs[1], pen=get_plot_pen(0))
            self.fc2.setData([])
            self.fc3.setData([])
            self.fc4.setData([])

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

    def stop_scan(self):
        self.scanning = False
        self.scanEtaLabel.setText("ETA: stopped")

    def closeEvent(self, event):
        self.scanning = False
