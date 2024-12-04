# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import time

import numpy as np
import pyaudio
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import zhinst.utils as utils
import zhinst.core
import math
import serial
import keyboard
from pydub import AudioSegment
from pydub.generators import Sine
from pydub.playback import play
from scipy.signal import hilbert
import matplotlib.pyplot as plt


def connect_lia(device_ip='192.168.70.166', device_id='dev4521'):
    """

    :param args:  Contains the UI element strings of IP address for the LIA connection
    :param kwargs:
    :return:
    """
    try:
        server_host: str = device_ip  # this needs to be a user input - remove the magic number
        device_id = device_id
        server_port = 8004  # this also needs to be a user defined input
        api_level = 6  # determines how detailed returning information from the LIA is when using the API commands
        (daq, device, _) = zhinst.utils.create_api_session(
            device_id, api_level, server_host=server_host, server_port=server_port
        )
        zhinst.utils.api_server_version_check(daq)
        daq.set(f"/{device}/demods/0/enable", 1)  # enable the demodulation
        clockbase = float(daq.getInt(f"/{device}/clockbase"))  # get the clockspeed of the LIA for
        LIA_connected = True
    except Exception as e:
        # Probably should make this a popup message instead of console output..
        print(e)
    return daq, device


def connect_stage(com_port, baud_rate=115200):
    """
    :param com_port: (str) the com port to connect to i.e "COM4"
    :param baud_rate: (int) the baud rate (or bit rate) of the stage
    :return:
    """
    try:
        # connect to stage code here
        ser = serial.Serial(port=com_port, baudrate=baud_rate)
    except Exception as error:
        print("could not connect")
    return ser


def execute_gcode(command):
    """ For sending g-codes to the stage to execute them - does not read any data coming back from the stage, use
    read_gcode for queries.

    :param command: The G-code to send to the printer e.g. G24
    :return:
    """
    try:
        ser.write(f'{command}\r\n'.encode())
    except:
        print("ERROR: Could not execute stage command")


def set_stage_pos(x, y):
    """ Move the stage in the xy plane

    :param x: (float) desired x position
    :param y: (float) desired y position
    :return:
    """
    execute_gcode(f'G00 X{x} Y{y}')
    return


def set_stage_height(z):
    """ Move the stage up and down

    :param z: (float) desired z position or "height"
    :return:
    """
    execute_gcode(f'G00 Z{z}')
    return


daq, device = connect_lia()

# t0 = time.time()
# sample = daq.getSample("/%s/demods/0/sample" % device)
# print(time.time() - t0)

daq.subscribe('/%s/demods/0/sample' % device)
stream = daq.poll(0.5, 200, 1, True)
# np.mean(stream['/dev4521/demods/0/sample']['x'])

print(stream['/dev4521/demods/0/sample']['time'])

ser = connect_stage("COM6")
# coords = [[70, 85], [90, 85], [110, 85], [130, 85], [150, 85]]
# coords = [[50, 85], [70, 85], [90, 85], [110, 85], [130, 85]]
# coords = [[51, 48]] #change in height at single point in xy
# coords = [[50, 52], [50, 55], [50, 58], [50, 61], [50, 64],
#           [55, 52], [55, 55], [55, 58], [55, 61], [55, 64],
#           [60, 52], [60, 55], [60, 58], [60, 61], [60, 64],
#           [65, 52], [65, 55], [65, 58], [65, 61], [65, 64],
#           [70, 52], [70, 55], [70, 58], [70, 61], [70, 64]]
# coords = [[110, 85]]

coord_x = 52
coord_y = np.linspace(30, 100, 140)
heights = np.linspace(9, 19, 40)
# heights = [10.5, 10, 9.5, 9, 8.5, 8, 7.5, 7, 6.5, 6, 5.5, 5]

# PUT THIS BACK IN FOR CHANGES IN HEIGHT AT A SINGLE POINT
r = np.zeros([len(coord_y), len(heights)])
r_std = np.zeros([len(coord_y), len(heights)])


# # THIS IS FOR DOING LINE PROFILES AT A CONSTANT HEIGHT
# r = np.zeros([len(coord_y), 2])
# r_std = np.zeros([len(coord_y), 1])
# r[:, -1] = coord_y

# ser.close()
# while True:
#     stream = daq.poll(0.5, 200, 1, True)
#     print(np.mean(stream['/dev4521/demods/0/sample']['x'])*1000, np.std(stream['/dev4521/demods/0/sample']['x'])*1000)
#     time.sleep(1)

try:
    for j in range(len(heights)):
        set_stage_height(heights[j])
        time.sleep(5)
        x = coord_x
        y = coord_y[0]
        set_stage_pos(x, y)
        time.sleep(5)
        for i in range(len(coord_y)):
            x = coord_x
            y = coord_y[i]
            print("moving to", x, y)
            set_stage_pos(x, y)
            stream = daq.poll(0.5, 200, 1, True)
            r[i][j] = np.mean(stream['/dev4521/demods/0/sample']['x'])
            r_std[i][j] = np.std(stream['/dev4521/demods/0/sample']['x'])
    np.savetxt(
        "Z:/Alex N/Lab Data/August 24/Diluted Iron Oxide Scans In Microplate/vials_varied_height/signal_vs_height/r.csv",
        r, delimiter=',')
    np.savetxt(
        "Z:/Alex N/Lab Data/August 24/Diluted Iron Oxide Scans In Microplate/vials_varied_height/signal_vs_height/r_std.csv",
        r_std, delimiter=',')
    np.savetxt(
        "Z:/Alex N/Lab Data/August 24/Diluted Iron Oxide Scans In Microplate/vials_varied_height/signal_vs_height/line_profile_heights.csv",
        heights, delimiter=',')
except KeyboardInterrupt:
    print("stopping")
    ser.close()

#
# def generate_audio_chunk(f=220, duration=0.05, volume=0.2, phi = 0):
#     # volume = 0.2  # range [0.0, 1.0]
#     # fs = 12000  # sampling rate, Hz, must be integer
#     # duration = 2  # in seconds, may be float
#     # f = 300  # sine frequency, Hz, may be float
#
#     # generate samples, note conversion to float32 array
#     samples = (np.sin((2 * np.pi * np.arange(fs * duration) * f / fs) + phi)).astype(np.float32)
#     # T = 1.0/f
#     # D=round(duration/T)*T
#     # samples = (np.sin(2 * np.pi * np.arange(fs * D) * f / fs)).astype(np.float32)
#     # samples = np.append(samples, samples[0])
#
#     output_bytes = (volume * samples).tobytes()
#     return output_bytes, samples

# def round_up_to_even(f):
#     return math.ceil(f / 2.) * 2
#
# def find_nearest(array, value):
#     array = np.asarray(array)
#     idx = (np.abs(array - value)).argmin()
#     return array[idx], idx
#
# def get_cos_params(samples):
#     N = len(samples)
#     x = np.linspace(-np.pi, np.pi, N, endpoint=False)
#     template = np.exp(1j * x)
#     corr = 2 / N * template@samples
#     R = np.abs(corr)
#     phi = np.log(corr).imag
#     return phi


# p = pyaudio.PyAudio()
# fs = 44000
#
# stream = p.open(format=pyaudio.paFloat32,
#                 channels=1,
#                 rate=fs,
#                 output=True)
#
# cycles = 2  # how many sine cycles
# resolution = 100  # how many datapoints to generate
# length = np.pi * 2 * cycles
# dummy_data = np.sin(np.arange(0, length, length / resolution))
# dummy_data += np.random.normal(5,0.6, len(dummy_data))
#
# play_audio = True
#
# if play_audio:
#     df = 10000000
#     f_list = np.linspace(120, 3000, df)
#     v_list = np.linspace(0, max(f_list) * (1/df), len(f_list)) #create a conversion list of equivalent voltages
#     sample = daq.getSample("/%s/demods/0/sample" % device)
#     v_ref = np.sqrt(((sample['x'][0]) ** 2 + (sample['y'][0]) ** 2)) #set a reference signal to use as a comparison value to determine what freq to play
#     start_time = time.time()
#     daq.subscribe(f"/{device}/demods/0/sample")
#
#     f_start = f_list[0]
#     f_last = f_start
#     old_tone, old_raw = generate_audio_chunk(f=120)
#     con_signals = np.array([])
#     phase_diff = 0
#
#     i = 0
#     try:
#         while True:
#             #if h key is pressed, set new reference value
#             if keyboard.is_pressed("h"):
#                 sample = daq.getSample("/%s/demods/0/sample" % device)
#                 v_ref = np.sqrt(((sample['x'][0]) ** 2 + (sample['y'][0]) ** 2))
#             sample = daq.getSample("/%s/demods/0/sample" % device)
#             signal = np.sqrt(((sample['x'][0]) ** 2 + (sample['y'][0]) ** 2))
#             dV = abs(signal - v_ref) #work out the absolute difference between the ref value and the current data value
#             nearest_voltage_value, nearest_voltage_idx = find_nearest(v_list, dV)
#             equivalent_freq_value = round(f_list[nearest_voltage_idx])
#
#             phase_increment = 2 * np.pi * f_last / fs
#             phase_offset = phase_increment * len(old_raw)
#
#             output_bytes, new_raw = generate_audio_chunk(f=equivalent_freq_value, phi = phase_offset)
#
#             old_raw = new_raw
#             f_last = equivalent_freq_value
#             stream.write(output_bytes)
#
#             con_signals = np.append(con_signals, new_raw)
#             i += 1
#     except KeyboardInterrupt:
#         print('Stopping')
#
#     p = pg.plot(con_signals)
#     if __name__ == '__main__':
#         import sys
#         if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
#             # QtGui.QApplication.instance().exec_()
#             QtCore.QCoreApplication.instance().exec()
#
#     # for paFloat32 sample values must be in range [-1.0, 1.0]
#
#     # play. May repeat with different volume values (if done interactively)
#     # print("Played sound for {:.2f} seconds".format(time.time() - start_time))
#     # print("Length of audio array", len(output_bytes))
#     stream.stop_stream()
#     stream.close()
#
#     p.terminate()
#
# else:
#     pg.plot(dummy_data)
#     if __name__ == '__main__':
#         import sys
#         if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
#             # QtGui.QApplication.instance().exec_()
#             QtCore.QCoreApplication.instance().exec()