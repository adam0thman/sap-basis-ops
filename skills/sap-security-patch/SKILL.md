---
name: sap-security-patch
description: >-
  Run the monthly SAP Security Patch Day workflow — retrieve the current month's SAP Security Notes from
  the SAP Support Portal (SAP Security Patch Day, second Tuesday), narrow them to the subset that applies
  to THIS system (installed software-component versions + kernel), compare against what's already applied
  (System Recommendations / SAP Focused Run / RSECNOTE), prioritize by CVSS/HotNews, and implement via
  SNOTE. Use for "check this month's SAP security notes", "which security notes apply to <SID>", "SAP
  patch day", "HotNews", "compare released notes vs applied". Browses the SAP Security Notes page. Cited
  to help.sap.com / SAP Support Portal.
---

# SAP Security Patch Day

SAP publishes Security Notes on the **second Tuesday of each month (~09:00 CET)**. This skill turns "the
month's notes" into "the prioritized subset that applies to *your* system and isn't applied yet." [P1]

> **Guardrail — patching is change management, not a shell command.**
> - **Never apply notes directly to PRD.** Path is **DEV → QAS → PRD** via the transport route.
> - **HotNews first:** CVSS **9.0–10.0** notes within your emergency-patch SLA; then High (7.0–8.9). [P2]
> - Take a **backup/snapshot** and check each note's **prerequisites, manual pre/post steps, and side
>   effects** before implementing (SNOTE shows dependencies).
> - This skill **produces the analysis and plan**; it does not auto-apply. Implementation is a human,
>   change-controlled action.

---

## 1. Cadence & priority model

- **When:** 2nd Tuesday monthly. Track it as a recurring task. [P1]
- **Priority (CVSS v3):** **HotNews** 9.0–10.0 · **High** 7.0–8.9 · **Medium** 4.0–6.9 · **Low** <4.0.
  HotNews = "very high" priority, patch fastest. [P2]
- **Note types:** ABAP **correction** notes (→ SNOTE), **kernel/SP** notes (→ SUM/SPAM, not SNOTE),
  **manual/config** notes (parameter or config change). Know which before planning (§5).

---

## 2. Retrieve the month's Security Notes (browse)

The authoritative source is the **SAP Support Portal → "SAP Security Notes"** (ONE Support Launchpad /
SAP for Me). It is **behind S-user authentication**, so retrieval needs an authenticated session: [P1]

- **Browser (authenticated):** open the SAP Security Notes / Patch Day page and read the current month's
  list — number, title, component, **CVSS/priority**, released-on. (Same authenticated-browser approach
  used elsewhere in this plugin for `me.sap.com`.)
  - SAP Security Patch Day: `https://support.sap.com/en/my-support/knowledge-base/security-notes-news.html`
  - Monthly list / filter: the **SAP Security Notes** app on `me.sap.com`.
- **SAP Notes MCP (once its content path is fixed):** the reverse-engineered `snogwsmynotes` search
  supports a document-type filter — filter to security notes and the month, then `fetch` each note's
  Header (CVSS/priority/component) + LongText. See the plugin's SAP Notes MCP notes.

Capture for each note: **Number, Title, Component, CVSS, Priority, affected software-component versions.**

---

## 3. Narrow to YOUR applicable subset

A note only applies if the system **has the affected software component at an affected version** (and, for
kernel notes, the affected kernel). Build the system's inventory, then intersect:

- **Installed component versions:** `System → Status → Component information` in SAP GUI, or **SM51** →
  release info, or table **`CVERS`** (e.g. `SAP_BASIS 758`, `SAP_ABA`, `SAP_UI`, `S4CORE`, …).
- **Kernel version:** `disp+work -version` (OS shell) or SM51 → kernel info.
- **Intersect:** keep only notes whose *affected component + version range* overlaps the system's. Drop
  notes for components you don't have installed. This intersection **is the "applicable subset."**

> Doing this by hand is error-prone at scale — **System Recommendations (§4) computes this subset
> automatically** from the managed system's real note/patch status. Use it as the source of truth; use the
> manual intersect above when SysRec/FRUN isn't available.

---

## 4. Compare against what's already applied

| Tool | What it does | Where |
|------|--------------|-------|
| **System Recommendations (SysRec)** | weekly, compares SAP's released notes against a **managed system's actual note status** and lists the ones to apply — including security notes each Patch Day | SAP Solution Manager (`/nSYSTEM_RECOMMENDATIONS` / SM work center) [P3] |
| **SAP Focused Run — CSA** | Configuration & Security Analytics; superior at-scale security-note validation across a landscape | SAP Focused Run [P4] |
| **`RSECNOTE`** | older report listing security-relevant notes and their implementation status | SE38 / directly on the system [P5] |
| **SNOTE** | per-note implementation **status** (New / Can be implemented / Completely implemented / Obsolete) | Note Assistant on the system [P5] |

The output you want: **notes in the applicable subset (§3) whose status is NOT "Completely implemented."**
Those are the action items.

---

## 5. Prioritize & plan

1. **HotNews (CVSS 9–10)** → emergency change, fastest SLA.
2. **High (7–8.9)** → next scheduled window.
3. Group by **implementation tool**: SNOTE (correction notes) vs **kernel/SP** (SUM/SPAM, need downtime)
   vs **manual/config**.
4. Note **prerequisites & sequence** (SNOTE resolves dependency notes; some require an SP first).
5. Record CVSS, affected component, and the change reference for each.

---

## 6. Implement & verify (change-controlled)

- **SNOTE** (Note Assistant): download + implement in **DEV**, run the automatic activities, resolve
  prerequisites, test → **transport to QAS → PRD**. [P5]
- **Kernel / SP notes:** apply the patched kernel or Support Package via **SUM / SPAM/SAINT** in a
  maintenance window (OS-specific kernel per platform — Linux/Windows/AIX download from the SAP Software
  Center). Cross-ref a future `sap-kernel-patch` skill.
- **Manual/config notes:** apply the documented parameter/config change; some need a restart
  ([sap-system-lifecycle](../sap-system-lifecycle/SKILL.md)).
- **Verify:** re-run **System Recommendations / RSECNOTE** → the note now shows implemented; confirm no new
  ST22 dumps ([sap-health-triage](../sap-health-triage/SKILL.md)).

---

## OS note

The analysis (portal, SysRec, SNOTE) is **OS-independent**. Only **kernel** security patches are
OS-specific — download the correct kernel for the system's platform (Linux/Windows/AIX) from the SAP
Software Center.

## Cross-references

- **Restart after config/kernel notes:** [sap-system-lifecycle](../sap-system-lifecycle/SKILL.md).
- **Post-patch health / new dumps:** [sap-health-triage](../sap-health-triage/SKILL.md).
- **SAP Notes MCP** (retrieval): see the plugin's SAP Notes MCP notes (content path fix pending).

## Sources

- **[P1]** *SAP Security Patch Day* — SAP Support Portal (2nd Tuesday monthly; the **SAP Security Notes**
  app). https://support.sap.com/en/my-support/knowledge-base/security-notes-news.html
- **[P2]** SAP Note priority / **CVSS v3** model (HotNews 9.0–10.0, High 7.0–8.9, Medium 4.0–6.9, Low <4.0)
  — SAP security notes classification.
- **[P3]** *System Recommendations* — SAP Solution Manager; weekly comparison of released notes vs a
  managed system's note status, incl. Patch Day security notes. help.sap.com (Solution Manager).
- **[P4]** *Configuration & Security Analytics (CSA)* — SAP Focused Run, landscape-scale security-note
  validation. help.sap.com (Focused Run).
- **[P5]** **SNOTE** (Note Assistant) + **`RSECNOTE`** — implement/track security notes on the system.
  help.sap.com (Note Assistant).

**To confirm/deepen** (once the SAP Notes session can read content): the current SAP Security Notes FAQ
note and the System Recommendations setup guide for your Solution Manager / Focused Run release.
