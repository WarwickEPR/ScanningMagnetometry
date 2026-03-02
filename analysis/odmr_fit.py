import numpy as np
from sklearn.linear_model import LinearRegression
from scipy.signal import savgol_filter, find_peaks, peak_widths


def compute_odmr_linear_regions(
    x,
    y,
    linear_region_width=50,
    window_length=50,
    polyorder=3,
    peak_height=-5,
    peak_distance=100,
    peak_prom=5,
    denoise=False,
    use_positive_gradients=False,
    max_peaks=24,
):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 7 or len(y) < 7:
        return None

    window_length = int(window_length)
    polyorder = int(polyorder)

    max_allowed_window = len(y) if len(y) % 2 == 1 else len(y) - 1
    if max_allowed_window < 5:
        max_allowed_window = 5
    window_length = min(window_length, max_allowed_window)
    if window_length % 2 == 0:
        window_length -= 1
    window_length = max(5, window_length)
    polyorder = max(1, min(polyorder, window_length - 2))

    y_for_fit = y
    if denoise:
        y_for_fit = savgol_filter(y, window_length=window_length, polyorder=polyorder)

    linear_region_width = max(7, int(linear_region_width))
    if linear_region_width % 2 == 0:
        linear_region_width += 1

    if use_positive_gradients:
        derivative = np.gradient(y_for_fit, x)
    else:
        derivative = -1 * np.gradient(y_for_fit, x)

    deriv_median = float(np.median(derivative))
    mad = float(np.median(np.abs(derivative - deriv_median)))
    robust_sigma = max(1e-12, 1.4826 * mad)
    auto_height = deriv_median + 2.0 * robust_sigma
    auto_prom = max(robust_sigma * 2.5, float(np.ptp(derivative)) * 0.04)
    auto_distance = max(3, int(len(x) / 120))

    detect_height = float(peak_height) if float(peak_height) > 0 else auto_height
    detect_prom = float(peak_prom) if float(peak_prom) > 0 else auto_prom
    detect_distance = int(peak_distance) if int(peak_distance) > 0 else auto_distance

    peaks, peak_props = find_peaks(
        derivative,
        height=detect_height,
        distance=detect_distance,
        prominence=detect_prom,
    )

    if len(peaks) == 0:
        peaks, peak_props = find_peaks(
            derivative,
            distance=max(2, detect_distance // 2),
            prominence=max(auto_prom * 0.45, 1e-12),
        )

    if len(peaks) == 0:
        return {
            "x": x,
            "y_for_fit": y_for_fit,
            "derivative": derivative,
            "regions": [],
            "prominences": np.array([]),
        }

    prominences = peak_props.get("prominences", np.ones(len(peaks)))
    if len(peaks) > max_peaks:
        keep = np.argsort(prominences)[-max_peaks:]
        keep = keep[np.argsort(peaks[keep])]
        peaks = peaks[keep]
        prominences = prominences[keep]

    widths, _, _, _ = peak_widths(derivative, peaks, rel_height=0.5)

    regions = []
    for i in range(len(peaks)):
        adaptive_width = max(linear_region_width, int(np.ceil(widths[i] * 1.8)))
        if adaptive_width % 2 == 0:
            adaptive_width += 1

        linear_region_start = max(0, peaks[i] - adaptive_width // 2)
        linear_region_end = min(len(x) - 1, peaks[i] + adaptive_width // 2)

        x_linear = x[linear_region_start:linear_region_end].reshape(-1, 1)
        y_linear = y_for_fit[linear_region_start:linear_region_end]
        if len(x_linear) < 3:
            continue

        model = LinearRegression()
        model.fit(x_linear, y_linear)

        slope = model.coef_[0]
        predicted = model.predict(x_linear)
        x_linear_flat = x_linear.flatten()

        ss_res = float(np.sum((y_linear - predicted) ** 2))
        ss_tot = float(np.sum((y_linear - np.mean(y_linear)) ** 2))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        regions.append(
            {
                "center_freq": float((x_linear_flat[0] + x_linear_flat[-1]) / 2),
                "slope": float(slope),
                "x_linear": x_linear_flat,
                "predicted": predicted,
                "prominence": float(prominences[i]),
                "r_squared": float(r_squared),
            }
        )

    return {
        "x": x,
        "y_for_fit": y_for_fit,
        "derivative": derivative,
        "regions": regions,
        "prominences": np.asarray(prominences),
    }
