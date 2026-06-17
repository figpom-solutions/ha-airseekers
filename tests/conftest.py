"""Pytest configuration for ha-airseekers.

Ensures the repository root is importable so tests can ``import custom_components.airseekers...``.
The Home Assistant test harness (pytest-homeassistant-custom-component) provides the ``homeassistant``
package; the API-layer tests only need the repo root on ``sys.path``.
"""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
