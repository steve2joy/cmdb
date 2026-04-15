# -*- coding: utf-8 -*-
"""Minimal settings module for pytest-based app startup."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_base_settings():
    settings_path = Path(__file__).resolve().parents[1] / "settings.example.py"
    spec = spec_from_file_location("cmdb_settings_example", settings_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_base = _load_base_settings()

for _name in dir(_base):
    if _name.isupper():
        globals()[_name] = getattr(_base, _name)

ENV = "testing"
TESTING = True
DEBUG = False
LOG_PATH = "/dev/stdout"
SECRET_KEY = getattr(_base, "SECRET_KEY", None) or "cmdb-test-secret"
