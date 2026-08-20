# Per-DB backup & recovery commands

Reference detail for [../SKILL.md](../SKILL.md). Connect/start-stop for each DB is in
[../../sap-db-command-reference/SKILL.md](../../sap-db-command-reference/SKILL.md). ⚠️ all restore/recover
commands are destructive on the target — confirm recovery point and target first.

## SAP HANA (`hdb`)

> **Establish two things first:** the revision (`SELECT VERSION FROM M_DATABASE;`) and whether this is
> **MDC** (tenants) or single-container — system-DB and tenant recovery are different operations. If
> **encryption or Local Secure Store (LSS)** is active, read
> [backup-encryption-keys.md](backup-encryption-keys.md) **before** restoring anywhere but the source host.

- **PITR prereq:** `log_mode = normal` + automatic log backups on.
- **Backup:** `BACKUP DATA USING FILE ('<prefix>')`; `BACKUP DATA FOR <TENANT> …` (from SYSTEMDB).
- **Recover** (via HANA Cockpit / Studio *Recover Database*, or SQL `RECOVER DATA`): [B1]
  - most recent state · to a **point in time** · to a **specific data backup**; system DB vs tenant.
  - the DB is stopped during recovery; recovery reads the **backup catalog** + log backups.
- **Verify:** DB returns to ONLINE (`M_DATABASES`); check `backup.log` / `nameserver_alert`.

## Oracle (`ora`)

- **PITR prereq:** database in **ARCHIVELOG** mode; `brarchive` running.
- **Backup:** `brbackup -t online -m all`; `brarchive -sd` (logs). (or RMAN)
- **Restore/recover:** BR\*Tools — `brrestore` (restore files) then `brrecover` (guided): complete DB
  recovery, **point-in-time**, redo-log-only, whole-DB reset, or disaster recovery. RMAN equivalent:
  `RESTORE DATABASE; RECOVER DATABASE [UNTIL TIME '…']; ALTER DATABASE OPEN [RESETLOGS];`
- **Verify:** `SELECT status FROM v$instance;` OPEN; check `alert_<SID>.log`.

### ⚠️ Multitenant (CDB/PDB) changes the recovery model — check FIRST

```sql
SELECT cdb FROM v$database;      -- YES = container database, everything below applies
```

**The gate is the BR\*Tools patch level, not just the Oracle version.** BR\*Tools 7.40 supports
multitenant **as of Patch 24** (limited), and: **[V, MT]**

| BR\*Tools 7.40 patch | Adds |
|---|---|
| **24** | multitenant support, limited |
| **27** | **restore/recovery of individual PDBs**; **tablespace point-in-time recovery**; the `-rpd\|-recov_pdb` option |
| **30** | *Recreate database* and **Manage data encryption** (BRSPACE) |

Prerequisites: Oracle **12.1.0.2 or higher**, Oracle Client 12c on the DB server. **Multitenant RAC is not
released.** SAP states multitenant support is "to the best of our knowledge and ability" — no guaranteed
root-cause analysis or fix. **[V, MT]**

🚨 **The single most consequential option — `-rpd|-recov_pdb`:** **[V, MT]**

```
-v|-rpd|-recov_pdb <pdb_name>|<pdb_name_list>      # default: the ENTIRE container database
```

> **If `-rpd` is not specified, the entire container database with all pluggable databases is stopped at
> the start of the recovery.** On a container hosting three SAP systems, omitting one option takes down
> all three instead of one.

And the blast radius differs **by recovery type**, which is the part people miss: **[V, MT]**

| BRRECOVER function | Effect on PDBs *not* named in `-rpd` |
|---|---|
| **Complete (media) recovery** | **Unaffected** — if they were open they stay open and usable throughout |
| **Database point-in-time recovery** | **Plugged out** before restore, plugged back in after → **all PDBs unavailable for the whole recovery** |
| **Tablespace point-in-time recovery** | same — and `-rpd` **must** be set, to a single PDB |
| **Database reset** | same plug-out/plug-in behaviour |

Before a complete recovery, **the DBA must determine which PDBs are actually affected by the media
errors** — that determination is what makes `-rpd` correct. To cut downtime for uninvolved PDBs, they can
be plugged into another container on the same host/Oracle home (BRRECOVER generates the XML for it), then
plugged back later — skip the automatic plug-in if you do. Flashback applies **only to the whole CDB**. **[V, MT]**

Configuration that must exist in `init<DBSID>.sap`: **[V, MT]**

```
active_pdbs = all_pdbs | (<PDB>[:<SAPSID>],…)   # PDBs BR*Tools may administer; inactive ones are skipped by backups
primary_pdb = any_pdb | <PDB_NAME>              # recommended: set it — global ops and logs land here
```

Backups and archive-log backups are **global** operations (a full backup covers the CDB and *all* PDBs),
so they are scheduled **once**, under the `<sapsid>adm` tied to the primary PDB. `ORA_PDB_NAME` (or the
`-pdb` option) selects the *working* PDB for local operations. PDB-scoped partial backups:
`brbackup -m all:<pdb_name>` — **counts as a partial, not a full, backup**. **[V, MT]**

Users: BRBACKUP/BRARCHIVE connect as **SYSBACKUP** (new in 12c); `sapdba_role.sql` must be run **once for
the CDB and once per PDB**. **[V, MT]**

## SAP ASE / Sybase (`syb`)

- **PITR prereq:** `trunc log on chkpt = false`; regular `dump transaction`.
- **Backup:** `dump database <DB> to '<file>'`; `dump transaction <DB> to '<file>'`.
- **Restore/recover** (via `isql`):
  ```sql
  load database <DB> from '<full_dump>'
  load transaction <DB> from '<log_dump>'       -- repeat in order; PIT: ... with until_time = '<ts>'
  online database <DB>                            -- bring it back online
  ```
- **Verify:** `sp_helpdb <DB>`; errorlog `<SERVER>.log`.

## IBM Db2 for LUW (`db6`)

- **PITR prereq:** `LOGARCHMETH1 = DISK:/…` (archive logging).
- **Backup:** `db2 backup database <SID> online to <path>`.
- **Restore/recover:**
  ```bash
  db2 restore database <SID> from <path> taken at <timestamp> [replace existing]
  db2 rollforward database <SID> to end of logs and complete        # or: to <ts> using local time
  ```
- **Verify:** `db2 connect to <SID>`; `db2 rollforward database <SID> query status`.

## SAP MaxDB / liveCache (`ada`)

- **PITR prereq:** log mode not `OVERWRITE`; automatic log backup on.
- **Backup:** `dbmcli … backup_start <template>` (data), `… backup_start <logtemplate>` (log).
- **Restore/recover:** put DB in **ADMIN**, then `dbmcli`:
  ```
  recover_start <template> DATA            # restore data backup
  recover_start <logtemplate> LOG          # then apply log(s); PIT via recovery-until options
  recover_replace / recover_config         # media/config-driven recovery
  ```
  (Database Studio has a Recovery Wizard for the same.) → then `db_online`.
- **Verify:** `db_state` → ONLINE; `KnlMsg`.

## Microsoft SQL Server (`mss`) — Windows only

- **PITR prereq:** database **FULL** recovery model + log backups.
- **Backup:** `BACKUP DATABASE [<SID>] TO DISK='…' WITH INIT`; `BACKUP LOG [<SID>] TO DISK='…'`.
- **Restore/recover:**
  ```sql
  RESTORE DATABASE [<SID>] FROM DISK='<full.bak>' WITH NORECOVERY, REPLACE;
  RESTORE LOG      [<SID>] FROM DISK='<log.trn>'  WITH RECOVERY [, STOPAT='<yyyy-mm-dd hh:mm:ss>'];
  ```
  (`NORECOVERY` on each restore until the last; `RECOVERY` on the final one to bring the DB online.)
- **Verify:** `SELECT state_desc FROM sys.databases WHERE name='<SID>';` ONLINE; `ERRORLOG`.

## Sources

Per DB, the admin/recovery guides cited in [../SKILL.md](../SKILL.md) §Sources ([B1]–[B6]) and the matching
files under sap-db-command-reference/references. In addition:

- **[MT]** **SAP Note 2333995** — *BR\*Tools support for Oracle multitenant database* (BC-DB-ORA-DBA, v16,
  2026-07-13). **[V]** Retrieved via the SAP Notes MCP during authoring. Source for the entire multitenant
  section: the BR\*Tools 7.40 patch gates (24 / 27 / 30), the Oracle 12.1.0.2 + Oracle Client 12c
  prerequisite, multitenant RAC not being released, the `-rpd|-recov_pdb` option and the fact that omitting
  it stops the **entire container database**, the per-recovery-type plug-out behaviour, `active_pdbs` /
  `primary_pdb`, `brbackup -m all:<pdb>` counting as a partial backup, SYSBACKUP, and `sapdba_role.sql` per
  PDB. Related: **2336881** (*Using Oracle Multitenant with SAP NetWeaver based Products*), **2335850**
  (transform an existing DB into a PDB), **134592** (`sapdba_role.sql`), **3654508** (BRSPACE RC 9999 with
  multitenant). https://me.sap.com/notes/2333995
- **SAP Note 1642148** — *FAQ: SAP HANA Database Backup & Recovery* (HAN-DB-BAC) — the HANA hub note. **[V]**
- **SAP Note 2165547** — *FAQ: … in an SAP HANA System Replication Landscape* (HAN-DB-BAC). **[V]**
- **SAP Note 2101244** — *FAQ: SAP HANA Multitenant Database Containers (MDC)* (HAN-DB). **[V]**
- Version/support matrices and the PAM procedure: [version-support-matrix.md](version-support-matrix.md).
- Encryption and key management: [backup-encryption-keys.md](backup-encryption-keys.md).
