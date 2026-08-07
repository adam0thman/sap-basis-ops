# SAPControl read-only diagnostics, `sappfpar`, and the work directory

Reference detail for [../SKILL.md](../SKILL.md). All `sapcontrol`/`sappfpar`/`disp+work` here are kernel
tools — **identical on Linux, Windows and AIX** (path/extension aside). Prefix every `sapcontrol` call
with `-nr <nr> -function`.

## Getting the definitive `-function` list for **your** kernel

The set of supported webmethods **varies by kernel release and patch level**, so never assume a function
exists — ask the binary. SAP documents the command-line help as the authoritative list: [V, T4]

```bash
# UNIX
/usr/sap/<SAPSID>/<INSTANCE><NUMBER>/exe/sapcontrol --help
# Windows
<Drive>:\usr\sap\<SAPSID>\<INSTANCE><NUMBER>\exe\sapcontrol.exe --help
```

Practical filters:
```bash
sapcontrol --help 2>&1 | grep -iE "read|list|get"      # the read-only surface
sapcontrol --help 2>&1 | grep -ciE "^ +[A-Z]"          # how many functions this kernel exposes
sapcontrol -nr <nr> -function AccessCheck <Function>   # is this one permitted for me?
```

> Per the plugin's execution discipline: derive the list with `--help` rather than assuming from this
> file, and use `AccessCheck` before concluding a method is unavailable — it may simply be *protected*
> (see `service/protectedwebmethods` below) rather than missing.

## Function map by category

Availability varies by release — confirm with `--help`. **⚠️ = state-changing**; those belong to
[sap-system-lifecycle](../../sap-system-lifecycle/SKILL.md), not to triage, and are listed here only so
you recognise them and *don't* fire one while diagnosing. [T5]

| Category | Functions |
|---|---|
| **Instance lifecycle ⚠️** | `Start` · `Stop` · `Restart` · `StartWait` · `StopWait` · `RestartWait` |
| **System lifecycle ⚠️** | `StartSystem` · `StopSystem` · `RestartSystem` |
| **Control service ⚠️** | `StartService` · `StopService` · `RestartService` |
| **Database ⚠️** | `StartDatabase` · `StopDatabase` (only if registered with the Host Agent) |
| **Status / inventory** | `GetProcessList` · `GetSystemInstanceList` · `GetInstanceProperties` · `GetVersionInfo` · `GetEnvironment` · `GetStartProfile` · `GetAccessPointList` |
| **Logs & traces** | `ABAPReadSyslog` · `ABAPReadRawSyslog` · `ListDeveloperTraces` · `ReadDeveloperTrace` · `ListLogFiles` · `ReadLogFile` |
| **Work processes / sessions** | `ABAPGetWPTable` · `GetQueueStatistic` · `ABAPGetComponentList` |
| **Enqueue** | `EnqGetStatistic` · `EnqGetLockTable` · `EnqRemoveLock` ⚠️ |
| **ICM** | `ICMGetThreadList` · `ICMGetConnectionList` · `ICMGetCacheEntries` · `ICMGetProxyConnectionList` |
| **Alerts / monitoring** | `GetAlerts` · `GetAlertTree` · `ABAPAcknowledgeAlert` ⚠️ |
| **Parameters** | `ParameterValue` (read; **setting** a parameter is ⚠️ and belongs to a change, not triage) |
| **High availability** | `HACheckConfig` · `HACheckFailoverConfig` · `HAGetFailoverConfig` · `HAFailoverToNode` ⚠️ |
| **Security / permission** | `AccessCheck <Function>` (unprotected — safe first call) |

> Note the naming convention: **`Get*` / `List*` / `Read*` / `*Check*` are read-only**; `Start*`,
> `Stop*`, `Restart*`, `Remove*`, `Acknowledge*`, `Failover*` change state. When in doubt, run
> `--help` and read the description before executing.

## Read-only SAPControl function catalog (triage-relevant)

**Status / inventory**
| Function | Shows |
|----------|-------|
| `GetProcessList` | processes of the instance + colour status |
| `GetSystemInstanceList` | all instances: host, ports, `startPriority`, `features`, `dispstatus` |
| `GetInstanceProperties` | instance metadata (dirs, ports, SID, nr) |
| `GetVersionInfo` | kernel patch level of the running instance |
| `GetEnvironment` | the instance's OS environment |

**Logs & traces** *(protected — see below)*
| Function | Equivalent |
|----------|-----------|
| `ABAPReadSyslog` | SM21 system log |
| `ABAPReadRawSyslog` | raw syslog stream |
| `ListDeveloperTraces` | list `dev_*` trace files in `DIR_HOME` |
| `ReadDeveloperTrace <file> <size>` | read a trace file (`size=0` → whole file) |
| `ReadLogFile <path> <filter>` | read an arbitrary instance log |

**Work processes / sessions / locks** *(protected)*
| Function | Equivalent |
|----------|-----------|
| `ABAPGetWPTable` | SM50 (work processes of this instance) |
| `GetQueueStatistic` | dispatcher request queues |
| `EnqGetStatistic` / `EnqGetLockTable` | enqueue server stats / lock table (on ASCS/SCS) |
| `ICMGetThreadList` / `ICMGetConnectionList` | ICM threads / connections |

**Alerts / HA / checks**
| Function | Shows |
|----------|-------|
| `GetAlertTree` / `GetAlerts` | CCMS alert tree (RZ20-style) |
| `HACheckConfig` / `HACheckFailoverConfig` | HA configuration validation |
| `AccessCheck <Function>` | whether a given web method is permitted (no auth needed) |

## `service/protectedwebmethods` (security)

Most logs/traces/WP methods are **protected by default** — governed by the profile parameter
`service/protectedwebmethods` (SAP Note 1439348). A protected method returns an authorization error
unless you either:
- call it **authenticated**: `sapcontrol -nr <nr> -user <sidadm> <password> -function <Function> …`, or
- it is **allow-listed** in the profile, e.g. `service/protectedwebmethods = SDEFAULT -GetProcessList`
  (start from the secure `SDEFAULT` set and add/remove specific methods deliberately).

Check first: `sapcontrol -nr <nr> -function AccessCheck <Function>` (this one is not protected).

## `sappfpar` argument reference

Kernel profile validator — works while the system is **down**. [KBA 2733511]
```
sappfpar <command> [pf=<profile>] [nr=<nr>] [name=<SID>]
  check     validate parameters, check shared-memory config, estimate memory requirement
  all       print every parameter the kernel knows + effective value from the profile
  <name>    print a single parameter's value
  help      usage
```
- Effective values shown are those that apply **after the next startup**; the `SAP:` column = kernel
  default.
- Typical use: `sappfpar check pf=/usr/sap/<SID>/SYS/profile/<SID>_<INST><nr>_<host>` after any profile
  change, **before** `StartSystem`.

## Instance work directory — what to read

`/usr/sap/<SID>/<INST><nr>/work/` (Windows: `…\work\`). First stop when an instance won't start:

| File | Content |
|------|---------|
| `dev_disp` | dispatcher trace (start failures show here first) |
| `dev_w0` … `dev_w<n>` | work-process traces |
| `dev_ms` | message server trace (ASCS/SCS) |
| `dev_rd` | gateway trace |
| `dev_icm` | Internet Communication Manager trace |
| `dev_enq*` / `enserver` logs | enqueue server |
| `stderr1`, `stderr2`, … | instance stdout/stderr per start |
| `available.log`, `sapstart.log` | start-service / availability logs |

Reading these from the shell = `sapcontrol … ReadDeveloperTrace <file> 0`; on disk = your pager. Cleanup
of old traces/logs is **`sap-housekeeping`**, not triage.

## Sources

Same as [../SKILL.md](../SKILL.md) §Sources — SAP S/4HANA Technical Operation curriculum [T1], SAP Note
1439348 (`service/protectedwebmethods`) [T2], SAP KBA 2733511 (`sappfpar`) [T3], the SAPControl page
[T4], and *How to use the SAPControl Web Service Interface* [T5].

On the `-function` list specifically:

- **[T4]** *Starting and Stopping SAP Systems Using SAPControl* — SAP Help Portal. **[V]** verified
  during authoring: *"You can find a detailed list of all SAPControl options and features in the command
  line help, which you can call as follows: UNIX: `/usr/sap/<SAPSID>/<INSTANCE><NUMBER>/exe/sapcontrol
  --help`"* (Windows: `sapcontrol.exe --help`). This is why `--help` — not this file — is authoritative
  for a given kernel.
  https://help.sap.com/docs/ABAP_PLATFORM_NEW/30eef4341efd4a2c86f2f98f187eccb3/471d6feeff6e0d46e10000000a155369.html
- **[T5]** *How to use the SAPControl Web Service Interface* — SAP NetWeaver Server Infrastructure; the
  webmethod reference behind the category map. Function availability differs by release/patch level, so
  treat the map as orientation and `--help` + `AccessCheck` as ground truth. [G]
