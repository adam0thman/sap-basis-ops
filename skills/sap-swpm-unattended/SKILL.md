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

> ## Read this before you plan an unattended install
>
> **A response file cannot complete a fresh installation on its own.** It answers the dialog phase —
> SID, passwords, instance numbers, database connection, kernel archives — and then stops at the
> **installation export media**, which SWPM resolves through its own media server and exposes **no
> inifile parameter for**. **[F]**
>
> That is not a gap in your parameter set. It was reached with a 1265-key file harvested from SWPM's
> own `control.xml`, after fifteen headless runs, and every workaround SAP's own error message
> suggests was tried (§3).
>
> So plan for **headless to step ~148, then the SL-UI for the rest**. The response file is still
> worth building: it answers everything except the media question, makes the run repeatable, and
> leaves a reviewable record of what you actually asked for.
>
> **Exception:** a *system copy* or an *additional application server* has no installation export to
> resolve, so those can genuinely run end to end unattended. **[A]**

---

## 0. Decide the route before you build anything

| Your task | Route |
|---|---|
| Fresh system install (`NW_ABAP_OneHost`, `…_Standard`) | Response file **+ SL-UI to finish** — §1, §2, §3, §4 |
| Additional application server | Response file, likely end to end **[A]** |
| System copy / restore | Response file, likely end to end **[A]** |
| You cannot get an OS password for the host | **Stop.** The SL-UI authenticates against an OS user; without one a fresh install cannot finish. Resolve that first — §4 |

Check which UI your SWPM build defaults to:

```bash
cd <swpm_dir> && ./sapinst -h | grep -iE 'noguiserver|guiserver|slui'
```

SWPM 1.0 SP48 and SWPM 2.0 start the **browser-based SL-UI** by default — a web server on port
**4237** that prints a one-time URL. No X11 is involved, and `--noguiserver` turns it off. **[V]**

---

## 1. Build `inifile.params`

### 1a. Harvest the real keys — do not guess them

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

> ### 🛑 Two keys that are in no guide, found the hard way **[F]**
>
> **`archives.downloadBasket` — a directory, not a file.** Without it the run fails with
> *"Parameter for download basket is empty"* even though every `NW_Unpack.*` path is set. The
> individual archive paths are **not** sufficient; SWPM wants the directory that contains them.
>
> **`NW_GetSidNoProfiles.SAP_GUI_DEFAULT_LANGUAGE` must be left UNSET.** The validator checks it
> against a language list read from the installation export. A forced value — even a correct one
> like `EN` — fails. Omit the key.

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

### 1d. The response file is a plaintext secret store

`inifile.params` holds the **master password** and the **database SYSTEM password** in cleartext.
SWPM writes it `600`, which is not the same as safe. **[F]**

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

## 3. The media wall — and every workaround that does not work

```
Empty package path. … (Requested package : EXPORT1)
SOLUTION: If Software Provisioning Manager is running with option SAPINST_SKIP_DIALOGS=true,
run the service again without that option and you will be asked about the missing package location.
```

**SAP's own message is the answer: there is no parameter for this.** `NW_ABAP_Import_CD_Dialog` and
`NW_CreateDBandLoad` expose no inifile keys at all. **[V]**

Everything tried, so you do not repeat it: **[F]**

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
directory is. The media location can only be supplied by answering the dialog. **[F]**

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
- **Parameter-key reference and the failure catalogue:**
  [references/inifile-parameters.md](references/inifile-parameters.md).

## Sources

- SWPM's own `control.xml` (`defval-for-inifile-generation` attributes) and `sapinst.log`, read from
  the running build — the only authoritative key list. **[V]**
- `sapinst -h` and the SL-UI startup banner, quoted above. **[V]**
- Error text of `loadInstallationExportCDs`, quoted above. **[V]**
