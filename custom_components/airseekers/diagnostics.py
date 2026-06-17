"""Diagnostics for the AIRSEEKERS integration.

Never includes credentials, tokens, signed URLs, or camera stream URLs (see ``redact.py``). Camera
stream/snapshot URLs are dropped entirely regardless of redaction settings.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import AirseekersConfigEntry
from .redact import redact_mapping


def _camera_diag(cam: Any) -> dict[str, Any]:
    # Explicitly omit stream_url / snapshot_url — they may carry tokens.
    return {
        "camera_id": cam.camera_id,
        "role": cam.role,
        "stream_type": cam.stream_type,
        "supports_live": cam.supports_live,
        "supports_snapshot": cam.supports_snapshot,
        "supports_ptz": cam.supports_ptz,
        "is_composite": cam.is_composite,
        "is_privacy_sensitive": cam.is_privacy_sensitive,
        "source": cam.source,
        "has_stream_url": cam.stream_url is not None,
        "has_snapshot_url": cam.snapshot_url is not None,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirseekersConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data
    status = data.status

    return {
        "entry": {
            "backend": entry.data.get("backend"),
            "data": redact_mapping(dict(entry.data)),
            "options": redact_mapping(dict(entry.options)),
        },
        "device": {
            "model": data.device.model,
            "firmware": data.device.firmware,
            "capabilities": sorted(data.device.capabilities),
            "cutting_height_min": data.device.cutting_height_min,
            "cutting_height_max": data.device.cutting_height_max,
        },
        "status": {
            "state": status.state,
            "online": status.online,
            "battery_level": status.battery_level,
            "charging": status.charging,
            "docked": status.docked,
            "returning": status.returning,
            "raining": status.raining,
            "obstacle_detected": status.obstacle_detected,
            "blade_motor_on": status.blade_motor_on,
            "rtk_status": status.rtk_status,
            "gps_signal": status.gps_signal,
            "wifi_rssi": status.wifi_rssi,
            "cutting_height_mm": status.cutting_height_mm,
            "total_mowing_time_hours": status.total_mowing_time_hours,
            "total_cycles": status.total_cycles,
            "has_error": status.has_error,
            "error_code": status.fault.code,
            "error_message": status.fault.message,
            # current_zone is kept (a zone label, not sensitive)
            "current_zone": status.current_zone,
            "last_update": status.last_update.isoformat() if status.last_update else None,
        },
        "zones": {"count": len(data.zones), "ids": [z.zone_id for z in data.zones]},
        "cameras": {
            "count": len(data.cameras),
            "roles": [c.role for c in data.cameras],
            "items": [_camera_diag(c) for c in data.cameras],
        },
        "update": {
            "interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            "last_update_success": coordinator.last_update_success,
        },
    }
