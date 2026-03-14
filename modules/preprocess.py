import numpy as np
from obspy import UTCDateTime
from scipy import signal


def detrend_stream(st):
    st = st.copy()
    st.detrend("linear")
    st.detrend("demean")
    return st


def maybe_resample_to(st, fs_target: float):
    fs = float(st[0].stats.sampling_rate)
    if abs(fs - fs_target) < 1e-9:
        return st
    out = st.copy()
    out.resample(fs_target)
    return out


def _butter_sos(filter_type: str, fs: float, order: int, fmin: float | None, fmax: float | None):
    ftype = str(filter_type or "").lower().strip()
    nyq = 0.5 * float(fs)

    if ftype == "highpass":
        if fmin is None:
            raise ValueError("highpass richiede fmin")
        wn = max(float(fmin) / nyq, 1e-9)
        return signal.butter(int(order), wn, btype="highpass", output="sos")

    if ftype == "lowpass":
        if fmax is None:
            raise ValueError("lowpass richiede fmax")
        wn = min(float(fmax) / nyq, 0.999999)
        return signal.butter(int(order), wn, btype="lowpass", output="sos")

    if fmin is None or fmax is None:
        raise ValueError("bandpass richiede fmin e fmax")
    low = max(float(fmin) / nyq, 1e-9)
    high = min(float(fmax) / nyq, 0.999999)
    if high <= low:
        raise ValueError(f"Filtro bandpass non valido: fmin={fmin} fmax={fmax} fs={fs}")
    return signal.butter(int(order), [low, high], btype="bandpass", output="sos")


def _component_from_label(label: str) -> str | None:
    if not label:
        return None
    s = str(label).strip().upper()
    if s.startswith(("Z", "N", "E")):
        return s[0]
    if s.endswith(("Z", "N", "E")):
        return s[-1]
    return None


def maybe_filter_stream(cfg: dict, st, label: str | None = None):
    proc = (cfg.get("processing", {}) or {})
    fc_global = (proc.get("filter", {}) or {})

    if not bool(fc_global.get("enabled", False)):
        return st

    comp = _component_from_label(label)
    fc = fc_global

    by_comp = (fc_global.get("by_comp", {}) or {})
    if comp in ("Z", "N", "E"):
        fc_c = (by_comp.get(comp, {}) or {})
        if bool(fc_c.get("enabled", False)):
            fc = fc_c

    st = st.copy()
    ftype = str(fc.get("type", "bandpass"))
    order = int(fc.get("order", 4))
    fmin = fc.get("fmin", None)
    fmax = fc.get("fmax", None)

    for tr in st:
        fs = float(tr.stats.sampling_rate)
        sos = _butter_sos(ftype, fs, order, fmin, fmax)
        x = np.asarray(tr.data, dtype=np.float64)
        if x.size < max(16, order * 6):
            continue
        try:
            tr.data = signal.sosfiltfilt(sos, x).astype(x.dtype, copy=False)
        except Exception:
            pass

    return st


def _parse_pick_time_utc(pick_time_utc: str) -> UTCDateTime:
    return UTCDateTime(str(pick_time_utc).strip())


def _stream_time_bounds_str(st) -> str:
    if st is None or len(st) == 0:
        return "EMPTY"
    tr = st[0]
    return f"{tr.stats.starttime} .. {tr.stats.endtime} (sr={tr.stats.sampling_rate}, npts={tr.stats.npts})"


def apply_pick_window_to_streams(cfg: dict, streams: dict) -> dict:
    ev = cfg.get("event", {}) or {}
    fa = (ev.get("first_arrival", {}) or {})
    if not bool(fa.get("enabled", False)):
        return streams

    pick_time_utc = fa.get("pick_time_utc", None)
    if not pick_time_utc:
        raise ValueError("event.first_arrival.enabled=true ma pick_time_utc è nullo")

    win = fa.get("window", {}) or {}
    pre = float(win.get("pre_sec", 0.0))
    post = float(win.get("post_sec", 0.0))
    if pre < 0 or post <= 0:
        raise ValueError("event.first_arrival.window non valida (pre>=0, post>0)")

    pick = _parse_pick_time_utc(pick_time_utc)
    t0 = pick - pre
    t1 = pick + post

    print(f"[PICK] pick_time_utc={pick}  window=[-{pre:.2f}s, +{post:.2f}s] => trim {t0} .. {t1}")

    out = {}
    errors = []
    for lab, st in streams.items():
        before = _stream_time_bounds_str(st)
        st2 = st.copy().trim(t0, t1, nearest_sample=False)
        after = _stream_time_bounds_str(st2)
        print(f"[PICK] {lab}: before {before} | after {after}")

        if st2 is None or len(st2) == 0:
            errors.append(f"{lab}: became EMPTY after trim. Before={before}. Requested trim={t0}..{t1}")
        out[lab] = st2

    if errors:
        msg = "Pick-window trimming produced empty streams:\n- " + "\n- ".join(errors)
        raise ValueError(msg)

    return out