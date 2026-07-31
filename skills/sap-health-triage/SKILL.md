---
name: sap-health-triage
description: >-
  First-response health check and triage for a SAP NetWeaver / S/4HANA system from the OS shell — is it
  up, is it healthy, and if not, why. Uses SAPControl's read-only diagnostics (GetProcessList, extract
  the SM21 syslog via ABAPReadSyslog, work processes via ABAPGetWPTable, dev traces via
  ListDeveloperTraces/ReadDeveloperTrace, CCMS alerts via GetAlertTree), the sappfpar profile/memory
  validator, and OS-level checks (disp+work, dpmon, filesystem). Use for "is <SID> up/healthy?",
  "verify the start worked", "why won't it start", "check the syslog / traces / work processes / profile
  parameters". Linux/Windows/AIX. Cited to help.sap.com / SAP Notes.
---

# SAP Health Triage

The "is it up and healthy — and if not, why?" skill. Mostly **read-only** — safe to run — but confirm
the **SID** before pointing at a system, and note that several SAPControl methods are **protected** and
may need to be permitted/authenticated (§7).

## Guardrail note

Health checks don't change state, so the full stop/delete guardrails don't apply — but still:
**Identify** the SID/host/instance before running, and treat any command that *writes* (none here) with
the repo guardrails. Reading another system's syslog/traces is still accessing that system — confirm you
have the right SID.

---

## 1. Is it up?

```bash
# UNIX (host agent copy); Windows: %ProgramFiles%\SAP\hostctrl\exe\sapcontrol.exe
/usr/sap/hostctrl/exe/sapcontrol -nr <nr> -function GetSystemInstanceList   # all instances + dispstatus
/usr/sap/hostctrl/exe/sapcontrol -nr <nr> -function GetProcessList          # this instance's processes
/usr/sap/hostctrl/exe/saphostexec -status                                   # host agent control layer
```
`dispstatus`/process colour: **GREEN** up · **YELLOW** starting/stopping · **GRAY** stopped · **RED**
error. A start is only "done" when the expected instances are GREEN. [G, T4]

---

## 2. Extract logs & traces (via SAPControl — no SAP GUI needed)

```bash
# SM21 system log (the ABAP syslog) straight from the shell:
sapcontrol -nr <nr> -function ABAPReadSyslog                     # [V, T2]
# list all instance trace files in DIR_HOME (dev_disp, dev_w*, dev_ms, dev_rd, …):
sapcontrol -nr <nr> -function ListDeveloperTraces                # [V, T1]
# read one trace file (size=0 → whole file):
sapcontrol -nr <nr> -function ReadDeveloperTrace dev_w0 0        # [V, T1]
# read an arbitrary instance log file:
sapcontrol -nr <nr> -function ReadLogFile <path> ''             # [G, T5]
```
On the filesystem these live in the instance **work directory**
`/usr/sap/<SID>/<INST><nr>/work/` (`dev_*` traces, `stderr*`, `available.log`) — the first place to look
when an instance won't come up. Trace/work-dir **cleanup** is `sap-housekeeping`, not here.

---

## 3. Work processes, queues & locks

```bash
sapcontrol -nr <nr> -function ABAPGetWPTable        # work processes, like SM50 / SAP MC  [V, T1]
sapcontrol -nr <nr> -function GetQueueStatistic     # dispatcher request queues
sapcontrol -nr <nr> -function EnqGetStatistic       # enqueue (lock) server statistics (on ASCS/SCS)
```
Watch for: all WPs in status `running`/`stopped` (hung), a growing dispatcher queue, or enqueue
lock-table saturation.

---

## 4. CCMS alerts

```bash
sapcontrol -nr <nr> -function GetAlertTree           # CCMS alert tree (RZ20-style) from the shell  [G, T5]
```

---

## 5. Validate profiles & memory — `sappfpar`

`sappfpar` is a **SAP kernel tool** that checks the profile configuration, validates shared-memory
setup, and **estimates memory requirements** — usable **while the system is down**, so it's the key tool
for *"won't start"* and *post-change* validation. [V, T3]

```bash
# check a profile: validates parameters + shared memory + estimates memory need
sappfpar check pf=/usr/sap/<SID>/SYS/profile/<SID>_<INST><nr>_<host>      # [V, T3]
# dump every parameter the kernel knows + the effective value from the profile:
sappfpar all pf=/usr/sap/<SID>/SYS/profile/<SID>_<INST><nr>_<host>
# scope to an instance / system:
sappfpar check pf=<profile> nr=<nr> name=<SID>
```
Notes [V/G, T3]: displayed values are those that become **effective after the next startup**; the `SAP:`
column shows kernel **defaults**. Run `sappfpar check` **after any profile change and before restarting**
— it catches bad parameter values and insufficient memory that would otherwise fail the start. (Same
binary/args on Linux, Windows and AIX.)

---

## 6. OS-level triage

```bash
disp+work -version                     # kernel release + patch level, DB client, unicode (all OS)
dpmon pf=<profile>                      # dispatcher/WP monitor from the shell (SM50-like)
# UNIX resource checks:
df -h                                   # ⚠️ FILESYSTEM FULL is the #1 "won't start / hung" cause
ps -ef | grep -E "disp\+work|ms\.sap|sapstartsrv|enserver|enq"
free -m ; top                           # memory / load
```
**Windows** equivalents: Task Manager / `Get-Service SAP*` / `wmic logicaldisk get name,freespace` for
disk, and the **SAP MMC** for the process view. `disp+work -version` and `dpmon` are identical.

---

## 7. "Won't start" triage checklist

Work top-down; each line is the check and the tool:

1. **Control layer down?** `saphostexec -status`; `sapcontrol … GetProcessList` unreachable → start
   `sapstartsrv` / the host agent first.
2. **Filesystem full?** `df -h` on `/usr/sap`, `/sapmnt`, the DB and log filesystems — full `work`/log
   dirs block startup. → `sap-housekeeping`.
3. **Database down?** app servers (PAS/AAS) need the DB → check via
   [sap-db-command-reference](../sap-db-command-reference/SKILL.md).
4. **Bad profile / not enough memory?** `sappfpar check pf=<profile>` (§5).
5. **Ports in use / wrong?** dispatcher `32<nr>`, gateway `33<nr>`, ICM `8xxx`, message server `36<nr>` —
   `netstat`/`ss` for conflicts.
6. **What does the trace say?** `ReadDeveloperTrace dev_disp 0` / `dev_w0` (§2), or the work dir directly.
7. **Kernel mismatch after a patch?** `disp+work -version`.

---

## 8. Security: protected web methods

Many SAPControl methods (`ABAPReadSyslog`, `ABAPGetWPTable`, `ReadDeveloperTrace`, …) are **protected**
by default and governed by the profile parameter **`service/protectedwebmethods`** (SAP Note 1439348).
Protected methods require an authenticated call (e.g. `-user <sidadm> <password>`), or must be explicitly
allow-listed for monitoring. Check with:
```bash
sapcontrol -nr <nr> -function AccessCheck <FunctionName>     # is this method permitted?
```

## Cross-references

- **Start/stop the system** (and the order): [sap-system-lifecycle](../sap-system-lifecycle/SKILL.md).
- **Database up/health:** [sap-db-command-reference](../sap-db-command-reference/SKILL.md).
- **Clean up full work/trace/log dirs** found here: `sap-housekeeping`.
- **Full read-only SAPControl diagnostic catalog + `service/protectedwebmethods` detail:**
  [references/diagnostics-catalog.md](references/diagnostics-catalog.md).

## Sources

- **[T1]** *Log and Trace Information for System Start and Stop* — SAP S/4HANA Technical Operation
  curriculum. **[V]** `ABAPGetWPTable` (=SM50), `ListDeveloperTraces` (trace files in `DIR_HOME`),
  `ReadDeveloperTrace <file> <size>` (size 0 = whole file).
  https://learning.sap.com/courses/technical-implementation-and-operation-i-of-sap-s-4hana-and-sap-business-suite/log-and-trace-information-for-system-start-and-stop
- **[T2]** `ABAPReadSyslog` (SM21 syslog) + restriction via `service/protectedwebmethods` — **SAP Note
  1439348** (protected web methods of sapstartsrv). https://me.sap.com/notes/1439348
- **[T3]** `sappfpar` (`check pf=<profile>`, `all`, `nr=`/`name=`; validates params + shared memory +
  memory estimate; usable while the system is down) — SAP kernel tool; **SAP KBA 2733511**.
  https://me.sap.com/notes/2733511
- **[T4]** `GetProcessList` / `GetSystemInstanceList` / status colours — *Starting and Stopping SAP
  Systems Using SAPControl* (see sap-system-lifecycle §Sources).
- **[T5]** *How to use the SAPControl Web Service Interface* — SAP NetWeaver Server Infrastructure
  (function reference: `GetAlertTree`, `ReadLogFile`, `GetQueueStatistic`, `EnqGetStatistic`, …). [G]

**To confirm/deepen** (once the SAP Notes session can read content): SAP Note 1439348 for the exact
`service/protectedwebmethods` default list and syntax, and KBA 2733511 for `sappfpar check` behaviour.
