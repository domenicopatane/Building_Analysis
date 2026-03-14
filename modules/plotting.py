import os
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

from .coherence_analysis import (
    compute_global_spectra_welch,
    compute_windowed_metrics,
    compute_psd_multitaper,
)


def _db10(x):
    x = np.asarray(x, float)
    x = np.where(x > 0, x, np.nan)
    return 10.0 * np.log10(x)


def _db20(x):
    x = np.asarray(x, float)
    x = np.where(np.isfinite(x) & (np.abs(x) > 0), x, np.nan)
    return 20.0 * np.log10(np.abs(x))


def _limit_freq(f, *arrays, fmax=60.0):
    f = np.asarray(f)
    mask = (f > 0) & (f <= fmax)
    outs = [f[mask]]
    for a in arrays:
        a = np.asarray(a)
        outs.append(a[mask])
    return outs


def _peaks_from_curve_db(f, y_db, search_band_hz, min_prom_db, min_distance_hz, max_n, qc_mask=None):
    f = np.asarray(f, float)
    y_db = np.asarray(y_db, float)
    if f.size == 0 or y_db.size == 0:
        return []

    m = (f >= search_band_hz[0]) & (f <= search_band_hz[1]) & np.isfinite(y_db)
    if qc_mask is not None:
        qc_mask = np.asarray(qc_mask, bool)
        if qc_mask.shape == y_db.shape:
            m = m & qc_mask

    f2 = f[m]
    y2 = y_db[m]
    if f2.size < 10:
        return []

    df = np.nanmedian(np.diff(f2))
    if not np.isfinite(df) or df <= 0:
        return []
    min_dist_samples = int(max(1, round(min_distance_hz / df)))

    peaks, props = signal.find_peaks(y2, prominence=min_prom_db, distance=min_dist_samples)
    if peaks.size == 0:
        return []

    order = np.argsort(y2[peaks])[::-1]
    peaks = peaks[order][:max_n]
    prom = props.get("prominences", np.full(peaks.shape, np.nan))[order][:max_n]

    out = []
    for i, p in enumerate(peaks):
        out.append({"freq_hz": float(f2[p]), "y_db": float(y2[p]), "prom_db": float(prom[i])})
    return out


def _draw_peaks(ax, peaks, color="k", y_offset_db=0.8, fontsize=8, fmt="{:.2f} Hz"):
    if not peaks:
        return
    for p in peaks:
        f0 = p["freq_hz"]
        y0 = p["y_db"]
        ax.plot([f0], [y0], marker="o", ms=5, color=color, zorder=6)
        ax.annotate(
            fmt.format(f0),
            xy=(f0, y0),
            xytext=(f0, y0 + y_offset_db),
            textcoords="data",
            fontsize=fontsize,
            color=color,
            ha="center",
            va="bottom",
            arrowprops=dict(arrowstyle="-", color=color, lw=0.8, alpha=0.7),
        )


def plot_component_results(cfg: dict, comp: str, pairs_data_comp: dict, figures_dir: str):
    proj = cfg.get("project", {}) or {}
    thresholds = cfg.get("thresholds", {}) or {}
    plot_cfg = cfg.get("plot", {}) or {}
    frf_cfg = (plot_cfg.get("frf", {}) or {})
    peak_cfg = cfg.get("peak_picking", {}) or {}
    welch_cfg = cfg.get("welch", {}) or {}
    mt_cfg = cfg.get("multitaper", {}) or {}

    base_name = str(proj.get("base_name", "BASE"))
    top_name = str(proj.get("top_name", "TOP"))
    out_prefix = str(proj.get("out_prefix", "coherence_building_3C"))

    coh_threshold = float(thresholds.get("coh_threshold", 0.7))
    corr_threshold = float(thresholds.get("corr_threshold", 0.5))

    save_fig = bool(plot_cfg.get("save_fig", True))
    plot_max_freq = float(plot_cfg.get("plot_max_freq", 60.0))

    frf_min_coh = float(frf_cfg.get("min_coh_to_plot", 0.6))
    frf_db_clip = tuple(frf_cfg.get("db_clip", [-80.0, 80.0]))

    label_fontsize = int(peak_cfg.get("label_fontsize", 8))

    x = pairs_data_comp["x"]
    y = pairs_data_comp["y"]
    fs = float(pairs_data_comp["fs"])

    welch_spec = compute_global_spectra_welch(x, y, fs, welch_cfg)
    f, Cxy, Pxx, Pyy, H1, H2, amp_ratio, nps = welch_spec

    fmax = min(plot_max_freq, fs * 0.5)
    f_w, coh_w, Pxx_w, Pyy_w, H1_w, H2_w, amp_w = _limit_freq(f, Cxy, Pxx, Pyy, H1, H2, amp_ratio, fmax=fmax)

    Pxx_w_db = _db10(Pxx_w)
    Pyy_w_db = _db10(Pyy_w)
    amp_w_db = _db10(amp_w)

    mask_frf = np.isfinite(coh_w) & (coh_w >= frf_min_coh)
    H1_w_db = _db20(np.where(mask_frf, H1_w, np.nan))
    H2_w_db = _db20(np.where(mask_frf, H2_w, np.nan))
    H1_w_db = np.clip(H1_w_db, frf_db_clip[0], frf_db_clip[1])
    H2_w_db = np.clip(H2_w_db, frf_db_clip[0], frf_db_clip[1])

    # Peaks (Welch)
    amp_cfg = (peak_cfg.get("amp", {}) or {})
    psd_cfg = (peak_cfg.get("psd_top", {}) or {})
    peaks_amp_w = []
    peaks_psdtop_w = []
    if bool(peak_cfg.get("enabled", True)):
        qc = np.isfinite(coh_w) & (coh_w >= float(amp_cfg.get("min_coh", 0.5)))
        peaks_amp_w = _peaks_from_curve_db(
            f_w, amp_w_db,
            search_band_hz=amp_cfg.get("search_band_hz", [0.5, 20.0]),
            min_prom_db=float(amp_cfg.get("min_prom_db", 1.5)),
            min_distance_hz=float(amp_cfg.get("min_distance_hz", 0.1)),
            max_n=int(amp_cfg.get("max_n", 5)),
            qc_mask=qc,
        )
        peaks_psdtop_w = _peaks_from_curve_db(
            f_w, Pyy_w_db,
            search_band_hz=psd_cfg.get("search_band_hz", [0.5, 20.0]),
            min_prom_db=float(psd_cfg.get("min_prom_db", 3.0)),
            min_distance_hz=float(psd_cfg.get("min_distance_hz", 0.3)),
            max_n=int(psd_cfg.get("max_n", 5)),
            qc_mask=None,
        )

    # Multitaper PSD + amp (optional)
    do_mt = bool(mt_cfg.get("enabled", False))
    mt_spec = None
    peaks_amp_mt = []
    peaks_psdtop_mt = []
    if do_mt:
        try:
            f_mt0, Pxx_mt0, Pyy_mt0, amp_mt0 = compute_psd_multitaper(x, y, fs, mt_cfg)
            f_mt, Pxx_mt, Pyy_mt, amp_mt = _limit_freq(f_mt0, Pxx_mt0, Pyy_mt0, amp_mt0, fmax=fmax)
            Pxx_mt_db = _db10(Pxx_mt)
            Pyy_mt_db = _db10(Pyy_mt)
            amp_mt_db = _db10(amp_mt)
            mt_spec = (f_mt, Pxx_mt_db, Pyy_mt_db, amp_mt_db)

            if bool(peak_cfg.get("enabled", True)):
                # per MT non abbiamo coerenza; riusiamo gli stessi criteri (senza qc coh)
                peaks_amp_mt = _peaks_from_curve_db(
                    f_mt, amp_mt_db,
                    search_band_hz=amp_cfg.get("search_band_hz", [0.5, 20.0]),
                    min_prom_db=float(amp_cfg.get("min_prom_db", 1.5)),
                    min_distance_hz=float(amp_cfg.get("min_distance_hz", 0.1)),
                    max_n=int(amp_cfg.get("max_n", 5)),
                    qc_mask=None,
                )
                peaks_psdtop_mt = _peaks_from_curve_db(
                    f_mt, Pyy_mt_db,
                    search_band_hz=psd_cfg.get("search_band_hz", [0.5, 20.0]),
                    min_prom_db=float(psd_cfg.get("min_prom_db", 3.0)),
                    min_distance_hz=float(psd_cfg.get("min_distance_hz", 0.3)),
                    max_n=int(psd_cfg.get("max_n", 5)),
                    qc_mask=None,
                )
        except Exception as e:
            print(f"⚠️  Multitaper fallito su {comp}: {e}")
            do_mt = False

    # Windowed metrics
    bands_hz = cfg.get("bands_hz", []) or []
    window_sec = float(((cfg.get("windowed", {}) or {}).get("window_sec", 10.0)) if "windowed" in cfg else 10.0)
    overlap = float(((cfg.get("windowed", {}) or {}).get("overlap", 0.90)) if "windowed" in cfg else 0.90)
    filt_order = int(((cfg.get("lag_alignment", {}) or {}).get("filter_order", 4)))

    metrics = compute_windowed_metrics(
        x, y, fs,
        bands_hz=bands_hz,
        window_sec=window_sec,
        overlap=overlap,
        nperseg_coh=int(welch_cfg.get("nperseg", 1024)),
        filter_order=filt_order
    )

    # -------- Layout: 6x2 if multitaper enabled else 5x2 --------
    if do_mt:
        fig = plt.figure(figsize=(18, 22))
        gs = fig.add_gridspec(6, 2, hspace=0.35, wspace=0.25)
        row_rms = 4
        row_win = 5
        row_frf = 2
        row_mt = 3
    else:
        fig = plt.figure(figsize=(18, 20))
        gs = fig.add_gridspec(5, 2, hspace=0.35, wspace=0.25)
        row_rms = 3
        row_win = 4
        row_frf = 2

    fig.suptitle(f"Building Response - {comp} | {base_name}->{top_name}", fontsize=14, fontweight="bold")

    # Global Coherence (+ lag box)
    ax1 = fig.add_subplot(gs[0, :])
    ax1.semilogx(f_w, coh_w, color="purple", lw=2.0, label="Coherence (Welch-like)")
    ax1.axhline(y=coh_threshold, color="green", ls="--", lw=1.6, alpha=0.8, label=f"Threshold ({coh_threshold})")
    for b in bands_hz:
        ax1.axvspan(float(b[0]), float(b[1]), alpha=0.12, color="0.7")
    ax1.set_xlim([max(0.05, float(np.nanmin(f_w))) if f_w.size else 0.05, float(fmax)])
    ax1.set_ylim([0, 1.05])
    ax1.set_xlabel("Frequency (Hz)")
    ax1.set_ylabel("Coherence")
    ax1.set_title("Global Coherence")
    ax1.grid(True, which="both", alpha=0.25)
    ax1.legend(fontsize=9, loc="upper right")

    lag_lines = []
    align_band = pairs_data_comp.get("align_band", None)
    lag_samp = pairs_data_comp.get("lag_samp", None)
    lag_sec = pairs_data_comp.get("lag_sec", None)
    lag_cc = pairs_data_comp.get("lag_cc", None)
    applied = pairs_data_comp.get("align_applied", None)

    if align_band is not None:
        try:
            lag_lines.append(f"band: {float(align_band[0]):g}-{float(align_band[1]):g} Hz")
        except Exception:
            lag_lines.append(f"band: {align_band}")
    if lag_samp is not None:
        lag_lines.append(f"lag: {int(lag_samp):+d} samp")
    if lag_sec is not None:
        lag_lines.append(f"Δt: {float(lag_sec):+.4f} s")
    if lag_cc is not None and np.isfinite(lag_cc):
        lag_lines.append(f"xcorr: {float(lag_cc):.3f}")
    if applied is not None:
        lag_lines.append(f"applied: {bool(applied)}")

    if lag_lines:
        ax1.text(
            0.01, 0.06,
            "\n".join(lag_lines),
            transform=ax1.transAxes,
            ha="left", va="bottom",
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="0.4", alpha=0.85),
            zorder=10,
        )

    # Welch PSD
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.semilogx(f_w, Pxx_w_db, lw=1.8, color="tab:blue", label="PSD BASE (Welch)")
    ax2.semilogx(f_w, Pyy_w_db, lw=1.8, color="tab:red", alpha=0.85, label="PSD TOP (Welch)")
    if bool(psd_cfg.get("draw_on_welch_psd", True)):
        _draw_peaks(ax2, peaks_psdtop_w, color="tab:red", y_offset_db=1.0, fontsize=label_fontsize)
    ax2.set_xlim([0.05, float(fmax)])
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("PSD (dB)")
    ax2.set_title("PSD (Welch) + TOP peaks")
    ax2.grid(True, which="both", alpha=0.25)
    ax2.legend(fontsize=9)

    # Welch Amp
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.semilogx(f_w, amp_w_db, lw=2.0, color="tab:orange", label="10log10(PSD_top/PSD_base) (Welch)")
    if bool(amp_cfg.get("draw_on_welch_amp", True)):
        _draw_peaks(ax3, peaks_amp_w, color="k", y_offset_db=0.8, fontsize=label_fontsize)
    ax3.axhline(0.0, color="k", lw=1, alpha=0.5)
    ax3.set_xlim([0.05, float(fmax)])
    ax3.set_xlabel("Frequency (Hz)")
    ax3.set_ylabel("Amplification (dB)")
    ax3.set_title("Roof/Base Amplification (Welch) + peaks")
    ax3.grid(True, which="both", alpha=0.25)
    ax3.legend(fontsize=9)

    # FRF
    ax4 = fig.add_subplot(gs[row_frf, :])
    ax4.semilogx(f_w, H1_w_db, lw=1.8, color="tab:blue", label="|H1| (masked+clipped)")
    ax4.semilogx(f_w, H2_w_db, lw=1.8, color="tab:red", alpha=0.85, label="|H2| (masked+clipped)")
    ax4.axhline(0.0, color="k", lw=1, alpha=0.35)
    ax4.set_xlim([0.05, float(fmax)])
    ax4.set_ylim(frf_db_clip)
    ax4.set_xlabel("Frequency (Hz)")
    ax4.set_ylabel("FRF magnitude (dB)")
    ax4.set_title(f"FRF magnitude (Welch) — nperseg={nps} — mask coh≥{frf_min_coh}, clip {frf_db_clip}")
    ax4.grid(True, which="both", alpha=0.25)
    ax4.legend(fontsize=9, loc="upper left")

    # Multitaper panels (if enabled)
    if do_mt and mt_spec is not None:
        f_mt, Pxx_mt_db, Pyy_mt_db, amp_mt_db = mt_spec

        ax_mt_psd = fig.add_subplot(gs[row_mt, 0])
        ax_mt_psd.semilogx(f_mt, Pxx_mt_db, lw=1.8, color="tab:blue", label="PSD BASE (MT)")
        ax_mt_psd.semilogx(f_mt, Pyy_mt_db, lw=1.8, color="tab:red", alpha=0.85, label="PSD TOP (MT)")
        _draw_peaks(ax_mt_psd, peaks_psdtop_mt, color="tab:red", y_offset_db=1.0, fontsize=label_fontsize)
        ax_mt_psd.set_xlim([0.05, float(fmax)])
        ax_mt_psd.set_xlabel("Frequency (Hz)")
        ax_mt_psd.set_ylabel("PSD (dB)")
        ax_mt_psd.set_title(f"PSD (Multitaper) — NW={mt_cfg.get('nw', 3.5)} + TOP peaks")
        ax_mt_psd.grid(True, which="both", alpha=0.25)
        ax_mt_psd.legend(fontsize=9)

        ax_mt_amp = fig.add_subplot(gs[row_mt, 1])
        ax_mt_amp.semilogx(f_mt, amp_mt_db, lw=2.0, color="tab:orange", label="10log10(PSD_top/PSD_base) (MT)")
        _draw_peaks(ax_mt_amp, peaks_amp_mt, color="k", y_offset_db=0.8, fontsize=label_fontsize)
        ax_mt_amp.axhline(0.0, color="k", lw=1, alpha=0.5)
        ax_mt_amp.set_xlim([0.05, float(fmax)])
        ax_mt_amp.set_xlabel("Frequency (Hz)")
        ax_mt_amp.set_ylabel("Amplification (dB)")
        ax_mt_amp.set_title("Roof/Base Amplification (Multitaper) + peaks")
        ax_mt_amp.grid(True, which="both", alpha=0.25)
        ax_mt_amp.legend(fontsize=9)

    # RMS
    ax5 = fig.add_subplot(gs[row_rms, :])
    tmin = metrics["times_min"]
    ax5.plot(tmin, metrics["rms_x"], color="tab:blue", lw=1.5, label="RMS BASE")
    ax5.plot(tmin, metrics["rms_y"], color="tab:red", lw=1.5, alpha=0.85, label="RMS TOP")
    ax5.set_xlabel("Time (minutes)")
    ax5.set_ylabel("RMS")
    ax5.set_title("Signal Energy (RMS)")
    ax5.grid(True, alpha=0.3)
    ax5.legend()

    # Windowed coherence/corr
    ax6 = fig.add_subplot(gs[row_win, 0])
    colors = ["tab:blue", "tab:orange", "tab:red", "tab:purple", "tab:green"]
    for i, b in enumerate(bands_hz):
        b = tuple(b)
        ax6.plot(tmin, metrics["coh_by_band"][b], lw=1.6, color=colors[i % len(colors)], label=f"Coh {b[0]}-{b[1]} Hz")
    ax6.axhline(y=coh_threshold, color="green", ls="--", lw=1.4, alpha=0.7)
    ax6.set_ylim([0, 1.0])
    ax6.set_xlabel("Time (minutes)")
    ax6.set_ylabel("Coherence")
    ax6.set_title("Windowed Coherence (bands)")
    ax6.grid(True, alpha=0.3)
    ax6.legend(fontsize=8)

    ax7 = fig.add_subplot(gs[row_win, 1])
    for i, b in enumerate(bands_hz):
        b = tuple(b)
        ax7.plot(tmin, metrics["corr_by_band"][b], lw=1.6, color=colors[i % len(colors)], label=f"Corr {b[0]}-{b[1]} Hz")
    ax7.axhline(y=corr_threshold, color="green", ls="--", lw=1.4, alpha=0.7)
    ax7.axhline(y=0.0, color="0.4", lw=1, alpha=0.4)
    ax7.set_ylim([-1.0, 1.0])
    ax7.set_xlabel("Time (minutes)")
    ax7.set_ylabel("Correlation")
    ax7.set_title("Windowed Correlation (filtered, bands)")
    ax7.grid(True, alpha=0.3)
    ax7.legend(fontsize=8)

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])

    if save_fig:
        out_path = os.path.join(figures_dir, f"{out_prefix}_{comp}.png")
        fig.savefig(out_path, dpi=250, bbox_inches="tight")
        print(f"✅ Salvata figura {comp}: {out_path}")

    plt.close(fig)


def plot_all_components(cfg: dict, pairs_data: dict, figures_dir: str):
    for comp, d in pairs_data.items():
        plot_component_results(cfg, comp, d, figures_dir)


def maybe_plot_time_traces(cfg: dict, pairs_data: dict, figures_dir: str):
    tt_cfg = ((cfg.get("extra_figures", {}) or {}).get("time_traces", {}) or {})
    if not bool(tt_cfg.get("enabled", False)):
        return

    if "Z" not in pairs_data:
        return

    fs = float(pairs_data["Z"]["fs"])
    x = pairs_data["Z"]["x"]
    y = pairs_data["Z"]["y"]
    n = min(len(x), len(y))
    t = np.arange(n) / fs

    fig = plt.figure(figsize=(14, 6))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(t, x[:n], "k", lw=1.0, label="BASE Z")
    ax.plot(t, y[:n], "r", lw=1.0, alpha=0.7, label="TOP Z")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    out_path = os.path.join(figures_dir, "time_traces_Z.png")
    fig.savefig(out_path, dpi=250, bbox_inches="tight")
    plt.close(fig)