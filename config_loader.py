"""Load GOP3 config from external file when available (works with PyInstaller)."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_CONFIG = None


def get_external_config_path() -> Path:
    override = os.environ.get("GOP3_CONFIG_PATH")
    if override:
        return Path(override).expanduser().resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "gop3_config.py"

    return Path(__file__).resolve().parent / "gop3_config.py"


def load_config():
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    external = get_external_config_path()
    if external.exists():
        spec = importlib.util.spec_from_file_location("gop3_config_user", external)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CONFIG = module
        return _CONFIG

    import gop3_config as module
    _CONFIG = module
    return _CONFIG
