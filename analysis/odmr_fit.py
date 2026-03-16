import numpy as np
from sklearn.linear_model import LinearRegression
from scipy.signal import savgol_filter, find_peaks, peak_widths
from scipy.optimize import least_squares
from scipy import sparse
from scipy.sparse.linalg import spsolve


def _asymmetric_least_squares(y, lam=1e6, p=0.01, niter=10):
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 5:
        return y.copy()

    d = sparse.diags([1.0, -2.0, 1.0], [0, -1, -2], shape=(n, n - 2))
    w = np.ones(n, dtype=float)
    for _ in range(niter):
        w_mat = sparse.spdiags(w, 0, n, n)
        z = spsolve(w_mat + lam * d.dot(d.transpose()), w * y)
        w = p * (y > z) + (1 - p) * (y <= z)
    return np.asarray(z, dtype=float)


def _lorentzian_sum_model(x, params, n_peaks):
    baseline = params[0] + params[1] * (x - np.mean(x))
    y_model = baseline
    for i in range(n_peaks):
        amp = params[2 + 3 * i]
        center = params[2 + 3 * i + 1]
        width = params[2 + 3 * i + 2]
        y_model = y_model + amp / (1.0 + ((x - center) / width) ** 2)
    return y_model


def _fit_global_lorentzian(x, y, centers_guess, amps_guess, widths_guess):
    n_peaks = len(centers_guess)
    if n_peaks == 0:
        return None

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    y_span = max(1e-12, float(np.ptp(y)))
    x_span = max(1e-12, float(np.ptp(x)))
    dx = max(1e-12, float(np.median(np.diff(x)))) if len(x) > 1 else 1e-6

    p0 = [float(np.median(y)), 0.0]
    lower = [float(np.min(y) - y_span), -10 * y_span / x_span]
    upper = [float(np.max(y) + y_span), 10 * y_span / x_span]

    for amp_guess, center_guess, width_guess in zip(amps_guess, centers_guess, widths_guess):
        amp0 = float(min(-1e-12, amp_guess))
        width0 = float(max(2 * dx, width_guess))

        p0.extend([amp0, float(center_guess), width0])
        lower.extend([-2.0 * y_span, float(np.min(x)), dx])
        upper.extend([-1e-12, float(np.max(x)), max(dx * 4, x_span)])

    p0 = np.asarray(p0, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)

    def residuals(p):
        return _lorentzian_sum_model(x, p, n_peaks) - y

    result = least_squares(
        residuals,
        p0,
        bounds=(lower, upper),
        method="trf",
        loss="soft_l1",
        f_scale=max(1e-12, 0.03 * y_span),
        max_nfev=8000,
    )

    if not result.success:
        return None
    return result.x


def _bic_score(y_true, y_pred, n_params):
    n = len(y_true)
    if n <= 1:
        return np.inf
    rss = float(np.sum((y_true - y_pred) ** 2))
    rss = max(rss, 1e-24)
    return n * np.log(rss / n) + n_params * np.log(n)


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

    baseline = _asymmetric_least_squares(y_for_fit, lam=1e6, p=0.01, niter=10)
    y_corrected = y_for_fit - baseline

    linear_region_width = max(7, int(linear_region_width))
    if linear_region_width % 2 == 0:
        linear_region_width += 1

    dip_signal = -y_corrected
    dip_med = float(np.median(dip_signal))
    dip_mad = float(np.median(np.abs(dip_signal - dip_med)))
    robust_sigma = max(1e-12, 1.4826 * dip_mad)

    auto_prom = max(2.5 * robust_sigma, 0.03 * float(np.ptp(dip_signal)))
    auto_height = dip_med + 2.0 * robust_sigma
    auto_distance = max(3, int(len(x) / 120))

    detect_height = float(peak_height) if float(peak_height) > 0 else auto_height
    detect_prom = float(peak_prom) if float(peak_prom) > 0 else auto_prom
    detect_distance = int(peak_distance) if int(peak_distance) > 0 else auto_distance

    peaks, peak_props = find_peaks(
        dip_signal,
        height=detect_height,
        distance=detect_distance,
        prominence=detect_prom,
    )

    if len(peaks) == 0:
        peaks, peak_props = find_peaks(
            dip_signal,
            distance=max(2, detect_distance // 2),
            prominence=max(auto_prom * 0.45, 1e-12),
        )

    if len(peaks) == 0:
        derivative = np.gradient(y_for_fit, x)
        if not use_positive_gradients:
            derivative = -1.0 * derivative
        return {
            "x": x,
            "y_for_fit": y_for_fit,
            "derivative": derivative,
            "regions": [],
            "prominences": np.array([]),
        }

    prominences = np.asarray(peak_props.get("prominences", np.ones(len(peaks))), dtype=float)
    if len(peaks) > max_peaks:
        keep = np.argsort(prominences)[-max_peaks:]
        keep = keep[np.argsort(peaks[keep])]
        peaks = peaks[keep]
        prominences = prominences[keep]

    widths, _, _, _ = peak_widths(dip_signal, peaks, rel_height=0.5)
    dx = max(1e-12, float(np.median(np.diff(x)))) if len(x) > 1 else 1e-6
    center_guesses = x[peaks]
    width_guesses = np.maximum(widths * dx * 0.5, 2 * dx)

    amp_guesses = []
    for idx in peaks:
        local_amp = y_corrected[idx]
        amp_guesses.append(float(min(-1e-12, local_amp)))
    amp_guesses = np.asarray(amp_guesses, dtype=float)

    max_candidate_models = min(8, len(peaks))
    sorted_idx = np.argsort(prominences)[::-1]

    best = None
    for k in range(1, max_candidate_models + 1):
        chosen = np.sort(sorted_idx[:k])
        fit_params = _fit_global_lorentzian(
            x=x,
            y=y_for_fit,
            centers_guess=center_guesses[chosen],
            amps_guess=amp_guesses[chosen],
            widths_guess=width_guesses[chosen],
        )
        if fit_params is None:
            continue
        y_model = _lorentzian_sum_model(x, fit_params, k)
        n_params = 2 + 3 * k
        bic = _bic_score(y_for_fit, y_model, n_params)
        if (best is None) or (bic < best["bic"]):
            best = {
                "k": k,
                "chosen": chosen,
                "params": fit_params,
                "y_model": y_model,
                "bic": bic,
            }

    if best is None:
        derivative = np.gradient(y_for_fit, x)
        if not use_positive_gradients:
            derivative = -1.0 * derivative
        return {
            "x": x,
            "y_for_fit": y_for_fit,
            "derivative": derivative,
            "regions": [],
            "prominences": np.array([]),
        }

    y_model = best["y_model"]
    model_derivative = np.gradient(y_model, x)
    signed_derivative = model_derivative if use_positive_gradients else (-1.0 * model_derivative)

    chosen_prominences = prominences[best["chosen"]]
    centers_fit = []
    widths_fit = []
    for i in range(best["k"]):
        centers_fit.append(float(best["params"][2 + 3 * i + 1]))
        widths_fit.append(float(best["params"][2 + 3 * i + 2]))

    regions = []
    for i in range(best["k"]):
        center = centers_fit[i]
        width = max(widths_fit[i], 2 * dx)

        mask = (x >= center - 2.0 * width) & (x <= center + 2.0 * width)
        if not np.any(mask):
            continue
        idx_local = np.where(mask)[0]
        local_derivative = signed_derivative[idx_local]
        lock_idx = idx_local[int(np.argmax(local_derivative))]

        half = linear_region_width // 2
        start = max(0, lock_idx - half)
        end = min(len(x), lock_idx + half + 1)
        x_linear = x[start:end]
        y_linear = y_model[start:end]
        if len(x_linear) < 3:
            continue

        model = LinearRegression()
        model.fit(x_linear.reshape(-1, 1), y_linear)
        slope = float(model.coef_[0])
        predicted = model.predict(x_linear.reshape(-1, 1))

        ss_res = float(np.sum((y_linear - predicted) ** 2))
        ss_tot = float(np.sum((y_linear - np.mean(y_linear)) ** 2))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        regions.append(
            {
                "center_freq": float(x[lock_idx]),
                "slope": slope,
                "x_linear": x_linear,
                "predicted": predicted,
                "prominence": float(chosen_prominences[i]),
                "r_squared": float(r_squared),
            }
        )

    regions = sorted(regions, key=lambda item: item["center_freq"])

    return {
        "x": x,
        "y_for_fit": y_for_fit,
        "y_model": y_model,
        "derivative": signed_derivative,
        "regions": regions,
        "prominences": np.asarray([r["prominence"] for r in regions], dtype=float),
    }
