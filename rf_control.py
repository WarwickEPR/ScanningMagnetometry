# -*- coding: utf-8 -*-
"""RF (Microwave Source) control module for the Scanning Magnetometer.

Handles all communication with the Keysight Signal Generator via PyVISA.
Controls frequency, power, and modulation settings.
"""

import time
import numpy as np
import pyvisa
from threading_utils import ThreadedComponent


class RfControl(ThreadedComponent):
    """Controls the connection to the RF Source via PyVISA.
    
    Works using a PyVISA connection to the Keysight Signal Generator.
    Has functions for changing output frequency/power & modulation settings.

    Attributes:
        mw_power_on: (bool) Checks if the output is on or off for the RF source
        mod_on: (bool) Checks if modulation is applied to the output signal
        rf_connected: (bool) Check if a successful connection has been made to the signal generator
        inst: PyVISA instrument instance for the RF generator
        num_points: Number of frequency points in a sweep
        start_freq: Start frequency for sweep
        stop_freq: Stop frequency for sweep
        samples: Data samples collected during sweep
    """

    def __init__(self, window):
        super(RfControl, self).__init__()
        self.window = window
        self.num_points = None
        self.stop_freq = None
        self.start_freq = None
        self.frequency_axis = None
        self.sweep_mode = None
        self.sweep_step_khz = None
        self.worker_running = None
        self.samples = None
        self.mw_power_on = False
        self.mod_on = False
        self.rf_connected = False
        self.inst = None
        self.rm = None
        self.sweeping = False

    @staticmethod
    def create_resource_manager():
        last_error = None
        for backend in (None, "@py"):
            try:
                if backend is None:
                    return pyvisa.ResourceManager()
                return pyvisa.ResourceManager(backend)
            except Exception as error:
                last_error = error
        raise last_error

    @staticmethod
    def _estimate_points_from_step(start_ghz, stop_ghz, step_khz):
        step_ghz = abs(float(step_khz)) / 1e6
        if step_ghz <= 0:
            return 2
        span_ghz = abs(float(stop_ghz) - float(start_ghz))
        return max(2, int(np.floor(span_ghz / step_ghz)) + 1)

    def _refresh_effective_sweep_axis(self):
        """Build the best-known frequency axis (GHz) for plotting ODMR data."""
        if self.start_freq is None or self.stop_freq is None or self.num_points is None:
            self.frequency_axis = None
            return
        points = max(2, int(self.num_points))
        self.frequency_axis = np.linspace(float(self.start_freq), float(self.stop_freq), points)

    def _query_instrument_sweep_points(self):
        """Query instrument for effective sweep point count, if supported."""
        try:
            reported = self.inst.query(':SWE:POINTS?')
            value = int(round(float(str(reported).strip())))
            if value >= 2:
                return value
        except Exception:
            pass
        return None

    def connect_rf(self, *args, **kwargs):
        """Connect to the RF source via network address.

        :param args: Contains the IP address string from the UI
        :param kwargs: Additional keyword arguments
        :return:
        """
        ip_address = args[0][0]
        self.rm = self.create_resource_manager()
        ip_address = "TCPIP::" + ip_address + "::INSTR"
        self.inst = self.rm.open_resource(ip_address,
                                          query_delay=0.1,
                                          timeout=0.1,
                                          send_end=True)
        self.inst.chunk_size = 102400
        self.inst.write("*CLS")  # clear error bank
        self.inst.baud_rate = 115200

        # Update UI with current status
        self.window.powerLabel.setText(str(round(float(self.inst.query('POW?')), 3)))
        self.window.currentFreqLabel.setText(str(round(float(self.get_freq()) / 1e9, 3)))
        mod_freq, mod_amp = self.get_mod_params()
        self.window.modAmpLabel.setText(str(round(float(mod_amp) / 1e6, 3)))
        self.window.modFreqLabel.setText(str(round(float(mod_freq) / 1e3, 3)))

        # Get current power state and set UI button to appropriate state
        power = int(self.inst.query("OUTP?"))
        if power == 0:
            self.mw_power_on = False
            self.window.togglePwrChk.setChecked(False)
        elif power == 1:
            self.mw_power_on = True
            self.window.togglePwrChk.setChecked(True)
        
        time.sleep(0.05)
        
        # Set frequency modulation on by default
        time.sleep(0.05)
        self.inst.write('FM:STAT ON')
        time.sleep(0.05)
        self.inst.write('OUTP:MOD:STAT ON')
        time.sleep(0.05)
        self.inst.write('LFO:STAT ON')
        time.sleep(0.05)
        self.window.toggleModOnOff.setChecked(True)
        self.rf_connected = True
        return

    def power_on_off(self, state):
        """Toggle RF output power on/off.

        :param state: (bool) True to turn on, False to turn off
        :return:
        """
        if state:
            self.inst.write('OUTP ON')
            self.mw_power_on = True
        elif not state:
            self.inst.write('OUTP OFF')
            self.mw_power_on = False
        return

    def set_freq(self):
        """Set the RF output frequency from UI value."""
        self.inst.write('FREQ ' + str(round(float(self.window.freqBox.value()) * 1e9, 12)))
        self.window.currentFreqLabel.setText(str(round(float(self.get_freq()) / 1e9, 3)))

    def get_freq(self):
        """Get the current RF output frequency.
        
        :return: Current frequency in Hz
        """
        return self.inst.query("FREQ?")

    def set_power(self):
        """Set the RF output power from UI value."""
        self.inst.write(f'POW {float(self.window.pwrBox.value())} dBm')
        curr_p = round(float(self.inst.query('POW?')), 3)
        self.window.powerLabel.setText(str(curr_p))

    def mod_on_off(self, state):
        """Toggle frequency modulation on/off.

        :param state: (bool) True to enable, False to disable
        :return:
        """
        if state:
            self.mod_on = True
            self.inst.write('FM:STAT ON')
            self.inst.write('OUTP:MOD:STAT ON')
        elif not state:
            self.mod_on = False
            self.inst.write('FM:STAT OFF')
            self.inst.write('OUTP:MOD:STAT OFF')
        return

    def set_mod_params(self):
        """Set modulation frequency and amplitude from UI values."""
        self.inst.write(f'FM {float(self.window.modAmpSpinBox.value())} MHz')
        self.inst.write(f'FM:INT:FREQ {float(self.window.modFreqSpinBox.value())} kHz')
        mod_freq, mod_amp = self.get_mod_params()
        self.window.modAmpLabel.setText(str(round(float(mod_amp) / 1e6, 3)))
        self.window.modFreqLabel.setText(str(round(float(mod_freq) / 1e3, 3)))
        return

    def get_mod_params(self):
        """Get current modulation frequency and amplitude settings.
        
        :return: Tuple of (mod_freq, mod_amp)
        """
        return self.inst.query('FM:INT:FREQ?'), self.inst.query('FM?')

    def change_mod_type(self):
        """Toggle modulation type between sine and square wave."""
        if self.window.squareWaveRadio.isChecked():
            self.inst.write(':FM:INT:FUNC SQU')  # set square wave FM
        elif self.window.sineWaveRadio.isChecked():
            self.inst.write(':FM:INT:FUNC SIN')  # set sine wave FM

    def ext_mod_on_off(self, state):
        """Toggle between internal and external frequency modulation.

        :param state: (bool) True for external modulation, False for internal
        :return:
        """
        if state:
            self.inst.write(':FM:SOUR EXT')
        elif not state:
            self.inst.write(':FM:SOUR INT')
        return

    def setup_sweep(self, *args, **kwargs):
        """Set parameters for ODMR sweep on both RF source and LIA.
        
        Parameters are set using the UI elements.

        :param args: Contains float values from UI elements
        :param kwargs: Contains progress callback function
        :return:
        """
        self.worker_running = True
        self.window.LIAController.odmr_sweep = True
        self.sweeping = True
        self.start_freq = float(args[0][0])  # Start frequency in GHz
        self.stop_freq = float(args[0][1])   # Stop frequency in GHz
        self.num_points = int(args[0][2])  # Number of frequency points
        dwell_time = args[0][3] / 1000
        sweep_step = float(args[0][4])
        self.sweep_step_khz = sweep_step
        self.sweep_mode = self.window.sweepDefBox.currentText()

        # Set RF source parameters
        self.inst.write(':INIT:CONT OFF')
        self.inst.write(':TRIG:SEQ:SOUR BUS')
        self.inst.write('ROUT:CONN:TRIG1:OUTP SRun')
        self.inst.write('ROUT:CONN:TRIG2:OUTP SETT')
        self.inst.write(':SOURce:FREQuency:MODE LIST')
        self.inst.write(f':SWE:DWELL {dwell_time}')
        
        if self.sweep_mode == 'Points':
            self.inst.write(f':SWE:POINTS {self.num_points}')
        elif self.sweep_mode == 'Step Size':
            self.inst.write(f':SWE:STEP {sweep_step} kHz')
            self.num_points = self._estimate_points_from_step(
                self.start_freq,
                self.stop_freq,
                sweep_step,
            )
        
        self.inst.write(f':SOURce:FREQuency:STARt {self.start_freq} GHz')
        self.inst.write(f':SOURce:FREQuency:STOP {self.stop_freq} GHz')
        self.inst.write('TSWeep')

        # Prefer instrument-reported effective points to keep axis exactly aligned.
        reported_points = self._query_instrument_sweep_points()
        if reported_points is not None:
            self.num_points = reported_points

        self._refresh_effective_sweep_axis()
        
        # Setup LIA for data acquisition
        self.window.LIAController.setup_sweep()
        self.window.LIAController.daq_module.execute()

        # Record data in a loop
        self.samples = []
        i = 0
        j = 0
        last_emit = 0.0
        emit_interval = 0.05
        self.inst.write('*TRG')  # trigger sweep to start
        
        while self.sweeping:
            data_read = self.window.LIAController.daq_module.read(True)
            returned_signal_paths = [signal_path.lower() for signal_path in data_read.keys()]
            got_new_samples = False
            
            for signal_path in self.window.LIAController.signal_paths:
                if signal_path.lower() in returned_signal_paths:
                    for index, signal_burst in enumerate(data_read[signal_path.lower()]):
                        i += 1
                        self.samples.append(np.mean(signal_burst['value'][0]))
                        self.window.LIAController.data[signal_path].append(signal_burst)
                        got_new_samples = True
                else:
                    j += 1

            now = time.monotonic()
            if got_new_samples and now - last_emit >= emit_interval:
                kwargs['progress_callback'].emit(self.samples)
                last_emit = now
            elif not got_new_samples:
                time.sleep(0.01)

            if (int(self.inst.query(':STATus:OPERation:CONDition?')) & 8) == 8:
                pass
            else:
                if self.window.odmrSweepContinous.isChecked():
                    self.window.LIAController.daq_module.unsubscribe('*')
                    self.inst.write('TSWeep')
                    self.window.LIAController.setup_sweep()
                    self.samples = []
                    self.window.LIAController.daq_module.execute()
                    self.inst.write('*TRG')
                else:
                    # Drain any remaining bursts before finishing so final points are not lost.
                    tail_read = self.window.LIAController.daq_module.read(True)
                    tail_paths = [signal_path.lower() for signal_path in tail_read.keys()]
                    for signal_path in self.window.LIAController.signal_paths:
                        if signal_path.lower() in tail_paths:
                            for signal_burst in tail_read[signal_path.lower()]:
                                self.samples.append(np.mean(signal_burst['value'][0]))
                                self.window.LIAController.data[signal_path].append(signal_burst)
                    kwargs['progress_callback'].emit(self.samples)
                    self.window.LIAController.daq_module.finish()
                    self.sweeping = False

        # Cleanup after sweep
        self.window.LIAController.daq_module.unsubscribe('*')
        self.window.LIAController.odmr_sweep = False
        return
