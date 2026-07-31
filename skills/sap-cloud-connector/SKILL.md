---
name: sap-cloud-connector
description: >-
  Operate the SAP Cloud Connector (SCC) — the secure on-premise agent that links SAP BTP to on-prem
  systems — start, stop, restart, the admin UI (port 8443), Master/Shadow high availability, ports and
  auto-restart, on Linux, Windows and macOS (not AIX). Use for "start/stop/restart cloud connector", "scc
  is down", "cloud connector admin UI 8443", "SCC high availability master shadow". Logs (ljs_trace.log)
  in sap-log-reference. Cited to help.sap.com / SAP KBAs.
---

# SAP Cloud Connector (SCC)

SCC is a Java agent that establishes an **outbound TLS tunnel** from your network to an SAP BTP subaccount,
exposing selected on-prem systems to cloud apps under fine-grained access control. It runs on its own JVM
(not an SAP kernel instance).

> **Platform note:** SCC runs on **Linux, Windows and macOS** — **not AIX** (unlike the SAP kernel
> components). If the on-prem hosts are AIX, SCC still runs on a separate Linux/Windows host. [C2]

> **Guardrail:** SCC is the **single bridge** between BTP and on-prem — stopping it **breaks all
> cloud→on-prem connectivity** (cloud Fiori, integration flows, RFC/HTTP to the backend). Use the
> **Shadow** for zero-downtime; confirm before stopping a Master. Access-control changes expose/hide
> internal systems — treat as security-sensitive.

---

## 1. Start / stop / restart  [C1]

**Linux** — as the SCC/OS admin:
```bash
# systemd distributions:
systemctl start|stop|restart scc_daemon
# System V distributions:
service scc_daemon start|stop|restart
```
**Windows:** the Cloud Connector is a **Windows service** (auto-start after install) — start/stop via
`Services.msc` or `net start|stop <SCC service>`.

**macOS / portable install:** the `<scc>/` install dir scripts (`go.sh` / daemon control).

The daemon **auto-restarts** on host reboot by default (disable per **KBA 3474163** if required). [C1]

---

## 2. Admin UI & first login

```
https://<host>:8443        # default admin UI port; default user "Administrator"
```
- First login forces a password change. [C2]
- Change the admin UI port per **KBA 2955431** (e.g. behind a reverse proxy). [C3]
- The UI is where you do everything else: add subaccounts, define **access control** (map a *virtual*
  host/port to an *internal* system), configure **service channels**, and view **Log And Trace Files**.

---

## 3. Ports

| Purpose | Port |
|---------|------|
| Administration UI (HTTPS) | **8443** (default; changeable — KBA 2955431) |
| Outbound tunnel to BTP region | **443** (TLS, outbound only — no inbound firewall opening) |
| Exposed backend systems | the *virtual* host/port you define per access-control mapping |

---

## 4. High availability (Master / Shadow)

- **Master** — the standard, fully-functional installation.
- **Shadow** — a second SCC configured as backup; it takes over if the Master fails, giving HA. Configure
  the Shadow to point at the Master; failover keeps the BTP tunnel available. [C2]

Check state and trigger/monitor failover from the admin UI (Master/Shadow status).

---

## 5. Logs

`ljs_trace.log` (main Java trace, rotates ~20×50 MB), plus `scc_*` and audit logs, in the SCC `log/`
directory — downloadable from the admin UI (Log And Trace Files). Details in
[sap-log-reference](../sap-log-reference/SKILL.md).

## Cross-references

- Traces: [sap-log-reference](../sap-log-reference/SKILL.md).
- Other connectivity front-ends: `sap-web-dispatcher` (HTTP reverse proxy), `sap-saprouter` (NI proxy).

## Sources

- **[C1]** **SAP KBA 2485510** — *How to start/stop/restart SAP Cloud Connector (SCC)*
  (`systemctl`/`service scc_daemon`, Windows service). https://me.sap.com/notes/2485510
- **[C2]** *SAP Cloud Connector* documentation — SAP BTP Connectivity (install, admin UI 8443,
  Master/Shadow high availability, supported platforms). help.sap.com (SAP BTP Connectivity → Cloud
  Connector).
- **[C3]** **SAP KBA 2955431** — *How to change the default admin UI port of SAP Cloud Connector*.
  https://me.sap.com/notes/2955431
- Auto-restart control: **SAP KBA 3474163** (disable auto-restart on Linux). https://me.sap.com/notes/3474163

**To confirm/deepen:** the SAP Cloud Connector documentation for your version (system requirements +
Master/Shadow setup) and KBA 2485510 for the exact service/daemon names on your OS.
