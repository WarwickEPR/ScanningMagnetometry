# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import time

import numpy as np
import pyaudio

p = pyaudio.PyAudio()
fs = 12000

stream = p.open(format=pyaudio.paFloat32,
                channels=1,
                rate=fs,
                output=True)


def generate_audio_chunk(f=220, duration=0.5, volume=0.2):
    # volume = 0.2  # range [0.0, 1.0]
    # fs = 12000  # sampling rate, Hz, must be integer
    # duration = 2  # in seconds, may be float
    # f = 300  # sine frequency, Hz, may be float

    # generate samples, note conversion to float32 array
    samples = (np.sin(2 * np.pi * np.arange(fs * duration) * f / fs)).astype(np.float32)

    # per @yahweh comment explicitly convert to bytes sequence
    output_bytes = (volume * samples).tobytes()
    return output_bytes


cycles = 2  # how many sine cycles
resolution = 50  # how many datapoints to generate

length = np.pi * 2 * cycles
dummy_data = np.sin(np.arange(0, length, length / resolution))

f_list = np.linspace(120, 1000, 11)

start_time = time.time()
for i in dummy_data:
    output_bytes = generate_audio_chunk(f=i)
    stream.write(output_bytes)

# for paFloat32 sample values must be in range [-1.0, 1.0]

# play. May repeat with different volume values (if done interactively)
print("Played sound for {:.2f} seconds".format(time.time() - start_time))
print("Length of audio array", len(output_bytes))
stream.stop_stream()
stream.close()

p.terminate()
