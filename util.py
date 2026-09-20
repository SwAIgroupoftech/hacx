"""Shared helpers."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def json_safe(obj):
    """Convert numpy / pandas values so json.dump never fails."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
            return None
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if (np.isnan(v) or np.isinf(v)) else v
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return json_safe(obj.tolist())
    return str(obj)


def write_json(path, payload) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2), encoding="utf-8")
    return path


def load_config(root: Path) -> dict:
    import os

    import yaml
    from dotenv import load_dotenv

    load_dotenv(root / ".env")
    cfg_path = root / os.getenv("CONFIG_PATH", "config/config.yaml")
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
