# `inifile.params` — key harvesting, proven keys, and the failure catalogue

Companion to the parent skill. **[F]** = proven on the NetWeaver 7.52 AS ABAP / HANA install this
comes from; **[V]** = read from SWPM's own output; **[A]** = reasoned, not executed.

---

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

**Easier route when the product has run before:** let `sapinst` complete the dialog phase
interactively once. It writes its own `inifile.params` under `sapinst_instdir/<product>/…`. Copy
that and edit it — the keys are then guaranteed correct for your build. **[A]**

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
| `archives.downloadBasket` | **directory** | see §C |
| `nwUsers.sidadmPassword` | secret | derived from master if unset |
| `hostAgent.sapAdmPassword` | secret | derived from master if unset |

HANA port formula: for instance number `nn`, SYSTEMDB SQL is **`3nn13`** and a tenant's SQL port is
typically **`3nn41`** upward. Read the real value rather than assuming:

```sql
SELECT DATABASE_NAME, SERVICE_NAME, SQL_PORT
  FROM SYS_DATABASES.M_SERVICES WHERE SERVICE_NAME = 'indexserver';
```

---

## C. The two keys that are in no guide **[F]**

### `archives.downloadBasket` is a directory

Symptom: **"Parameter for download basket is empty"**, with every `NW_Unpack.*` path correctly set.

The individual archive paths are not sufficient. SWPM wants the **directory containing** the kernel
archives, as a separate key. Set both.

### `SAP_GUI_DEFAULT_LANGUAGE` must be left unset

The validator checks the value against a language list it reads **from the installation export**. A
forced value fails even when it is a language the export contains. Omitting the key lets SWPM
resolve it.

---

## D. Failure catalogue — the media wall

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

**Conclusion: answer the dialog in the SL-UI.** Parent skill §4.

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

`inifile.params` holds the master password and the database SYSTEM password **in cleartext**. SWPM
creates it mode `600`. **[F]**

- Build it inside a credential-store child process; never interpolate a password into a command
  whose output you read.
- `shred -u` it as soon as the install completes.
- SWPM **does** mask passwords in its own logs — confirmed by scanning the sapinst leftovers after
  the run. Your response file is not one of its logs. **[F]**
- When scanning for leftover secrets, **self-test the scan**: a pattern that returns zero hits
  proves nothing until you have shown it matches a known positive. **[F]**
