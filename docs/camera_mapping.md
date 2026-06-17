# AIRSEEKERS Camera Mapping (research-grounded)

How the TRON / TRON Max camera system is believed to work, so the integration can map real cameras to
Home Assistant entities once the owner verifies streaming details. Nothing here is invented.

## Status legend

✅ VERIFIED · 🟡 LIKELY · ❓ UNVERIFIED · ⛔ UNKNOWN

## What is known / suspected

- ✅ Marketed as **"360° AI Vision"** with VSLAM-based navigation; the Android app requests Camera +
  Microphone permissions.
- 🟡 The community repo enumerates **4 camera positions**: `main` (front), `rear`, `left`, `right`.
- 🟡 Streaming is **NOT** plain LAN RTSP. It is believed to be **WebRTC, relayed over MQTT through the
  cloud** — i.e. signalling via the cloud, media via WebRTC (likely needs STUN/TURN).
- ⛔ The 300°/360° "composite" the user sees may be an **app-side stitch** of the lenses rather than a
  single composite stream. UNKNOWN whether a composite stream is exposed at the protocol level.
- ⛔ Exact stream URLs, WebRTC signalling, STUN/TURN servers, and any snapshot endpoint are UNKNOWN.

## Camera role map

| Role | Likely on TRON / TRON Max | Stream type | Exposed to user? | Status |
|------|---------------------------|-------------|------------------|--------|
| `front` (main) | yes | WebRTC (cloud-relayed) | yes | 🟡 |
| `rear` | yes | WebRTC (cloud-relayed) | yes | 🟡 |
| `left` | yes | WebRTC (cloud-relayed) | likely | 🟡 |
| `right` | yes | WebRTC (cloud-relayed) | likely | 🟡 |
| `front_left` / `front_right` | maybe (lens layout unknown) | unknown | ⛔ | ❓ |
| `top` / `bottom` | unlikely | unknown | ⛔ | ❓ |
| `obstacle` | possibly a derived/AI view | unknown | maybe (app overlay) | ❓ |
| `navigation` / `mapping` | derived (VSLAM) | unknown | in-app map, not a video feed | ❓ |
| `ai_detection` | possibly an annotated view | unknown | maybe (app overlay) | ❓ |
| `composite_300` | maybe (app-side stitch) | unknown | yes (in app) | ❓ |
| `composite_360` | maybe (app-side stitch) | unknown | yes (in app) | 🟡 |

## Implications for the integration

- The integration must support **dynamic** cameras: create one `camera.*` entity per camera the backend
  actually reports — do not assume a fixed set. Roles drive entity names.
- Stream type per camera is one of: `snapshot`, `mjpeg`, `hls`, `rtsp`, `webrtc`, `cloud`, `proprietary`,
  `unknown`. WebRTC/cloud are expected here, which Home Assistant supports via `stream`/`go2rtc`/WebRTC,
  but only once signalling is known.
- Until verified, the **stub backend** simulates `front`/`left`/`right`/`rear`/`composite_360` with
  distinct labelled snapshot images so the camera UI/dashboards can be built and tested.
- Stream URLs and tokens are **privacy-sensitive**: never logged, never in diagnostics, no external
  re-exposure by default.

## How to complete this (for the owner)

1. `python tools/discover_camera_streams.py --host <IP_ROBOT>` — see which camera-related ports respond
   on the LAN (expected: little/none, since streaming is cloud-relayed).
2. Follow `tools/analyze_app_camera_calls.md`: open each camera view in the app, switch views, open the
   map and obstacle view, and capture the signalling (mitmproxy on your own phone).
3. Record per camera: role · how the app requests it · stream type · whether snapshot is available →
   fill the role map above and `tools/discover_camera_inventory.py`'s template.
4. If streaming proves to be cloud WebRTC only, document the signalling so a `webrtc`/`cloud` camera
   backend can be built; otherwise note snapshot fallbacks.

*Roles and stream types here are LIKELY/UNVERIFIED. The integration adapts to whatever the verified
backend reports.*
