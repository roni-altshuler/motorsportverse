"""Shared pytest fixtures and project-root path setup."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DATA = PROJECT_ROOT / "website" / "public" / "data"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
