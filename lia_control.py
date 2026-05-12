# -*- coding: utf-8 -*-
"""Lock-In Amplifier (LIA) control module for the Scanning Magnetometer.

Handles all communication with the Zurich Lock-In Amplifier via the Python API.
Manages data acquisition for both ODMR sweeps and FFT measurements.
"""

import numpy as np
import zhinst.utils
from threading_utils import ThreadedComponent


class LIAControl(ThreadedComponent):
    """Control connection to the Zurich Lock-In Amplifier.
    
    Contains functions to measure inputs/outputs and set various parameters.
    Also contains functions to setup different data acquisition modules for
    ODMR sweeps and FFT measurements.

    Attributes:
        LIA_connected: (bool) Zurich LIA connection state
        odmr_sweep: (bool) Is an ODMR sweep currently happening?
        fft_sweep: (bool) Is an FFT sweep/acquisition currently happening?
        daq: API session with the LIA
        device: Device identifier string
        daq_module: Data acquisition module instance
        data: Dictionary storing acquired data
        signal_paths: List of signal paths to subscribe to
        clockbase: Clock base frequency of the LIA
    """

    def __init__(self, window):
        super(LIAControl, self).__init__()
        self.window = window
        self.data = None
        self.clockbase = None
        self.device_id = None
        self.server_host = None
        self.scaling_Factor = None
        self.LIA_connected = False
        self.odmr_sweep = False
        self.fft_sweep = False
        self.daq = None
        self.device = None
        self.daq_module = None
        self.signal_paths = None
        return

    @staticmethod
    def _normalize_device_id(device_id):
        """Normalize user-entered Zurich device IDs to LabOne format (e.g. dev4521)."""
        value = str(device_id).strip().lower().replace(" ", "")
        if value.startswith("device"):
            value = "dev" + value[6:]
        elif value.isdigit():
            value = "dev" + value
        if not value.startswith("dev") or not value[3:].isdigit():
            raise ValueError(
                f"Invalid LIA device ID '{device_id}'. Expected format like 'dev4521'."
            )
        return value

    def connect_lia(self, *args, **kwargs):
        """Connect to the Zurich Lock-In Amplifier.

        :param args: Contains UI element strings (device_ip, device_id, etc)
        :param kwargs: Additional keyword arguments
        :return:
        """
        try:
            self.server_host = args[1]['device_ip']
            self.device_id = self._normalize_device_id(args[1]['device_id'])
            server_port = 8004
            api_level = 6  # API detail level
            
            (self.daq, self.device, _) = zhinst.utils.create_api_session(
                self.device_id, api_level, server_host=self.server_host, server_port=server_port
            )
            zhinst.utils.api_server_version_check(self.daq)
            self.daq.set(f"/{self.device}/demods/0/enable", 1)  # enable demodulation
            self.clockbase = float(self.daq.getInt(f"/{self.device}/clockbase"))
            self.LIA_connected = True
            self.apply_runtime_settings()
        except Exception as e:
            self.LIA_connected = False
            raise ConnectionError(
                f"Couldn't connect to LIA at {self.server_host}:8004 using device ID '{self.device_id}'. "
                f"Check LabOne is reachable at the given IP and use ID format like 'dev4521'. "
                f"Original error: {e}"
            )

    def apply_runtime_settings(self, *args, **kwargs):
        """Apply current UI LIA settings to hardware immediately."""
        if not self.LIA_connected or self.daq is None or self.device is None:
            return

        try:
            range_text = str(self.window.rangeSelect.currentText()).strip()
            if range_text:
                v_range = float(range_text)
            else:
                v_range = float(self.window.rangeSelect.currentIndex())

            order_text = str(self.window.harmonicOrderSelect.currentText()).strip()
            if order_text and order_text.replace('.', '', 1).isdigit():
                filter_order = int(float(order_text))
            else:
                filter_order = int(self.window.harmonicOrderSelect.currentIndex()) + 1
            filter_order = max(1, filter_order)

            time_constant = float(self.window.get_lia_time_constant_seconds())
            imp_fifty = int(self.window.fiftyOhmCheck.isChecked())
            ac_coupled = int(self.window.acCoupleCheck.isChecked())
            scaling = float(self.window.scalingFactorSpinBox.value())

            self.daq.setInt(f"/{self.device}/sigins/0/imp50", imp_fifty)
            self.daq.setInt(f"/{self.device}/sigins/0/ac", ac_coupled)
            self.daq.setDouble(f"/{self.device}/sigins/0/range", v_range)
            self.daq.setInt(f"/{self.device}/demods/0/order", filter_order)
            self.daq.setDouble(f"/{self.device}/demods/0/timeconstant", time_constant)
            self.daq.setDouble(f"/{self.device}/auxouts/0/scale", scaling)
            self.daq.set(f"/{self.device}/demods/0/enable", 1)
            self.scaling_Factor = scaling
        except Exception as error:
            raise RuntimeError(f"Failed to apply LIA runtime settings: {error}")

    def setup_sweep(self):
        """Set parameters and arm data acquisition module for ODMR sweep.

        Configures the LIA to receive triggered data acquisitions synchronized
        with the RF source sweep.

        :return:
        """
        self.demod_path = f"/{self.device}/demods/0/sample"
        self.signal_paths = []
        self.signal_paths.append(self.demod_path + ".x")
        
        # Get sweep parameters from UI
        self.total_duration = self.window.odmrAqDurBox.value()
        self.module_sampling_rate = self.window.odmrAqSampleRateBox.value()
        self.burst_duration = self.window.odmrAqBurstDurBox.value()
        self.num_cols = int(np.ceil(self.module_sampling_rate * self.burst_duration))
        self.num_bursts = int(np.ceil(self.total_duration / self.burst_duration))
        
        self.daq.sync()
        
        # Create data acquisition module
        self.daq_module = self.daq.dataAcquisitionModule()
        self.daq_module.set("device", self.device)

        # Configure for triggered acquisition
        trigger = True
        if trigger:
            self.daq_module.set("grid/mode", 4)
            self.daq_module.set('type', 6)
            self.daq_module.set('triggernode', self.demod_path + '.TrigIn1')
            self.daq_module.set("duration", self.burst_duration)
            self.daq_module.set('edge', 0)
            effective_count = int(
                getattr(self.window.rfController, "num_points", self.window.pointsBox.value())
            )
            self.daq_module.set("count", max(1, effective_count))
            self.daq_module.set("grid/cols", max(1, self.num_cols))
            self.daq_module.set('holdoff/time', 0.001)
            self.daq_module.set('delay', 0)
            self.daq_module.set('endless', 0)
            self.daq.setInt("/%s/sigins/0/imp50" % self.device, int(self.window.fiftyOhmCheck.isChecked()))
            self.daq.setInt("/%s/sigins/0/ac" % self.device, int(self.window.acCoupleCheck.isChecked()))
            self.daq.setInt('/%s/demods/0/order' % self.device, 
                                    (int(self.window.harmonicOrderSelect.currentIndex()) + 1))
            self.daq.setDouble('/%s/demods/0/timeconstant' % self.device, 
                                        float(self.window.get_lia_time_constant_seconds()))
        else:
            self.daq_module.set("grid/mode", 2)
            self.daq_module.set("type", 0)
            self.daq_module.set("count", self.num_bursts)
            self.daq_module.set("duration", self.burst_duration)
            self.daq_module.set("grid/cols", self.num_cols)

        self.data = {}
        for signal_path in self.signal_paths:
            print("Subscribing to ", signal_path)
            self.daq_module.subscribe(signal_path)
            self.data[signal_path] = []
        return

    def setup_fft(self):
        """Set parameters and arm data acquisition module for FFT measurement.

        Configures the LIA for continuous FFT acquisition for sensitivity measurements.

        :return:
        """
        self.scaling_Factor = int(self.window.scalingFactorSpinBox.value())
        demod_select = 0
        v_range = int(self.window.rangeSelect.currentText())
        imp_fifty = int(self.window.fiftyOhmCheck.isChecked())
        ac_coupled = int(self.window.acCoupleCheck.isChecked())
        in_channel = 0
        demod_index = 1
        filter_order = int(self.window.harmonicOrderSelect.currentText())
        time_constant = float(self.window.get_lia_time_constant_seconds())

        # Configure signal inputs
        exp_setting = [
            ["/%s/sigins/%d/ac" % (self.device, in_channel), ac_coupled],
            ["/%s/sigins/%d/imp50" % (self.device, in_channel), imp_fifty],
            ["/%s/sigins/%d/range" % (self.device, in_channel), v_range],
            ["/%s/demods/%d/enable" % (self.device, demod_index), 1],
            ["/%s/demods/%d/adcselect" % (self.device, 0), 0],
            ["/%s/demods/%d/adcselect" % (self.device, 1), 8],
            ["/%s/demods/%d/timeconstant" % (self.device, demod_index), time_constant],
            ["/%s/demods/%d/harmonic" % (self.device, demod_index), 1],
            ["/%s/extrefs/%d/enable" % (self.device, in_channel), 1],
            ["/%s/auxouts/%d/outputselect" % (self.device, 0), demod_select],
        ]
        self.daq.set(exp_setting)
        self.daq.set(f"/{self.device}/demods/0/enable", 1)
        self.daq.set(f"/{self.device}/demods/1/enable", 1)
        self.daq.set("/%s/demods/%d/harmonic" % (self.device, demod_index), 1)
        self.daq.set("/%s/auxouts/%d/scale" % (self.device, 0), self.scaling_Factor)
        self.daq.set("/%s/demods/%d/order" % (self.device, demod_index), filter_order)

        demod_path = f"/{self.device}/demods/0/sample"
        self.signal_paths = []
        self.signal_paths.append(demod_path + ".x.fft.abs.avg")

        self.count = int(self.window.fftAverageSpinBox.value())
        self.fft_duration = int(self.window.fftDurationSpinBox.value())
        cols = int(self.window.sampleRateSpinBox.value())

        # Create and configure data acquisition module
        self.daq_module = self.daq.dataAcquisitionModule()
        self.daq_module.set("device", self.device)
        self.daq_module.set("type", 0)  # Continuous acquisition
        self.daq_module.set("grid/mode", 2)
        self.daq_module.set("count", self.count)
        self.daq_module.set("duration", self.fft_duration)
        self.daq_module.set("grid/cols", cols)

        self.data = {}
        for signal_path in self.signal_paths:
            print("Subscribing to ", signal_path)
            self.daq_module.subscribe(signal_path)
            self.data[signal_path] = []
        return
    
    def set_reference_input_type(self, *args, **kwargs):
        """Set the reference input type for the LIA.

        :param input_type: (str) Type of reference input (e.g. "internal", "external")
        :return:
        """
        if not self.LIA_connected or self.daq is None or self.device is None:
            return

        try:
            # ThreadedComponent passes wrapped args as (args_tuple, kwargs_dict).
            if len(args) >= 1 and isinstance(args[0], tuple):
                input_type = args[0][0]
            elif len(args) >= 1:
                input_type = args[0]
            else:
                input_type = kwargs.get("input_type")

            if input_type is None:
                raise ValueError("Reference input type was not provided")

            input_type = str(input_type).strip().lower()
            if input_type == "internal":
                self.daq.setInt(f"/{self.device}/extrefs/0/enable", 0)
            elif input_type == "external":
                self.daq.setInt(f"/{self.device}/extrefs/0/enable", 1)
            else:
                raise ValueError(f"Invalid reference input type: {input_type}")
        except Exception as error:
            raise RuntimeError(f"Failed to set reference input type: {error}")
        
    def set_external_reference_signal_path(self, *args, **kwargs):
        """Set the external reference input signal for the LIA. Can choose from signal inputs, aux inputs, triggers etc. 
        :param signal_path: (integer) The signal path related integer, check Zurich LIA docs for correct values. 
                                        For example, 0-7 for signal inputs, 8-15 for aux inputs, etc.
        :return:
        """
        if not self.LIA_connected or self.daq is None or self.device is None:
            return
        
        try:
            # ThreadedComponent passes wrapped args as (args_tuple, kwargs_dict).
            if len(args) >= 1 and isinstance(args[0], tuple):
                signal_path_integer = args[0][0]
            elif len(args) >= 1:
                signal_path_integer = args[0]
            else:
                signal_path_integer = kwargs.get("signal_path_integer")

            if signal_path_integer is None:
                raise ValueError("External reference signal path was not provided")

            signal_path_integer = int(signal_path_integer)
            if signal_path_integer < 0:
                raise ValueError(f"Signal path integer must be non-negative. Got: {signal_path_integer}")
            else:
                self.daq.setInt(f"/{self.device}/demods/1/adcselect", signal_path_integer)
        except Exception as error:
            raise RuntimeError(f"Failed to set external reference signal path: {error}")
