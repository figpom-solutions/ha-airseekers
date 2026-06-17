# AIRSEEKERS TRON / TRON Max — Network Discovery & Protocol Mapping Guide

This guide explains how to discover your AIRSEEKERS robot's network presence and map the protocols
it uses, so you can build or contribute to a Home Assistant integration.

---

## 1. Legal & Ethics Preamble

**All techniques described in this document apply exclusively to your own device on your own
network.** You must own the mower, own or administer the network, and be the registered account
holder for the AIRSEEKERS app.

- Do not apply any of these techniques to equipment you do not own.
- Do not intercept or record traffic from other users' accounts or devices.
- Do not share raw captures containing credentials, serial numbers, or personally identifiable
  information. See section 8 (Anonymisation) before contributing findings.
- Manufacturer terms of service may restrict reverse-engineering. This guide is provided for
  **interoperability and home-automation purposes** under the principle that an owner has the right
  to understand and automate their own property. Consult local law if in doubt.

---

## 2. Finding the Robot's IP via the Router DHCP Table

The easiest first step is to check which IP address your router assigned to the mower.

### Common router admin UIs

| Router brand / firmware | Admin URL | DHCP table location |
|-------------------------|-----------|---------------------|
| Livebox (Orange France) | http://192.168.1.1 | Network > Devices |
| Freebox | http://mafreebox.freebox.fr | Network > DHCP |
| OpenWrt / DD-WRT | http://192.168.1.1 | Network > DHCP Leases |
| pfSense / OPNsense | https://192.168.1.1 | Services > DHCP Server > Leases |
| UniFi | https://unifi.ui.com | Clients tab |
| Generic | http://192.168.0.1 or 192.168.1.1 | "Connected Devices" or "DHCP Leases" |

Look for a hostname containing `AIRSEEKERS`, `TRON`, or a MAC address OUI that belongs to the
mower's Wi-Fi chipset manufacturer. Note the assigned IP — call it `<IP_ROBOT>` throughout this
guide.

### Network scan fallback

If the router UI is inaccessible, use `nmap` to enumerate all live hosts on your subnet:

```bash
# Replace 192.168.1 with your actual subnet
nmap -sn 192.168.1.0/24
```

Cross-reference the MAC address on the mower's label (usually under the chassis or in the app
Settings > Device Info) with the scan output.

---

## 3. Confirming the IP with nmap Service Detection

Once you have a candidate IP, verify it belongs to the mower and discover which ports are open:

```bash
nmap -sV <IP_ROBOT>
```

The `-sV` flag probes open ports to identify the running service and its version. This is standard
practice when auditing your own device. Look for:

- Port 80 / 443 — HTTP/HTTPS API or web UI
- Port 554 — RTSP (camera streaming)
- Port 8080 — alternative HTTP or MJPEG stream
- Port 1883 / 8883 — MQTT (plain / TLS)
- Port 9000 — possible WebSocket

Record every open port; each one is a candidate for integration.

---

## 4. Observing DNS Traffic from the Robot

Watching which hostnames the mower resolves tells you which cloud services it contacts.

### Option A — dnsmasq log (router or Pi-hole)

If your router runs dnsmasq (OpenWrt, DD-WRT, Pi-hole):

```bash
# On the router via SSH
grep <IP_ROBOT> /var/log/dnsmasq.log
# or
logread | grep dnsmasq | grep <IP_ROBOT>
```

### Option B — Router DNS query log

Many consumer routers have a "DNS query log" or "traffic monitor" page. Filter by the mower's IP.

### Option C — tcpdump on the gateway interface

```bash
# Run on the router or a Linux host that sees all LAN traffic
sudo tcpdump -i <iface> -n udp port 53 and host <IP_ROBOT>
```

Replace `<iface>` with your LAN interface name (e.g. `eth0`, `br-lan`, `enp3s0`). Every DNS
query the mower emits will appear here. Log the session, then extract unique hostnames for your
domain inventory (see `extract_app_domains.md` for the recording template).

---

## 5. Capturing Robot Traffic with Wireshark / tcpdump

### tcpdump — command-line capture

```bash
# Capture all traffic to/from the robot, save to a file
sudo tcpdump -i <iface> -n host <IP_ROBOT> -w robot_traffic.pcap

# Capture only TCP (skip ARP/mDNS noise)
sudo tcpdump -i <iface> -n host <IP_ROBOT> and tcp -w robot_traffic_tcp.pcap

# Capture MQTT specifically
sudo tcpdump -i <iface> -n host <IP_ROBOT> and port 1883 -w robot_mqtt.pcap

# Capture RTSP
sudo tcpdump -i <iface> -n host <IP_ROBOT> and port 554 -w robot_rtsp.pcap
```

Stop with `Ctrl+C`. Open `.pcap` files in Wireshark or analyse with `tshark`.

### Wireshark — GUI capture

1. Open Wireshark and select your LAN interface.
2. Enter a capture filter in the toolbar: `host <IP_ROBOT>`
3. Press the blue shark-fin button to start.
4. Trigger mowing, camera view, map update, and status polling from the AIRSEEKERS app.
5. Press the red square to stop.
6. Use the display filter bar to narrow down:
   - `mqtt` — MQTT messages
   - `rtsp` — RTSP negotiation
   - `http` — plain HTTP
   - `tcp.port == 8080` — alternative HTTP/MJPEG

Save the capture: File > Save As > `robot_full_session.pcap`.

### tshark — command-line Wireshark

```bash
# Capture to file
sudo tshark -i <iface> -f "host <IP_ROBOT>" -w robot_traffic.pcap

# Read and filter an existing pcap
tshark -r robot_traffic.pcap -Y "mqtt" -T fields -e mqtt.topic -e mqtt.msg
tshark -r robot_traffic.pcap -Y "rtsp" -T text
```

---

## 6. Intercepting the AIRSEEKERS Mobile App with mitmproxy

mitmproxy acts as a transparent HTTPS proxy between your phone and the internet, letting you see
every API call the AIRSEEKERS app makes. **Use this only on your own phone with your own account.**

### 6.1 Install mitmproxy on your laptop

```bash
pip install mitmproxy
# or via package manager
brew install mitmproxy        # macOS
sudo apt install mitmproxy    # Debian/Ubuntu
```

Verify: `mitmproxy --version`

### 6.2 Configure your phone's Wi-Fi proxy

1. Connect your phone to the same Wi-Fi network as your laptop.
2. Find your laptop's local IP on that network: `ip addr show` or `ifconfig`.
3. On the phone:
   - **Android**: Settings > Wi-Fi > long-press network > Modify > Advanced > Proxy: Manual.
     Host: `<LAPTOP_IP>`, Port: `8080`.
   - **iOS**: Settings > Wi-Fi > tap the network > Configure Proxy > Manual.
     Server: `<LAPTOP_IP>`, Port: `8080`.

### 6.3 Install the mitmproxy CA certificate on the phone

1. Start mitmproxy once: `mitmproxy` then stop it. This generates the CA cert at
   `~/.mitmproxy/mitmproxy-ca-cert.pem`.
2. Serve it:
   ```bash
   cd ~/.mitmproxy && python3 -m http.server 8888
   ```
3. On the phone, browse to `http://<LAPTOP_IP>:8888/mitmproxy-ca-cert.pem` and install it:
   - **Android**: tap the file > name it "mitmproxy" > install as "CA certificate" (may require
     device encryption to be enabled).
   - **iOS**: tap the file > Settings > General > VPN & Device Management > tap the profile >
     Install. Then Settings > General > About > Certificate Trust Settings > enable the cert.

### 6.4 Run mitmproxy or mitmweb

```bash
# Terminal UI (press ? for help, q to quit)
mitmproxy

# Browser UI at http://127.0.0.1:8081 — easier to read
mitmweb

# Transparent mode (less commonly needed for app interception)
mitmproxy --mode transparent
```

While mitmproxy is running, use the AIRSEEKERS app normally: log in, connect to the mower, open
camera, start mowing, check the map, etc. Every HTTPS request appears in the proxy UI.

### 6.5 Certificate pinning

Some apps bundle their own certificate and refuse the mitmproxy CA. If you see SSL errors in the
app while the proxy is running, the app likely uses certificate pinning.

**Android (owner's own phone and APK only):**

```bash
pip install apk-mitm
# Download your own APK (e.g. via APKPure or from your device with adb backup)
apk-mitm airseekers.apk
# Install the patched APK
adb install airseekers-patched.apk
```

`apk-mitm` patches the network security config to trust user-installed CAs. Only do this with
your own APK on your own device.

**iOS:** Tools such as SSL Kill Switch 2 (jailbroken device only) can disable pinning. This is
at the owner's own risk and is not covered further here.

---

## 7. Recording Discovered Endpoints

Create a file such as `tools/reports/api_endpoints.md` and fill in a table for every endpoint
you discover. Redact any authentication tokens or passwords.

```markdown
| # | Method | Host | Path | Payload (redacted) | Status | Response shape | Notes |
|---|--------|------|------|--------------------|--------|----------------|-------|
| 1 | POST | api.airseekers.com | /v1/auth/login | `{"username":"<USER>","password":"<REDACTED>"}` | 200 | `{"token":"<TOKEN>"}` | JWT login |
| 2 | GET | api.airseekers.com | /v1/device/status | — | 200 | `{"battery":85,"mode":"mowing"}` | Poll interval ~30 s |
| 3 | GET | <IP_ROBOT> | /video | — | 200 | MJPEG multipart | Local stream |
```

At minimum record: HTTP method, full path, whether auth is required, response Content-Type, and
a sketch of the response schema.

---

## 8. Anonymising Traces Before Sharing

Before uploading a capture or pasting a flow in a GitHub issue:

1. **Export from mitmproxy:**
   ```bash
   # In mitmweb, use File > Export > flows.har  (HAR format)
   # or from the CLI:
   mitmdump -r /tmp/captured.flows -w flows_export.flows --set hardump=flows.har
   ```

2. **Strip Authorization headers** — search for `Authorization:` and replace the value with
   `<REDACTED_TOKEN>`.

3. **Replace serial numbers** — find the mower's serial (from the app or label) and replace all
   occurrences with `<DEVICE_SERIAL>`.

4. **Replace your IP addresses** — replace `<IP_ROBOT>` with `192.168.x.x` or `<ROBOT_IP>` and
   your phone/laptop IPs similarly.

5. **Search-replace in the HAR / pcap text export:**
   ```bash
   sed -i 's/YOUR_REAL_TOKEN/<REDACTED_TOKEN>/g' flows.har
   sed -i 's/YOUR_SERIAL/<DEVICE_SERIAL>/g' flows.har
   ```

6. **Verify** — open the anonymised file and search for your email, phone number, serial, and
   any long token strings before sharing.

---

## 9. Running the Discovery Tool Suite

All tools live in `tools/`. Run them from the repository root. Replace `<IP_ROBOT>` with your
mower's LAN IP (e.g. `192.168.1.42`).

### LAN discovery

```bash
# Scan the local network for any AIRSEEKERS device
python tools/discover_lan.py

# Target a specific IP directly
python tools/discover_lan.py --host <IP_ROBOT>
```

### HTTP probe

```bash
# Enumerate HTTP endpoints on the robot
python tools/probe_http.py --host <IP_ROBOT>
```

### MQTT probe

```bash
# Check whether an MQTT broker is reachable on the robot
python tools/mqtt_probe.py --host <IP_ROBOT>

# Attempt to connect and subscribe to all topics (#)
python tools/mqtt_probe.py --host <IP_ROBOT> --connect
```

### Camera discovery

```bash
# Broad sweep: tries common camera paths and ports
python tools/discover_camera_streams.py --host <IP_ROBOT>

# Build a structured inventory of found streams
python tools/discover_camera_inventory.py --host <IP_ROBOT>
```

### Stream probes (use after discovery identifies candidates)

```bash
# Probe an RTSP URL
python tools/probe_rtsp.py rtsp://<IP_ROBOT>:554/

# Probe an MJPEG HTTP stream
python tools/probe_mjpeg.py --url http://<IP_ROBOT>:8080/video

# Probe any camera URL (auto-detects type)
python tools/probe_camera_url.py --url <URL>
```

### Cloud API probe

```bash
# Requires a .env file — see tools/.env.example
python tools/airseekers_cloud_probe.py --env-file .env
```

The `.env` file must contain at minimum:

```ini
AIRSEEKERS_BASE_URL=https://<API_DOMAIN>
AIRSEEKERS_USERNAME=your@email.com
AIRSEEKERS_PASSWORD=your_password
```

Do **not** commit `.env` to git. It is in `.gitignore`.

---

## 10. Reading Reports in tools/reports/

Each tool writes JSON and/or Markdown reports to `tools/reports/`. After a scan session you
will find files such as:

| Filename | Generated by | Contents |
|----------|-------------|----------|
| `lan_discovery.json` | `discover_lan.py` | Open ports, hostname, MAC |
| `http_probe.json` | `probe_http.py` | HTTP paths tried, status codes |
| `mqtt_probe.json` | `mqtt_probe.py` | MQTT reachability, topics found |
| `camera_streams.json` | `discover_camera_streams.py` | Stream URLs found, types |
| `camera_inventory.json` | `discover_camera_inventory.py` | Structured per-view inventory |
| `rtsp_probe.json` | `probe_rtsp.py` | RTSP OPTIONS/DESCRIBE results |
| `mjpeg_probe.json` | `probe_mjpeg.py` | MJPEG frame size, FPS estimate |
| `cloud_probe.json` | `airseekers_cloud_probe.py` | Auth result, discovered endpoints |

Open the `.json` files with any JSON viewer, or use `python3 -m json.tool tools/reports/<file>`.

The `tools/reports/` directory is listed in `.gitignore` so reports containing raw data are never
accidentally committed. Only anonymised, curated excerpts should be pasted into issues or PRs.

---

## 11. Next Steps After Discovery

Once you have run the tools and captured some traffic:

1. **Fill in the camera inventory template** — update `tools/discover_camera_inventory.py`'s
   expected stream list with the URLs, ports, and content types you confirmed.

2. **Record cloud API endpoints** — paste the anonymised endpoint table from section 7 into
   `tools/reports/api_endpoints.md` and reference it in your issue or PR.

3. **Open an issue on the project** — title it "Discovery results: <your mower model> firmware
   <X.Y.Z>". Attach anonymised HAR/pcap excerpts, the endpoint table, and the MQTT topic list.
   The more firmware versions are covered, the more robust the integration becomes.

4. **Cross-reference with existing Home Assistant custom components** — search
   [HACS](https://hacs.xyz) and GitHub for `airseekers` or `husqvarna automower` patterns to
   avoid reinventing the wheel.

5. **Prototype an entity** — once you know the status polling endpoint or MQTT topic, the next
   step is a minimal `sensor` platform in `custom_components/airseekers/`.
