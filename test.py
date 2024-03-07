
import numpy as np
import matplotlib.pyplot as plt

thresholds = [1,2,3,4,5]
angles = [1,2,3,4,5]
cluster_list = [1,2,3,4,5]

weighted_angles_array = np.ones([len(thresholds), len(cluster_list)])

def get_weighted_angles(thresholds, angles):
    weighted_angles = []
    for value in thresholds:
        weighted_angles.append(value)
    return weighted_angles


for i in range(len(cluster_list)):
    weighted_angles_array[:,i] = get_weighted_angles(thresholds, angles)

print(weighted_angles_array)

x = [1,2,3,4,5]

plt.plot(x,weighted_angles_array[:,0])