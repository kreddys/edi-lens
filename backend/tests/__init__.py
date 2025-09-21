"""Tests for EDI Lens backend."""

from __future__ import annotations

import sys
from pathlib import Path


_BACKEND_ROOT = Path(__file__).resolve().parent.parent

if _BACKEND_ROOT.exists():
    sys.path.insert(0, str(_BACKEND_ROOT))
