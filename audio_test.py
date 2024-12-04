import numpy as np
import pyaudio
import zhinst
import zhinst.utils
import keyboard
import time
# Constants
SAMPLE_RATE = 44100  # Sampling rate in Hz
BUFFER_SIZE = 1024  # Number of samples per buffer

# Initialize PyAudio
p = pyaudio.PyAudio()

def connect_lia(device_ip = '192.168.70.166', device_id = 'dev4521'):
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

# Function to generate a sine wave
def generate_sine_wave(frequency, duration, sample_rate=SAMPLE_RATE):
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    wave = 0.5 * np.sin(2 * np.pi * frequency * t)  # amplitude of 0.5 to avoid clipping
    return wave

def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return array[idx], idx

# Stream callback function
def callback(in_data, frame_count, time_info, status):
    global current_frequency, next_frequency, phase, crossfade_frames

    # Generate buffer
    t = (np.arange(frame_count) + phase) / SAMPLE_RATE
    phase = (phase + frame_count) % SAMPLE_RATE

    if crossfade_frames > 0:
        fade_ratio = crossfade_frames / float(BUFFER_SIZE)
        buffer = (fade_ratio * 0.5 * np.sin(2 * np.pi * current_frequency * t) +
                  (1 - fade_ratio) * 0.5 * np.sin(2 * np.pi * next_frequency * t)).astype(np.float32)
        crossfade_frames -= frame_count
    else:
        buffer = 0.5 * np.sin(2 * np.pi * current_frequency * t).astype(np.float32)
        if current_frequency != next_frequency:
            current_frequency = next_frequency

    return (buffer.tobytes(), pyaudio.paContinue)

# Initial frequencies
current_frequency = 200  # Starting frequency (A4)
next_frequency = 440.0
phase = 0
crossfade_frames = 0

# Open audio stream
stream = p.open(format=pyaudio.paFloat32,
                channels=1,
                rate=SAMPLE_RATE,
                output=True,
                stream_callback=callback)

# Start the stream
stream.start_stream()

daq, device = connect_lia()

df = 10000000
f_list = np.linspace(120, 3000, df)
v_list = np.linspace(0, max(f_list) * (1/df), len(f_list)) #create a conversion list of equivalent voltages
sample = daq.getSample("/%s/demods/0/sample" % device)
v_ref = np.sqrt(((sample['x'][0]) ** 2 + (sample['y'][0]) ** 2)) #set a reference signal to use as a comparison value to determine what freq to play
start_time = time.time()
daq.subscribe(f"/{device}/demods/0/sample")

try:
    while stream.is_active():
        # Here, you can change the frequency smoothly
        try:
            if keyboard.is_pressed("h"):
                sample = daq.getSample("/%s/demods/0/sample" % device)
                v_ref = np.sqrt(((sample['x'][0]) ** 2 + (sample['y'][0]) ** 2))
            sample = daq.getSample("/%s/demods/0/sample" % device)
            signal = np.sqrt(((sample['x'][0]) ** 2 + (sample['y'][0]) ** 2))
            dV = abs(signal - v_ref) #work out the absolute difference between the ref value and the current data value
            nearest_voltage_value, nearest_voltage_idx = find_nearest(v_list, dV)
            new_freq = round(f_list[nearest_voltage_idx])
            print(new_freq)
            next_frequency = new_freq
            crossfade_frames = BUFFER_SIZE  # Trigger crossfade
        except ValueError:
            print("Please enter a valid number.")
except KeyboardInterrupt:
    pass

# Stop and close the stream
stream.stop_stream()
stream.close()
p.terminate()
