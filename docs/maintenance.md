# AIRSEEKERS — Maintenance, warranty & blade wear

The integration tracks real-world maintenance independently of the robot's cloud, using a persistent
Home Assistant `Store` (these are durable counters, not transient timers — they survive restarts).

## What is tracked

| Item | Entity | Source |
|------|--------|--------|
| Warranty end date / days remaining / status | `sensor.*_warranty_end_date` / `_warranty_days_remaining` / `_warranty_status` | purchase date + duration |
| Blade runtime / life remaining / status | `sensor.*_blade_runtime` / `_blade_life_remaining` / `_blade_status` | device mowing hours − baseline at last change |
| Last / next blade change | `sensor.*_last_blade_change` / `_next_blade_change_estimate` | stored date + usage rate |
| Total mowing time / cycles | `sensor.*_total_mowing_time` / `_total_mowing_cycles` | device counters |
| Maintenance status | `sensor.*_maintenance_status` | blades-replace OR active error |

Binary sensors: `warranty_expiring_soon`, `warranty_expired`, `blades_need_replacement`,
`maintenance_required`.

## Configuring

- **Purchase date / warranty duration:** services `airseekers.set_purchase_date` and
  `airseekers.set_warranty_duration` (or the options flow seeds the duration).
- **Thresholds** (live, editable as Number entities): `number.*_blade_lifetime_hours` (default 100 h),
  `number.*_warranty_warning_days` (default 60 d), `number.*_blade_warning_percent` (default 20 %).
  The options flow provides the initial seeds; the Number entities (backed by the Store) are
  authoritative afterwards.

## Actions

| Action | Button | Service |
|--------|--------|---------|
| Record a blade change (resets wear + logs) | `button.*_mark_blades_changed` | `airseekers.mark_blades_changed` |
| Reset blade timer only | `button.*_reset_blade_timer` | — |
| Acknowledge/clear alerts (re-arms them) | `button.*_reset_maintenance_alert` | — |
| Export the log (as a notification) | `button.*_export_maintenance_log` | `airseekers.export_maintenance_log` |
| Add a log entry | — | `airseekers.add_maintenance_event` |
| Reset maintenance counters (keeps log) | — | `airseekers.reset_maintenance_counters` |

## Maintenance log

Each event is stored as:

```json
{ "date": "2026-06-18", "type": "blade_change", "comment": "Replaced 3 blades", "mowing_hours": 42.5, "cycles": 18 }
```

Event types: `blade_change`, `cleaning`, `firmware_update`, `repair`, `warranty_claim`,
`battery_check`, `user_note`. Every new event also fires the `airseekers_maintenance_event` bus event
(usable as an automation trigger).

## Alerts (anti-spam)

Persistent notifications are raised when the warranty is expiring soon / expired, blades need
replacement, or maintenance is required. Each alert fires **once**, then **re-arms automatically** when
the condition clears, and is also re-armed after a reset, a threshold change, or a new maintenance
event — so you are not spammed but are reminded again when something new happens.
