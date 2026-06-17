# AIRSEEKERS — Lovelace dashboard & automations

> Entity IDs depend on your device name. With the default name *AIRSEEKERS TRON Max* you get IDs like
> `lawn_mower.airseekers_tron_max`, `sensor.airseekers_tron_max_battery`,
> `camera.airseekers_tron_max_front`, etc. Adjust the IDs below to match **Developer Tools → States**.

## Dashboard (YAML mode)

```yaml
title: AIRSEEKERS
views:
  - title: Mower
    cards:
      - type: vertical-stack
        cards:
          - type: heading
            heading: AIRSEEKERS TRON Max

          # Robot status & control
          - type: entities
            title: Status
            entities:
              - entity: lawn_mower.airseekers_tron_max
              - entity: sensor.airseekers_tron_max_state
              - entity: sensor.airseekers_tron_max_battery
              - entity: binary_sensor.airseekers_tron_max_online
              - entity: binary_sensor.airseekers_tron_max_charging
              - entity: binary_sensor.airseekers_tron_max_raining
              - entity: sensor.airseekers_tron_max_error_message

          - type: gauge
            name: Battery
            entity: sensor.airseekers_tron_max_battery
            min: 0
            max: 100
            severity: { green: 40, yellow: 20, red: 0 }

          # Control buttons
          - type: horizontal-stack
            cards:
              - type: button
                name: Start
                icon: mdi:play
                tap_action: { action: perform-action, perform_action: button.press,
                  target: { entity_id: button.airseekers_tron_max_start } }
              - type: button
                name: Pause
                icon: mdi:pause
                tap_action: { action: perform-action, perform_action: button.press,
                  target: { entity_id: button.airseekers_tron_max_pause } }
              - type: button
                name: Dock
                icon: mdi:home-import-outline
                tap_action: { action: perform-action, perform_action: button.press,
                  target: { entity_id: button.airseekers_tron_max_dock } }
              - type: button
                name: Stop
                icon: mdi:stop
                tap_action: { action: perform-action, perform_action: button.press,
                  target: { entity_id: button.airseekers_tron_max_stop } }

          - type: entities
            entities:
              - entity: select.airseekers_tron_max_zone
              - entity: number.airseekers_tron_max_cutting_height
              - entity: sensor.airseekers_tron_max_rtk_status
              - entity: sensor.airseekers_tron_max_gps_signal
              - entity: sensor.airseekers_tron_max_wifi_rssi

      # Cameras — grid adapts to however many camera entities exist
      - type: grid
        columns: 2
        square: false
        cards:
          - type: picture-entity
            entity: camera.airseekers_tron_max_360_view
            camera_view: auto
          - type: picture-entity
            entity: camera.airseekers_tron_max_front
            camera_view: auto
          - type: picture-entity
            entity: camera.airseekers_tron_max_left
            camera_view: auto
          - type: picture-entity
            entity: camera.airseekers_tron_max_right
            camera_view: auto
          - type: picture-entity
            entity: camera.airseekers_tron_max_rear
            camera_view: auto

  - title: Maintenance AIRSEEKERS
    cards:
      - type: vertical-stack
        cards:
          - type: heading
            heading: Maintenance
          - type: gauge
            name: Blade life remaining
            entity: sensor.airseekers_tron_max_blade_life_remaining
            min: 0
            max: 100
            severity: { green: 40, yellow: 20, red: 0 }
          - type: entities
            title: Warranty
            entities:
              - entity: sensor.airseekers_tron_max_warranty_status
              - entity: sensor.airseekers_tron_max_warranty_days_remaining
              - entity: sensor.airseekers_tron_max_warranty_end_date
          - type: entities
            title: Blades
            entities:
              - entity: sensor.airseekers_tron_max_blade_status
              - entity: sensor.airseekers_tron_max_blade_runtime
              - entity: sensor.airseekers_tron_max_last_blade_change
              - entity: sensor.airseekers_tron_max_next_blade_change_estimate
          - type: entities
            title: Counters & actions
            entities:
              - entity: sensor.airseekers_tron_max_total_mowing_time
              - entity: sensor.airseekers_tron_max_total_mowing_cycles
              - entity: sensor.airseekers_tron_max_maintenance_status
              - entity: button.airseekers_tron_max_mark_blades_changed
              - entity: button.airseekers_tron_max_export_maintenance_log
```

## Example automations

```yaml
# 1) Don't mow while it's raining — dock instead
- alias: AIRSEEKERS - dock when raining
  triggers:
    - trigger: state
      entity_id: binary_sensor.airseekers_tron_max_raining
      to: "on"
  conditions:
    - condition: state
      entity_id: lawn_mower.airseekers_tron_max
      state: mowing
  actions:
    - action: button.press
      target: { entity_id: button.airseekers_tron_max_dock }

# 2) No mowing at night (example: pause between 21:00 and 07:00 if it starts)
- alias: AIRSEEKERS - no night mowing
  triggers:
    - trigger: state
      entity_id: lawn_mower.airseekers_tron_max
      to: mowing
  conditions:
    - condition: time
      after: "21:00:00"
      before: "07:00:00"
  actions:
    - action: button.press
      target: { entity_id: button.airseekers_tron_max_pause }

# 3) Return to base on error
- alias: AIRSEEKERS - dock on error
  triggers:
    - trigger: state
      entity_id: binary_sensor.airseekers_tron_max_error
      to: "on"
  actions:
    - action: button.press
      target: { entity_id: button.airseekers_tron_max_dock }

# 4) Notify if the robot is stuck (obstacle detected for 5 min)
- alias: AIRSEEKERS - stuck notification
  triggers:
    - trigger: state
      entity_id: binary_sensor.airseekers_tron_max_obstacle_detected
      to: "on"
      for: "00:05:00"
  actions:
    - action: notify.persistent_notification
      data:
        title: AIRSEEKERS
        message: The robot may be stuck (obstacle detected for 5 minutes).

# 5) Warranty reminder (fires from the integration's own binary sensor)
- alias: AIRSEEKERS - warranty expiring soon
  triggers:
    - trigger: state
      entity_id: binary_sensor.airseekers_tron_max_warranty_expiring_soon
      to: "on"
  actions:
    - action: notify.persistent_notification
      data:
        title: AIRSEEKERS warranty
        message: >-
          The AIRSEEKERS warranty expires in
          {{ states('sensor.airseekers_tron_max_warranty_days_remaining') }} days.
          Check for any issues before it ends.

# 6) Blade replacement reminder
- alias: AIRSEEKERS - blades need replacement
  triggers:
    - trigger: state
      entity_id: binary_sensor.airseekers_tron_max_blades_need_replacement
      to: "on"
  actions:
    - action: notify.persistent_notification
      data:
        title: AIRSEEKERS blades
        message: >-
          The blades reached {{ states('sensor.airseekers_tron_max_blade_runtime') }} h. Plan a replacement.

# 7) Block mowing on critical maintenance (blades/ error / rain)
- alias: AIRSEEKERS - block mowing on critical maintenance
  triggers:
    - trigger: state
      entity_id: lawn_mower.airseekers_tron_max
      to: mowing
  conditions:
    - condition: or
      conditions:
        - condition: state
          entity_id: binary_sensor.airseekers_tron_max_blades_need_replacement
          state: "on"
        - condition: state
          entity_id: binary_sensor.airseekers_tron_max_error
          state: "on"
        - condition: state
          entity_id: binary_sensor.airseekers_tron_max_raining
          state: "on"
  actions:
    - action: button.press
      target: { entity_id: button.airseekers_tron_max_dock }
    - action: notify.persistent_notification
      data:
        title: AIRSEEKERS
        message: Mowing blocked — resolve the active maintenance/weather condition first.
```

> The integration also raises its own persistent-notification alerts for warranty/blade/maintenance,
> so automations 5–6 are optional reinforcements.
