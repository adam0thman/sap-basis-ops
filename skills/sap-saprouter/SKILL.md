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

## Execution discipline (non-negotiable)

### The holy rule — nothing runs unbacked

**Every command executed must be traceable to one of exactly three things:**

1. an **official SAP source** — help.sap.com page / Operations or Administration Guide, or
2. an **SAP Note / KBA**, or
3. an **explicit instruction from the user**.

If a command is backed by none of those, **do not run it** — say what backing is missing and stop.
"It's probably fine", "this is standard", and "I recall the syntax" are not backing. When the backing is
a source, name it (page or Note number) alongside the command; when it is the user, quote the instruction.

### Ambiguity ⇒ stop and confirm, before any execution

If executing would require **assuming** anything the user did not state, you are **obliged** to confirm
first. Never fill a gap with a plausible default. Common gaps that force a stop:

- **client number**, SID, instance number, target host/node
- **read-only vs state-changing** — if it is not explicit which was wanted, ask
- **scope** — one instance vs the whole system, one tenant vs all, one client vs cross-client
- which **database / dbms_type**, which environment (**PRD vs non-PRD**)
- retention/age cut-offs, recovery points, target of a restore, transport target

A wrong assumption here is not a typo — it is the difference between reading a log and stopping production.

### But verify programmatically FIRST — *then* ask

**Asking the user for something the system can answer is a failure.** Before you raise a question, ask
the user to go and look, or request Computer Use / GUI access, you **must** first try to determine it
programmatically. Only what genuinely cannot be derived — intent, authorization, a business decision, a
value that exists only in the user's head — is a legitimate question.

| Determine programmatically (do NOT ask) | Ask the user (cannot be derived) |
|---|---|
| Which DB — `echo $dbms_type`, profile `dbms/type` | Which **client** to act on |
| SIDs / instances / hosts / ports — `sapcontrol … GetSystemInstanceList`, `ls /usr/sap` | Whether this system is in scope / approved |
| Is it up, is the DB up — `GetProcessList`, `R3trans -d` | PRD change approval, downtime window |
| Kernel / release / patch — `disp+work -version`, `saphostexec -version` | The intended recovery point or retention policy |
| Which clients **exist** — table `T000` | Which of those clients is **meant** |
| Free space, log locations, parameter values — `df -h`, `sappfpar`, profile | Business impact / urgency |

Order, always: **verify programmatically → ask only what remains → never assume.**

### Prefer programmatic over manual or GUI

If a task can be done via **CLI, API, SQL or a report**, do it that way rather than GUI clicks, screen
automation or Computer Use. Programmatic execution is repeatable, reviewable, loggable and diffable;
screen-driving is none of those. Reach for the GUI or Computer Use only when there is **no programmatic
path** (some SAP GUI-only transactions genuinely qualify) or when the user asks for it — and say which
it is and why.

### Ask how output should be handled

Work that produces evidence (logs, traces, command output, screenshots, reports) has two reasonable
endings. **Ask which the user wants** rather than guessing:

- **(a) persist it** — write the output/logs/screenshots to a file, and say exactly where; or
- **(b) execute and report** — just run it and give a short final status summary.

Don't dump large output into the conversation unasked, and don't silently discard evidence either — for
troubleshooting and any change with a rollback, (a) is usually the right default to offer.

## Run as the correct OS user

**Identify the right OS user *before* running anything, and switch with a login shell.** Wrong-user
execution is a top cause of SAP failures, and the damage outlives the command: files created by `root`
under `/usr/sap`, `/sapmnt` or a DB directory break every later start by the real owner. A login shell
also matters because each user carries the environment the tools need (`SAPSYSTEMNAME`, `ORACLE_HOME`/
`ORACLE_SID`, `SYBASE`, `DB2INSTANCE`, library paths) — without it, commands fail or act on the wrong system.

| What you're operating | UNIX user | Windows |
|---|---|---|
| SAP instances — `sapcontrol`, `startsap`/`stopsap`, `tp`, `R3trans`, `disp+work`, `sappfpar`, `cleanipc` | **`<sid>adm`** (lower-case **SAP** SID) | `<SID>adm`; services run as `SAPService<SID>` |
| SAP HANA — `HDB`, `hdbsql`, `hdbnsutil` | **`<sid>adm` of the HANA SID** (e.g. `h10adm` — may differ from the SAP SID) | n/a (HANA server is Linux-only) |
| Oracle — `sqlplus`, `lsnrctl`, BR\*Tools | **`ora<dbsid>`** (BR\*Tools also runs as `<sid>adm`; generic installs may use `oracle`) | `<SID>adm`; DB runs as a service |
| SAP ASE — `isql`, `startserver`, Backup Server | **`syb<dbsid>`** | `syb<dbsid>` / `SAPService<SID>` |
| IBM Db2 — `db2start`/`db2stop`, `db2` CLP | **`db2<dbsid>`** (the instance owner = `DB2INSTANCE`) | same; Db2 runs as a service |
| SAP MaxDB / liveCache — `dbmcli`, `x_server` | **`sdb`** (software owner, group `sdba`) + a DBM operator at DB level | install/service account |
| MS SQL Server — `sqlcmd`, service control | n/a (Windows-only for SAP) | `<SID>adm` / the SQL Server service account |
| SAP Host Agent — `saphostexec`, `saphostctrl` | **`root`** | Administrator / `SAPHostExec` service |

**Rules**

- **Switch with a login shell:** `su - <user>` (the `-` is what loads the environment) or `sudo -iu <user>`.
  Windows: use the correct account, or an elevated shell only where documented.
- **`root` only where the procedure explicitly says so** — e.g. `saproot.sh` after a kernel extract, SAP Host
  Agent install/upgrade. Never as a shortcut around a permission error; that is how root-owned files get
  created and break the system later.
- **Verify before acting:** `whoami` / `id`, plus the env actually being set (`echo $SAPSYSTEMNAME`,
  `echo $ORACLE_SID`, `echo $DB2INSTANCE`, `echo $SYBASE`).
- **State the user in every command you hand over** (e.g. "as `<sid>adm`:"), and if the required user is not
  available, say so and stop — do not substitute another user.

## Staying current — check SAP Notes first

SAP Notes supersede this file. Landscapes differ by release, patch level, DB and OS, and SAP changes
procedures via Notes/KBAs between doc revisions.

**If the [SAP Notes MCP](https://github.com/marianfoo/sap-mcp-servers) is configured, use it before
acting on anything version-specific** — especially any destructive step, or when a command here doesn't
behave as documented:

1. `search` the topic (e.g. the component + symptom, or a Note number cited below).
2. `fetch` the promising Note IDs for the current text, validity (affected releases/components),
   prerequisites and side effects.
3. **Check the `attachments` array.** SAP routinely puts the actual deliverable *in an attachment* rather
   than the Note body — sizing guides, SQL script collections, configuration PDFs, spreadsheets. A Note
   whose text says "see the attached document" is not fully read until you have it.
4. Prefer the Note over this file where they disagree, and say which Note you followed.

**Downloading an attachment:** `fetch` returns `attachments[].url` **and `attachments[].filename`**;
**`fetch_attachment`** retrieves the bytes. Pass the URL verbatim — the URLs are opaque and cannot be
constructed. If your MCP build predates that tool, open the URL in a signed-in browser instead and say the
file was fetched manually.

> ⚠️ **Two ways a hand-rolled fetch goes wrong — both verified.**
> **1. Trusting the status code.** An unauthenticated request returns **HTTP 200 with a small HTML login
> stub**, not an error. Check the content type and magic bytes, or you save a JavaScript redirect page
> under a `.pdf` name.
> **2. Naming the file from the URL.** SAP serves many attachments from a *generic endpoint* —
> `…/services/attachment.htm?iv_key=…&iv_guid=…` — so the URL basename is `attachment.htm` even when the
> payload is a 24-page PDF. Take the name from **`attachments[].filename`** or the response's
> **`Content-Disposition`** header, never from the URL path.

No MCP available? Look the Note up on `me.sap.com/notes/<id>` and say the check was skipped rather than
assuming this file is current.

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
