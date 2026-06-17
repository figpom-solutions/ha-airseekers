# AIRSEEKERS API Mapping (research-grounded)

This documents what is **publicly known** about how the AIRSEEKERS TRON / TRON Max communicates, so
the integration's real backends can be completed from **owner-verified** observation — never invented.

## Status legend

| Mark | Meaning |
|------|---------|
| ✅ VERIFIED | Confirmed from a primary/credible source (cited) |
| 🟡 LIKELY | Reported by community work or strong analogy; not vendor-confirmed |
| ❓ UNVERIFIED | Plausible but unconfirmed — must be observed before use |
| ⛔ UNKNOWN | Not known; do not guess |

## Mobile app

| Item | Value | Status |
|------|-------|--------|
| iOS app | "Airseekers" — bundle `com.changyao.app.airseekers` (App Store ID 6670376112) | ✅ |
| Android app | "AIrseekers" — package `com.changyao.asMower` | ✅ |
| Developer | Changyao Innovation Technology (Shenzhen) | ✅ |
| Android permissions | Camera, Microphone, Wi-Fi | ✅ |

## Cloud vs Local

- ✅ **Control is cloud-dependent.** The proven, documented path is **HTTPS REST cloud polling**.
- 🟡 A community Home Assistant integration exists — **`AdrianTIonut/airseekers-tron-ha`** — declaring
  `iot_class: cloud_polling`. Treat its endpoint paths as **LIKELY**, a starting point for the owner to
  verify against their own account; do not assume vendor-confirmed.
- ⛔ Whether the robot exposes **any** local API is UNKNOWN (likely not). Do not invent one.

## Known domains (names only — no endpoint paths assumed)

| Domain | Role | Status |
|--------|------|--------|
| `airseekers-robotics.com` | Marketing / store | ✅ |
| `cloud-eu.airseekers-robotics.com` | Cloud API (EU region) | 🟡 |

> Region matters: there may be non-EU API hosts. The owner must confirm the host **their** app uses;
> it is a config-flow input, never hardcoded.

## Auth model

| Item | Value | Status |
|------|-------|--------|
| Login | email + password | 🟡 |
| Token | JWT **Bearer**, ~2h lifetime | 🟡 |
| Refresh | refresh token | 🟡 |
| Sessions | **one active session per account** | 🟡 |

> ⚠️ **One-session caveat (design-critical).** If the cloud backend logs in, it may evict the phone
> app's session (and vice-versa). The integration must: (a) use a **long idle poll interval**, (b) make
> polling intervals configurable, and (c) document this clearly. Consider an option to pause polling.

## Suspected protocol(s)

| Channel | Use | Status | Reusable by 3rd party? |
|---------|-----|--------|------------------------|
| HTTPS REST (cloud) | Login, status polling, commands | 🟡 | Yes (with account creds) |
| MQTT + protobuf | Real-time control / telemetry | 🟡 | ⛔ No — locked by a **per-device IoT TLS client cert** (single client ID) |
| WebRTC over MQTT (cloud-relayed) | Camera streaming | 🟡 | ⛔ Not publicly built |

Implication for backends:
- `cloud_http`: the realistic first real backend — REST polling + commands, JWT auth. Stays a **stub**
  here until the owner verifies request/response shapes against their account.
- `mqtt`: blocked for third parties by the device cert; treat as research-only unless the owner can
  extract their own device's credentials legitimately.
- `local_http`: likely non-existent; keep as a stub.

## Endpoint table (fill in from YOUR OWN observed traffic)

> Do **not** paste community-repo paths here as if confirmed. Capture from your own account and mark
> the status. Anonymise (no real tokens/serials) before sharing.

| Endpoint | Method | Auth | Request payload | Response | HA mapping | Source/Status |
|----------|--------|------|-----------------|----------|------------|---------------|
| _(login)_ | POST | none → returns JWT | email, password | access+refresh token | reauth/login | ❓ UNVERIFIED |
| _(token refresh)_ | POST | refresh token | refresh token | new access token | coordinator reauth | ❓ UNVERIFIED |
| _(device list)_ | GET | Bearer | — | devices[] | `async_get_devices` | ❓ UNVERIFIED |
| _(device status)_ | GET | Bearer | device id | status object | coordinator → all sensors | ❓ UNVERIFIED |
| _(start/pause/dock)_ | POST | Bearer | device id, command | ack | `lawn_mower` actions | ❓ UNVERIFIED |
| _(cutting height)_ | POST | Bearer | device id, height | ack | `number.cutting_height` | ❓ UNVERIFIED |

## Existing community work

- 🟡 `AdrianTIonut/airseekers-tron-ha` — community HA integration, `cloud_polling`. Best reference for
  the REST surface. **Verify, don't copy blindly.**

## Analogous mowers (ANALOGY only — not AIRSEEKERS fact)

- Mammotion Luba/Yuka, Segway Navimow, Ecovacs Goat — all cloud + MQTT/protobuf, with HA integrations
  reverse-engineered from app traffic. They show the expected shape (cloud REST + MQTT realtime + cloud
  camera relay) but say nothing definitive about AIRSEEKERS.

## How to complete this (for the owner)

1. Find the robot IP from your router/DHCP. Run `python tools/discover_lan.py` (non-intrusive).
2. On **your own phone/account**, use mitmproxy to observe the app's HTTPS traffic
   (`tools/extract_app_domains.md`, `tools/README_DISCOVERY.md`). Confirm the API host.
3. Record each call: endpoint · method · payload · response · matching HA entity → fill the table above.
4. **Anonymise** (strip tokens, serials, emails) before sharing or contributing.
5. Mind the one-session caveat: testing the cloud backend may log your app out.

*Nothing in this file is hardcoded into the integration. Real backends are completed only after the
above verification.*
