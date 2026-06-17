# ha-airseekers

## What This Is

A Home Assistant **custom integration** (domain `airseekers`, display name `AIRSEEKERS`) for the
AIRSEEKERS **TRON / TRON Max** RTK robotic lawn mower. It lets the owner monitor and control their
own robot from Home Assistant, view its on-board camera(s), and track real-world maintenance
(warranty countdown, blade wear, mowing hours/cycles, maintenance history). It is HACS-installable
as a custom repository and is built to run **first against a fully functional stub/mock backend**,
then have its real backends completed after clean, owner-driven protocol discovery.

## Core Value

The owner can install the integration via HACS, add their robot through a config flow, and
immediately get a **working, fully populated Home Assistant device** (mower entity, sensors,
multiple cameras, maintenance tracking) — even before the real AIRSEEKERS protocol is mapped —
thanks to a complete stub backend. Everything else builds toward swapping the stub for verified
real backends without changing the entity layer.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Installable via HACS as a custom repository; loads cleanly in Home Assistant
- [ ] Fully functional `stub` backend so the whole integration works with no real API
- [ ] Async API client with a backend abstraction (stub / local_http / cloud_http / mqtt / rtsp)
- [ ] `lawn_mower` entity with start/pause/dock (+ best-effort stop) and mapped activity states
- [ ] DataUpdateCoordinator with adaptive polling (fast when active, slow when idle), configurable
- [ ] Config flow + options flow + reauth flow
- [ ] Sensors, binary sensors, buttons, numbers, selects driven by reported capabilities
- [ ] Dynamic multi-camera support (1..N cameras, composite 360, snapshot/live, multiple stream types)
- [ ] Persistent maintenance: warranty countdown, blade wear, mowing time/cycles, maintenance log
- [ ] Maintenance alerts via persistent notifications without spam (armed/re-armed correctly)
- [ ] Home Assistant services for control and maintenance
- [ ] Diagnostics with strict redaction of all secrets/tokens/signed URLs/stream URLs
- [ ] Non-intrusive LAN / HTTP / MQTT / camera discovery tools to complete the real API
- [ ] Lovelace dashboard + example automations
- [ ] Tests (pytest), ruff/mypy clean, complete README and docs

### Out of Scope

- Inventing or guessing any AIRSEEKERS API endpoint, URL, port, or payload — only verified protocol details get real backends
- Hardcoding credentials, tokens, or "magic" URLs
- Breaking, bypassing, or weakening any encryption/authentication
- Logging or persisting any secret, token, signed URL, or private camera stream
- Recording/re-exposing camera streams outside Home Assistant by default (privacy-first)
- Cloud reverse-engineering of anyone else's account — interoperability is limited to the owner's own robot/account/network

## Context

- **Greenfield** standalone repo (`airseekers/`) with its own git history, isolated from the
  surrounding Home Assistant Docker infra repo (which is itself a separate GSD project).
- Target runtime: Home Assistant Core on Python 3.12+; full async; typed.
- The robot is already on the owner's Wi-Fi; coverage spans the whole property.
- It is currently UNKNOWN whether the robot exposes a local API, is cloud-only, uses MQTT, and how
  its camera(s) stream. The architecture must not assume; the stub backend de-risks this entirely.
- Comparable RTK camera mowers (Mammotion, Segway Navimow, Ecovacs Goat) inform expectations only
  as analogy — never as AIRSEEKERS fact.

## Constraints

- **Tech stack**: Home Assistant Core integration, Python 3.12+, asyncio/aiohttp, full async, typed.
- **Distribution**: HACS custom repository — repo must be self-contained and HACS-valid.
- **Security**: never log/persist secrets; redact diagnostics; privacy-first cameras; no encryption bypass.
- **Honesty**: no invented APIs; clearly mark VERIFIED vs UNVERIFIED throughout docs.
- **Process**: GSD-managed manually (parent is an active GSD project); atomic git commits per phase.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Standalone git repo in `airseekers/` | HACS custom repo must be self-contained; isolates `.planning/` from the parent infra GSD project | ✓ Good |
| GSD managed manually (no `gsd-sdk` here) | `gsd-sdk` anchors to the outer worktree which is already a GSD project; manual keeps this repo clean | — Pending |
| Backend abstraction with a complete `stub` first | De-risks unknown protocol; entity layer stable while real backends are filled in later | — Pending |
| Never invent AIRSEEKERS endpoints | Honesty + safety constraint; real backends only from owner-verified discovery | — Pending |
| Persistent maintenance via `Store` + `RestoreEntity` | Counters/dates are durable maintenance state, not transient `timer`s | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

---
*Last updated: 2026-06-17 after initialization*
