
import numpy as np
import matplotlib.pyplot as plt

# def fit_linear_region(self, x, y, linear_region_width=50, window_length=50, polyorder=3, plot_derivative=False,
#                       denoise=False):
#     try:
#         window_length = int(window_length)
#         polyorder = int(polyorder)
#         if denoise:
#             y = savgol_filter(y, window_length=window_length, polyorder=polyorder)
#         try:
#             self.odmr_plot.clear()
#             self.dummy_data(x, y)
#         except:
#             self.dummy_data(x, y)
#         linear_region_width = int(linear_region_width)
#         derivative = np.gradient(y, x)  # take derivative of curve, find elbow or "knee" point of curve
#         elbow_index = np.argmin(derivative)  # find the minimum of the gradient, use that to determine linear region
#         # Adjust linear region parameter to control the width of the linear region
#         linear_region_start = max(0, elbow_index - linear_region_width // 2)
#         linear_region_end = min(len(x) - 1, elbow_index + linear_region_width // 2)
#         # Extract data points for the linear region
#         x_linear = x[linear_region_start:linear_region_end].reshape(-1, 1)
#         y_linear = y[linear_region_start:linear_region_end]
#
#         # Perform linear regression
#         model = LinearRegression()
#         model.fit(x_linear, y_linear)
#
#         slope = model.coef_[0]
#         intercept = model.intercept_
#
#         prd = model.predict(x_linear)
#         x_linear = x_linear.flatten()
#
#
#         pen = pg.mkPen(color=(255, 0, 0), width=5)
#         if self.odmr_linear_region_plot == None:
#             self.odmr_linear_region_plot = self.graphWidget.plot(x_linear, prd, pen=pen)
#         else:
#             self.odmr_linear_region_plot.setData(x_linear,prd)
#
#
#         #if plot deriviate is true, plot it else, if false, clear deriv plot.
#         if plot_derivative:
#             try:
#                 self.odmr_deriv_plot.clear()
#             except:
#                 pass
#             pen = pg.mkPen(color=(0,255,0), style=QtCore.Qt.PenStyle.DashDotLine)
#             self.odmr_deriv_plot = self.graphWidget.plot(x, derivative, pen=pen)
#         else:
#             try:
#                 self.odmr_deriv_plot.clear()
#             except:
#                 pass
#
#
#         self.odmrGradientLabel.setText(str(round(slope,3)))
#         return
#
#     except Exception as error:
#         print(error)
#         window.show_error_message("ERROR: Linear region too large/small")