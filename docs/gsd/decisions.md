# Technical Decisions (ADR log) — ha-airseekers

Lightweight ADRs. Newest first. Status: ✅ accepted · 🔄 revisit · ⏳ pending.

## ADR-0007 — Maintenance state via `Store` + `RestoreEntity`, not `timer` ⏳
**Context:** Warranty dates, blade hours, mowing cycles are durable maintenance counters.
**Decision:** Persist via `homeassistant.helpers.storage.Store` (the maintenance log + arming state) and
`RestoreEntity`/`RestoreSensor` (cumulative sensors), not HA `timer` helpers.
**Why:** `timer`s are transient and reset; maintenance must survive restarts and reconfigure.

## ADR-0006 — Privacy-first cameras ⏳
**Decision:** Default to no recording, no external exposure; never write stream URLs/tokens to logs or
diagnostics; provide `privacy_mode`, disable-when-docked, disable-at-night options.
**Why:** Cameras on a yard robot are sensitive; safe defaults protect the owner.

## ADR-0005 — Capability-driven entities ⏳
**Decision:** Entities (sensors, controls, cameras) are created only when the backend reports the
matching capability; cameras are created dynamically, one per reported camera.
**Why:** Avoids dead entities and adapts to TRON vs TRON Max and to whatever the real protocol exposes.

## ADR-0004 — Never invent the AIRSEEKERS API ✅
**Decision:** Real backends (`local_http`, `cloud_http`, `mqtt`, `rtsp`) ship as stubs that raise a clear
"unsupported until discovered" error. No endpoint/URL/port/payload is fabricated anywhere.
**Why:** Honesty + safety constraint; only owner-verified discovery yields real backends.

## ADR-0003 — Backend abstraction with a complete `stub` first ✅
**Decision:** One `AirseekersClient` interface; selectable backend; `stub` is fully functional and is the
default. The entity layer depends only on the client interface.
**Why:** De-risks the unknown protocol and keeps every phase shippable.

## ADR-0002 — GSD managed manually in this repo ✅
**Context:** The parent directory is itself an active GSD project, so `gsd-sdk` anchors to the outer
worktree and won't target the nested `airseekers/` repo (`--project-dir` doesn't override it).
**Decision:** Maintain GSD artifacts (`.planning/`, `docs/gsd/`) by hand; commit with plain git here;
still use GSD research/roadmap *agents* for quality.
**Why:** Keeps the HACS repo self-contained and avoids colliding with the parent project's GSD state.

## ADR-0001 — Standalone git repo for the HACS integration ✅
**Decision:** `git init` inside `airseekers/`, isolated from the parent Home Assistant infra repo.
**Why:** HACS custom repositories must be self-contained git repos; isolation keeps `.planning/` and code clean.
