"""Constants for the AIRSEEKERS integration.

This module is the shared contract for every other module in the integration. It deliberately
contains NO Home Assistant imports beyond `Platform` so it can be imported by tooling and tests
cheaply. Backend/protocol specifics live in ``api.py``; nothing here hardcodes a real AIRSEEKERS
endpoint, URL, or credential.
"""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "airseekers"
MANUFACTURER: Final = "AIRSEEKERS"

# Platforms this integration sets up. Kept in build order; entities are still capability-gated.
PLATFORMS: Final[list[Platform]] = [
    Platform.LAWN_MOWER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.CAMERA,
]

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
MODEL_TRON: Final = "TRON"
MODEL_TRON_MAX: Final = "TRON Max"
MODEL_OTHER: Final = "other"
MODELS: Final[list[str]] = [MODEL_TRON, MODEL_TRON_MAX, MODEL_OTHER]
DEFAULT_MODEL: Final = MODEL_TRON_MAX

# ---------------------------------------------------------------------------
# Backends — `stub` is the only fully functional backend. The others are stubs that raise
# AirseekersUnsupportedFeature until the real protocol is verified by the owner. We NEVER invent
# endpoints, URLs, ports, or payloads.
# ---------------------------------------------------------------------------
BACKEND_STUB: Final = "stub"
BACKEND_LOCAL_HTTP: Final = "local_http"
BACKEND_CLOUD_HTTP: Final = "cloud_http"
BACKEND_MQTT: Final = "mqtt"
BACKEND_RTSP: Final = "rtsp"
BACKENDS: Final[list[str]] = [
    BACKEND_STUB,
    BACKEND_LOCAL_HTTP,
    BACKEND_CLOUD_HTTP,
    BACKEND_MQTT,
]
DEFAULT_BACKEND: Final = BACKEND_STUB

# ---------------------------------------------------------------------------
# Config / Options keys
# ---------------------------------------------------------------------------
CONF_BACKEND: Final = "backend"
CONF_MODEL: Final = "model"
CONF_DEVICE_NAME: Final = "device_name"
CONF_HOST: Final = "host"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_PREFER_LOCAL: Final = "prefer_local"

# Tokens are stored in the config entry data only when an authenticated backend needs them. They
# are NEVER logged or written to diagnostics (see SENSITIVE_KEYS / diagnostics.py).
CONF_TOKEN: Final = "token"
CONF_REFRESH_TOKEN: Final = "refresh_token"

# Polling
CONF_POLL_ACTIVE: Final = "poll_active_interval"
CONF_POLL_IDLE: Final = "poll_idle_interval"
DEFAULT_POLL_ACTIVE: Final = 30  # seconds, robot active
DEFAULT_POLL_IDLE: Final = 300  # seconds, robot docked/idle

# Cutting height bounds (used when the backend does not report its own bounds)
CONF_CUTTING_HEIGHT_MIN: Final = "cutting_height_min"
CONF_CUTTING_HEIGHT_MAX: Final = "cutting_height_max"
DEFAULT_CUTTING_HEIGHT_MIN: Final = 20  # mm
DEFAULT_CUTTING_HEIGHT_MAX: Final = 70  # mm

# ---------------------------------------------------------------------------
# Camera options (privacy-first defaults)
# ---------------------------------------------------------------------------
CONF_ENABLE_CAMERA_ENTITIES: Final = "enable_camera_entities"
CONF_ENABLE_ALL_CAMERAS: Final = "enable_all_cameras"
CONF_ENABLED_CAMERA_ROLES: Final = "enabled_camera_roles"
CONF_PREFER_COMPOSITE_CAMERA: Final = "prefer_composite_camera"
CONF_PREFER_LOCAL_CAMERA: Final = "prefer_local_camera"
CONF_CAMERA_DISCOVERY_MODE: Final = "camera_discovery_mode"
CONF_CAMERA_REFRESH_INTERVAL: Final = "camera_refresh_interval"
CONF_DISABLE_CAMERAS_WHEN_DOCKED: Final = "disable_cameras_when_docked"
CONF_DISABLE_CAMERAS_AT_NIGHT: Final = "disable_cameras_at_night"
CONF_PRIVACY_MODE: Final = "privacy_mode"
CONF_REDACT_STREAM_URLS_IN_DIAGNOSTICS: Final = "redact_stream_urls_in_diagnostics"

CAMERA_DISCOVERY_AUTO: Final = "auto"
CAMERA_DISCOVERY_MANUAL: Final = "manual"
CAMERA_DISCOVERY_DISABLED: Final = "disabled"
CAMERA_DISCOVERY_MODES: Final = [
    CAMERA_DISCOVERY_AUTO,
    CAMERA_DISCOVERY_MANUAL,
    CAMERA_DISCOVERY_DISABLED,
]

DEFAULT_ENABLE_CAMERA_ENTITIES: Final = True
DEFAULT_ENABLE_ALL_CAMERAS: Final = False
DEFAULT_PREFER_COMPOSITE_CAMERA: Final = True
DEFAULT_PREFER_LOCAL_CAMERA: Final = True
DEFAULT_CAMERA_DISCOVERY_MODE: Final = CAMERA_DISCOVERY_AUTO
DEFAULT_CAMERA_REFRESH_INTERVAL: Final = 10  # seconds for snapshot polling
DEFAULT_DISABLE_CAMERAS_WHEN_DOCKED: Final = False
DEFAULT_DISABLE_CAMERAS_AT_NIGHT: Final = False
DEFAULT_PRIVACY_MODE: Final = False
DEFAULT_REDACT_STREAM_URLS_IN_DIAGNOSTICS: Final = True

# Camera roles (a superset; only roles the backend reports become entities)
ROLE_FRONT: Final = "front"
ROLE_FRONT_LEFT: Final = "front_left"
ROLE_FRONT_RIGHT: Final = "front_right"
ROLE_LEFT: Final = "left"
ROLE_RIGHT: Final = "right"
ROLE_REAR: Final = "rear"
ROLE_TOP: Final = "top"
ROLE_BOTTOM: Final = "bottom"
ROLE_OBSTACLE: Final = "obstacle"
ROLE_NAVIGATION: Final = "navigation"
ROLE_MAPPING: Final = "mapping"
ROLE_AI_DETECTION: Final = "ai_detection"
ROLE_COMPOSITE_300: Final = "composite_300"
ROLE_COMPOSITE_360: Final = "composite_360"
ROLE_UNKNOWN: Final = "unknown"
CAMERA_ROLES: Final[list[str]] = [
    ROLE_FRONT,
    ROLE_FRONT_LEFT,
    ROLE_FRONT_RIGHT,
    ROLE_LEFT,
    ROLE_RIGHT,
    ROLE_REAR,
    ROLE_TOP,
    ROLE_BOTTOM,
    ROLE_OBSTACLE,
    ROLE_NAVIGATION,
    ROLE_MAPPING,
    ROLE_AI_DETECTION,
    ROLE_COMPOSITE_300,
    ROLE_COMPOSITE_360,
    ROLE_UNKNOWN,
]

# Camera stream types
STREAM_SNAPSHOT: Final = "snapshot"
STREAM_MJPEG: Final = "mjpeg"
STREAM_HLS: Final = "hls"
STREAM_RTSP: Final = "rtsp"
STREAM_WEBRTC: Final = "webrtc"
STREAM_CLOUD: Final = "cloud"
STREAM_PROPRIETARY: Final = "proprietary"
STREAM_UNKNOWN: Final = "unknown"

# ---------------------------------------------------------------------------
# Mower activity (mapped to homeassistant LawnMowerActivity in lawn_mower.py)
# ---------------------------------------------------------------------------
STATE_DOCKED: Final = "docked"
STATE_MOWING: Final = "mowing"
STATE_PAUSED: Final = "paused"
STATE_RETURNING: Final = "returning"
STATE_CHARGING: Final = "charging"
STATE_ERROR: Final = "error"
STATE_OFFLINE: Final = "offline"
STATE_IDLE: Final = "idle"
STATE_UNKNOWN: Final = "unknown"

# ---------------------------------------------------------------------------
# Capability keys — entities are created only when the backend advertises the capability.
# ---------------------------------------------------------------------------
CAP_BATTERY: Final = "battery"
CAP_ZONES: Final = "zones"
CAP_CUTTING_HEIGHT: Final = "cutting_height"
CAP_MOWING_MODE: Final = "mowing_mode"
CAP_RTK: Final = "rtk"
CAP_GPS: Final = "gps"
CAP_WIFI_RSSI: Final = "wifi_rssi"
CAP_BLADE_MOTOR: Final = "blade_motor"
CAP_RAIN_SENSOR: Final = "rain_sensor"
CAP_OBSTACLE: Final = "obstacle"
CAP_CAMERAS: Final = "cameras"
CAP_LOCATE: Final = "locate"
CAP_RESET_ERROR: Final = "reset_error"
CAP_STOP: Final = "stop"

# ---------------------------------------------------------------------------
# Maintenance / warranty / blades
# ---------------------------------------------------------------------------
CONF_PURCHASE_DATE: Final = "purchase_date"
CONF_WARRANTY_MONTHS: Final = "warranty_months"
CONF_WARRANTY_WARNING_DAYS: Final = "warranty_warning_days"
CONF_LAST_BLADE_CHANGE: Final = "last_blade_change"
CONF_BLADE_LIFETIME_HOURS: Final = "blade_lifetime_hours"
CONF_BLADE_WARNING_PERCENT: Final = "blade_warning_percent"
CONF_ENABLE_MAINTENANCE_SENSORS: Final = "enable_maintenance_sensors"

DEFAULT_WARRANTY_MONTHS: Final = 24
DEFAULT_WARRANTY_WARNING_DAYS: Final = 60
DEFAULT_BLADE_LIFETIME_HOURS: Final = 100
DEFAULT_BLADE_WARNING_PERCENT: Final = 20
DEFAULT_ENABLE_MAINTENANCE_SENSORS: Final = True

# Maintenance status enums
WARRANTY_OK: Final = "OK"
WARRANTY_EXPIRE_SOON: Final = "expire_soon"
WARRANTY_EXPIRED: Final = "expired"

BLADE_OK: Final = "OK"
BLADE_SOON: Final = "soon"
BLADE_REPLACE: Final = "replace"

MAINTENANCE_OK: Final = "OK"
MAINTENANCE_DUE: Final = "due"

# Maintenance event types (for the persistent maintenance log)
EVENT_BLADE_CHANGE: Final = "blade_change"
EVENT_CLEANING: Final = "cleaning"
EVENT_FIRMWARE_UPDATE: Final = "firmware_update"
EVENT_REPAIR: Final = "repair"
EVENT_WARRANTY_CLAIM: Final = "warranty_claim"
EVENT_BATTERY_CHECK: Final = "battery_check"
EVENT_USER_NOTE: Final = "user_note"
MAINTENANCE_EVENT_TYPES: Final[list[str]] = [
    EVENT_BLADE_CHANGE,
    EVENT_CLEANING,
    EVENT_FIRMWARE_UPDATE,
    EVENT_REPAIR,
    EVENT_WARRANTY_CLAIM,
    EVENT_BATTERY_CHECK,
    EVENT_USER_NOTE,
]

# Storage / events
STORAGE_VERSION: Final = 1
STORAGE_KEY_MAINTENANCE: Final = f"{DOMAIN}_maintenance"
EVENT_MAINTENANCE_LOG: Final = f"{DOMAIN}_maintenance_event"
NOTIFICATION_ID_PREFIX: Final = f"{DOMAIN}_"

# ---------------------------------------------------------------------------
# Service names
# ---------------------------------------------------------------------------
SERVICE_START_ZONE: Final = "start_zone"
SERVICE_SET_CUTTING_HEIGHT: Final = "set_cutting_height"
SERVICE_REFRESH: Final = "refresh"
SERVICE_SEND_COMMAND_RAW: Final = "send_command_raw"
SERVICE_SET_PURCHASE_DATE: Final = "set_purchase_date"
SERVICE_SET_WARRANTY_DURATION: Final = "set_warranty_duration"
SERVICE_MARK_BLADES_CHANGED: Final = "mark_blades_changed"
SERVICE_ADD_MAINTENANCE_EVENT: Final = "add_maintenance_event"
SERVICE_EXPORT_MAINTENANCE_LOG: Final = "export_maintenance_log"
SERVICE_RESET_MAINTENANCE_COUNTERS: Final = "reset_maintenance_counters"

# Debug service is opt-in only.
CONF_ENABLE_RAW_COMMAND: Final = "enable_raw_command"
DEFAULT_ENABLE_RAW_COMMAND: Final = False

# ---------------------------------------------------------------------------
# Sensitive keys / patterns — used by the redaction helper (diagnostics + safe logging).
# ---------------------------------------------------------------------------
SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        CONF_USERNAME,
        CONF_PASSWORD,
        CONF_TOKEN,
        CONF_REFRESH_TOKEN,
        "access_token",
        "refresh_token",
        "id_token",
        "authorization",
        "api_key",
        "apikey",
        "secret",
        "client_secret",
        "password",
        "pwd",
        "stream_url",
        "snapshot_url",
        "signed_url",
        "rtsp_url",
        "public_ip",
        "wan_ip",
        "serial",
        "serial_number",
        "sn",
        "mac",
        "ssid",
    }
)
