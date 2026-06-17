# Identifying Domains Contacted by the AIRSEEKERS App

This guide explains how to build a complete list of every hostname the AIRSEEKERS mobile app
contacts, so you know which cloud services the integration must interact with.

---

## 1. Legal Preamble

All methods described here apply **only to your own device and your own account**. You must:

- Own the phone or tablet running the AIRSEEKERS app.
- Be the registered account holder for the AIRSEEKERS service.
- Administer the network you are monitoring, or have explicit permission from the administrator.

Do not sniff traffic from other users' devices. Anonymise any data before sharing — see section 8.

---

## 2. Method A — DNS Logging on the Router

This is the least invasive method and works even if the app uses certificate pinning.

### Enable DNS query logging

**dnsmasq (OpenWrt, DD-WRT, or Pi-hole):**

```bash
# SSH into the router, then:
uci set dhcp.@dnsmasq[0].logqueries=1
uci commit dhcp
/etc/init.d/dnsmasq restart

# Tail the log
logread -f | grep dnsmasq
```

**Pi-hole:**

Pi-hole logs all DNS queries by default. Open the Pi-hole web UI > Query Log. Filter by the
phone's IP address.

**Unbound:**

```ini
# In /etc/unbound/unbound.conf, add:
server:
    log-queries: yes
    verbosity: 2
```

Restart Unbound. Queries appear in `/var/log/unbound/unbound.log`.

### Collect data

With logging enabled, use the AIRSEEKERS app for 10–15 minutes and perform every major action:

1. Open the app and log in
2. Connect to the mower
3. Open the camera / live view
4. Switch between camera views (front, rear, obstacle, map)
5. Start and stop mowing
6. Check the mowing schedule
7. Open device settings / firmware info

### Filter for the phone's IP

```bash
# dnsmasq log
grep "<PHONE_IP>" /var/log/dnsmasq.log | grep "query\[A\]" | awk '{print $NF}' | sort -u

# Pi-hole CLI
pihole -t | grep "<PHONE_IP>"
```

---

## 3. Method B — DNS Sniffing with tcpdump

Use this when you cannot access the router's DNS log, or want a one-off pcap without changing
router configuration.

### Capture DNS queries from the phone

```bash
# Run on a machine that can see the phone's Wi-Fi traffic
# (the router itself, or a Linux host with a mirror/span port)
sudo tcpdump -i <wifi_iface> -n 'udp port 53 and host <PHONE_IP>' -w app_dns.pcap
```

Use the app for 10–15 minutes (same workflow as Method A), then stop the capture with `Ctrl+C`.

### Analyse the pcap

```bash
# List unique queried hostnames
tshark -r app_dns.pcap -Y 'dns.flags.response == 0' \
  -T fields -e dns.qry.name | sort -u

# Include the response IPs alongside the names
tshark -r app_dns.pcap -Y 'dns.flags.response == 1' \
  -T fields -e dns.qry.name -e dns.a | sort -u
```

---

## 4. Method C — mitmproxy Domain Harvest

mitmproxy sees only HTTPS traffic that successfully passes through the proxy (i.e. the app does
not pin certificates). Setup instructions are in README_DISCOVERY.md sections 6.1–6.4.

### Collect flows

```bash
# Save all flows to a file
mitmdump -w flows.mitm

# Or use mitmweb and export from the UI: File > Export > flows.har
```

Use the app for 10–15 minutes, then stop mitmdump.

### Extract unique hostnames from a flows file

```bash
# From a mitmproxy binary flows file (requires mitmproxy Python API)
python3 - <<'EOF'
import mitmproxy.io, sys
with open("flows.mitm", "rb") as f:
    reader = mitmproxy.io.FlowReader(f)
    hosts = set()
    for flow in reader.stream():
        if hasattr(flow, "request"):
            hosts.add(flow.request.host)
for h in sorted(hosts):
    print(h)
EOF
```

### Extract unique hostnames from a HAR export

```bash
python3 - <<'EOF'
import json, sys

with open("flows.har") as f:
    har = json.load(f)

hosts = set()
for entry in har.get("log", {}).get("entries", []):
    req = entry.get("request", {})
    url = req.get("url", "")
    if "://" in url:
        host = url.split("://", 1)[1].split("/")[0].split(":")[0]
        hosts.add(host)

for h in sorted(hosts):
    print(h)
EOF
```

---

## 5. Method D — Android logcat (Owner's Own Device)

On Android, `adb logcat` streams the system log including network activity logged by the app or
the OS network stack.

```bash
# Connect phone via USB with USB Debugging enabled
adb devices   # verify the device is listed

# Stream logs and filter for network-related lines
adb logcat | grep -iE 'http|https|connect|socket|hostname|url'

# Filter more tightly for host/URL patterns
adb logcat | grep -iE '(https?://[^ ]+|connect.*:[0-9]{2,5})'

# Save to file for analysis
adb logcat > logcat_session.txt
# In another terminal, use the app for 10-15 minutes, then Ctrl+C

# Extract URLs from the log
grep -oE 'https?://[^" >]+' logcat_session.txt | sed 's/[?].*//' | sort -u
```

Note: many modern apps log less than older ones. Combine with Method C for best coverage.

---

## 6. Domain Categories to Expect

Once you have the raw list of hostnames, classify each one:

| Category | What to look for | Examples |
|----------|-----------------|---------|
| Auth / identity provider | OAuth endpoints, JWT issuer, `/login`, `/token`, `/oauth2` | `auth.airseekers.com`, `cognito.amazonaws.com`, `accounts.google.com` |
| Main API server | REST API calls with `/v1/`, `/v2/`, `/device/`, `/user/` | `api.airseekers.com`, `app-api.airseekers.net` |
| MQTT broker (cloud) | Port 8883 (TLS) or 1883, MQTT protocol | `mqtt.airseekers.com`, `iot.eu-west-1.amazonaws.com` |
| Media / camera CDN | Stream URLs, video/image content | `stream.airseekers.com`, `*.cloudfront.net`, `*.akamaized.net` |
| Telemetry / analytics | Crash reports, usage stats | `*.firebase.com`, `analytics.airseekers.com`, `sentry.io` |
| OTA firmware updates | `/firmware/`, `/ota/`, `.bin` downloads | `ota.airseekers.com`, `firmware.airseekers.net` |
| Map tile provider | `/{z}/{x}/{y}` URL patterns | `tile.openstreetmap.org`, `*.mapbox.com`, `*.googleapis.com` |

Fill in the recording template in section 7 for each domain you identify.

---

## 7. Recording Template

Create `tools/reports/domain_inventory.md` and fill in the following table. Add one row per
distinct hostname.

```markdown
| domain | purpose | protocol | port | first_seen_in_action | notes |
|--------|---------|----------|------|----------------------|-------|
| api.airseekers.com | Main REST API | HTTPS | 443 | Login | Returns JWT, all device control calls |
| mqtt.airseekers.com | Cloud MQTT broker | MQTT/TLS | 8883 | Connect to mower | Subscribe to device/+/status |
| stream.airseekers.com | Camera stream CDN | HTTPS | 443 | Open camera view | Returns MJPEG or RTSP redirect |
| ota.airseekers.com | Firmware OTA | HTTPS | 443 | Open device settings | Checked on app startup |
| tile.openstreetmap.org | Map tiles | HTTPS | 443 | Open map view | Standard OSM slippy tiles |
| auth.airseekers.com | OAuth2 / JWT | HTTPS | 443 | Login | Issues access + refresh tokens |
| analytics.airseekers.com | Telemetry | HTTPS | 443 | App launch | Crash reports and usage events |
```

Columns:

- **domain** — the hostname (anonymise if needed, see section 8)
- **purpose** — what this server does in the app flow
- **protocol** — HTTPS, MQTT/TLS, WebSocket/TLS, RTSP, etc.
- **port** — default is 443; note any non-standard ports
- **first_seen_in_action** — which app action first triggered a call to this domain
- **notes** — anything notable: CDN provider, AWS region, unusual headers, connection reuse, etc.

---

## 8. Anonymisation Before Sharing

If any discovered domains contain identifiable information (e.g. a company internal hostname,
an AWS account-specific endpoint, a UUID that could identify your device), replace them before
posting:

| Original | Placeholder |
|---------|------------|
| Actual API domain | `<AIRSEEKERS_API_DOMAIN>` |
| MQTT broker hostname | `<AIRSEEKERS_MQTT_HOST>` |
| Stream CDN hostname | `<AIRSEEKERS_STREAM_CDN>` |
| OTA server hostname | `<AIRSEEKERS_OTA_HOST>` |
| Auth server hostname | `<AIRSEEKERS_AUTH_DOMAIN>` |
| AWS account-specific endpoint | `<AWS_IOT_ENDPOINT>` |

Example sed replacement before sharing a domain list:

```bash
sed 's/a1b2c3d4e5.iot.eu-west-1.amazonaws.com/<AWS_IOT_ENDPOINT>/g' domain_inventory.md
```

Keep your own unredacted copy locally for reference; only share the anonymised version in GitHub
issues or PRs.

---

## 9. Cross-Reference with the Tools

The discovered domains feed directly into the tool suite:

### airseekers_cloud_probe.py

Set `AIRSEEKERS_BASE_URL` in your `.env` file to the main REST API domain:

```ini
AIRSEEKERS_BASE_URL=https://<AIRSEEKERS_API_DOMAIN>
AIRSEEKERS_USERNAME=your@email.com
AIRSEEKERS_PASSWORD=your_password
AIRSEEKERS_MQTT_HOST=<AIRSEEKERS_MQTT_HOST>
AIRSEEKERS_MQTT_PORT=8883
```

Then run:

```bash
python tools/airseekers_cloud_probe.py --env-file .env
```

The probe will attempt to authenticate, enumerate device endpoints, and test MQTT connectivity
using the values you discovered.

### mqtt_probe.py

If you confirmed a cloud MQTT broker hostname:

```bash
python tools/mqtt_probe.py --host <AIRSEEKERS_MQTT_HOST> --port 8883 --tls
```

### discover_camera_streams.py

If the camera stream is served from a CDN rather than the robot's LAN IP, pass the CDN hostname:

```bash
python tools/discover_camera_streams.py --host <AIRSEEKERS_STREAM_CDN>
```

Keeping your domain inventory up to date ensures the tool suite targets the correct endpoints
across firmware and app version updates.
