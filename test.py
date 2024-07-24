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

p = pyaudio.PyAudio()
fs = 12000

stream = p.open(format=pyaudio.paFloat32,
                channels=1,
                rate=fs,
                output=True)


def generate_audio_chunk(f=220, duration=0.05, volume=0.1):
    # volume = 0.2  # range [0.0, 1.0]
    # fs = 12000  # sampling rate, Hz, must be integer
    # duration = 2  # in seconds, may be float
    # f = 300  # sine frequency, Hz, may be float

    # generate samples, note conversion to float32 array
    samples = (np.sin(2 * np.pi * np.arange(fs * duration) * f / fs)).astype(np.float32)

    # per @yahweh comment explicitly convert to bytes sequence
    output_bytes = (volume * samples).tobytes()
    return output_bytes

def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return array[idx]


cycles = 2  # how many sine cycles
resolution = 100  # how many datapoints to generate
length = np.pi * 2 * cycles
dummy_data = np.sin(np.arange(0, length, length / resolution))
dummy_data += np.random.normal(5,0.6, len(dummy_data))



play_audio = True

if play_audio:
    f_list = np.linspace(100, 1000, 1000)
    v_ref = dummy_data[0] #set a reference signal to use as a comparison value to determine what freq to play

    start_time = time.time()
    for i in range(len(dummy_data)):
        dV = abs(dummy_data[i] - v_ref) #work out the absolute difference between the ref value and the current data value
        map_value = dV/(1/len(f_list))
        output_bytes = generate_audio_chunk(f=find_nearest(f_list, map_value))
        stream.write(output_bytes)
        print(map_value)
    # for paFloat32 sample values must be in range [-1.0, 1.0]

    # play. May repeat with different volume values (if done interactively)
    # print("Played sound for {:.2f} seconds".format(time.time() - start_time))
    # print("Length of audio array", len(output_bytes))
    stream.stop_stream()
    stream.close()

    p.terminate()

else:
    pg.plot(dummy_data)
    if __name__ == '__main__':
        import sys
        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            # QtGui.QApplication.instance().exec_()
            QtCore.QCoreApplication.instance().exec()