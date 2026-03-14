import os

from modules.io_utils import (
    load_config,
    get_scenario,
    resolve_files_abs,
    ensure_files_exist,
    build_run_output_dirs,
)
from modules.preprocess import (
    detrend_stream,
    maybe_filter_stream,
    apply_pick_window_to_streams,
)
from modules.coherence_analysis import build_pairs_data
from modules.response_spectra import (
    maybe_run_response_spectra,
    maybe_run_station_summary,
    maybe_export_station_csv,  # NEW
)
from modules.plotting import plot_all_components, maybe_plot_time_traces


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(script_dir, "config", "config.yaml")

    print(f"[CONFIG] loading: {cfg_path}")
    cfg = load_config(cfg_path)

    # stampa i valori realmente letti
    fa = ((cfg.get("event", {}) or {}).get("first_arrival", {}) or {})
    win = (fa.get("window", {}) or {})
    print(f"[CONFIG] pick_time_utc={fa.get('pick_time_utc')}")
    print(f"[CONFIG] pre_sec={win.get('pre_sec')}  post_sec={win.get('post_sec')}")

    scenario_name, scenario = get_scenario(cfg)
    files_abs, counts_to_g = resolve_files_abs(cfg, scenario)
    ensure_files_exist(files_abs)

    run_dirs = build_run_output_dirs(cfg, scenario_name, scenario)
    figures_dir = run_dirs["figures_dir"]
    output_dir = run_dirs.get("output_dir", os.path.dirname(figures_dir))  # fallback safe

    print(f"Scenario: {scenario_name}")
    print(f"Figures dir: {figures_dir}")
    print(f"Output dir: {output_dir}")

    from obspy import read

    streams = {}
    do_detrend = bool((cfg.get("processing", {}) or {}).get("detrend", True))
    for lab, path in files_abs.items():
        st = read(path)
        if do_detrend:
            st = detrend_stream(st)
        st = maybe_filter_stream(cfg, st, label=lab)
        streams[lab] = st

    streams = apply_pick_window_to_streams(cfg, streams)

    pairs_data = build_pairs_data(cfg, streams, counts_to_g)

    # plots + exports
    maybe_plot_time_traces(cfg, pairs_data, figures_dir)
    maybe_run_response_spectra(cfg, pairs_data, figures_dir)
    maybe_run_station_summary(cfg, pairs_data, figures_dir)

    # NEW: CSV export (se abilitato in cfg.export.station_csv.enabled)
    maybe_export_station_csv(cfg, pairs_data, output_dir)

    plot_all_components(cfg, pairs_data, figures_dir)

    print("Analisi completata.")


if __name__ == "__main__":
    main()