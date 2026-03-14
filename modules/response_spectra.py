import os
import numpy as np

from .response_plots import (
    plot_response_spectra,
    plot_station_summary_like_image,
    export_station_metrics_csv,
)


def maybe_run_response_spectra(cfg: dict, pairs_data: dict, figures_dir: str):
    # FIX: chiave corretta nel YAML
    rs_cfg = ((cfg.get("extra_figures", {}) or {}).get("response_spectra", {}) or {})
    if not bool(rs_cfg.get("enabled", False)):
        return

    damping = float(rs_cfg.get("damping", 0.05))
    tmin = float(rs_cfg.get("tmin", 0.02))
    tmax = float(rs_cfg.get("tmax", 5.0))
    tn = int(rs_cfg.get("tn", 140))
    periods = np.logspace(np.log10(tmin), np.log10(tmax), tn)

    save_kinds = tuple(str(k).upper() for k in (rs_cfg.get("save_kinds", ["SA", "PSA"]) or ["SA", "PSA"]))
    save_units = tuple(rs_cfg.get("save_units", ["m/s^2", "g"]) or ["m/s^2", "g"])

    plot_response_spectra(
        pairs_data,
        out_dir=figures_dir,
        prefix="rs",
        save=True,
        show=False,
        damping=damping,
        periods=periods,
        kind="PSA",
        save_kinds=save_kinds,
        save_units=save_units,
    )


def maybe_run_station_summary(cfg: dict, pairs_data: dict, figures_dir: str):
    ss_cfg = ((cfg.get("extra_figures", {}) or {}).get("station_summary", {}) or {})
    if not bool(ss_cfg.get("enabled", False)):
        return

    # FIX: chiave corretta nel YAML
    rs_cfg = ((cfg.get("extra_figures", {}) or {}).get("response_spectra", {}) or {})

    station_name = str(ss_cfg.get("station_name", "Station"))
    rs_kind = str(ss_cfg.get("rs_kind", "PSA")).upper().strip()
    damping = float(rs_cfg.get("damping", 0.05))

    tmin = float(rs_cfg.get("tmin", 0.02))
    tmax = float(rs_cfg.get("tmax", 5.0))
    tn = int(rs_cfg.get("tn", 140))
    periods = np.logspace(np.log10(tmin), np.log10(tmax), tn)

    ms = ss_cfg.get("max_seconds", 60.0)
    max_seconds = None if ms is None else float(ms)

    show = bool(ss_cfg.get("show_on_screen", True))
    units_list = ss_cfg.get("sa_units_list", ["g", "m/s^2"]) or ["g", "m/s^2"]

    for i, sa_units in enumerate(units_list):
        plot_station_summary_like_image(
            pairs_data,
            out_dir=figures_dir,
            prefix="summary_like_image",
            save=True,
            show=show if i == 0 else False,
            station_name=station_name,
            damping=damping,
            periods=periods,
            rs_kind=rs_kind,
            sa_units=sa_units,
            max_seconds=max_seconds,
            draw_husid=True,
            mark_max_peak=True,
            peak_on_component=None,
        )


def maybe_export_station_csv(cfg: dict, pairs_data: dict, out_dir: str):
    """
    Export CSV con parametri tipo tabella (PGA/PGV/PGD/PSA03/PSA1/PSA3/T75/T90).
    Salva in: <out_dir>/csv/<filename>

    PATCH:
    - supporta which: "BASE" | "TOP" | "BOTH" (default: BOTH)
    - salva in output_dir/csv
    - passa base_station_name / top_station_name a export_station_metrics_csv, così la colonna
      Station sarà il nome reale della stazione per ogni riga (BASE/TOP)
    """
    ex_cfg = ((cfg.get("export", {}) or {}).get("station_csv", {}) or {})
    if not bool(ex_cfg.get("enabled", False)):
        return

    ss_cfg = ((cfg.get("extra_figures", {}) or {}).get("station_summary", {}) or {})

    # nomi stazione (fallback: vuoto -> la funzione CSV userà station_name)
    base_station = str(ex_cfg.get("base_station", ss_cfg.get("base_station", "")) or "").strip()
    top_station = str(ex_cfg.get("top_station", ss_cfg.get("top_station", "")) or "").strip()

    # nome "generico" (usato come fallback se base/top non forniti)
    generic_station = str(ex_cfg.get("station_name", ss_cfg.get("station_name", "Station")))

    event_cfg = (cfg.get("event", {}) or {})
    fa_cfg = (event_cfg.get("first_arrival", {}) or {})
    origin_time_utc = str(
        ex_cfg.get(
            "origin_time_utc",
            event_cfg.get("origin_time_utc", fa_cfg.get("pick_time_utc", "")),
        )
        or ""
    )

    which = str(ex_cfg.get("which", "BOTH")).upper().strip()
    if which not in ("BASE", "TOP", "BOTH"):
        raise ValueError("export.station_csv.which deve essere 'BASE', 'TOP' o 'BOTH'")

    rs_cfg = ((cfg.get("extra_figures", {}) or {}).get("response_spectra", {}) or {})
    damping = float(ex_cfg.get("damping", rs_cfg.get("damping", 0.05)))

    tmin = float(ex_cfg.get("tmin", rs_cfg.get("tmin", 0.02)))
    tmax = float(ex_cfg.get("tmax", rs_cfg.get("tmax", 5.0)))
    tn = int(ex_cfg.get("tn", rs_cfg.get("tn", 140)))
    periods = np.logspace(np.log10(tmin), np.log10(tmax), tn)

    default_filename = f"station_metrics_{which}.csv"
    filename = str(ex_cfg.get("filename", default_filename))

    # salva in output_dir/csv
    csv_dir = os.path.join(out_dir, "csv")
    os.makedirs(csv_dir, exist_ok=True)
    out_csv_path = os.path.join(csv_dir, filename)

    io_cfg = (cfg.get("io", {}) or {})
    acc_units = str(io_cfg.get("output_units", "m/s^2"))

    export_station_metrics_csv(
        pairs_data=pairs_data,
        out_csv_path=out_csv_path,
        station_name=generic_station,
        origin_time_utc=origin_time_utc,
        which=which,  # BASE | TOP | BOTH
        damping=damping,
        periods=periods,
        psa_periods=tuple(ex_cfg.get("psa_periods", [0.3, 1.0, 3.0])),
        husid_frac_75=float(ex_cfg.get("husid_frac_75", 0.75)),
        husid_frac_90=float(ex_cfg.get("husid_frac_90", 0.90)),
        acc_input_units=acc_units,
        base_station_name=base_station or None,
        top_station_name=top_station or None,
    )