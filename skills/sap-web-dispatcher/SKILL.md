---
name: sap-web-dispatcher
description: >-
  Operate the SAP Web Dispatcher (the reverse proxy / load balancer in front of SAP HTTP(S) traffic) —
  start, stop, status, ports, profile essentials and the admin UI — on Linux, Windows and AIX. Use for
  "start/stop/restart the web dispatcher", "webdisp is down", "web dispatcher ports/profile", "wdisp/system
  backend", "/sap/wdisp/admin". Logs are in sap-log-reference. Cited to help.sap.com.
---

# SAP Web Dispatcher

The Web Dispatcher terminates/forwards HTTP(S) to the SAP back-end (message-server load balancing + SSL).
Two deployment shapes:
- **Instance-based** (modern S/4): a real SAP instance `W<nr>` with `sapstartsrv` — driven by **SAPControl**
  exactly like any instance ([sap-system-lifecycle](../sap-system-lifecycle/SKILL.md)).
- **Standalone binary**: the `sapwebdisp` executable + a profile, started/stopped directly.

> **Guardrail:** it's internet-/user-facing — a stop **drops all active HTTP sessions**. Identify SID/host,
> classify PRD, confirm before bouncing. `saprouttab`-style access and SSL config are security-sensitive.

---

## 1. Start / stop / status

### Instance-based (has `sapstartsrv`)
```bash
sapcontrol -nr <nr> -function Start          # start;  Stop / RestartSystem to stop / restart
sapcontrol -nr <nr> -function GetProcessList # status — the WEBDISP/ICMAN process GREEN
```

### Standalone binary
```bash
# start (UNIX/Windows) — profile holds ports + backend systems:
sapwebdisp pf=<path>/sapwebdisp.pfl          # Windows: sapwebdisp.exe pf=…   [G, W1]
# stop — send SIGINT to the PID:
kill -2 <pid>            # UNIX (graceful)                                     [G, W1]
sapntkill -INT <pid>     # Windows                                            [G, W1]
# or, if installed as a Windows service: Services.msc → stop "sapwebdisp"
```
Useful start options [G, W1]: `-f <tracefile>`, `-t <tracelevel>`, `-cleanup` (release shared memory),
`-auto_restart`, `-shm_attach_mode`, `-version`.

**Status also via the admin UI:** `https://<host>:<https_port>/sap/wdisp/admin` (see §3).

---

## 2. Ports

| Purpose | Profile parameter | Typical |
|---------|-------------------|---------|
| HTTP listener | `icm/server_port_<n> = PROT=HTTP,PORT=80<nr>` | `80<nr>` |
| HTTPS listener | `icm/server_port_<n> = PROT=HTTPS,PORT=443<nr>` | `443<nr>` |
| Admin UI | under `icm/HTTP/admin_<n>` / a dedicated port | e.g. `4<nr>xx` |

---

## 3. Profile essentials & admin UI

Minimum config in `sapwebdisp.pfl` / the instance profile: [G, W2]
```
SAPSYSTEMNAME = <SID>
icm/server_port_0 = PROT=HTTP,PORT=8000
icm/server_port_1 = PROT=HTTPS,PORT=44300
wdisp/system_0 = SID=<backendSID>, MSHOST=<msg-server-host>, MSPORT=81<nr>, SRCSRV=*:*, SRCURL=/
wdisp/ssl_encrypt = 1
icm/HTTP/admin_0 = PREFIX=/sap/wdisp/admin, DOCROOT=..., AUTHFILE=...
```
- `wdisp/system_<n>` defines each back-end system (message-server host/port for load balancing).
- **Admin UI:** `/sap/wdisp/admin` — status, back-end groups, trace level, restart. Protect with `AUTHFILE`.

---

## 4. Logs

`dev_webdisp` (main trace), `dev_webdisp_log` (start/stop/config), ICM-style HTTP access logs — details and
trace levels (`icm/trace_level`, `icm/HTTP/logging_<n>`) in
[sap-log-reference](../sap-log-reference/SKILL.md) → app-and-component-logs.

## Cross-references

- Instance-style start/stop & order: [sap-system-lifecycle](../sap-system-lifecycle/SKILL.md).
- Health/status detail: [sap-health-triage](../sap-health-triage/SKILL.md).
- Traces: [sap-log-reference](../sap-log-reference/SKILL.md).

## Sources

- **[W1]** *Starting and Stopping Web Dispatcher* — SAP Help Portal (`sapwebdisp pf=…`; stop via `kill -2`
  / `sapntkill -INT` / service; options `-cleanup`/`-auto_restart`/`-f`/`-t`).
  https://help.sap.com/doc/329ac769552a411b97bc7adb991b6197/3.0.12/en-US/eae7d26b822e4b1facc275f25b4f03a2.html
- **[W2]** *Operating / Installing and Configuring the SAP Web Dispatcher* — SAP Help Portal (profile,
  `icm/server_port`, `wdisp/system`, `/sap/wdisp/admin`). SAP NetWeaver AS documentation.

**To confirm/deepen:** the SAP Web Dispatcher guide for your release (profile parameter reference) and, for
instance-based deployments, [sap-system-lifecycle](../sap-system-lifecycle/SKILL.md).
