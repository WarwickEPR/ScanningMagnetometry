import numpy as np
from scipy import optimize, signal
from scipy.spatial.transform import Rotation as R
from numpy.linalg import eig, pinv
from itertools import product, chain

class ODMR_Fit:

    # Constants:
    gamma = 28.024951424285e9  # Hz/T

    def __init__(self, frequency, lia_response):
        self.frequency = frequency
        self.lia_response = lia_response
        self.dip_threshold = 0.2  # Threshold for peak finding, as a fraction of the maximum integrated signal
        self.fit_threshold = 0.1  # Threshold for slope fitting interval, as a fraction of the maximum integrated signal height
        self.resonance_count = 0
        self.resonance_frequency = np.array([])
        self.resonance_slope = np.array([])
        self.resonance_intercept = np.array([])
        self.B_lab100 = None
        #D = nv_zero_field_splitting(temperature);
        # We don't know the temperature and strain explicitly, but this is close enough at 300K
        # and we can update from the resonance frequencies iteratively if needed
        # Just needs to be close enough for the relative shift linearisation to be valid
        self.D = 2.87e9 # Hz
        self.D_adjustment = 0
    
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

    def find_B_lab100(self):

        if self.resonance_count != 8:
            raise ValueError("Exactly 8 resonance frequencies are expected for this initialization procedure.")

        splittings = ( self.resonance_frequency[4:8] - np.flip(self.resonance_frequency[0:4]) ) / ( 2 * self.gamma )
        sign_permutations = np.flip(np.array(list(chain(*product([-1,1], repeat=4)))).reshape((16,4)))
        minimal_permutation = np.argmin(np.abs(np.sum( sign_permutations * splittings, axis=1 )))
        splits = sign_permutations[minimal_permutation] * splittings

        # Coefficients matrix (signs unchanged)
        A = np.array([[1,  -1, -1],
                      [-1, -1,  1],
                      [-1,  1, -1],
                      [1,   1,  1]]) * np.sqrt(1/3)
        
        # Solve the set of linear equations to find the magnetic field components in a notional lab frame aligned to [100]
        self.B_lab100 = np.linalg.lstsq(A, splits)[0]
        return self.B_lab100

    def calculate_D_adjustment(self):
        calculated_freqs = self.calculate_frequencies(self.B_lab100)
        self.D_adjustment = - (np.sum(calculated_freqs) - np.sum(self.resonance_frequency)) / 8

    def calculate_frequencies(self, B_lab100):

        nv_orientations = np.array([[1,1,1], [-1,-1,1], [-1,1,-1], [1,-1,-1]]) / np.sqrt(3)
        lab_orientation = np.array([0, 0, 1])
        nv_rotation_A = R.align_vectors(nv_orientations[0,:], lab_orientation)[0]
        nv_rotation_B = R.align_vectors(nv_orientations[1,:], lab_orientation)[0]
        nv_rotation_C = R.align_vectors(nv_orientations[2,:], lab_orientation)[0]
        nv_rotation_D = R.align_vectors(nv_orientations[3,:], lab_orientation)[0]
        B_A = nv_rotation_A.apply(B_lab100)
        B_B = nv_rotation_B.apply(B_lab100)
        B_C = nv_rotation_C.apply(B_lab100)
        B_D = nv_rotation_D.apply(B_lab100)

        # Spin Operators:
        Sx = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]]) / np.sqrt(2)
        Sy = np.array([[0, -1j, 0], [1j, 0, -1j], [0, 1j, 0]]) / np.sqrt(2)
        Sz = np.array([[1, 0, 0], [0, 0, 0], [0, 0, -1]])

        # Hamiltonians for each NV orientation:
        D = self.D + self.D_adjustment
        H1 = (D)*Sz*Sz + self.gamma*(B_A[0]*Sx + B_A[1]*Sy + B_A[2]*Sz)
        H2 = (D)*Sz*Sz + self.gamma*(B_B[0]*Sx + B_B[1]*Sy + B_B[2]*Sz)
        H3 = (D)*Sz*Sz + self.gamma*(B_C[0]*Sx + B_C[1]*Sy + B_C[2]*Sz)
        H4 = (D)*Sz*Sz + self.gamma*(B_D[0]*Sx + B_D[1]*Sy + B_D[2]*Sz)

        # Eigenvalues:
        eig1, _ = eig(H1)
        #print("Eigenvalues1 (Hz):", eig1)
        freq2 = eig1[1]-eig1[0]
        freq7 = eig1[2]-eig1[0];
        eig2, _ = eig(H2);
        #print("Eigenvalues2 (Hz):", eig2)
        freq4 = eig2[1]-eig2[0];
        freq5 = eig2[2]-eig2[0];
        eig3, _ = eig(H3);
        #print("Eigenvalues3 (Hz):", eig3)
        freq3 = eig3[1]-eig3[0];
        freq6 = eig3[2]-eig3[0];
        eig4, _ = eig(H4);
        #print("Eigenvalues4 (Hz):", eig4)
        freq1 = eig4[1]-eig4[0];
        freq8 = eig4[2]-eig4[0];

        # Should return real values, so truncate any small imaginary parts due to numerical errors and sort the frequencies in ascending order for comparison with the input resonances
        return np.sort(np.real(np.array([freq1, freq2, freq3, freq4, freq5, freq6, freq7, freq8])))

    def calculate_A_matrix(self, selection=[4,5,6,7]):

        B0 = self.B_lab100
        self.A_selection = list(selection)
        self.A_reference_frequencies = np.asarray(self.resonance_frequency[selection], dtype=float)
        stepsize = 1e-9
        Bx = B0 + stepsize * np.array([1, 0, 0])
        By = B0 + stepsize * np.array([0, 1, 0])
        Bz = B0 + stepsize * np.array([0, 0, 1])
        freqs_B0 = self.calculate_frequencies(B0)
        freqs_Bx = self.calculate_frequencies(Bx)
        freqs_By = self.calculate_frequencies(By)
        freqs_Bz = self.calculate_frequencies(Bz)
        dx = freqs_Bx - freqs_B0
        dy = freqs_By - freqs_B0
        dz = freqs_Bz - freqs_B0
        shiftrates = np.array([dx, dy, dz]).T / stepsize
        shiftrates = shiftrates[selection,:]
        A = pinv(shiftrates)
        self.A = A
        return A
    
    def shift_to_field(self, frequency_shifts, reference_frequencies=None):
        frequency_shifts = np.asarray(frequency_shifts, dtype=float)
        if reference_frequencies is not None:
            reference_frequencies = np.asarray(reference_frequencies, dtype=float)
            if reference_frequencies.shape != frequency_shifts.shape:
                raise ValueError(
                    "reference_frequencies must match frequency_shifts shape."
                )
            frequency_shifts = (frequency_shifts - reference_frequencies) * 1e9

        if not hasattr(self, 'A'):
            self.calculate_A_matrix()
        return self.A @ frequency_shifts
    