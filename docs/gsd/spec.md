# GSD Spec — ha-airseekers

> Canonical project context and requirements live in `.planning/`. This file is the human-facing
> GSD entry point and a stable summary.

- **Project:** `ha-airseekers`
- **HA domain:** `airseekers` · **Display name:** `AIRSEEKERS` · **Initial model:** `TRON Max`
- **Type:** Home Assistant custom integration, HACS custom repository, Python 3.12+, full async.

## One-line goal

Install via HACS → add the robot → a fully working Home Assistant device (mower, sensors, cameras,
maintenance) on a complete **stub backend**, before the real AIRSEEKERS protocol is mapped — then
swap the stub for owner-verified real backends without changing the entity layer.

## Authoritative documents

| Topic | File |
|-------|------|
| Vision, scope, constraints, decisions | `.planning/PROJECT.md` |
| Requirements (REQ-IDs) | `.planning/REQUIREMENTS.md` |
| Phase plan | `.planning/ROADMAP.md` → mirrored in `docs/gsd/phases.md` |
| Live state | `.planning/STATE.md` |
| Technical decisions (ADR log) | `docs/gsd/decisions.md` |
| Technical context / notes | `docs/gsd/context.md` |
| Current task breakdown | `docs/gsd/tasks.md` |
| Protocol reality (research) | `docs/api_mapping.md`, `docs/camera_mapping.md` |
| HA architecture & API reference | `docs/architecture.md` |

## Hard constraints (non-negotiable)

1. Never invent an AIRSEEKERS API (no fabricated endpoints/URLs/ports/payloads).
2. No hardcoded credentials or magic URLs.
3. Never log/persist secrets, tokens, refresh tokens, signed URLs, or private camera streams.
4. Never break/bypass/weaken encryption or auth.
5. Privacy-first cameras; redact diagnostics.
6. Interop limited to the owner's own robot/account/network.

*Code generation for the integration is in scope and encouraged.*
