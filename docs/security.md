# AIRSEEKERS — Security & privacy

This integration is designed to be safe with credentials, tokens, and camera imagery, and to interact
only with **your own** robot, account, and network.

## Secrets are never leaked

- Credentials, tokens, refresh tokens, signed URLs, and camera **stream/snapshot URLs** are never
  written to logs.
- Diagnostics are passed through a reusable redaction helper (`redact.py`) that masks sensitive keys
  (`const.SENSITIVE_KEYS`), `Authorization` headers, and tokenised/signed URLs (user-info and sensitive
  query parameters are stripped). Camera stream/snapshot URLs are **dropped entirely** from diagnostics
  — only booleans like `has_stream_url` are reported.
- The client logs no payloads for the raw debug command; it only notes the command name.

## Camera privacy

- Cameras are **privacy-first**: by default the integration does not record images and does not expose
  streams outside Home Assistant.
- `privacy_mode` blanks camera images/streams without deleting the entities.
- `disable_cameras_when_docked` and `disable_cameras_at_night` (via `sun.sun`) make cameras unavailable
  on schedule.
- With `prefer_composite`, per-lens cameras are created but **disabled by default** in the entity
  registry (enable the ones you want).
- Stream URLs/tokens never appear in attributes, logs, or diagnostics.

## The raw debug service

`airseekers.send_command_raw` is **disabled by default**. It only works when *Enable raw debug command
service* is turned on in the integration options. It is an advanced/debug tool — use with care; an
unknown command could have unintended effects on a real backend. The stub backend treats it as a no-op.

## Discovery tooling ethics

The scripts in `tools/` are **non-intrusive** and intended for use on **your own** network/devices/
account only:

- No brute force, no credential/password lists, no aggressive port sweeps.
- Nothing is published to a device or broker without an explicit confirmation flag.
- No AIRSEEKERS endpoint, URL, port, or payload is fabricated — probes test only targets you supply.
- Reports redact embedded credentials and are written to a gitignored `tools/reports/` folder.

When capturing app/cloud traffic (mitmproxy on your own phone), **anonymise** traces — strip tokens,
serials, emails, and signed URLs — before sharing or contributing.

## Scope

Interoperability is limited to your own robot, your own account, and your own network. No part of this
project attempts to break, bypass, or weaken encryption or authentication, or to access third-party
accounts.
