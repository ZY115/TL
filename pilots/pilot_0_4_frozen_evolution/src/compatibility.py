"""Dynamic snapshot loading and immutable-source compatibility helpers."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_snapshot(path: Path, system: str, step: int) -> ModuleType:
    package_name = f"pilot04_{system}_{step}"
    spec = importlib.util.spec_from_file_location(
        package_name,
        path / "__init__.py",
        submodule_search_locations=[str(path)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load snapshot {path}")
    for name in [
        key
        for key in sys.modules
        if key == package_name or key.startswith(f"{package_name}.")
    ]:
        del sys.modules[name]
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
