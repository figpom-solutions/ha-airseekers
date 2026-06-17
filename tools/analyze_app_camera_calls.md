# Analyzing the AIRSEEKERS Mobile App's Camera Behaviour

This document is a step-by-step procedure for capturing and cataloguing every camera-related
network call the AIRSEEKERS app makes, so you can replicate those calls from a Home Assistant
integration.

---

## 1. Prerequisites

Before starting, complete the proxy setup described in **README_DISCOVERY.md sections 6.1–6.4**:

- mitmproxy installed on your laptop (`mitmproxy --version` returns a version string)
- Your phone's Wi-Fi proxy configured to `<LAPTOP_IP>:8080`
- The mitmproxy CA certificate installed and trusted on the phone
- The AIRSEEKERS app opens and logs in normally while the proxy is running (no TLS errors)

If you see SSL errors in the app, the app may use certificate pinning — see section 6 of this
document before continuing.

Useful tools:
```bash
mitmweb          # browser UI at http://127.0.0.1:8081 — recommended for this procedure
mitmdump -w session.flows   # save everything to a file for later analysis
```

---

## 2. Step-by-Step: One Camera View at a Time

Work through each view methodically. For every view listed below:

1. **Clear** the mitmproxy flow list (press `z` in mitmproxy, or use the "Clear" button in
   mitmweb) so you only see traffic from that specific interaction.
2. **Trigger** the view in the app.
3. **Wait** 5–10 seconds for the stream to stabilise or the first frames to appear.
4. **Record** every new flow in the proxy according to the template in section 3.
5. **Note** whether the connection closes immediately (snapshot) or stays open (stream).

### 2a. Opening the Camera View

Navigate from the main map screen to the camera/live-view screen.

What to look for:

- An initial HTTP/HTTPS request that returns a URL, token, or connection parameters for the
  actual stream (common pattern: REST call returns `{"rtsp_url": "rtsp://..."}` or
  `{"stream_token": "..."}`)
- A direct RTSP negotiation (OPTIONS, DESCRIBE, SETUP, PLAY) — visible in Wireshark but
  **not** in mitmproxy (RTSP is not HTTP; you need tcpdump/Wireshark for RTSP, see
  README_DISCOVERY.md section 5)
- An MJPEG stream: a single HTTP GET that returns `Content-Type: multipart/x-mixed-replace`
  and never closes
- A WebRTC signaling request: a POST to a `/rtc/offer` or `/webrtc/signal` endpoint carrying
  an SDP blob (see section 4)
- An HLS manifest: a GET returning `Content-Type: application/vnd.apple.mpegurl` (`.m3u8`)

### 2b. Switching Between Camera Views (Front / Rear / Obstacle / Mapping)

If the app shows multiple camera feeds (e.g. front camera, rear camera, obstacle-detection
camera):

1. Start on the first camera view with a clean mitmproxy session.
2. Switch to the second view.
3. Check whether:
   - A **new GET request** is made to a different URL/path
   - A **query parameter** changes (e.g. `?cam=rear`)
   - The **same URL** is reused but with a new token or session ID
   - The previous stream connection is closed before the new one opens

Record the URL pattern for each camera position in the table (section 3).

### 2c. Mapping / Top-Down View

The top-down map view often uses a different data source than the live camera feed:

- It may be a static satellite/aerial tile (requests to a map tile CDN with `/{z}/{x}/{y}.png`)
- It may be a locally-generated map uploaded to the cloud (a JPEG or PNG fetched from the API)
- It may be a continuously-updated raster pushed via WebSocket

Look for:
- Requests to tile CDN hostnames (e.g. `*.googleapis.com`, `*.mapbox.com`, custom tile server)
- A GET to an endpoint like `/device/<serial>/map/latest.png`
- A WebSocket upgrade (`101 Switching Protocols`) followed by binary frames

### 2d. Obstacle Detection View

The obstacle-detection camera feed may be:

- The same raw stream as the front camera (processed on the phone)
- A separate annotated/encoded stream served from the robot (different port or path)
- A periodic snapshot with bounding-box JSON overlaid by the app

Look for requests immediately after switching to this view, especially any JSON response
containing arrays of bounding boxes, coordinates, or confidence scores alongside a stream URL.

### 2e. Live Preview During Mowing

While mowing is in progress:

- Trigger the live preview.
- Wait 30 seconds and watch the proxy for repeated identical URLs (periodic snapshots) vs. a
  single persistent connection (continuous stream).
- If you see repeated GETs to the same URL every N seconds, the app is using snapshot polling —
  note the interval.
- If you see a single open connection, it is streaming — note the Content-Type.

---

## 3. What to Capture in mitmproxy for Each View

For each camera-related flow in mitmproxy, record the following fields. In mitmweb, click a
flow to open the detail pane.

| Field | Where to find it | What to record |
|-------|-----------------|----------------|
| Full URL | Request tab > URL | Full URL, redact tokens in query params |
| HTTP method | Request tab | GET / POST / etc. |
| Range header | Request tab > Headers | Present for HLS/DASH segments |
| Accept header | Request tab > Headers | `image/jpeg`, `video/*`, `application/sdp`, etc. |
| Authorization presence | Request tab > Headers | Yes/No (do not record the value) |
| Response Content-Type | Response tab > Headers | Key discriminator — see table below |
| Response status | Response tab | 200, 206, 301, 403, etc. |
| Connection behaviour | Response tab | Does the response body keep growing? (stream) or finish? (snapshot) |

### Content-Type quick reference

| Content-Type | Meaning |
|-------------|---------|
| `multipart/x-mixed-replace; boundary=...` | MJPEG push stream |
| `video/mp4` | MP4 segment (HLS/DASH or download) |
| `application/vnd.apple.mpegurl` | HLS manifest (.m3u8) |
| `application/x-mpegURL` | HLS manifest (alternate MIME) |
| `application/dash+xml` | DASH manifest (.mpd) |
| `image/jpeg` | Single JPEG snapshot |
| `application/json` + SDP content | WebRTC signaling response |
| `application/sdp` | SDP answer (WebRTC or RTSP over HTTP) |
| `video/x-flv` | Legacy FLV stream (rare) |

---

## 4. WebRTC Check

If the app uses WebRTC for the camera feed, you will see characteristic HTTP traffic:

1. A POST to a path such as `/rtc/offer`, `/webrtc/session`, `/signal`, or `/peer` carrying a
   JSON body with an `sdp` field (the SDP offer).
2. The server responds with a JSON body containing the SDP answer.
3. Subsequent STUN/TURN negotiation happens over UDP and will **not** appear in mitmproxy
   (capture with tcpdump to see it).

To find STUN/TURN:
```bash
sudo tcpdump -i <wifi_iface> -n udp and host <PHONE_IP>
```

STUN packets use port 3478 (UDP/TCP). The STUN server address is usually embedded in the SDP
offer/answer — look for `a=candidate:` lines.

If WebRTC is confirmed, note the signaling endpoint URL, the STUN/TURN server hostnames, and
whether the SDP contains `a=sendonly` (server sends, you receive) — this is the typical pattern
for one-way camera feeds.

---

## 5. Recording Format

Create or update `tools/reports/camera_calls.md` with the following table. Add one row per
distinct camera view or interaction:

```markdown
| view | url_pattern | method | content_type | stream_or_snapshot | auth | notes |
|------|-------------|--------|--------------|--------------------|------|-------|
| front_camera | https://<API>/v1/stream?cam=front&token=<REDACTED> | GET | multipart/x-mixed-replace | stream | Bearer token | Connection stays open ~60 s then re-established |
| rear_camera | https://<API>/v1/stream?cam=rear&token=<REDACTED> | GET | multipart/x-mixed-replace | stream | Bearer token | Same URL pattern, cam param changes |
| map_view | https://<TILE_CDN>/{z}/{x}/{y}.png | GET | image/png | snapshot | none | Standard slippy map tiles |
| obstacle_view | https://<API>/v1/stream?cam=front&overlay=1 | GET | multipart/x-mixed-replace | stream | Bearer token | Overlay param adds bounding boxes server-side? |
| live_preview | https://<API>/v1/snapshot?cam=front | GET | image/jpeg | snapshot | Bearer token | Polled every 5 s during mowing |
```

Columns:

- **view** — descriptive name of the app screen / camera position
- **url_pattern** — full URL with tokens replaced by `<REDACTED>`
- **method** — HTTP verb
- **content_type** — from the response Content-Type header
- **stream_or_snapshot** — `stream` if the connection stays open, `snapshot` if it closes
- **auth** — auth mechanism observed (Bearer token, API key, none)
- **notes** — anything unusual: reconnection behaviour, query params that change, WebRTC, etc.

---

## 6. Pitfalls

### Certificate pinning on Android

If the app refuses to work while the proxy is active, it is using certificate pinning. To bypass
**on your own APK and device only**:

```bash
pip install apk-mitm

# Extract the APK from your device
adb shell pm list packages | grep airseekers
adb shell pm path com.airseekers.app   # note the path
adb pull /data/app/com.airseekers.app-1/base.apk airseekers.apk

# Patch the APK
apk-mitm airseekers.apk
# Output: airseekers-patched.apk

# Install the patched version
adb install airseekers-patched.apk
```

`apk-mitm` modifies the network security configuration to trust user-installed CA certificates.
This is legal only on your own device with your own APK.

### Certificate pinning on iOS

On a non-jailbroken iPhone, bypassing pinning requires a jailbreak and tools such as SSL Kill
Switch 2. This is at the owner's own risk and voids the device warranty. If iOS pinning is a
blocker, consider using an Android device or emulator for capture.

### App switching to local LAN when on the same network

Some robot apps detect that the phone and the robot are on the same LAN and switch from cloud
streams to direct LAN streams. If this happens, mitmproxy will not see the camera traffic
(because LAN traffic is not proxied through the internet). In that case, use
`discover_camera_streams.py` and `probe_rtsp.py` / `probe_mjpeg.py` to probe the robot directly.

### Streams that require a local network handshake before cloud playback

The app may call a local endpoint first (e.g. `http://<IP_ROBOT>/stream/auth`) to obtain a
one-time token, then use that token with the cloud stream. Capturing both LAN traffic (tcpdump)
and cloud traffic (mitmproxy) simultaneously gives the full picture.

---

## 7. Using the Results to Fill in discover_camera_inventory.py

After completing the table in section 5, open `tools/discover_camera_inventory.py` and update
the `EXPECTED_STREAMS` or equivalent constant with the URL patterns and ports you confirmed:

```python
EXPECTED_STREAMS = [
    {
        "name": "front_camera",
        "url_template": "http://{host}:8080/video",   # or cloud URL pattern
        "type": "mjpeg",
        "auth_required": False,
    },
    {
        "name": "rtsp_main",
        "url_template": "rtsp://{host}:554/live",
        "type": "rtsp",
        "auth_required": False,
    },
    # Add additional streams from your recording table here
]
```

This allows `discover_camera_inventory.py --host <IP_ROBOT>` to automatically verify which
streams are reachable on future firmware versions and report regressions.
