---
name: sap-db-command-reference
description: >-
  Database-specific operational commands for SAP systems — start, stop, connect, status and
  basic backup for the SAP-supported databases (SAP HANA, Oracle, SAP ASE/Sybase, IBM Db2,
  SAP MaxDB/liveCache, Microsoft SQL Server), with Linux / Windows / AIX variants. Use whenever
  a Basis/operations task needs the DB layer: "stop the database", "connect to HANA/ASE/Oracle",
  "is the DB up", "restart the database before/after the SAP instances", or when sap-system-lifecycle
  hands off DB start/stop. Every command is cited to help.sap.com / the official Administration Guide.
---

# SAP DB Command Reference

`sapcontrol`/`stopsap` stop the **SAP instances but not the database** — the official SAPControl
documentation states: *"The database is not stopped by these commands. You have to stop the
database using database-specific tools or commands."* This skill is that database-specific layer.

## How to use

1. **Identify the DB.** Determine which database the SID runs on before doing anything:
   - `cat /usr/sap/<SID>/SYS/profile/<SID>_*` → look at `dbms/type` / `dbs/<db>/…`, or
   - environment of `<sid>adm`: `echo $dbms_type` (values: `hdb`, `ora`, `syb`, `db6`, `ada`, `mss`).
2. **Open the matching reference file** below and follow its Identify → Preview → Execute → Verify flow.
3. **Respect the guardrail contract** (see repo README): confirm SID/host/OS, classify PRD, preview
   before any `shutdown`/stop, execute one step at a time via the user-supplied shell/SSH MCP, verify after.

## Database reference files

| DB | `dbms_type` | Reference | Status |
|----|-------------|-----------|--------|
| SAP ASE (Sybase) | `syb` | [references/sap-ase.md](references/sap-ase.md) | ✅ complete |
| SAP HANA | `hdb` | [references/sap-hana.md](references/sap-hana.md) | ✅ complete |
| Oracle Database | `ora` | [references/oracle.md](references/oracle.md) | ✅ complete |
| IBM Db2 (LUW) | `db6` | [references/ibm-db2.md](references/ibm-db2.md) | ✅ complete |
| SAP MaxDB / liveCache | `ada` | [references/sap-maxdb.md](references/sap-maxdb.md) | ✅ complete |
| Microsoft SQL Server | `mss` | [references/sql-server.md](references/sql-server.md) | ✅ complete |

## Cross-references

- **Start/stop ordering** (DB relative to ASCS/ERS/PAS/AAS) lives in `sap-system-lifecycle`.
- **DB log/trace cleanup** (backup catalog, transaction logs, DB traces) lives in `sap-housekeeping`;
  this file covers only the operational start/stop/connect/status commands.

## Sources

See the Sources section at the end of each reference file for the exact help.sap.com pages and
SAP Notes used, and which commands were verified against the live page.
