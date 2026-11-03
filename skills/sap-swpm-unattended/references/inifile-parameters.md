# `inifile.params` — key harvesting, proven keys, and the failure catalogue

Companion to the parent skill. **[F]** = proven on the NetWeaver 7.52 AS ABAP / HANA install this
comes from; **[V]** = read from SWPM's own output; **[A]** = reasoned, not executed.

---

> **Primary source: SAP Note 2230669** — *System Provisioning Using an Input Parameter File*,
> mirrored at [help.sap.com](https://help.sap.com/docs/SLTOOLSET/af62b1a90092403b931973e2a264ba71/3e7738abf8674ed7a6448d8c04fa5de7.html).
> It is an **addition to** the per-scenario guides at support.sap.com/sltoolset, not a replacement.

## A. Where the keys come from

SWPM generates a response file from its product definition. The authoritative key list is the set of
**`defval-for-inifile-generation`** attributes in **`control.xml`**, unpacked into the sapinst
working directory when a product starts. **[V]**

SWPM's own documentation of the attribute: **[V]**

> `defval-for-inifile-generation` defines the key. Its value is used as the initial value when
> processing the component for the first time.

```bash
# 1. locate the control.xml for the build you are actually running
find / -name control.xml -path '*sapinst*' 2>/dev/null

# 2. list candidate keys
grep -oE '[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_]+' <path>/control.xml | sort -u | wc -l
```

**[F]** 1265 keys for `NW_ABAP_OneHost:NW752.HDB.PD`. They are product- and version-specific —
a key list from a blog post, or from a different SWPM SP, will not match.

**SAP's documented route, and the right default:** run the dialog phase interactively, **stop after
the "Parameter Summary" screen** (`SAPINST_STOP_AFTER_DIALOG_PHASE=true`), and take the generated
`inifile.params` — plus **`instkey.pkey`** — from the installation directory. Unset parameters are
left in the file as commented-out lines with their documentation above them, so it doubles as the
reference. **[V, 2230669 / 2609804]**

Harvesting `control.xml` is the fallback for when you cannot run the dialog phase at all.

---

## B. Keys proven on a NetWeaver 7.52 ABAP / HANA install **[F]**

| Key | Value shape | Notes |
|---|---|---|
| `NW_GetSidNoProfiles.sid` | `<SID>` | check against SAP Note 1979280 (reserved SIDs) first |
| `NW_GetSidNoProfiles.unicode` | `true` | |
| `NW_GetSidNoProfiles.SAP_GUI_DEFAULT_LANGUAGE` | — | **omit entirely**, see §C |
| `NW_GetMasterPassword.masterPwd` | secret | inject from a credential store, never a literal |
| `NW_getFQDN.FQDN` | `example.local` | |
| `NW_getFQDN.setFQDN` | `true` | |
| `NW_CI_Instance.ascsInstanceNumber` | `03` | |
| `NW_CI_Instance.ciInstanceNumber` | `04` | |
| `NW_HDB_getDBInfo.dbhost` | HANA host | |
| `NW_HDB_getDBInfo.dbsid` | **HANA SID** | the HANA system, e.g. `HDB` |
| `NW_HDB_getDBInfo.tenantPort` | `3<inst>41` | the **tenant's** SQL port |
| `HDB_Userstore.systemDBPort` | `3<inst>13` | SYSTEMDB |
| `NW_HDB_DB.abapSchemaName` | `SAP<SID>` | |
| `NW_HDB_DB.abapSchemaPassword` | secret | |
| `NW_Unpack.sapExeSar` | kernel part I | |
| `NW_Unpack.sapExeDbSar` | kernel part II (DB-specific) | |
| `NW_Unpack.igsExeSar` | IGS | |
| `NW_Unpack.igsHelperSar` | **igshelper** | commonly missed |
| `NW_Unpack.sapJvmSar` | **SAP JVM** | commonly missed |
| `archives.downloadBasket` | **directory** | see §C; one version of each archive only |
| `SAPINST.CD.PACKAGE.<media_name>` | **full path** | one line per medium; **whole media only, never a \*.SAR** **[V, 2230669]** |
| `nwUsers.sidadmPassword` | secret | derived from master if unset |
| `hostAgent.sapAdmPassword` | secret | derived from master if unset |

HANA port formula: for instance number `nn`, SYSTEMDB SQL is **`3nn13`** and a tenant's SQL port is
typically **`3nn41`** upward. Read the real value rather than assuming:

```sql
SELECT DATABASE_NAME, SERVICE_NAME, SQL_PORT
  FROM SYS_DATABASES.M_SERVICES WHERE SERVICE_NAME = 'indexserver';
```

---

## C. Two keys that trip up hand-written files

### `archives.downloadBasket` is a directory

Symptom: **"Parameter for download basket is empty"**, with every `NW_Unpack.*` path correctly set.

SWPM wants the **directory containing** the archives, as a separate key, and *"make sure that there
is only one version of the same archive in the directory"*. **[V, 2230669]**

KBA **2608474** gives four causes for this one message: **[V]**

| Cause | Check |
|---|---|
| `archives.downloadBasket` unset | the key itself |
| `SAPINST.CD.PACKAGE.<media_name>` cannot be validated | `grep -A3 SAPINST.CD.PACKAGE sapinst_dev.log` → *"Not a valid path or not accessible"* |
| parameter file not found | the path in `SAPINST_INPUT_PARAMETERS_URL` |
| wrong DB-specific kernel | `SAPEXEDB` must match your database |

### `SAP_GUI_DEFAULT_LANGUAGE` must be left unset

The validator checks the value against a language list it reads **from the installation export**. A
forced value fails even when it is a language the export contains. Omitting the key lets SWPM
resolve it.

---

## D. Media — the parameter, and the dead ends

**The supported mechanism is `SAPINST.CD.PACKAGE.<media_name> = <full path>`, one line per medium.**
SWPM does **not** carry over what you chose in the Media Browser dialog, and *"currently you can
only specify complete DVDs, not paths to single files like \*.SAR archives"*. **[V, 2230669]**

```
SAPINST.CD.PACKAGE.KERNEL     = /mnt/KERNEL
SAPINST.CD.PACKAGE.LOAD       = /mnt/LOAD
SAPINST.CD.PACKAGE.RDBMS      = /mnt/RDBMS
SAPINST.CD.PACKAGE.EXPORT1    = /mnt/export        # the name the error asks for
SAPINST.CD.PACKAGE.MIGRATION1 = /mnt/abap_export   # system copy: ABAP export
SAPINST.CD.PACKAGE.JMIG       = /mnt/java_export   # system copy: Java export
```

Relative paths are not sufficient — use full paths. **[V, 2230669]**

### The dead ends

Error at `loadInstallationExportCDs` (step ~148 of the dialog phase): **[V]**

```
Empty package path. … (Requested package : EXPORT1)
```

`NW_ABAP_Import_CD_Dialog` and `NW_CreateDBandLoad` expose **no inifile parameters**. Everything
below was tried and failed: **[F]**

| Attempt | Why it fails |
|---|---|
| `NW_Unpack.*` direct paths | not consulted for the export, only for kernel archives |
| `archives.downloadBasket` | kernel archives only |
| `download_service.directory` | no effect |
| `SAPINST_CWD` at a media root | that path becomes the *installation* directory instead |
| launching `sapinst` from the media root | `start_dir.cd` is seeded from the **executable's** directory, not the shell's cwd |
| `LABELIDX.ASC` in a media root | not scanned |
| symlink to the export under the SWPM directory | not scanned |
| **bind mount** of the export under the SWPM directory | not scanned — SWPM's own `LABEL.ASC` marks that directory as a single medium |
| `SAPINST_CLEANUP=false` + edit `start_dir.cd` + resume | regenerated on every run |

These were tried **before** `SAPINST.CD.PACKAGE.*` was found, and the run was finished by hand in
the SL-UI. None of them is necessary. **[F]**

---

## E. Reading progress out of a failing run

The dialog phase fails fast, so iterating is cheap. The **step number** is the progress metric —
each run should get further than the last.

```bash
grep -E 'ERROR|FAIL|is empty|not set' <instdir>/sapinst.log | tail -20
grep -c 'Execute step' <instdir>/sapinst.log          # rough progress
```

**[F]** Fifteen runs: step 4 → step 148. What passed along the way, and therefore what the response
file had proven correct:

| Validated | By |
|---|---|
| SID, FQDN, instance numbers | `getSID`, `sanityCheckAccounts` |
| HANA host, SID, instance, tenant port, SYSTEM credentials | `NW_HDB_getDBInfo` — checked against the live database |
| Master password and every derived password | `FormalPasswordCheck` |
| Kernel archives | `SpecifyArchive`, once `archives.downloadBasket` was set |
| HANA client | `HDB_Client_Dialogs` |

---

## F. Secret handling

**A SWPM-generated file encrypts passwords.** From SAPinst 749.0.69 they are coupled to a DES key in
`instkey.pkey`; from 753.0.6 the encryption is AES256. The key file must live in the same directory
as the parameter file. You cannot encrypt a value by hand — regenerate it through the dialog phase.
**[V, 2230669 / 2609804]**

**A hand-written file is cleartext**, master and database passwords included, at mode `600`. **[F]**

- Build it inside a credential-store child process; never interpolate a password into a command
  whose output you read.
- `shred -u` it as soon as the install completes.
- SWPM **does** mask passwords in its own logs — confirmed by scanning the sapinst leftovers after
  the run. Your response file is not one of its logs. **[F]**
- When scanning for leftover secrets, **self-test the scan**: a pattern that returns zero hits
  proves nothing until you have shown it matches a known positive. **[F]**
