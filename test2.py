import time
import numpy as np
import zhinst.utils as utils
import zhinst.core
import serial
from datetime import datetime
import matplotlib.pyplot as plt
import os
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation

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

# Function to generate cylindrical coordinates
def generate_cylindrical_coordinates(r_range, theta_range, z_range):
    cylindrical_coords = []

    for r in r_range:
        for theta in theta_range:
            cylindrical_coords.append((r, theta))

    x_coords = [r * np.cos(theta) + x_centre for r, theta in cylindrical_coords]
    y_coords = [r * np.sin(theta) + y_centre for r, theta in cylindrical_coords]



    return x_coords, y_coords

def point_sphere_plot():
    # Plot the coordinates
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(x_coords, y_coords, c='b', marker='o')

    for i, (x, y) in enumerate(zip(x_coords, y_coords)):
        ax.text(x, y, 0, f'{i}', fontsize=12, color='red')

    # Set labels
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title('3D Scatter Plot of Cylindrical Coordinates')
    plt.show()

def take_measurement():
    return


def update():
    return


# Define ranges for radius, theta, and z
r_range = np.linspace(10, 26, num=20)  # Radius from 0 to 5 with 6 points
theta_range = np.linspace(0, 2 * np.pi, num=40, endpoint=True)  # Theta from 0 to 2pi with 12 points
z_range = np.linspace(0, 25, num=20)  # Z from -5 to 5 with 11 points

x_centre = 56
y_centre = 56

# Generate cylindrical coordinates
x_coords, y_coords = generate_cylindrical_coordinates(r_range, theta_range, z_range)
plot_point_sphere = False

# Initialize measurement array to store measured values
measurements = []

fig, ax = plt.subplots(subplot_kw=dict(projection='polar'))

rmesh, theta_mesh = np.meshgrid(r_range, theta_range)
data = np.zeros((len(theta_range), len(r_range)))
polar_plot = ax.contourf(theta_mesh, rmesh, data, 100, cmap='plasma')
cbar = plt.colorbar(polar_plot)

daq, device = connect_lia()
daq.subscribe('/%s/demods/0/sample' % device)
ser = connect_stage("COM6")

today = datetime.now()   # Get date
datestring = today.strftime("%Y%m%d%H")
newpath = f'Z:/Alex N/Lab Data/October 24/Radial Scans around iron oxide/{datestring}'
if not os.path.exists(newpath):
    os.makedirs(newpath)


set_stage_height(z_range[0])
set_stage_pos(x_coords[0], y_coords[0])
input("Put Sample in Place then press any key to start")
# for i in range(len(z_coords)):
for h in range(len(z_range)):
    z = z_range[h]
    k = 0
    set_stage_height(z)
    time.sleep(1)
    data = np.zeros((len(theta_range), len(r_range)))
    for i in range(len(r_range)):
        for j in range(len(theta_range)):
            # print(x_coords[j], y_coords[j], j)
            set_stage_pos(x_coords[k],y_coords[k])
            time.sleep(0.5)
            stream = daq.poll(0.5, 200, 1, True)
            r = np.mean(stream['/dev4521/demods/0/sample']['x'])
            r_std = np.std(stream['/dev4521/demods/0/sample']['x'])
            k += 1
            data[j,i] = r
            for c in polar_plot.collections:
                c.remove()
            polar_plot = ax.contourf(theta_mesh, rmesh, data, 100, cmap='plasma')
            plt.pause(0.01)
            np.savetxt(f"{newpath}/{h}data_height{z}.csv", data, delimiter=',')
plt.show()





