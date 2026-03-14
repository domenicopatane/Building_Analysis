import numpy as np
from scipy import signal

from .preprocess import maybe_resample_to


def butter_bandpass_sos(lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low = max(lowcut / nyq, 1e-9)
    high = min(highcut / nyq, 0.999999)
    if high <= low:
        raise ValueError(f"Filtro non valido: low={lowcut}Hz high={highcut}Hz fs={fs}Hz")
    return signal.butter(order, [low, high], btype="bandpass", output="sos")


def bandpass_filtfilt(x, fs, band_hz, order=4):
    sos = butter_bandpass_sos(band_hz[0], band_hz[1], fs, order=order)
    return signal.sosfiltfilt(sos, x)


def estimate_lag_xcorr(x, y, fs, max_lag_sec):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    n = min(len(x), len(y))
    if n < 10:
        return 0, np.nan

    x = x[:n] - np.mean(x[:n])
    y = y[:n] - np.mean(y[:n])

    max_lag = int(round(max_lag_sec * fs))
    if max_lag < 1:
        return 0, np.nan

    corr = signal.correlate(y, x, mode="full", method="auto")
    lags = signal.correlation_lags(len(y), len(x), mode="full")

    mask = (lags >= -max_lag) & (lags <= max_lag)
    corr = corr[mask]
    lags = lags[mask]

    denom = (np.std(x) * np.std(y) * n)
    if denom <= 0:
        return 0, np.nan

    corrn = corr / denom
    k = int(np.nanargmax(corrn))
    return int(lags[k]), float(corrn[k])


def apply_lag(x, y, lag_samples):
    x = np.asarray(x)
    y = np.asarray(y)
    if lag_samples == 0:
        n = min(len(x), len(y))
        return x[:n], y[:n]

    if lag_samples > 0:
        y2 = y[lag_samples:]
        n = min(len(x), len(y2))
        return x[:n], y2[:n]

    lag = abs(lag_samples)
    x2 = x[lag:]
    n = min(len(x2), len(y))
    return x2[:n], y[:n]


def safe_nperseg(nperseg, n):
    if n < 16:
        return max(8, n)
    return int(min(nperseg, max(16, n // 2)))


def _welch_psd(x, fs, nperseg, window, noverlap_frac):
    f, Pxx = signal.welch(
        x,
        fs=fs,
        window=window,
        nperseg=nperseg,
        noverlap=int(round(nperseg * noverlap_frac)),
        detrend="constant",
        scaling="density",
    )
    return f, Pxx


def _csd(x, y, fs, nperseg, window, noverlap_frac):
    f, Pxy = signal.csd(
        x,
        y,
        fs=fs,
        window=window,
        nperseg=nperseg,
        noverlap=int(round(nperseg * noverlap_frac)),
        detrend="constant",
        scaling="density",
    )
    return f, Pxy


def compute_global_spectra_welch(x, y, fs, welch_cfg: dict):
    """
    PATCH: Pxy complesso interpolato correttamente (Re/Im separati).
    """
    n = min(len(x), len(y))
    nps = safe_nperseg(int(welch_cfg.get("nperseg", 1024)), n)
    window = str(welch_cfg.get("window", "hann"))
    noverlap_frac = float(welch_cfg.get("noverlap_frac", 0.5))

    f_coh, Cxy = signal.coherence(x, y, fs=fs, nperseg=nps)

    f_psd_x, Pxx = _welch_psd(x, fs, nps, window, noverlap_frac)
    f_psd_y, Pyy = _welch_psd(y, fs, nps, window, noverlap_frac)
    f_csd, Pxy = _csd(x, y, fs, nps, window, noverlap_frac)

    f = f_psd_x

    if not np.array_equal(f_psd_x, f_psd_y):
        Pyy = np.interp(f, f_psd_y, Pyy)

    if not np.array_equal(f_psd_x, f_csd):
        Pxy = np.interp(f, f_csd, Pxy.real) + 1j * np.interp(f, f_csd, Pxy.imag)

    if not np.array_equal(f_coh, f):
        Cxy = np.interp(f, f_coh, Cxy)

    eps = 1e-30
    H1 = Pxy / np.maximum(Pxx, eps)
    H2 = Pyy / np.maximum(np.conj(Pxy), eps)
    amp_ratio = Pyy / np.maximum(Pxx, eps)

    return f, Cxy, Pxx, Pyy, H1, H2, amp_ratio, nps


# -------------------- Multitaper PSD (Thomson) --------------------

def multitaper_psd_thomson_density(x, fs, NW=3.5, Kmax=None, weighting="eigs", detrend_mean=True):
    x = np.asarray(x, dtype=float)
    if detrend_mean:
        x = x - np.mean(x)

    n = x.size
    if n < 16:
        raise ValueError("Segnale troppo corto per Multitaper.")

    if Kmax is None:
        Kmax = int(np.floor(2 * NW - 1))
        Kmax = max(Kmax, 1)

    tapers, eigs = signal.windows.dpss(n, NW, Kmax=Kmax, return_ratios=True)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)

    Sk = np.fft.rfft(tapers * x[None, :], axis=1)
    Pk = np.abs(Sk) ** 2

    taper_power = np.sum(tapers**2, axis=1)
    denom = fs * taper_power[:, None]
    Pk = Pk / denom

    if Pk.shape[1] > 2:
        Pk[:, 1:-1] *= 2.0
    elif Pk.shape[1] == 2:
        Pk[:, 1] *= 2.0

    weighting = str(weighting or "eigs").lower().strip()
    if weighting == "eigs":
        w = np.asarray(eigs, float)
        w = w / np.sum(w)
    else:
        w = np.ones(Kmax, dtype=float) / Kmax

    P = np.sum(Pk * w[:, None], axis=0)
    return freqs, P


def compute_psd_multitaper(x, y, fs, mt_cfg: dict):
    NW = float(mt_cfg.get("nw", 3.5))
    Kmax = mt_cfg.get("kmax", None)
    Kmax = None if Kmax in (None, "null") else int(Kmax)
    weighting = str(mt_cfg.get("weighting", "eigs"))

    f1, Pxx = multitaper_psd_thomson_density(x, fs, NW=NW, Kmax=Kmax, weighting=weighting)
    f2, Pyy = multitaper_psd_thomson_density(y, fs, NW=NW, Kmax=Kmax, weighting=weighting)

    if not np.array_equal(f1, f2):
        Pyy = np.interp(f1, f2, Pyy, left=np.nan, right=np.nan)

    eps = 1e-30
    ratio = Pyy / np.maximum(Pxx, eps)
    return f1, Pxx, Pyy, ratio


def compute_windowed_metrics(x, y, fs, bands_hz, window_sec, overlap, nperseg_coh, filter_order):
    window_samples = int(round(window_sec * fs))
    step_samples = int(round(window_samples * (1 - overlap)))
    step_samples = max(step_samples, 1)

    if len(x) < window_samples or len(y) < window_samples:
        raise ValueError("Segnale troppo corto rispetto alla finestra scelta.")

    n_windows = (min(len(x), len(y)) - window_samples) // step_samples
    n_windows = max(n_windows, 0)

    times = []
    rms_x = []
    rms_y = []
    coh_by_band = {tuple(b): [] for b in bands_hz}
    corr_by_band = {tuple(b): [] for b in bands_hz}

    sos_by_band = {tuple(b): butter_bandpass_sos(b[0], b[1], fs, order=filter_order) for b in bands_hz}

    for i in range(n_windows):
        start = i * step_samples
        end = start + window_samples
        w1 = x[start:end]
        w2 = y[start:end]

        times.append(((start + end) / 2) / fs)
        rms_x.append(np.sqrt(np.mean(w1**2)))
        rms_y.append(np.sqrt(np.mean(w2**2)))

        try:
            nps = safe_nperseg(nperseg_coh, len(w1))
            f_win, Cxy_win = signal.coherence(w1, w2, fs=fs, nperseg=nps)
            for b in bands_hz:
                b = tuple(b)
                mask_b = (f_win >= b[0]) & (f_win <= b[1])
                coh_by_band[b].append(float(np.nanmean(Cxy_win[mask_b])) if np.any(mask_b) else 0.0)
        except Exception:
            for b in bands_hz:
                coh_by_band[tuple(b)].append(0.0)

        for b in bands_hz:
            b = tuple(b)
            try:
                w1f = signal.sosfiltfilt(sos_by_band[b], w1)
                w2f = signal.sosfiltfilt(sos_by_band[b], w2)
                corr_by_band[b].append(float(np.corrcoef(w1f, w2f)[0, 1]))
            except Exception:
                corr_by_band[b].append(0.0)

    return {
        "times_min": np.asarray(times) / 60.0,
        "rms_x": np.asarray(rms_x),
        "rms_y": np.asarray(rms_y),
        "coh_by_band": {b: np.nan_to_num(np.asarray(v), nan=0.0, posinf=0.0, neginf=0.0) for b, v in coh_by_band.items()},
        "corr_by_band": {b: np.nan_to_num(np.asarray(v), nan=0.0, posinf=0.0, neginf=0.0) for b, v in corr_by_band.items()},
        "n_windows": int(n_windows),
    }


def _trim_to_common_time(st_a, st_b):
    a = st_a[0]
    b = st_b[0]
    start = max(a.stats.starttime, b.stats.starttime)
    end = min(a.stats.endtime, b.stats.endtime)
    if start >= end:
        raise ValueError(f"Nessuna finestra temporale comune: start={start} end={end}")
    out_a = st_a.copy().trim(start, end, nearest_sample=False)
    out_b = st_b.copy().trim(start, end, nearest_sample=False)
    return out_a, out_b


def build_pairs_data(cfg: dict, streams: dict, counts_to_g: dict) -> dict:
    pair_map = (cfg.get("inputs", {}) or {}).get("pair_map", {}) or {}
    proc = (cfg.get("processing", {}) or {})
    align_cfg = (cfg.get("lag_alignment", {}) or {})
    io_cfg = (cfg.get("io", {}) or {})

    g0 = float(io_cfg.get("g0", 9.80665))
    output_units = str(io_cfg.get("output_units", "m/s^2")).lower()

    def counts_to_mps2(label: str) -> float:
        if label not in counts_to_g:
            raise KeyError(f"Manca fattore counts_to_g per {label}")
        return float(counts_to_g[label]) * g0

    def to_output_units_from_mps2(x_mps2: np.ndarray) -> np.ndarray:
        if output_units in ("g", "g0"):
            return x_mps2 / g0
        return x_mps2

    pairs_data = {}

    for comp, (lab1, lab2) in pair_map.items():
        st_base = streams[lab1]
        st_top = streams[lab2]

        st_base, st_top = _trim_to_common_time(st_base, st_top)

        fs_base = float(st_base[0].stats.sampling_rate)
        fs_top = float(st_top[0].stats.sampling_rate)
        if abs(fs_base - fs_top) > 1e-9:
            st_top = maybe_resample_to(st_top, fs_base)

        fs = float(st_base[0].stats.sampling_rate)

        x_counts = st_base[0].data.astype(np.float64)
        y_counts = st_top[0].data.astype(np.float64)

        x_mps2 = x_counts * counts_to_mps2(lab1)
        y_mps2 = y_counts * counts_to_mps2(lab2)

        x = to_output_units_from_mps2(x_mps2)
        y = to_output_units_from_mps2(y_mps2)

        n = min(len(x), len(y))
        x = x[:n]
        y = y[:n]

        lag_samp_used = 0
        lag_sec_used = 0.0
        lag_cc_used = np.nan
        align_band_used = None
        align_applied = False

        if bool(align_cfg.get("enabled", True)):
            try:
                filter_order = int(align_cfg.get("filter_order", 4))
                align_band_used = (align_cfg.get("align_band_hz_by_comp", {}) or {}).get(comp, (1.0, 15.0))
                xf = bandpass_filtfilt(x, fs, align_band_used, order=filter_order)
                yf = bandpass_filtfilt(y, fs, align_band_used, order=filter_order)

                lag_samp_est, lag_cc = estimate_lag_xcorr(xf, yf, fs, float(align_cfg.get("max_lag_sec", 0.5)))

                if np.isfinite(lag_cc) and (lag_cc >= float(align_cfg.get("min_xcorr_for_align", 0.5))):
                    x, y = apply_lag(x, y, lag_samp_est)
                    lag_samp_used = int(lag_samp_est)
                    lag_sec_used = float(lag_samp_est) / float(fs)
                    align_applied = True

                lag_cc_used = float(lag_cc) if lag_cc is not None else np.nan

                print(
                    f"[{comp}] align-band={float(align_band_used[0]):g}-{float(align_band_used[1]):g} Hz "
                    f"xcorr={lag_cc_used:.3f} applied={align_applied} "
                    f"lag={lag_samp_used} samp ({lag_sec_used:+.4f}s)"
                )
            except Exception as e:
                print(f"⚠️  Fine align fallito su {comp}: {e}")

        pairs_data[comp] = {
            "fs": fs,
            "x": x,
            "y": y,
            "lag_samp": lag_samp_used,
            "lag_sec": lag_sec_used,
            "lag_cc": lag_cc_used,
            "align_band": align_band_used,
            "align_applied": align_applied,
            "labels": (lab1, lab2),
        }

    horiz = (proc.get("horizontal_combined", {}) or {})
    if bool(horiz.get("enabled", False)) and ("N" in pairs_data) and ("E" in pairs_data):
        fsN = pairs_data["N"]["fs"]
        fsE = pairs_data["E"]["fs"]
        if abs(fsN - fsE) < 1e-9:
            n = min(
                len(pairs_data["N"]["x"]), len(pairs_data["E"]["x"]),
                len(pairs_data["N"]["y"]), len(pairs_data["E"]["y"])
            )
            Nx, Ex = pairs_data["N"]["x"][:n], pairs_data["E"]["x"][:n]
            Ny, Ey = pairs_data["N"]["y"][:n], pairs_data["E"]["y"][:n]
            method = str(horiz.get("method", "rms")).lower()
            if method == "sum":
                Hx = Nx + Ex
                Hy = Ny + Ey
            else:
                Hx = np.sqrt(Nx**2 + Ex**2)
                Hy = np.sqrt(Ny**2 + Ey**2)

            pairs_data["H"] = {
                "fs": fsN,
                "x": Hx,
                "y": Hy,
                "lag_samp": 0,
                "lag_sec": 0.0,
                "lag_cc": np.nan,
                "align_band": None,
                "align_applied": False,
                "labels": ("H1", "H2"),
            }

    return pairs_data