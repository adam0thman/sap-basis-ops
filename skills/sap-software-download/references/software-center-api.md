# SAP for Me Software Center — service reference

Everything here was **verified live against the service during authoring**, signed in as an S-user with an
active download profile. Marked **[V]**. Where behaviour may vary by entitlement, that is stated.

Service root:

```
https://launchpad.support.sap.com/services/odata/svt/swdcuisrv/
```

OData v2, namespace `SVT_SWDC_UI_SRV`. `$metadata` is reachable unauthenticated-ish (it redirects to SSO if
you have no session) and is the fastest way to re-derive this file if SAP changes the model. **[V]**

> **Origin matters.** `me.sap.com/softwarecenter` embeds `launchpad.support.sap.com` in an **iframe**.
> Scripts, network logs and accessibility trees scoped to the top frame see the shell only. Issue these
> calls from a tab whose top document is on `launchpad.support.sap.com` so they are same-origin and the
> session cookie is sent. **[V]**

---

## Entity sets

Twenty-one sets exist. The ones that matter for operations: **[V]**

| Entity set | Use |
|---|---|
| `SearchResultSet` | Free-text search — the main entry point |
| `ObjectSet` | Full metadata for one downloadable object (by key) |
| `ObjectAttributeSet` | Attributes incl. `EQUIVALENT` cross-release mapping |
| `ObjectConditionSet` | Import conditions SPAM enforces |
| `ObjectPropertySet` | Additional properties |
| `DownloadItemSet` | Download items |
| `DownloadBasketItemSet` | Current Download Basket contents |
| `DownloadAuthProfileSet` | Your download authorization |
| `HierarchyItemSet` | The browse tree (Installations & Upgrades / by category) |
| `ObjectListItemSet` | Object lists within a node |
| `DownloadContentSet` | Content info |
| `SAPNotes`, `SideEffects` | Notes / side effects attached to an object |
| `SourcePackageSet` | Source packages |
| `ExportBasketItemSet`, `ExportActionLogSet` | Basket export + action log |
| `DownloadBasketITCMRefreshSet` | Basket refresh |
| `SAPNotesPriorityFilter`, `SAPNotesCategoryFilter`, `SAPNotesCountryFilter`, `SAPNotesComponentFilter` | Note filter value help |

Corresponding entity types drop the `Set` suffix and singularise (`SearchResult`, `Object`, `DownloadItem`, …).

---

## Search

```
GET /services/odata/svt/swdcuisrv/SearchResultSet
      ?SEARCH_STRING=<what you'd type in the UI>
      &SEARCH_MAX_RESULT=200
      &RESULT_PER_PAGE=200
      &$format=json
Accept: application/json
```

`$format=json` **works on this service** — unlike the SAP Notes `CorrInsSet` service, where it silently
returns zero rows. **[V]**

`SearchResult` fields: **[V]**

| Field | Notes |
|---|---|
| `Id` | Result index (`000004`) — positional, not stable |
| `Title` | **The filename**, e.g. `SAPK-74035INSTPI` |
| `Description` | Human text, e.g. `ST-PI 740: SP 0035` |
| `Infotype` | `Support Package`, `Installation Software Component`, `Maintenance Software Component`, … |
| `Fastkey` | **The 19-digit object key** — the identifier that matters |
| `DownloadDirectLink` | `https://softwaredownloads.sap.com/file/<Fastkey>` |
| `ContentInfoLink` | `https://me.sap.com/softwarecenter/object/<Fastkey>` |
| `ApplicationLink`, `PackApplicationLink`, `InfoObjectLink`, `SideEffectsLink`, `DependenciesLink` | Often empty |
| `SubtreeEvent`, `SearchResultDescr` | UI plumbing |

**Result sets mix families.** `SEARCH_STRING=ST-PI 740` returned 60 rows: 58 `Support Package`, 1
`Installation Software Component`, 1 `Maintenance Software Component`. Of the 58, only **35** matched the
mainline `^SAPK-740\d+INSTPI$` pattern. Always filter on the filename pattern for the delivery you want. **[V]**

---

## Object metadata

```
GET /services/odata/svt/swdcuisrv/ObjectSet('<ObjectKey>')?$format=json
```

Live response for ST-PI 740 SP 0035, trimmed: **[V]**

```json
{
  "ObjectKey": "0010000000343432026",
  "Title": "ST-PI 740: SP 0035",
  "Status": "AVAILABLE",
  "StatusDescr": "The File is available to download",
  "FileType": "SAR",
  "FileSize": "11645 ",
  "FileName": "SAPK-74035INSTPI",
  "FileVersion": "002",
  "Checksum": "f414bf416b70649d43d5615db004688a80a4427e04a36f937ee9afa8e3cd3636",
  "PatchType": "CSP",
  "EpsFileName": "I710020751258_0179285.PAT",
  "PackageLevel": "0035",
  "ComponentRelease": "ST-PI 740",
  "MinimalBasisRelease": "740",
  "RequiredSpamVersion": "0081",
  "IsAbapObject": true,
  "CreatedOn": "/Date(1779350832000)/",
  "ChangedOn": "/Date(1782108443000)/"
}
```

Field notes:

- **`FileSize` is in KB and carries a trailing space** — trim before arithmetic. **[V]**
- **`Checksum` is SHA-256**, lowercase hex. **[V]**
- **`RequiredSpamVersion`** — take the **maximum across the whole queue**, not the last package.
- **`EpsFileName`** — the `.PAT` produced by `SAPCAR -xvf`; this is the name SPAM lists, not `FileName`.
- **`IsSupportPackage` was `false`** on a component SP whose `PatchType` is `CSP`. Do **not** branch on this
  flag — use `Infotype` from the search result or `PatchType`. **[V]**
- Dates are OData v2 `/Date(epoch_ms)/`.

### Navigation properties

```
GET /services/odata/svt/swdcuisrv/ObjectSet('<key>')/ObjectAttributes?$format=json
GET /services/odata/svt/swdcuisrv/ObjectSet('<key>')/ObjectConditions?$format=json
```

- **`ObjectAttributes`** — returned 3 rows for SP35, including an `EQUIVALENT` attribute whose value encoded
  `ST-PI,758:SAPK-75802INSTPI,0002` — i.e. **the same correction on ST-PI 758 SP02**. Use this to keep a
  mixed-release landscape consistent. Key shape:
  `ObjectAttributeSet(ObjectKey='…',AttributeId='EQUIVALENT',AttributeValue='…')` **[V]**
- **`ObjectConditions`** — returned 1 row keyed
  `ObjectConditionSet(ObjectKey='…',ConditionSet='01',ComponentCategory='01',SoftwareComponent='ST-PI',AlternativeSet='00',Release='740',PackageCategory='01')`.
  These are the conditions SPAM evaluates when building a queue. **[V]**

> `DownloadItemSet?$filter=Fastkey eq '<key>'` returned **200 with an empty result set** — `DownloadItemSet`
> is not a substitute for `ObjectSet`. Use `ObjectSet` for metadata. **[V]**

---

## Authorization and basket

```
GET /services/odata/svt/swdcuisrv/DownloadAuthProfileSet?$format=json
GET /services/odata/svt/swdcuisrv/DownloadBasketItemSet?$format=json
```

`DownloadAuthProfileSet` returns your S-user with `Active: true` when downloads are permitted — a cheap
precheck that separates "not entitled" from "technically broken". `DownloadBasketItemSet` returns the
basket contents (empty array when the basket is empty). **[V]**

---

## Download

| | |
|---|---|
| Direct file | `https://softwaredownloads.sap.com/file/<ObjectKey>` |
| Object page | `https://me.sap.com/softwarecenter/object/<ObjectKey>` |

The direct link **redirects into SAML SSO at `accounts.sap.com/saml2/idp/sso`**. Interactively this
completes (with an account picker if the e-mail maps to several S-users) and the `.SAR` downloads. Under
browser automation it **stalls on the IdP spinner and does not complete** — reproduced twice, on a session
whose `DownloadAuthProfileSet` showed `Active: true`, so this is the SSO flow and **not** an entitlement
problem. **[V]**

Treat the direct link as **navigation for a human**. For multi-file sets use the **Download Basket** and the
**SAP Download Manager**.

> This mirrors the TCI package behaviour documented in
> [sap-security-patch](../../sap-security-patch/SKILL.md): SAP's download endpoints are consistently
> SSO-gated, so URLs are for handing to a person, not for fetching programmatically.

---

## Re-deriving this file

If SAP changes the model, re-extract from a `launchpad.support.sap.com` tab:

```js
// entity sets + types
const t = await (await fetch('/services/odata/svt/swdcuisrv/$metadata')).text();
[...t.matchAll(/EntitySet Name="([A-Za-z0-9_]+)"/g)].map(m => m[1]);

// fields of one entity type
const seg = t.slice(t.indexOf('EntityType Name="Object"'), t.indexOf('</EntityType>', t.indexOf('EntityType Name="Object"')));
[...seg.matchAll(/Property Name="([A-Za-z0-9_]+)" Type="Edm\.([A-Za-z]+)"/g)].map(m => m[1] + ':' + m[2]);
```
