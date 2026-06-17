"""The AIRSEEKERS integration.

Phase 1 placeholder. The Home Assistant setup entry points (``async_setup_entry`` /
``async_unload_entry``), coordinator wiring, and service registration are implemented in Phase 3
(see ``.planning/ROADMAP.md`` and ``docs/architecture.md``). Until then this module only marks the
package and exposes the domain.
"""

from __future__ import annotations

from .const import DOMAIN

__all__ = ["DOMAIN"]
