# -*- coding: utf-8 -*-
"""Stage control module for the Scanning Magnetometer.

Handles all communication and control of the motorized XYZ stage via serial connection.
Uses G-code commands to control movement.
"""

from PyQt6 import QtWidgets
import serial
import re


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
            response = self.read_gcode('M114')
            if not response:
                raise RuntimeError("No response from stage for position query (M114).")

            decoded = response.decode("utf-8", errors="ignore").strip()
            # Robust parse for typical M114 format: "X:.. Y:.. Z:.."
            x_match = re.search(r"X:([-+]?\d*\.?\d+)", decoded)
            y_match = re.search(r"Y:([-+]?\d*\.?\d+)", decoded)
            z_match = re.search(r"Z:([-+]?\d*\.?\d+)", decoded)

            if x_match and y_match and z_match:
                xPos = x_match.group(1)
                yPos = y_match.group(1)
                zPos = z_match.group(1)
            else:
                # Fallback to token parsing for non-standard firmware responses.
                tokens = decoded.split()
                if len(tokens) < 3:
                    raise RuntimeError(f"Unexpected stage response: '{decoded}'")
                xPos, yPos, zPos = tokens[0], tokens[1], tokens[2]

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
