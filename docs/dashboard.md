# AIRSEEKERS — Lovelace dashboard & automations

The integration uses a **stable entity-ID convention** (prefix `tron`), so the shipped dashboard works
without renaming anything:

| Domain | Entity IDs |
|--------|-----------|
| Mower | `lawn_mower.tron` |
| Position | `device_tracker.tron` |
| Cameras | `camera.tron_front`, `camera.tron_rear`, `camera.tron_left`, `camera.tron_right`, `camera.tron_panoramic` |
| Sensors | `sensor.tron_battery`, `sensor.tron_status`, `sensor.tron_zone`, `sensor.tron_area`, `sensor.tron_rtk`, `sensor.tron_gps`, `sensor.tron_wifi`, `sensor.tron_firmware`, `sensor.tron_error_code` |
| Safety | `binary_sensor.tron_lifted`, `binary_sensor.tron_tilted`, `binary_sensor.tron_blade_blocked`, `binary_sensor.tron_obstacle_detected`, `binary_sensor.tron_rain_detected` |
| Buttons | `button.tron_start`, `button.tron_pause`, `button.tron_return_to_dock`, `button.tron_find`, `button.tron_reset_blade_timer` |
| Number | `number.tron_cutting_height` |
| Selects | `select.tron_zone`, `select.tron_mowing_mode` |
| Switches | `switch.tron_camera_privacy`, `switch.tron_night_mowing` |
| Maintenance | `sensor.tron_warranty_status`, `sensor.tron_blade_status`, `sensor.tron_blade_life_remaining_percent`, … |

These IDs are forced at creation and kept stable across versions by the entity registry (via each
entity's `unique_id`), so a dashboard built on them will not break when the integration updates.

## Full dashboard

The ready-to-use dashboard is **[`lovelace/airseekers_tron_dashboard.yaml`](../lovelace/airseekers_tron_dashboard.yaml)**
(Mower / Cameras / Maintenance views). Add it as a YAML-mode dashboard, or via `configuration.yaml`:

```yaml
lovelace:
  dashboards:
    airseekers-tron:
      mode: yaml
      title: AIRSEEKERS TRON
      filename: lovelace/airseekers_tron_dashboard.yaml
```

## Example automations

```yaml
# 1) Dock when it starts raining
- alias: AIRSEEKERS - dock when raining
  triggers:
    - trigger: state
      entity_id: binary_sensor.tron_rain_detected
      to: "on"
  conditions:
    - condition: state
      entity_id: lawn_mower.tron
      state: mowing
  actions:
    - action: button.press
      target: { entity_id: button.tron_return_to_dock }

# 2) No night mowing (respects the switch.tron_night_mowing preference)
- alias: AIRSEEKERS - no night mowing
  triggers:
    - trigger: state
      entity_id: lawn_mower.tron
      to: mowing
  conditions:
    - condition: time
      after: "21:00:00"
      before: "07:00:00"
    - condition: state
      entity_id: switch.tron_night_mowing
      state: "off"
  actions:
    - action: button.press
      target: { entity_id: button.tron_return_to_dock }

# 3) Return to base on error
- alias: AIRSEEKERS - dock on error
  triggers:
    - trigger: state
      entity_id: binary_sensor.tron_error
      to: "on"
  actions:
    - action: button.press
      target: { entity_id: button.tron_return_to_dock }

# 4) Notify if stuck (lifted/tilted/obstacle for 5 min)
- alias: AIRSEEKERS - stuck notification
  triggers:
    - trigger: state
      entity_id:
        - binary_sensor.tron_lifted
        - binary_sensor.tron_tilted
        - binary_sensor.tron_obstacle_detected
      to: "on"
      for: "00:05:00"
  actions:
    - action: notify.persistent_notification
      data:
        title: AIRSEEKERS
        message: The robot may be stuck (safety sensor active for 5 minutes).

# 5) Warranty reminder
- alias: AIRSEEKERS - warranty expiring soon
  triggers:
    - trigger: state
      entity_id: binary_sensor.tron_warranty_expiring_soon
      to: "on"
  actions:
    - action: notify.persistent_notification
      data:
        title: AIRSEEKERS warranty
        message: >-
          Warranty expires in {{ states('sensor.tron_warranty_days_remaining') }} days.

# 6) Blade replacement reminder
- alias: AIRSEEKERS - blades need replacement
  triggers:
    - trigger: state
      entity_id: binary_sensor.tron_blades_need_replacement
      to: "on"
  actions:
    - action: notify.persistent_notification
      data:
        title: AIRSEEKERS blades
        message: >-
          Blades reached {{ states('sensor.tron_blade_runtime_hours') }} h. Plan a replacement.

# 7) Block mowing on critical maintenance / weather
- alias: AIRSEEKERS - block mowing on critical condition
  triggers:
    - trigger: state
      entity_id: lawn_mower.tron
      to: mowing
  conditions:
    - condition: or
      conditions:
        - condition: state
          entity_id: binary_sensor.tron_blades_need_replacement
          state: "on"
        - condition: state
          entity_id: binary_sensor.tron_error
          state: "on"
        - condition: state
          entity_id: binary_sensor.tron_rain_detected
          state: "on"
  actions:
    - action: button.press
      target: { entity_id: button.tron_return_to_dock }
    - action: notify.persistent_notification
      data:
        title: AIRSEEKERS
        message: Mowing blocked — resolve the active maintenance/weather condition first.
```

> The integration also raises its own persistent-notification alerts for warranty/blade/maintenance,
> so automations 5–6 are optional reinforcements.
