import numpy as np
import time
import zhinst.core
import matplotlib as mpl
import matplotlib.pyplot as plt
mpl.use('TkAgg')

"""
Alex J. Newman - 18-05-2023=4
this is just a scratch pad of test scripts - remove for final release blah blah etc etc...

"""

device_id = "dev4521" # Device serial number available on its rear panel.
# interface = "1GbE" # For Ethernet connection or when MFLI/MFIA is connected to a remote Data Server.
#interface = "USB" # For all instruments connected to the host computer via USB except MFLI/MFIA.
interface = "PCIe" # For MFLI/MFIA devices in case the Data Server runs on the device.

server_host = "192.168.70.166"
server_port = 8004
#server_port = 8005 # Default port for HF2LI.
api_level = 6 # Maximum API level supported for all instruments except HF2LI.
#api_level = 1 # Maximum API level supported for HF2LI.

# Create an API session to the Data Server.
daq = zhinst.core.ziDAQServer(server_host, server_port, api_level)
# Establish a connection between Data Server and Device.
daq.connectDevice(device_id, interface)


daq.set(f"/{device_id}/demods/0/enable", 1)



demod_path = f"/{device_id}/demods/0/sample"
signal_paths = []
signal_paths.append(demod_path + ".x.fft.abs")  # The demodulator X output.

total_duration = 5  # Time in seconds for the aquisition.
module_sampling_rate = 30000  # Number of points/second.
burst_duration = 0.2  # Time in seconds for each data burst/segment.
num_cols = int(np.ceil(module_sampling_rate * burst_duration))
num_bursts = int(np.ceil(total_duration / burst_duration))

daq_module = daq.dataAcquisitionModule()
daq_module.set("device", device_id)

# Specify continuous acquisition. (continuous = 0)
daq_module.set("type", "continuous")
# 'grid/mode' - Specify the interpolation method of the returned data samples.
# (use ``daq_module.help("grid/mode")`` to se the available options)
# (linear = 2)
daq_module.set("grid/mode", "linear")
# 'count' - Specify the number of bursts of data the
#   module should return (if endless=0). The
#   total duration of data returned by the module will be
#   count*duration.
daq_module.set("count", num_bursts)
# 'duration' - Burst duration in seconds.
#   If the data is interpolated linearly or using nearest neighbor, specify
#   the duration of each burst of data that is returned by the DAQ Module.
daq_module.set("duration", burst_duration)
# 'grid/cols' - The number of points within each duration.
#   This parameter specifies the number of points to return within each
#   burst (duration seconds worth of data) that is
#   returned by the DAQ Module.
daq_module.set("grid/cols", num_cols)


data = {}
for signal_path in signal_paths:
    print("Subscribing to ", signal_path)
    daq_module.subscribe(signal_path)
    data[signal_path] = []

do_plot = True

clockbase = float(daq.getInt(f"/{device_id}/clockbase"))
if do_plot:
    timestamp0 = None
    max_value = None
    min_value = None
    fig, axis = plt.subplots()
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Subscribed signals")
    axis.set_xlim([0, total_duration])
    lines = [axis.plot([], [], label=path)[0] for path in signal_paths]
    axis.legend()
    axis.set_title("Continuous Data Acquisition")
    plt.ion()


def process_data(raw_data):
    global timestamp0, lines, max_value, min_value
    for i, signal_path in enumerate(signal_paths):
        # Loop over all the bursts for the subscribed signal. More than
        # one burst may be returned at a time, in particular if we call
        # read() less frequently than the burst_duration.
        for signal_burst in raw_data.get(signal_path.lower(), []):
            # Convert from device ticks to time in seconds.
            value = signal_burst["value"][0, :]
            data[signal_path].append(value)
            if do_plot:
                max_value = max(max_value, max(value)) if max_value else max(value)
                min_value = min(min_value, min(value)) if min_value else min(value)
                axis.set_ylim(min_value, max_value)
                timestamp0 = (
                    timestamp0 if timestamp0 else signal_burst["timestamp"][0, 0]
                )
                t = (signal_burst["timestamp"][0, :] - timestamp0) / clockbase
                lines[i].set_data(
                    np.concatenate((lines[i].get_xdata(), t), axis=0),
                    np.concatenate((lines[i].get_ydata(), value), axis=0),
                )
    if do_plot:
        fig.canvas.draw()

# Start recording data.
daq_module.execute()
# Record data in a loop with timeout.
timeout = 1.5 * total_duration
start = time.time()

while not daq_module.finished():
    t0_loop = time.time()
    if time.time() - start > timeout:
        raise Exception(
            f"Timeout after {timeout} s - recording not complete."
            "Are the streaming nodes enabled?"
            "Has a valid signal_path been specified?"
        )
    raw_data = daq_module.read(True)
    process_data(raw_data)
    time.sleep(max(0, burst_duration - (time.time() - t0_loop)))
# There may be new data between the last read() and calling finished().
raw_data = daq_module.read(True)
process_data(raw_data)