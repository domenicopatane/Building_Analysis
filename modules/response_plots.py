"""
Utility per:
- plot delle tracce nel tempo (base vs top)
- calcolo e plot degli spettri di risposta (SD, SV, SA, PSA) con Newmark-beta
- figure riepilogo "tipo immagine" (SA + tracce Z/N/E + Husid) per BASE e TOP

Dipendenze: numpy, matplotlib (nessuna libreria esterna). SciPy non è necessaria qui.

Note:
- L'input acc(t) deve essere un'accelerazione al suolo (tipicamente in m/s^2).
- SA restituita è l'accelerazione RELATIVA dell'SDOF (u_ddot).
- PSA = (omega^2) * SD (pseudo-accelerazione), spesso usata in ingegneria sismica.
"""

from __future__ import annotations

import os
import numpy as np
import matplotlib.pyplot as plt


G0 = 9.80665


def _ensure_dir(path: str):
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def _as_float_array(x):
    return np.asarray(x, dtype=float)


def _common_length_xyz(pairs_data: dict, comps=("Z", "N", "E")) -> int:
    n_list = []
    for c in comps:
        if c not in pairs_data:
            continue
        n_list.append(min(len(pairs_data[c]["x"]), len(pairs_data[c]["y"])))
    if not n_list:
        return 0
    return int(min(n_list))


def plot_time_traces(
    pairs_data: dict,
    out_dir: str | None = None,
    prefix: str = "traces",
    save: bool = True,
    show: bool = False,
    max_seconds: float | None = None,
):
    if out_dir:
        _ensure_dir(out_dir)

    for comp, d in pairs_data.items():
        fs = float(d["fs"])
        x = _as_float_array(d["x"])
        y = _as_float_array(d["y"])

        n = min(len(x), len(y))
        x = x[:n]
        y = y[:n]

        if max_seconds is not None:
            nmax = int(round(max_seconds * fs))
            nmax = max(1, min(nmax, n))
            x = x[:nmax]
            y = y[:nmax]
            n = nmax

        t = np.arange(n) / fs

        fig, ax = plt.subplots(1, 1, figsize=(14, 4))
        ax.plot(t, x, lw=1.0, label=f"{comp} base")
        ax.plot(t, y, lw=1.0, alpha=0.85, label=f"{comp} top")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Acceleration (input units)")
        ax.set_title(f"Time traces — {comp}")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()

        if save and out_dir:
            fp = os.path.join(out_dir, f"{prefix}_{comp}.png")
            fig.savefig(fp, dpi=200, bbox_inches="tight")
            print(f"✅ Saved: {fp}")

        if show:
            plt.show()
        else:
            plt.close(fig)


def plot_time_traces_all_components(
    pairs_data: dict,
    out_dir: str | None = None,
    prefix: str = "traces_all",
    save: bool = True,
    show: bool = False,
    max_seconds: float | None = None,
    comps_order: tuple[str, ...] = ("Z", "N", "E", "H"),
):
    if out_dir:
        _ensure_dir(out_dir)

    comps = [c for c in comps_order if c in pairs_data]
    if len(comps) == 0:
        return

    fs = float(pairs_data[comps[0]]["fs"])
    dt = 1.0 / fs

    n = min(min(len(pairs_data[c]["x"]), len(pairs_data[c]["y"])) for c in comps)
    if max_seconds is not None:
        nmax = int(round(max_seconds * fs))
        n = max(1, min(n, nmax))

    t = np.arange(n) * dt

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(16, 5), sharex=True, sharey=True)
    colors = {"Z": "k", "N": "tab:blue", "E": "tab:red", "H": "tab:green"}

    for comp in comps:
        x = _as_float_array(pairs_data[comp]["x"][:n])
        y = _as_float_array(pairs_data[comp]["y"][:n])
        col = colors.get(comp, None)
        axL.plot(t, x, lw=1.0, alpha=0.9, color=col, label=comp)
        axR.plot(t, y, lw=1.0, alpha=0.9, color=col, label=comp)

    axL.set_title("BASE — all components (overlay)")
    axR.set_title("TOP — all components (overlay)")
    for ax in (axL, axR):
        ax.set_xlabel("Time (s)")
        ax.grid(True, alpha=0.3)
        ax.legend(title="Comp", fontsize=9)

    axL.set_ylabel("Acceleration (input units)")
    fig.suptitle("Time traces overview — Base vs Top", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0.02, 1, 0.94])

    if save and out_dir:
        fp = os.path.join(out_dir, f"{prefix}.png")
        fig.savefig(fp, dpi=200, bbox_inches="tight")
        print(f"✅ Saved: {fp}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def response_spectrum_newmark(
    acc: np.ndarray,
    dt: float,
    periods: np.ndarray,
    damping: float = 0.05,
):
    acc = _as_float_array(acc)
    periods = _as_float_array(periods)

    beta = 1.0 / 4.0
    gamma = 1.0 / 2.0
    m = 1.0

    SD = np.zeros_like(periods)
    SV = np.zeros_like(periods)
    SA = np.zeros_like(periods)
    PSA = np.zeros_like(periods)

    p = -m * acc

    for i, T in enumerate(periods):
        if not np.isfinite(T) or T <= 0:
            SD[i] = SV[i] = SA[i] = PSA[i] = np.nan
            continue

        w = 2.0 * np.pi / T
        k = m * w * w
        c = 2.0 * damping * m * w

        a0 = 1.0 / (beta * dt * dt)
        a1 = gamma / (beta * dt)
        a2 = 1.0 / (beta * dt)
        a3 = 1.0 / (2.0 * beta) - 1.0
        a4 = gamma / beta - 1.0
        a5 = dt * (gamma / (2.0 * beta) - 1.0)

        k_eff = k + a0 * m + a1 * c

        u = ud = udd = 0.0
        u_max = ud_max = udd_max = 0.0

        for n in range(len(p)):
            p_eff = (
                p[n]
                + m * (a0 * u + a2 * ud + a3 * udd)
                + c * (a1 * u + a4 * ud + a5 * udd)
            )

            u_new = p_eff / k_eff
            udd_new = a0 * (u_new - u) - a2 * ud - a3 * udd
            ud_new = ud + dt * ((1.0 - gamma) * udd + gamma * udd_new)

            u, ud, udd = u_new, ud_new, udd_new

            u_max = max(u_max, abs(u))
            ud_max = max(ud_max, abs(ud))
            udd_max = max(udd_max, abs(udd))

        SD[i] = u_max
        SV[i] = ud_max
        SA[i] = udd_max
        PSA[i] = (w * w) * u_max

    return SD, SV, SA, PSA


def _unit_scale_for_acc(unit: str) -> tuple[float, str, str]:
    """
    Returns (scale, unit_label_for_axis, unit_tag_for_filename)
    converting from m/s^2 to the requested plotting unit.
    """
    u = unit.strip().lower()
    if u in ("g", "g0"):
        return 1.0 / G0, "g", "g"
    if u in ("m/s^2", "m/s2", "mps2"):
        return 1.0, "m/s²", "mps2"
    raise ValueError(f"Unità accelerazione non supportata: {unit}")


def plot_response_spectra(
    pairs_data: dict,
    out_dir: str | None = None,
    prefix: str = "rs",
    save: bool = True,
    show: bool = False,
    damping: float = 0.05,
    periods: np.ndarray | None = None,
    kind: str = "PSA",  # "PSA", "SA", "SV", "SD"
    y_label: str | None = None,
    units_acc: str = "m/s^2",
    units_vel: str = "m/s",
    units_disp: str = "m",
    save_kinds: tuple[str, ...] | None = None,
    save_units: tuple[str, ...] | None = None,
):
    """
    Plotta response spectrum per base e top, per ogni componente in pairs_data.

    PATCH:
    - Se save_kinds è passato, salva per tutti i kind richiesti.
    - Se save_units è passato (solo per SA/PSA), salva per tutte le unità richieste (g e/o m/s²).
    - Se non passi nulla, resta compatibile: produce un solo plot (kind + units_acc).
    """
    if out_dir:
        _ensure_dir(out_dir)

    if periods is None:
        periods = np.logspace(np.log10(0.05), np.log10(10.0), 120)

    kind = kind.upper().strip()
    kinds_to_do = tuple(k.upper().strip() for k in save_kinds) if save_kinds else (kind,)
    units_to_do = tuple(save_units) if save_units else (units_acc,)

    for comp, d in pairs_data.items():
        fs = float(d["fs"])
        dt = 1.0 / fs
        x = _as_float_array(d["x"])
        y = _as_float_array(d["y"])

        n = min(len(x), len(y))
        x = x[:n]
        y = y[:n]

        SDx, SVx, SAx, PSAx = response_spectrum_newmark(x, dt, periods, damping=damping)
        SDy, SVy, SAy, PSAy = response_spectrum_newmark(y, dt, periods, damping=damping)

        for knd in kinds_to_do:
            if knd == "PSA":
                bx0, ty0 = PSAx, PSAy
                base_ylabel = y_label or "PSA"
                is_acc = True
            elif knd == "SA":
                bx0, ty0 = SAx, SAy
                base_ylabel = y_label or "SA (relative)"
                is_acc = True
            elif knd == "SV":
                bx0, ty0 = SVx, SVy
                base_ylabel = y_label or "SV (relative)"
                is_acc = False
            elif knd == "SD":
                bx0, ty0 = SDx, SDy
                base_ylabel = y_label or "SD (relative)"
                is_acc = False
            else:
                raise ValueError(f"kind non riconosciuto: {knd}")

            for unit in units_to_do:
                if is_acc:
                    scale, unit_label, unit_tag = _unit_scale_for_acc(unit)
                    bx = bx0 * scale
                    ty = ty0 * scale
                    ylabel = f"{base_ylabel} [{unit_label}]"
                else:
                    bx, ty = bx0, ty0
                    unit_tag = "sv" if knd == "SV" else "sd"
                    if knd == "SV":
                        ylabel = f"{base_ylabel} [{units_vel}]"
                    else:
                        ylabel = f"{base_ylabel} [{units_disp}]"

                fig, ax = plt.subplots(1, 1, figsize=(7.5, 5))
                ax.loglog(periods, bx, lw=2.0, label=f"{comp} base")
                ax.loglog(periods, ty, lw=2.0, alpha=0.85, label=f"{comp} top")
                ax.grid(True, which="both", alpha=0.25)
                ax.set_xlabel("Period T (s)")
                ax.set_ylabel(ylabel)
                ax.set_title(f"Response spectrum ({knd}) — {comp} — ζ={damping*100:.1f}%")
                ax.legend()
                fig.tight_layout()

                if save and out_dir:
                    fp = os.path.join(out_dir, f"{prefix}_{knd}_{comp}_{unit_tag}.png")
                    fig.savefig(fp, dpi=200, bbox_inches="tight")
                    print(f"✅ Saved: {fp}")

                if show and (knd == kinds_to_do[-1]) and (unit == units_to_do[-1]):
                    plt.show()
                else:
                    plt.close(fig)


# -------------------------
# figure "tipo immagine"
# -------------------------

def _husid_normalized(acc: np.ndarray, dt: float) -> np.ndarray:
    a2 = np.asarray(acc, float) ** 2
    ia = np.cumsum(a2) * dt
    if ia.size == 0:
        return ia
    denom = ia[-1]
    if denom <= 0:
        return np.zeros_like(ia)
    return ia / denom


def _time_at_husid_fraction(husid: np.ndarray, t: np.ndarray, frac: float) -> float:
    if husid.size == 0:
        return float("nan")
    frac = float(frac)
    if frac <= 0:
        return float(t[0])
    if frac >= 1:
        return float(t[-1])

    idx = np.searchsorted(husid, frac, side="left")
    if idx <= 0:
        return float(t[0])
    if idx >= husid.size:
        return float(t[-1])

    x0, x1 = float(husid[idx - 1]), float(husid[idx])
    t0, t1 = float(t[idx - 1]), float(t[idx])
    if x1 == x0:
        return t1
    return t0 + (frac - x0) * (t1 - t0) / (x1 - x0)


def _annotate_vertical_time_mark(ax, x, text, color="red", y_frac=0.02):
    """
    Scrive una label alla base della linea tratteggiata, in coordinate dati.
    y_frac: frazione dell'altezza dell'asse dal basso.
    """
    y0, y1 = ax.get_ylim()
    ytxt = y0 + y_frac * (y1 - y0)
    ax.text(x, ytxt, text, color=color, fontsize=9, ha="center", va="bottom")


def plot_station_summary_like_image(
    pairs_data: dict,
    out_dir: str | None = None,
    prefix: str = "station_summary",
    save: bool = True,
    show: bool = False,
    station_name: str = "Station",
    damping: float = 0.05,
    periods: np.ndarray | None = None,
    rs_kind: str = "SA",     # "SA" o "PSA"
    sa_units: str = "g",     # "g" oppure "m/s^2"
    max_seconds: float | None = 20.0,
    draw_husid: bool = True,
    comps: tuple[str, ...] = ("Z", "N", "E"),
    mark_max_peak: bool = True,
    peak_on_component: str | None = None,
    husid_onset_frac: float = 0.05,
    husid_frac_75: float = 0.75,
    husid_frac_90: float = 0.90,
    draw_t_marks: bool = True,
):
    """
    Figure riepilogo "tipo immagine" per BASE e TOP.

    Include:
    - Response spectrum (SA o PSA) per Z/N/E
    - Tracce nel tempo per Z/N/E (con Husid normalizzata sovrapposta)
    - Linee T5 / T75 / T90 (da Husid)
    - Marker del massimo sullo spettro
    - PGA per componente (sulla finestra plottata) in basso a destra del subplot time history
    """
    if out_dir:
        _ensure_dir(out_dir)

    if periods is None:
        periods = np.logspace(np.log10(0.02), np.log10(3.0), 140)

    rs_kind = rs_kind.upper().strip()
    if rs_kind not in ("SA", "PSA"):
        raise ValueError("rs_kind deve essere 'SA' o 'PSA'")

    sa_units = sa_units.lower().strip()
    if sa_units not in ("g", "m/s^2", "m/s2"):
        raise ValueError("sa_units deve essere 'g' o 'm/s^2'")

    comps_avail = [c for c in comps if c in pairs_data]
    if len(comps_avail) == 0:
        print("⚠️ plot_station_summary_like_image: nessuna componente disponibile tra", comps)
        return

    fs = float(pairs_data[comps_avail[0]]["fs"])
    dt = 1.0 / fs

    n = _common_length_xyz(pairs_data, comps=comps_avail)
    if n <= 0:
        print("⚠️ plot_station_summary_like_image: lunghezza segnale nulla.")
        return

    if max_seconds is not None:
        nmax = int(round(max_seconds * fs))
        n = max(1, min(n, nmax))

    t = np.arange(n) * dt

    def _fmt_unit_text(yunit: str) -> str:
        return "g" if yunit == "g" else "m/s²"

    def _make_one(level: str, key: str):
        acc_ts = {c: _as_float_array(pairs_data[c][key][:n]) for c in comps_avail}

        rs = {}
        for c in comps_avail:
            _, _, SA, PSA = response_spectrum_newmark(acc_ts[c], dt, periods, damping=damping)
            rs[c] = SA if rs_kind == "SA" else PSA

        if sa_units == "g":
            scale = 1.0 / G0
            yunit = "g"
        else:
            scale = 1.0
            yunit = "m/s²"

        fig = plt.figure(figsize=(14.5, 5.5))
        gs = fig.add_gridspec(3, 2, width_ratios=[1.05, 1.25], wspace=0.28, hspace=0.25)

        ax_spec = fig.add_subplot(gs[:, 0])

        colors = {"Z": "k", "N": "tab:blue", "E": "tab:red"}
        labels = {"Z": "Z", "N": "N", "E": "E"}

        for c in comps_avail:
            ax_spec.plot(periods, rs[c] * scale, lw=2.0, color=colors.get(c, None), label=labels.get(c, c))

        ax_spec.set_xlabel("Period (s)")
        ax_spec.set_ylabel(f"Spectral acceleration ({rs_kind}) [{_fmt_unit_text(yunit)}]")
        ax_spec.set_title(f"{station_name} — {level} (Tmax={periods.max():.2f}s)")
        ax_spec.grid(True, alpha=0.3)
        ax_spec.legend(loc="upper right", fontsize=9)
        ax_spec.set_xlim([periods.min(), periods.max()])

        if mark_max_peak:
            if peak_on_component is not None and peak_on_component in rs:
                ycurve = np.asarray(rs[peak_on_component], float) * scale
                idx = int(np.nanargmax(ycurve))
                ypk = float(ycurve[idx])
            else:
                allY = np.vstack([np.asarray(rs[c], float) * scale for c in comps_avail])
                idx_flat = int(np.nanargmax(allY))
                idx = idx_flat % allY.shape[1]
                ypk = float(np.nanmax(allY[:, idx]))

            Tpk = float(periods[idx])
            ax_spec.plot([Tpk], [ypk], "o", ms=8, mfc="none", mec="red", mew=2.0, zorder=10)
            ax_spec.annotate(
                f"T={Tpk:.3f}s\n{rs_kind}={ypk:.4g} {_fmt_unit_text(yunit)}",
                xy=(Tpk, ypk),
                xytext=(18, 0),
                textcoords="offset points",
                fontsize=10,
                ha="left",
                va="center",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.5", alpha=0.9),
            )

        for i, c in enumerate(comps_avail[:3]):
            ax = fig.add_subplot(gs[i, 1])
            ax.plot(t, acc_ts[c] * scale, lw=1.2, color=colors.get(c, None), label=labels.get(c, c))
            ax.set_xlim([t[0], t[-1]])
            ax.grid(True, alpha=0.25)
            ax.set_ylabel(f"Acc. [{_fmt_unit_text(yunit)}]")

            if i == 0:
                ax.set_title("Time histories")
            if i < 2:
                ax.set_xticklabels([])
            else:
                ax.set_xlabel("Time (s)")

            ax.legend(loc="upper right", fontsize=9)

            # PGA in basso a destra (sempre)
            pga_val = float(np.nanmax(np.abs(acc_ts[c] * scale))) if acc_ts[c].size else float("nan")
            ax.text(
                0.99, 0.06,
                f"PGA = {pga_val:.4g} {_fmt_unit_text(yunit)}",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=10,
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.6", alpha=0.85),
                zorder=10,
            )

            if draw_husid:
                hus = _husid_normalized(acc_ts[c], dt)
                ax2 = ax.twinx()
                ax2.plot(t, hus, color="tab:green", lw=1.6, alpha=0.95)
                ax2.set_ylim([0, 1.02])
                ax2.set_ylabel("Normalized Husid")
                ax2.set_yticks([0.0, 0.5, 1.0])

                if draw_t_marks:
                    t5 = _time_at_husid_fraction(hus, t, husid_onset_frac)
                    t75 = _time_at_husid_fraction(hus, t, husid_frac_75)
                    t90 = _time_at_husid_fraction(hus, t, husid_frac_90)

                    ax.axvline(t5, color="0.4", ls="--", lw=1.0, alpha=0.9)
                    ax.axvline(t75, color="0.4", ls="--", lw=1.0, alpha=0.9)
                    ax.axvline(t90, color="0.4", ls="--", lw=1.0, alpha=0.9)

                    _annotate_vertical_time_mark(ax, t5, "T5", color="red", y_frac=0.02)
                    _annotate_vertical_time_mark(ax, t75, "T75", color="red", y_frac=0.02)
                    _annotate_vertical_time_mark(ax, t90, "T90", color="red", y_frac=0.02)

        fig.tight_layout()

        if save and out_dir:
            safe_unit = "g" if yunit == "g" else "mps2"
            fp = os.path.join(out_dir, f"{prefix}_{level}_{rs_kind}_{safe_unit}.png")
            fig.savefig(fp, dpi=220, bbox_inches="tight")
            print(f"✅ Saved: {fp}")

        if show:
            plt.show()
        else:
            plt.close(fig)

    _make_one(level="BASE", key="x")
    _make_one(level="TOP", key="y")
# ----------------------------------------parte per Tabella CSV ----------------------------------------
import csv
from datetime import datetime


def _cumtrapz_np(y: np.ndarray, dt: float) -> np.ndarray:
    """Integrazione cumulativa trapezoidale (numpy only), stessa lunghezza di y."""
    y = np.asarray(y, float)
    if y.size == 0:
        return y
    out = np.zeros_like(y)
    out[1:] = np.cumsum(0.5 * (y[1:] + y[:-1]) * dt)
    return out


def _remove_linear_trend(y: np.ndarray) -> np.ndarray:
    """Rimuove trend lineare via least squares: y ~ a*t + b."""
    y = np.asarray(y, float)
    n = y.size
    if n < 2:
        return y
    t = np.arange(n, dtype=float)
    A = np.column_stack([t, np.ones(n)])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    a, b = coef
    return y - (a * t + b)


def _integrate_acc_to_vel_disp(acc_mps2: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Integra accelerazione -> velocità -> spostamento.
    Per limitare drift: rimuove media su acc, poi detrend lineare su v e d.
    """
    a = np.asarray(acc_mps2, float)
    if a.size == 0:
        return a, a

    a0 = a - np.nanmean(a)  # baseline semplice
    v = _cumtrapz_np(a0, dt)
    v = _remove_linear_trend(v)
    d = _cumtrapz_np(v, dt)
    d = _remove_linear_trend(d)
    return v, d


def _psa_at_periods(acc: np.ndarray, dt: float, periods: np.ndarray, damping: float, target_T: float) -> float:
    """
    Calcola PSA(Ttarget) interpolando (log-log) dallo spettro PSA calcolato su `periods`.
    acc deve essere in m/s^2.
    Restituisce PSA in m/s^2.
    """
    periods = np.asarray(periods, float)
    _, _, _, PSA = response_spectrum_newmark(acc, dt, periods, damping=damping)  # PSA in m/s^2

    T = float(target_T)
    if periods.size < 2 or not np.isfinite(T) or T <= 0:
        return float("nan")

    if T <= periods.min():
        return float(PSA[np.nanargmin(periods)])
    if T >= periods.max():
        return float(PSA[np.nanargmax(periods)])

    # log-log interp più stabile su spettri
    x = np.log(periods)
    y = np.log(np.maximum(np.asarray(PSA, float), 1e-30))
    yT = np.interp(np.log(T), x, y)
    return float(np.exp(yT))


def _fmt_dt_utc(utc_str: str | None) -> str:
    """
    Normalizza la stringa UTC nel CSV. Se non parseable, la restituisce com'è.
    """
    if not utc_str:
        return ""
    s = str(utc_str).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # millisecondi
        except Exception:
            pass
    return s


def export_station_metrics_csv(
    pairs_data: dict,
    out_csv_path: str,
    station_name: str,
    origin_time_utc: str | None = None,
    comps: tuple[str, ...] = ("Z", "N", "E"),
    which: str = "BOTH",  # "BASE" | "TOP" | "BOTH"
    damping: float = 0.05,
    periods: np.ndarray | None = None,
    psa_periods: tuple[float, float, float] = (0.3, 1.0, 3.0),
    husid_frac_75: float = 0.75,
    husid_frac_90: float = 0.90,
    acc_input_units: str = "m/s^2",
    base_station_name: str | None = None,
    top_station_name: str | None = None,
):
    """
    Esporta CSV con righe per canale e per livello (BASE/TOP).

    Colonne:
    P-Pick Time [UTC], Station, Level, Channel,
    PGA (g), PGA (cm/s^2), PGV (cm/s), PGD (cm),
    PSA03 (g), PSA1 (g), PSA3 (g),
    T75 (s), T90 (s)
    """
    import csv

    if periods is None:
        periods = np.logspace(np.log10(0.02), np.log10(3.0), 140)

    which = which.upper().strip()
    if which not in ("BASE", "TOP", "BOTH"):
        raise ValueError("which deve essere 'BASE', 'TOP' o 'BOTH'")

    u = str(acc_input_units).lower().strip()
    to_mps2 = G0 if u in ("g", "g0") else 1.0

    levels = [("BASE", "x"), ("TOP", "y")] if which == "BOTH" else [(which, "x" if which == "BASE" else "y")]

    base_station_name = (base_station_name or "").strip() or station_name
    top_station_name = (top_station_name or "").strip() or station_name

    rows = []
    pick_fmt = _fmt_dt_utc(origin_time_utc)

    for level_name, key in levels:
        station_for_level = base_station_name if level_name == "BASE" else top_station_name

        for c in comps:
            if c not in pairs_data:
                continue

            fs = float(pairs_data[c]["fs"])
            dt = 1.0 / fs

            a_in = _as_float_array(pairs_data[c][key])
            a_mps2 = a_in * to_mps2
            if a_mps2.size == 0:
                continue

            pga_mps2 = float(np.nanmax(np.abs(a_mps2)))
            pga_g = pga_mps2 / G0
            pga_cms2 = pga_mps2 * 100.0

            v_mps, d_m = _integrate_acc_to_vel_disp(a_mps2, dt)
            pgv_cms = float(np.nanmax(np.abs(v_mps))) * 100.0
            pgd_cm = float(np.nanmax(np.abs(d_m))) * 100.0

            psa_vals_g = []
            for Tt in psa_periods:
                psa_mps2 = _psa_at_periods(a_mps2, dt, periods, damping, target_T=float(Tt))
                psa_vals_g.append(psa_mps2 / G0)

            hus = _husid_normalized(a_mps2, dt)
            t = np.arange(a_mps2.size) * dt
            t75 = _time_at_husid_fraction(hus, t, float(husid_frac_75))
            t90 = _time_at_husid_fraction(hus, t, float(husid_frac_90))

            rows.append(
                {
                    "P-Pick Time [UTC]": pick_fmt,
                    "Station": station_for_level,
                    "Level": level_name,
                    "Channel": c,  # Z/N/E
                    "PGA (g)": pga_g,
                    "PGA (cm/s^2)": pga_cms2,
                    "PGV (cm/s)": pgv_cms,
                    "PGD (cm)": pgd_cm,
                    "PSA03 (g)": psa_vals_g[0] if len(psa_vals_g) > 0 else np.nan,
                    "PSA1 (g)": psa_vals_g[1] if len(psa_vals_g) > 1 else np.nan,
                    "PSA3 (g)": psa_vals_g[2] if len(psa_vals_g) > 2 else np.nan,
                    "T75 (s)": t75,
                    "T90 (s)": t90,
                }
            )

    fieldnames = [
        "P-Pick Time [UTC]",
        "Station",
        "Level",
        "Channel",
        "PGA (g)",
        "PGA (cm/s^2)",
        "PGV (cm/s)",
        "PGD (cm)",
        "PSA03 (g)",
        "PSA1 (g)",
        "PSA3 (g)",
        "T75 (s)",
        "T90 (s)",
    ]

    _ensure_dir(os.path.dirname(out_csv_path))

    with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"✅ CSV exported: {out_csv_path}")