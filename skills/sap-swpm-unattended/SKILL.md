---
name: sap-swpm-unattended
description: >-
  Install a SAP system with Software Provisioning Manager without clicking through the UI — build an
  `inifile.params` response file, harvest its parameter keys from SWPM's own `control.xml` rather
  than guessing, and run `sapinst` headless. Says where the headless route stops: installation
  export media is resolved by SWPM's media server, not the response file, so a fresh install must be
  finished in the SL-UI. Covers reaching that UI without putting root's password in a browser, the
  pre-filled values that silently target the wrong database or thrash the host, and the plaintext
  passwords left on disk. Use for "unattended SAP install", "silent sapinst", "SWPM response file",
  "inifile.params", "SAPINST_SKIP_DIALOGS", "automate SWPM", "sapinst without GUI", "Empty package
  path EXPORT1", "Parameter for download basket is empty", "install NetWeaver silently".
---

# Unattended SWPM installation (`sapinst` + response file)

**[F]** = proven on the NetWeaver 7.52 AS ABAP / HANA install this skill comes from; **[V]** = read
from SWPM's own output or SAP documentation; **[A]** = reasoned analogue, not executed here.

> ## The media parameter almost nobody finds
>
> A response file **can** complete a fresh installation unattended. But SWPM does **not** carry over
> the media locations you pick in the Media Browser dialog, and there is no `NW_Unpack` key for the
> installation export. You must add a line per medium by hand: **[V, 2230669]**
>
> ```
> SAPINST.CD.PACKAGE.<media_name> = /full/path/to/medium
> ```
>
> Miss it and the run dies at `loadInstallationExportCDs` with *"Empty package path … (Requested
> package : EXPORT1)"*, whose own suggested fix is to re-run **without** `SAPINST_SKIP_DIALOGS` —
> which reads as "this cannot be automated". It can. **The error names the media you are missing:**
> `Requested package : EXPORT1` → add `SAPINST.CD.PACKAGE.EXPORT1`.
>
> ⚠️ **Only whole media, never single files.** *"Currently you can only specify complete DVDs, not
> paths to single files like \*.SAR archives."* **[V, 2230669]** Point it at the directory that holds
> `DATA_UNITS`/`LABEL.ASC`, not at an archive. Kernel SAR files go through
> `archives.downloadBasket` instead (§1b).
>
> **[F]** On the install this skill comes from, this parameter was not found. Nine workarounds were
> tried instead — bind mounts, `SAPINST_CWD`, editing `start_dir.cd` — and the run was finished by
> hand in the SL-UI (§4). §3 lists them so nobody repeats that.

## 0. Decide the route before you build anything

SAP names two unattended modes, and the difference matters for automation: **[V, 2230669]**

| Mode | Flags | Use |
|---|---|---|
| **Observer** | `SAPINST_SKIP_DIALOGS=true` | Runs unattended **and** starts the SL-UI so you can watch progress and read logs in a browser. Parameters still come only from the file and cannot be changed there. |
| **Non-observer** | the above **+ `SAPINST_START_GUISERVER=false`** | Scripted or overnight runs. No web dispatcher, no UI. *"It is crucial that the process is started without a Web Dispatcher … otherwise the automation could be stuck if Software Provisioning Manager encounters a situation that requires user interaction."* |

| Your task | Route |
|---|---|
| Fresh system install, system copy, additional app server | Response file, **end to end** — §1, §2 |
| You want to watch it | Same, in **observer** mode |
| A parameter exists only in the UI | SAP's instruction is to **raise a ticket under `BC-INS`** so it gets exposed. **[V, 2230669]** Finish that run in the SL-UI (§4) meanwhile. |

Check which UI your SWPM build defaults to:

```bash
cd <swpm_dir> && ./sapinst -h | grep -iE 'noguiserver|guiserver|slui'
```

SWPM 1.0 SP48 and SWPM 2.0 start the **browser-based SL-UI** by default — a web server on port
**4237** that prints a one-time URL. No X11 is involved, and `--noguiserver` turns it off. **[V]**

---

## 1. Build `inifile.params`

### 1a. Generate the file — do not hand-write it

**SAP's documented method, and the one to use: [V, 2230669]**

1. Start `sapinst` normally and answer the screens.
2. **Stop after the "Parameter Summary" screen** — `SAPINST_STOP_AFTER_DIALOG_PHASE=true` does this
   for you. **[V, 2609804]**
3. Take **`inifile.params`** from the installation directory, and **`instkey.pkey`** beside it.
4. Edit values, add the `SAPINST.CD.PACKAGE.*` media lines, re-run.

The generated file documents itself: every unset parameter is left in as a **commented-out line with
its description above it**, so the file doubles as the parameter reference. **[V, 2230669]**

Find the **product ID** in `sapinst_dev.log`, or in the generated file's own header —
`product-id=NW_ABAP_ASCS:NW750.ADA.ABAP`. **[V, 2230669]**

### 1a-bis. Building one from scratch

The keys are the `defval-for-inifile-generation` attributes in SWPM's **`control.xml`**, which is
unpacked into the sapinst working directory. Read them from the build you are actually running:

```bash
# control.xml lands under the extracted SWPM directory / sapinst working dir
find / -name control.xml -path '*sapinst*' 2>/dev/null
grep -oE '[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_]+' <path>/control.xml | sort -u
```

**[F]** On the install this comes from that yielded **1265 keys**. Guessing from blog posts does not
work — the key names are product- and version-specific.

A faster route if the product has already run once: start `sapinst` interactively, let it reach the
end of the dialog phase, and it writes an `inifile.params` of its own under
`sapinst_instdir/<product>/…`. Copy that and edit it. **[A]**

### 1b. The keys that matter (NetWeaver ABAP on HANA)

| Key | Note |
|---|---|
| `NW_GetSidNoProfiles.sid` | the new system's SID |
| `NW_GetSidNoProfiles.unicode` | `true` |
| `NW_GetMasterPassword.masterPwd` | see §1d — never a literal |
| `NW_getFQDN.FQDN` / `.setFQDN` | domain, and `true` |
| `NW_CI_Instance.ascsInstanceNumber` / `.ciInstanceNumber` | e.g. `03` / `04` |
| `NW_HDB_getDBInfo.dbhost` / `.dbsid` | the **HANA host and HANA SID** |
| `NW_HDB_getDBInfo.tenantPort` | the **tenant's** SQL port — `3<inst_nr>41` |
| `HDB_Userstore.systemDBPort` | SYSTEMDB — `3<inst_nr>13` |
| `NW_HDB_DB.abapSchemaName` / `.abapSchemaPassword` | e.g. `SAP<SID>` |
| `NW_Unpack.sapExeSar` `.sapExeDbSar` `.igsExeSar` `.igsHelperSar` `.sapJvmSar` | **five** archives, not three |
| `nwUsers.sidadmPassword`, `hostAgent.sapAdmPassword` | derived from master unless set |
| **`SAPINST.CD.PACKAGE.<media_name>`** | **one line per medium, full path, whole media only** **[V, 2230669]** |

> ### 🛑 Two keys that trip up hand-written files
>
> **`archives.downloadBasket` — a directory, not a file.** Without it the run fails with
> *"Parameter for download basket is empty"* even though every `NW_Unpack.*` path is set. The
> individual archive paths are **not** sufficient; SWPM wants the directory that contains them, and
> **only one version of each archive may be in it**. **[V, 2230669 + KBA 2608474]**
>
> That KBA lists three further causes of the same message: a `SAPINST.CD.PACKAGE.<media_name>` path
> SWPM cannot validate, a parameter file missing at `SAPINST_INPUT_PARAMETERS_URL`, and the **wrong
> DB-specific kernel** (`SAPEXEDB` built for another database). **[V, 2608474]**
>
> **`NW_GetSidNoProfiles.SAP_GUI_DEFAULT_LANGUAGE` must be left UNSET.** The validator checks it
> against a language list read from the installation export. A forced value — even a correct one
> like `EN` — fails. Omit the key. **[F]** — field-observed only; a Notes search turned up nothing
> covering it, so treat it as a local observation, not documented behaviour. Note **2626837**
> records the same *shape* of failure for `isUnicode` (*"Radio group contains an invalid
> value"*). **[V]**

> ⚠️ **`NW_Unpack` wants five kernel archives.** A BOM built from "kernel part I + part II + IGS" is
> missing **`igshelper`** and **SAP JVM**, and the run stops at the unpack step. Stage all five before
> you start. **[F]**

### 1c. Validate the file is complete before a long run

The dialog phase fails fast and cheaply. Iterate deliberately — each run tells you the next missing
key by name, and the step number is your progress metric:

```bash
grep -E 'ERROR|FAIL|is empty|not set' <instdir>/sapinst.log | tail -20
```

**[F]** Fifteen headless runs took the parameter set from failing at step 4 to failing at step 148.
That is the expected shape of the work; budget for it.

### 1d. Passwords: encrypted if generated, plaintext if hand-written

**A SWPM-generated file encrypts them.** Since SAPinst **749.0.69** `inifile.params` is coupled to a
DES key in **`instkey.pkey`**; from **753.0.6** the encryption is AES256. The key file must sit in
the **same directory** as the parameter file or the values cannot be decrypted — copy both, or
neither. **[V, 2230669 + 2609804]**

**You cannot encrypt a password by hand.** To change one, re-run the dialog phase
(`SAPINST_STOP_AFTER_DIALOG_PHASE=true`), enter the new password, and take the re-generated
encrypted value. **[V, 2609804]**

> ⚠️ **A hand-written `inifile.params` is cleartext**, including the master and database passwords.
> SWPM writes mode `600`, which is not the same as safe — and this is a second reason to generate
> the file rather than author it. **[F]**

- Generate it inside a `creds exec` child so the passwords never reach a command line or a log.
- **Shred it the moment the install finishes** — `shred -u` — and treat its directory as sensitive
  until you have.
- SWPM masks passwords in its *own* logs (verified by scanning the leftovers), but your response
  file is not one of its logs. **[F]**

---

## 2. Run it headless

```bash
cd <swpm_dir>
./sapinst SAPINST_EXECUTE_PRODUCT_ID=<PRODUCT_ID> \
          SAPINST_REMOTE_ACCESS_USER_IS_TRUSTED=true \
          SAPINST_START_GUISERVER=false \
          SAPINST_SKIP_DIALOGS=true \
          SAPINST_INPUT_PARAMETERS_URL=/path/to/inifile.params
```

`SAPINST_START_GUISERVER=false` is what keeps it off port 4237; `SAPINST_SKIP_DIALOGS=true` is what
makes it consume the response file instead of asking. **[V]**

---

## 3. Media — the one parameter you must add by hand

```
Empty package path. … (Requested package : EXPORT1)
SOLUTION: If Software Provisioning Manager is running with option SAPINST_SKIP_DIALOGS=true,
run the service again without that option and you will be asked about the missing package location.
```

**The message is misleading.** Its suggested fix — re-run without `SAPINST_SKIP_DIALOGS` — reads as
"not automatable". The actual fix is one line, and the error names the medium for you: **[V, 2230669]**

```
SAPINST.CD.PACKAGE.EXPORT1 = /full/path/to/the/export
```

`NW_ABAP_Import_CD_Dialog` and `NW_CreateDBandLoad` genuinely expose no inifile keys — media is
simply not resolved through them. **Diagnose a path SWPM rejects** in `sapinst_dev.log`: **[V, 2608474]**

```bash
grep -A3 'SAPINST.CD.PACKAGE' <instdir>/sapinst_dev.log
# Scanning parameter SAPINST.CD.PACKAGE.KERNEL = /mnt/kernel753 for CDs.
# Not a valid path or not accessible: /mnt/kernel753
```

### What was tried before the parameter was found **[F]**

Recorded so nobody repeats it. Every one of these fails, and none is necessary:

| Attempt | Result |
|---|---|
| `NW_Unpack.*` direct archive paths | not consulted for the export |
| `archives.downloadBasket` | fixes the **kernel** archives only |
| `download_service.directory` | no effect |
| `SAPINST_CWD` at a media root | rejected — that becomes the *installation* directory |
| starting `sapinst` from the media root | `start_dir.cd` ignores the shell's cwd |
| `LABELIDX.ASC` placed in a media root | not scanned |
| symlink, then a **bind mount** of the export under the SWPM directory | not scanned — SWPM's own `LABEL.ASC` makes that directory a single medium |
| `SAPINST_CLEANUP=false`, edit `start_dir.cd`, resume | SWPM **regenerates** `start_dir.cd` every run |

`start_dir.cd` is seeded from the **sapinst executable's own directory**, whatever your working
directory is — which is why none of the path tricks work. **[F]** The supported mechanism is
`SAPINST.CD.PACKAGE.*`, not the filesystem.

---

## 4. Finishing in the SL-UI without putting root's password in a browser

The SL-UI uses **HTTP Basic auth against an OS user** — root, or a non-root account named in
`SAPINST_REMOTE_ACCESS_USER`. SWPM says so itself: **[V]**

> You are starting the 'sapinst' executable without using the SAPINST_REMOTE_ACCESS_USER property.
> … the root user password does not reach the client browser, which reduces the attack surface.

**Prefer `SAPINST_REMOTE_ACCESS_USER=<non-root account>`.** It is the supported way to keep root's
password out of the browser, and it is one parameter.

Where that is not possible, a local proxy can inject the `Authorization` header from inside a
`creds exec` child, so the password never reaches a command line, a log, or your terminal: **[F]**

```
browser → 127.0.0.1:4238   local proxy, adds the auth header
        → 127.0.0.1:4237   ssh -L tunnel
        → <host>:4237      sapinst SL-UI
```

```bash
ssh -N -L 127.0.0.1:4237:127.0.0.1:4237 <host>
```

> ⚠️ **Two snags that cost time.** **[F]**
>
> - `sapinst` runs a **TLS selftest against its own self-signed certificate** and aborts the whole
>   process when the cert does not match the hostname you reach it by. Set
>   `SAPINST_CHECK_SELFTEST_RESULT=false`.
> - **Pin the SSH forward to IPv4** — `-L 127.0.0.1:4237:…`. Without the explicit `127.0.0.1` it
>   binds `::1` only, and the proxy cannot reach it.

---

## 5. Review the pre-filled values — two of them do real damage

Choose **Custom** parameter mode, not Typical. Typical accepts pre-filled values **without showing
you the screen**. Both of the following were caught only because Custom displayed them: **[F]**

| Screen | SWPM offered | Must be | Why it matters |
|---|---|---|---|
| SAP HANA Database | DBSID = the **HANA SID** | the **tenant name** | 🛑 On this screen "DBSID" means the **tenant**, not the HANA system. Leaving the HANA SID — or any existing tenant's name — creates the new ABAP schema **inside that existing database**. On a shared HANA this silently targets a production tenant. |
| Database Import | parallel jobs = a formula from core count (e.g. **72**) | what the host can actually serve (e.g. **8**) | SWPM's formula ignores co-resident systems and per-tenant memory caps. Oversubscribing thrashes the host or runs the tenant out of memory mid-import. |

> **The DBSID trap came from the response file itself.** A wrong value in `inifile.params` is
> pre-filled silently and looks authoritative on screen. Review the generated screens even when you
> wrote the parameters. **[F]**

Other choices worth making deliberately: **[F]**

- **Secure Storage Key: Default, not Individual**, for a sandbox. Individual is for productive
  systems and requires escrowing a displayed key — lose it and secure storage is unrecoverable.
- **Cleanup of OS users: enable it.** SAP's security recommendation, and it is **off by default** —
  otherwise `<sid>adm` stays in the `sapinst` group.
- **Host Agent upgrade** is offered and is shared with every system on the host. Routine and
  backward compatible; only `saphostexec` restarts.

---

## 6. After it finishes

1. **`shred -u` the response file.** Plaintext master and database passwords (§1d).
2. **Tear down the access path** — stop the proxy and the SSH tunnel.
3. **Scan for leftover secrets, and self-test the scan.** A grep returning zero hits proves nothing
   until you have confirmed the pattern matches something. **[F]**
4. **Put any memory limit you raised for the import back down** — a tenant `allocationlimit` lifted
   for the load will otherwise stay lifted.
5. **Decide autostart deliberately.** A demo or on-demand system should not come up with the host;
   disable the systemd units rather than discovering it after a reboot.
6. **Licence key.** A temporary key is installed automatically; the permanent one comes from SAP for
   Me. Download rights are not use rights.

---

## Cross-references

- **`sapinst` among the other OS executables:** [sap-os-executables](../sap-os-executables/SKILL.md)
  — the flag list lives there too; this skill is the worked method.
- **Stage the media first:** [sap-software-download](../sap-software-download/SKILL.md) — resolves
  exact filenames, sizes and SHA-256, and `sapdl.py` scripts the download. Note the five-archive
  kernel requirement in §1b when building the BOM.
- **Start/stop order afterwards:** [sap-system-lifecycle](../sap-system-lifecycle/SKILL.md).
- **Verify the system came up:** [sap-health-triage](../sap-health-triage/SKILL.md).
- **HANA tenant creation and `hdblcm`:** [sap-hana-lifecycle-tools](../sap-hana-lifecycle-tools/SKILL.md).
- **Add-ons and support packages after the platform is up:**
  [sap-transport-mgmt](../sap-transport-mgmt/SKILL.md) for SPAM/SAINT queue mechanics.
- **Parameter-key reference, the media keys and the dead ends:**
  [references/inifile-parameters.md](references/inifile-parameters.md).

## Sources

**SAP Notes / KBAs** — read in full via the SAP for Me Notes service:

- **2230669** — *System Provisioning Using an Input Parameter File* (v38, 2026-03-30,
  `BC-INS-SWPM`). **The central note.** Observer vs non-observer mode, `SAPINST.CD.PACKAGE.*`, the
  whole-media restriction, `archives.downloadBasket`, `instkey.pkey`, product-ID lookup, and the
  "raise a BC-INS ticket" escape hatch for UI-only parameters. **[V]**
- **2609804** — *SWPM Unattended Installation: password handling* (`BC-INS-SWPM`). Passwords cannot
  be encrypted by hand; `SAPINST_STOP_AFTER_DIALOG_PHASE=true` to regenerate them. **[V]**
- **2608474** — *"Parameter for download basket is empty" during Archive-Based / Unattended
  installation* (`BC-INS-SWPM`). Four causes and the `sapinst_dev.log` diagnostic. **[V]**
- **2393060** — *SAPinst Framework 749 Central Note* (`BC-INS-FWK`). **[G]**
- **1680045** / **2568783** — Release Notes for SWPM 1.0 (rec. SP48) and SWPM 2.0 (rec. SP25). **[G]**
- **2742212** — *Unattended installation fails with "Empty directory name is not allowed."* **[G]**
- **2626837** — *'isUnicode': Radio group contains an invalid value*. **[G]**
- **2974889** — *Unattended install fails in step getDBInfo due to missing parameters* (`HAN-LM-INS-SAP`). **[G]**
- **2482103** — *Installation with SWPM in unattended mode using parameter input file fails*. **[G]**
- **2506859** — *SAP system installation on Oracle with SWPM in unattended mode* (`BC-DB-ORA-SYS`). **[G]**
- **2509959** — *Diagnostics Agent unattended installation, SWPM SP20+*. **[G]**

**help.sap.com**

- [System Provisioning Using an Input Parameter File](https://help.sap.com/docs/SLTOOLSET/af62b1a90092403b931973e2a264ba71/3e7738abf8674ed7a6448d8c04fa5de7.html)
  — the SL Toolset guide page; same content as Note 2230669. **[V]**
- [Running Software Provisioning Manager](https://help.sap.com/docs/SLTOOLSET/3741bfe0345f4892ae190ee7cfc53d4c/3bef20d729b84e31bbced506c5b287c0.html) **[G]**
- [Additional Information about Software Provisioning Manager](https://help.sap.com/docs/SLTOOLSET/df78c1d3e27044d29dd9c77765a7e40f/c0d644d57afb44ff9d7788b80163608f.html) **[G]**
- Per-scenario Installation and System Copy guides: **support.sap.com/sltoolset** → System Provisioning.
  Note 2230669 is explicitly an *addition* to those guides, not a replacement. **[V]**

**From the running system** — always outrank the above for your build:

- SWPM's own `control.xml` (`defval-for-inifile-generation`), and the generated `inifile.params`
  with its self-documenting comments. **[V]**
- `sapinst_dev.log` for the product ID and the media scan. **[V]**
