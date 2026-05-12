# -*- coding: utf-8 -*-
"""Stage control module for the Scanning Magnetometer.

Handles all communication and control of the motorized XYZ stage via serial connection.
Uses G-code commands to control movement.
"""

from PyQt6 import QtWidgets
import serial
import re
import time


class StageControl:
    """Controls the connection to the stage and contains the functions to operate it.
    
    Includes read and send g-code functionality for stage movement and positioning.

    Attributes:
        ser: Serial connection instance
        stage_connected: Boolean to check if a successful stage connection has been made
        stage_options: Window instance for stage configuration
    """

    def __init__(self, window, stage_options_cls):
        super(StageControl, self).__init__()
        self.window = window
        self.stage_options_cls = stage_options_cls
        self.stage_options = None
        self.ser = None
        self.stage_connected = False
        return

    def execute_gcode(self, command):
        """Send a g-code command to the stage without expecting a response.

        :param command: The G-code to send to the printer e.g. G28
        :return:
        """
        try:
            self.ser.write(f'{command}\r\n'.encode())
        except:
            self.show_error_message("ERROR: Could not execute stage command")

    @staticmethod
    def _parse_position_from_response(decoded_response):
        x_match = re.search(r"X:([-+]?\d*\.?\d+)", decoded_response)
        y_match = re.search(r"Y:([-+]?\d*\.?\d+)", decoded_response)
        z_match = re.search(r"Z:([-+]?\d*\.?\d+)", decoded_response)
        if x_match and y_match and z_match:
            return float(x_match.group(1)), float(y_match.group(1)), float(z_match.group(1))

        # Fallback for non-standard tokenized formats.
        tokens = decoded_response.split()
        if len(tokens) >= 3:
            try:
                return float(tokens[0]), float(tokens[1]), float(tokens[2])
            except Exception:
                pass
        return None

    def get_stage_position_tuple(self):
        response = self.read_gcode('M114')
        if not response:
            return None
        decoded = response.decode("utf-8", errors="ignore").strip()
        return self._parse_position_from_response(decoded)

    def move_stage_pos_wait(
        self,
        x,
        y,
        tolerance_mm=0.02,
        speed_mm_s=5.0,
        timeout_s=None,
        poll_s=0.05,
    ):
        """Move stage in XY and wait until position reaches target within tolerance.

        If no explicit timeout is provided, compute a dynamic timeout from travel distance
        and a conservative default speed.
        """
        start_pos = self.get_stage_position_tuple()
        self.set_stage_pos(x, y)

        if timeout_s is None:
            if start_pos is not None:
                distance_mm = ((float(x) - start_pos[0]) ** 2 + (float(y) - start_pos[1]) ** 2) ** 0.5
                timeout_s = max(0.5, (distance_mm / max(1e-6, float(speed_mm_s))) + 1.0)
            else:
                timeout_s = 5.0

        end_t = time.monotonic() + max(0.1, float(timeout_s))
        while time.monotonic() < end_t:
            pos = self.get_stage_position_tuple()
            if pos is not None:
                dx = abs(pos[0] - float(x))
                dy = abs(pos[1] - float(y))
                if dx <= float(tolerance_mm) and dy <= float(tolerance_mm):
                    return True
            time.sleep(max(0.01, float(poll_s)))
        return False

    def read_gcode(self, command):
        """Send a g-code command to the stage and read the response.
        
        Use this for queries where a response is expected.

        :param command: The G-code to send (e.g. M114 for position query)
        :return: The response from the stage
        """
        response = b""
        try:
            self.ser.write(f'{command}\r\n'.encode())
            response = self.ser.readline()
            self.ser.readline()  # clears next line

        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(self.window)
            error_dialog.showMessage(str(error))
        return response

    def connect_stage(self, com_port, baud_rate=115200):
        """Connect to the stage via serial port.

        :param com_port: (str) the com port to connect to i.e "COM4"
        :param baud_rate: (int) the baud rate (or bit rate) of the stage
        :return:
        """
        try:
            self.ser = serial.Serial(
                port=com_port,
                baudrate=baud_rate,
                timeout=0.5,
                write_timeout=0.5,
            )
            self.stage_connected = True
            return True
        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(self.window)
            error_dialog.showMessage(str(error))
            self.stage_connected = False
            return False

    def home_stage(self):
        """Start the stage homing process.
        
        Important to do this before starting a scan so x, y and z positions are correct
        and don't cause stage crashes.

        :return:
        """
        self.execute_gcode('G28')  # home gcode
        return

    def set_stage_pos(self, x, y):
        """Move the stage in the xy plane.

        :param x: (float) desired x position in mm
        :param y: (float) desired y position in mm
        :return:
        """
        self.execute_gcode(f'G00 X{x} Y{y}')
        return

    def set_stage_height(self, z):
        """Move the stage up and down (z-axis).

        :param z: (float) desired z position or "height" in mm
        :return:
        """
        self.execute_gcode(f'G00 Z{z}')
        return

    def get_stage_pos(self):
        """Query the stage to get current x, y, and z coordinates.
        
        Note: May return inaccurate values if stage is not homed first.

        :return:
        """
        try:
            pos = self.get_stage_position_tuple()
            if pos is None:
                raise RuntimeError("No response from stage for position query (M114).")

            xPos, yPos, zPos = pos

            self.window.currentXLabel.setText(str(xPos))
            self.window.currentYLabel.setText(str(yPos))
            self.window.currentHeightLabel.setText(str(zPos))
        except Exception as error:
            error_dialog = QtWidgets.QErrorMessage(self.window)
            error_dialog.showMessage(str(error))

    def set_max_stage_position(self):
        """Open the stage options window for user configuration.
        
        Allows users to set desired max parameters like position and speed.
        Useful if the stage size changes, and it needs to be limited to prevent
        stage crashes with the sensor head or sample.
        """
        self.stage_options = self.stage_options_cls()

    def show_error_message(self, text):
        """Display an error message dialog.

        :param text: The error message to display
        :return:
        """
        error_dialog = QtWidgets.QErrorMessage(self.window)
        error_dialog.showMessage(text)
        return
