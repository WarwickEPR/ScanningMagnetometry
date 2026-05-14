import numpy as np
from scipy import optimize, signal

class ODMR_Fit:
    def __init__(self, frequency, lia_response):
        self.frequency = frequency
        self.lia_response = lia_response
        self.dip_threshold = 0.2  # Threshold for peak finding, as a fraction of the maximum integrated signal
        self.fit_threshold = 0.1  # Threshold for slope fitting interval, as a fraction of the maximum integrated signal height
    
    def _integrate(self):
        integrated = np.cumsum(self.lia_response)
        bg_slope = integrated[-1] / len(integrated)  # Any zero error accumulates, take it off to first order for fitting
        bg = bg_slope * np.arange(len(integrated))  # Calculate the background
        return integrated - bg

    def find_resonances(self):
        # Use the integrated lia signal to locate the resonances approximately, then fit the original data to find the exact resonance frequencies and widths
        integrated = self._integrate()
        m = np.mean(integrated)
        if m < 0:
            integrated = -integrated  # Invert if the mean is negative
            self.positive_gradient = True
        else:
            self.positive_gradient = False
        
        # Assume that "runt" resonances are no less than 20% of maximum and that they are well spaced, so we can use a simple peak finding algorithm to locate them
        threshold = np.max(integrated) * self.dip_threshold  # Set threshold at 20% of the maximum
        peak_index, _ = signal.find_peaks(integrated, height=threshold)

        # To get the window for fitting each peak by find the peak width at some fraction of height
        widths, _, peak_l, peak_r = signal.peak_widths(integrated, peak_index, rel_height=self.fit_threshold)  # Calculate resonance widths
        frequency_step = self.frequency[1] - self.frequency[0]
        peak_l = np.floor(peak_l).astype(int)
        peak_r = np.ceil(peak_r).astype(int)
        widths = widths * frequency_step  # Convert widths from index to frequency units

        self.resonance_count = len(peak_index)
        self.width = widths
        self.resonance_frequency = np.zeros(self.resonance_count)
        self.resonance_slope = np.zeros(self.resonance_count)
        self.resonance_intercept = np.zeros(self.resonance_count)

        for i, (resonance_index, width, peak_l, peak_r) in enumerate(zip(peak_index, widths, peak_l, peak_r)):
            peak_internal_indices = np.arange(peak_l, peak_r)
            popt, pcov = optimize.curve_fit(lambda x, a, b: a * x + b, self.frequency[peak_internal_indices], self.lia_response[peak_internal_indices])
            slope = popt[0]
            intercept = popt[1]
            zero_crossing = -intercept / slope  # Calculate the zero-crossing point
            self.resonance_frequency[i] = zero_crossing
            self.resonance_slope[i] = slope
            self.resonance_intercept[i] = intercept
            #print(f"Resonance at {resonance_index} with width {width*1000:.2f} MHz, zero-crossing at {zero_crossing:.3f} GHz")

        return self.resonance_frequency

    def fitted_slope(self, i, interval=None):
        if interval is None:
            interval = np.linspace(self.resonance_frequency[i] - self.width[i]*0.5, self.resonance_frequency[i] + self.width[i]*0.5, 100)
        return interval, self.resonance_intercept[i] + self.resonance_slope[i] * interval
