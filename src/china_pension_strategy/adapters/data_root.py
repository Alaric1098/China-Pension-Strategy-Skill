"""Locate bundled data (schemas, policy packages) across install layouts.

Resolution order:

1. the ``CHINA_PENSION_DATA_ROOT`` environment variable (explicit override);
2. the ``share/china-pension-strategy`` directory of the active environment
   (setuptools ``data-files`` wheel installation);
3. the repository root next to the source tree (editable install or checkout).

Raising a clear error here keeps every loader honest: an installation without
its data is unusable and must not silently fall back to partial rules.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ENV_VAR = "CHINA_PENSION_DATA_ROOT"
_SHARE_DIR = Path(sys.prefix) / "share" / "china-pension-strategy"


def data_root() -> Path:
    """Return the directory that contains ``schemas`` and ``policy-data``."""
    explicit = os.environ.get(_ENV_VAR)
    if explicit:
        return Path(explicit)
    if (_SHARE_DIR / "policy-data").is_dir():
        return _SHARE_DIR
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "policy-data").is_dir():
            return parent
    raise FileNotFoundError(
        "bundled policy data not found; set CHINA_PENSION_DATA_ROOT or install "
        "the package with its data files"
    )
