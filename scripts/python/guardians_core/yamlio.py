"""YAML reading.

PyYAML (safe_load) is used when importable. Otherwise the reader of an installed sibling is used -
auditGuard's `auditguard_core.yamlio`, then archiGuard's `archiguard_core.yamlio` - because the bundle
installs them next to Guardians. Guardians never writes YAML through a dumper: its edits are line edits
that keep the siblings' comments (see edits.py).

Dates and timestamps are normalised to ISO strings so both readers return the same data.
"""

from __future__ import annotations

import datetime as _dt
import importlib
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .common import GuardiansError, read_text

Reader = Callable[[str, str], Any]

_SEARCH: List[Path] = []
_READER: Optional[Reader] = None
_READER_NAME = ""


def set_search_root(root: Path) -> None:
    """Where to look for a sibling's reader when PyYAML is missing."""
    global _SEARCH, _READER, _READER_NAME
    _SEARCH = [root / ".specify" / "extensions" / ext / "scripts" / "python" for ext in ("auditguard", "archiguard")]
    _READER, _READER_NAME = None, ""


def reader_name() -> str:
    _reader()
    return _READER_NAME


def _normalise(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalise(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    return value


def _pyyaml() -> Optional[Reader]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return None

    def load(text: str, where: str) -> Any:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:  # type: ignore[attr-defined]
            raise GuardiansError(f"{where}: invalid YAML ({exc})")

    return load


def _sibling() -> Optional[Reader]:
    global _READER_NAME
    for base in _SEARCH:
        for package in ("auditguard_core", "archiguard_core"):
            if not (base / package / "yamlio.py").is_file():
                continue
            try:
                if str(base) not in sys.path:
                    sys.path.append(str(base))
                module = importlib.import_module(f"{package}.yamlio")
                loads = getattr(module, "loads")
            except Exception:  # a sibling we cannot import is not an error of ours
                continue

            def load(text: str, where: str, _loads: Callable[..., Any] = loads) -> Any:
                try:
                    return _loads(text, where)
                except Exception as exc:
                    raise GuardiansError(f"{where}: invalid YAML ({exc})")

            _READER_NAME = f"{package}.yamlio"
            return load
    return None


def _reader() -> Reader:
    global _READER, _READER_NAME
    if _READER is None:
        _READER = _pyyaml()
        if _READER is not None:
            _READER_NAME = "PyYAML"
        else:
            _READER = _sibling()
    if _READER is None:
        raise GuardiansError("cannot read YAML: install PyYAML (python -m pip install pyyaml), install auditGuard or "
                             "archiGuard in this project (their reader is used), or run with specify-cli's Python "
                             "(GUARDIANS_PYTHON=<path>)")
    return _READER


def loads(text: str, where: str = "<yaml>") -> Any:
    if text.startswith("\ufeff"):
        text = text[1:]          # a byte-order mark (PowerShell 5 writes one); PyYAML skips it, a sibling reader may not
    return _normalise(_reader()(text, where))


def load_file(path: Path, required: bool = False) -> Dict[str, Any]:
    """A YAML mapping from a file; {} when the file is missing and not required."""
    if not path.is_file():
        if required:
            raise GuardiansError(f"{path}: not found")
        return {}
    data = loads(read_text(path), str(path))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise GuardiansError(f"{path}: expected a mapping at the top level")
    return data


def get(data: Any, *keys: str, default: Any = None) -> Any:
    """Nested lookup that tolerates missing or non-mapping levels."""
    node = data
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return default if node is None else node
