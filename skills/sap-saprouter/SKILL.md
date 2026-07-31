---
name: sap-saprouter
description: >-
  Operate SAProuter — the SAP application-level proxy that controls and secures network routes (typically
  to/from SAP support and between networks) — start, stop, status, the saprouttab route-permission table,
  port 3299, SNC, and niping connection tests, on Linux, Windows and AIX. Use for "start/stop saprouter",
  "saprouttab", "route to SAP support", "niping test", "saprouter SNC". Traces in sap-log-reference. Cited
  to help.sap.com.
---

# SAProuter

SAProuter is a small proxy that permits/denies network routes based on the **route-permission table
(`saprouttab`)** — most commonly the controlled path to **SAP support** and between security zones.
Default NI port **3299**.

> **Guardrail:** SAProuter is a **security control** and often the **only path to SAP support**. A stop
> can cut support connectivity and any tunnelled traffic. Editing `saprouttab` changes who can reach what —
> treat it like a firewall rule: preview, confirm, keep `D` (deny) defaults tight. Never open `P * * *`.

---

## 1. Start / stop / status

```bash
saprouter -r                       # START: run and load saprouttab (the permission table)   [V, R1]
saprouter -s                       # STOP (soft shutdown)                                     [V, R1]
saprouter -s -S <service>          # STOP when running on a non-default port (not 3299)       [V, R1]
```
Common start options:
```bash
saprouter -r -R <routtab> -G <logfile> -T <tracefile> -W <timeout-ms> &
```
- `-R <file>` alternate route table (default `saprouttab` in the working dir)
- `-G <logfile>` connection log · `-T <tracefile>` trace (see [logs](../sap-log-reference/SKILL.md))
- Windows: often run as a **service** (installed with `ntscmgr`); otherwise the same flags.

**Status / info:**
```bash
saprouter -l                       # list current routes/connections (info dump)
saprouter -d                       # detailed dump
```

---

## 2. Route-permission table (`saprouttab`)

Line format [R2]:
```
<P|D|S|K>  <source-host>  <dest-host>  <dest-service/port>  [password]
# P = permit   D = deny   S = permit (native SAP protocol only)   K = permit with SNC
```
Examples:
```
P  10.0.0.0/8   sapserv2   3299          # permit internal net → SAP support router
D  *            *          *             # deny everything else (keep last / default tight)
```
> Rules are evaluated top-down. Keep a restrictive default; only permit the specific routes needed. Port
> range `3200–3299` is what `*` allows for security reasons; **3299/3298** are used toward SAP. [R2]

---

## 3. SNC (secure) & connection testing

```bash
saprouter -K "p:CN=<router-cert-DN>" -r      # start with SNC (encrypted, authenticated)   [R3]
```
Test reachability through the router with **niping**:
```bash
niping -s                                     # on the target host: start a niping server
niping -c -H /H/<saprouter-host>/H/<target>   # from the client: connect through the route string
```
`niping` reports a clear error when the route/connection is not possible. [R2]

---

## 4. Logs

Connection log via `-G`, trace via `-T` (level-2 trace for SAP support per **KBA 3570238**); route file
`saprouttab`. See [sap-log-reference](../sap-log-reference/SKILL.md).

## Cross-references

- Traces / trace levels: [sap-log-reference](../sap-log-reference/SKILL.md).
- Connectivity to the wider landscape: `sap-cloud-connector` (BTP), Web Dispatcher (HTTP front).

## Sources

- **[R1]** *Starting and Stopping SAProuter: Option -r and -s* — SAP Help Portal. **[V]** `saprouter -r`
  (loads `saprouttab`), `saprouter -s` (stop), `-S <service>` when not on 3299.
  https://help.sap.com/saphelp_snc700_ehp04/helpdata/en/48/6caa3d6c0707dce10000000a42189d/content.htm
- **[R2]** *Configure SAProuter* + route-permission table (`P/D/S`, port 3299/3200–3299, `niping`) — SAP
  Support Portal Connectivity Tools. https://support.sap.com/en/tools/connectivity-tools/saprouter/configure.html
- **[R3]** *How to set up an SNC connection between SAProuters* — SAP Support Content.
  https://help.sap.com/docs/SUPPORT_CONTENT/basis/3354611421.html
- SAProuter level-2 trace: **SAP KBA 3570238** (see sap-log-reference).

**To confirm/deepen:** the SAProuter documentation (BC-CST-NI) for your kernel, and the SAP support-portal
SAProuter setup pages for the current `sapserv*` targets.
