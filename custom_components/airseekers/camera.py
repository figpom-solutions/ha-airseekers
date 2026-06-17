"""Camera platform for AIRSEEKERS — dynamic multi-camera support.

One ``camera.*`` entity is created per camera the backend reports (1..N), named by role, with a stable
``unique_id`` of ``{device_id}_{camera_id}``. Snapshot-only cameras implement ``async_camera_image``;
cameras advertising a live stream also implement ``stream_source``. Composite (300/360) cameras are
flagged in attributes.

Privacy-first: stream/snapshot URLs are NEVER exposed in attributes, logs, or diagnostics. Privacy
mode and the docked/night switches suppress imagery without deleting the entity.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant

from .api import (
    AirseekersCameraInfo,
    AirseekersCameraUnavailable,
    AirseekersError,
)
from .const import (
    CAMERA_DISCOVERY_DISABLED,
    CONF_CAMERA_DISCOVERY_MODE,
    CONF_DISABLE_CAMERAS_AT_NIGHT,
    CONF_DISABLE_CAMERAS_WHEN_DOCKED,
    CONF_ENABLE_ALL_CAMERAS,
    CONF_ENABLE_CAMERA_ENTITIES,
    CONF_ENABLED_CAMERA_ROLES,
    CONF_PREFER_COMPOSITE_CAMERA,
    CONF_PRIVACY_MODE,
    DEFAULT_CAMERA_DISCOVERY_MODE,
    DEFAULT_ENABLE_ALL_CAMERAS,
    DEFAULT_ENABLE_CAMERA_ENTITIES,
    DEFAULT_PREFER_COMPOSITE_CAMERA,
    DEFAULT_PRIVACY_MODE,
)
from .coordinator import AirseekersConfigEntry, AirseekersDataUpdateCoordinator
from .entity import AirseekersEntity

_LOGGER = logging.getLogger(__name__)

_SUN_BELOW_HORIZON = "below_horizon"


def _enabled_default(
    cam: AirseekersCameraInfo, *, enable_all: bool, prefer_composite: bool, has_composite: bool
) -> bool:
    """Whether this camera should be enabled by default in the entity registry.

    With ``prefer_composite`` and a composite present, only composite cameras are enabled by default;
    the per-lens cameras are still created (showing the multi-camera architecture) but left disabled
    for the user to enable. ``enable_all`` overrides this.
    """
    if enable_all:
        return True
    if prefer_composite and has_composite:
        return cam.is_composite
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirseekersConfigEntry,
    async_add_entities,
) -> None:
    """Set up camera entities from the cameras the backend reports."""
    opts = entry.options
    if not opts.get(CONF_ENABLE_CAMERA_ENTITIES, DEFAULT_ENABLE_CAMERA_ENTITIES):
        return
    if opts.get(CONF_CAMERA_DISCOVERY_MODE, DEFAULT_CAMERA_DISCOVERY_MODE) == CAMERA_DISCOVERY_DISABLED:
        return

    coordinator = entry.runtime_data.coordinator
    cameras = list(coordinator.data.cameras)

    enable_all = opts.get(CONF_ENABLE_ALL_CAMERAS, DEFAULT_ENABLE_ALL_CAMERAS)
    roles = opts.get(CONF_ENABLED_CAMERA_ROLES) or []
    if not enable_all and roles:
        cameras = [c for c in cameras if c.role in roles]

    prefer_composite = opts.get(CONF_PREFER_COMPOSITE_CAMERA, DEFAULT_PREFER_COMPOSITE_CAMERA)
    has_composite = any(c.is_composite for c in cameras)

    async_add_entities(
        AirseekersCamera(
            coordinator,
            cam,
            enabled_default=_enabled_default(
                cam,
                enable_all=enable_all,
                prefer_composite=prefer_composite,
                has_composite=has_composite,
            ),
        )
        for cam in cameras
    )


class AirseekersCamera(AirseekersEntity, Camera):
    """A single AIRSEEKERS camera (snapshot and/or live)."""

    def __init__(
        self,
        coordinator: AirseekersDataUpdateCoordinator,
        cam: AirseekersCameraInfo,
        *,
        enabled_default: bool,
    ) -> None:
        super().__init__(coordinator)
        Camera.__init__(self)
        self._camera_id = cam.camera_id
        # Static descriptors captured at setup (role/type don't change for a given camera).
        self._role = cam.role
        self._stream_type = cam.stream_type
        self._supports_live = cam.supports_live
        self._supports_snapshot = cam.supports_snapshot
        self._is_composite = cam.is_composite
        self._source = cam.source
        self._last_frame_at: datetime | None = None

        self._attr_name = cam.name
        self._attr_unique_id = f"{self._device_id}_{cam.camera_id}"
        self._attr_entity_registry_enabled_default = enabled_default
        if cam.supports_live:
            self._attr_supported_features = CameraEntityFeature.STREAM
        # Stub snapshots are PNG; real backends may differ and can override later.
        self.content_type = "image/png"

    @property
    def _cam_info(self) -> AirseekersCameraInfo | None:
        return next(
            (c for c in self.coordinator.data.cameras if c.camera_id == self._camera_id), None
        )

    @property
    def _privacy_mode(self) -> bool:
        return bool(self.coordinator.config_entry.options.get(CONF_PRIVACY_MODE, DEFAULT_PRIVACY_MODE))

    def _is_night(self) -> bool:
        sun = self.hass.states.get("sun.sun")
        return sun is not None and sun.state == _SUN_BELOW_HORIZON

    @property
    def _suppressed_unavailable(self) -> bool:
        """True when the camera should report unavailable (docked/night switches)."""
        opts = self.coordinator.config_entry.options
        if opts.get(CONF_DISABLE_CAMERAS_WHEN_DOCKED) and self._status.docked:
            return True
        return bool(opts.get(CONF_DISABLE_CAMERAS_AT_NIGHT) and self._is_night())

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._cam_info is not None
            and not self._suppressed_unavailable
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        # NEVER include stream_url / snapshot_url here.
        return {
            "camera_id": self._camera_id,
            "role": self._role,
            "stream_type": self._stream_type,
            "supports_live": self._supports_live,
            "supports_snapshot": self._supports_snapshot,
            "is_composite": self._is_composite,
            "source": self._source,
            "last_frame_at": self._last_frame_at.isoformat() if self._last_frame_at else None,
            "privacy_mode": self._privacy_mode,
        }

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        if self._privacy_mode or self._suppressed_unavailable or not self._supports_snapshot:
            return None
        try:
            image = await self.coordinator.client.async_get_camera_snapshot(
                self._device_id, self._camera_id
            )
        except AirseekersCameraUnavailable:
            return None
        except AirseekersError as err:
            _LOGGER.debug("Camera %s snapshot failed: %s", self._camera_id, err)
            return None
        self._last_frame_at = datetime.now(timezone.utc)
        return image

    async def stream_source(self) -> str | None:
        if not self._supports_live or self._privacy_mode or self._suppressed_unavailable:
            return None
        try:
            return await self.coordinator.client.async_get_camera_stream_url(
                self._device_id, self._camera_id
            )
        except AirseekersError as err:
            _LOGGER.debug("Camera %s stream lookup failed: %s", self._camera_id, err)
            return None
