import os
import yaml
from datetime import datetime


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config non trovato: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_scenario(cfg: dict):
    name = cfg.get("active_scenario", None)
    if not name:
        raise ValueError("config: active_scenario mancante")
    scenario = (cfg.get("scenarios", {}) or {}).get(name, None)
    if not scenario:
        raise ValueError(f"Scenario non trovato: {name}")
    return name, scenario


def resolve_files_abs(cfg: dict, scenario: dict):
    data_dir = scenario.get("data_dir", None)
    if not data_dir:
        raise ValueError("scenario.data_dir mancante")

    files = scenario.get("files", {}) or {}
    if not isinstance(files, dict) or not files:
        raise ValueError("scenario.files mancante o vuoto")

    out = {}
    for lab, rel in files.items():
        if rel is None:
            continue
        rel = str(rel)
        out[lab] = os.path.join(data_dir, rel)

    counts_to_g = scenario.get("counts_to_g", {}) or {}
    return out, counts_to_g


def ensure_files_exist(files_abs: dict):
    for lab, path in files_abs.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"File non trovato ({lab}): {path}")


def _sanitize(value: str) -> str:
    value = str(value or "").strip()
    safe = []
    for ch in value:
        if ch.isalnum() or ch in ("_", "-"):
            safe.append(ch)
    return "".join(safe) or "run"


def build_run_output_dirs(cfg: dict, scenario_name: str, scenario: dict) -> dict:
    """
    Salva output nella stessa cartella dei dati di input:
      <scenario.data_dir>/<project.output_dir>/<run_name>/<project.figures_subdir>
    """
    proj = cfg.get("project", {}) or {}

    output_dirname = str(proj.get("output_dir", "output"))  # <--- ora configurabile
    figures_sub = str(proj.get("figures_subdir", "figures"))
    run_name = proj.get("run_name", None)

    data_dir = scenario.get("data_dir", None)
    if not data_dir:
        raise ValueError("scenario.data_dir mancante (necessario per output locale ai dati)")

    if not run_name:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"{_sanitize(scenario_name)}_{ts}"

    run_dir = os.path.join(data_dir, output_dirname, run_name)
    figures_dir = os.path.join(run_dir, figures_sub)

    os.makedirs(figures_dir, exist_ok=True)
    return {"run_dir": run_dir, "figures_dir": figures_dir}