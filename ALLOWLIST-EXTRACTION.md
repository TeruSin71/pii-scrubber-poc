# Allowlist source tables — extraction spec

Purpose: build `allowlist.txt`, the list of SAP technical tokens the scrubber
must **never** treat as PII. Without it, transaction codes, table names and
field names are redacted as account numbers or user IDs, destroying the
technical meaning the KB depends on.

**None of these tables contain personal data.** They are Customizing and
Repository (DDIC) tables — configuration metadata, not business or master
data. Extracting them is not a compliance event and needs no scrubbing.

Export via SE16N → one column → text/CSV. Deduplicate. One token per line.

---

## Tier 1 — required (fixes over-detections we measured)

| Table | Field | Contains | Status |
|---|---|---|---|
| `TSTC` | `TCODE` | Transaction codes — VA01, ME23N, VF04 | **Have it** |
| `DD02L` | `TABNAME` | Table names — VBAK, LIKP, MARA, KNA1 | **Have it** |
| ~~`DD03L`~~ | ~~`FIELDNAME`~~ | Field names — KUNNR, LIFNR, VBELN | **Skip — too large. Use `mine_allowlist.py` instead** |

**Filter for `DD02L`:** `AS4LOCAL = 'A'` and `TABCLASS = 'TRANSP'` (active
transparent tables) keeps the volume sane.

### Why DD03L is dropped

`DD03L` holds every field of every table — millions of rows, ~200k distinct
field names. Impractical to export, and unnecessary: your tickets only ever
mention a few hundred distinct field names.

`mine_allowlist.py` gets them from your own corpus instead:

```bash
python mine_allowlist.py ./corpus --out allowlist-candidates.txt
```

It runs the scrubber over a folder of ticket/spec text, collects every span it
*would* redact that has technical shape (all-uppercase, no spaces), and ranks
by frequency. Smaller, self-calibrating, and it covers exactly the vocabulary
you use — including field names, T-codes and message IDs in one pass.

**Review is mandatory, not advisory.** On a test corpus the miner proposed
`VBAK`, `KUNNR`, `WERKS`, `EKKO`, `BSEG` — correct — but also `BJOHNSON`,
`KMUELLER`, `MTANAKA`, which are **real user IDs**. Appending the candidates
file unreviewed would allowlist PII and create a leak. A human deletes the
personal entries before anything is merged into `allowlist.txt`.

Run the miner on real ticket text if you like — it executes locally, inside
your boundary, and writes only the candidate tokens. Do not commit the corpus
or an unreviewed candidates file.

---

## Custom objects — handled by rule, no extract needed

`Z*`, `Y*` and registered `/NAMESPACE/` prefixes are reserved by SAP for
customer development, so a token in that shape is *provably* a technical
object. This is implemented as a deterministic rule in `app.py`
(`is_custom_sap_object`) rather than a list — which means **no extract, no
maintenance, and it already covers Z-objects that do not exist yet.**

Verified against: `ZSD_REBATE_CALC`, `ZMM_INV_APPROVAL`, `ZVA01`, `Z001`,
`ZVBAK`, `YSD_CUSTOM`, `/SOVOSD/RFYTXDISPLAY`, `/IWFND/ERROR_LOG`.

**The surname trap, and how the rule avoids it.** Zhang, Young, Yamamoto and
Zimmermann all start with Z or Y. A bare prefix rule would stop redacting
those people. The discriminator is shape, not prefix:

| Shape | Example | Treated as |
|---|---|---|
| Contains `_` or a digit | `ZSD_REBATE_CALC`, `ZVA01` | Technical — unambiguous |
| Registered namespace | `/SOVOSD/RFYTXDISPLAY` | Technical — unambiguous |
| Title case | `Zhang`, `Young` | **Person** — rule requires all-uppercase |
| Pure uppercase letters | `ZVBAK` vs `ZHANG` | Technical, **except** a guard list of common all-caps Z/Y surnames |

Toggle with `CUSTOM_OBJECT_RULE=false` if it ever needs disabling.

**Consequence: `TADIR` is now optional.** The rule covers custom objects
better than an extract would. Pull `TADIR` only if you also want
SAP-*standard* object names allowlisted.

## Tier 2 — high value (dense in tickets and FSDs)

| Table | Field | Contains | Why it matters |
|---|---|---|---|
| `TFDIR` | `FUNCNAME` | Function modules and BAPIs | `BAPI_SALESORDER_CREATEFROMDAT2` — uppercase + underscores |
| `T100` | `ARBGB` | Message classes | Error references like `VF 052` |
| `TADIR` *(optional)* | `OBJ_NAME` | SAP-standard repository objects | Custom `Z*`/`Y*` already covered by the rule above |

---

## Tier 3 — domain codes (nice to have)

| Table | Field | Contains |
|---|---|---|
| `T685` | `KSCHL` | Condition types — PR00, MWST, K007 |
| `TVAK` | `AUART` | Sales document types |
| `TVFK` | `FKART` | Billing document types |
| `T161` | `BSART` | Purchasing document types |
| `TEDS1` | `STATUS` | IDoc status codes |
| `EDBAS` | `IDOCTYP` | IDoc basic types — ORDERS05, INVOIC02 |

---

## Rules when assembling the file

1. **Case is preserved exactly.** The allowlist matches case-sensitively on
   purpose. Several SAP names are also surnames — `MARA`, `LIPS`, `BRAUN`,
   `KLEIN`. Uppercase `MARA` is allowlisted; the person `Mara` is still
   redacted. Do not upper- or lower-case the export.
2. **Drop tokens shorter than 3 characters.** Two-character codes (`OR`,
   `TA`, `AG`) are too collision-prone to be worth the recall risk.
3. **Deduplicate** — the same token appears across several tables.
4. **Comments** — lines starting with `#` are ignored, so you can annotate
   which table a block came from.
5. **No PII in this file, ever.** It is technical vocabulary only.

---

## Explicitly NOT recommended: `USR02`

A gazetteer of real user IDs from `USR02` would sharply improve `USER_ID`
recall — the scrubber would recognise every genuine employee ID by lookup
rather than by pattern.

It is still the wrong call by default: user IDs are personal data, so the
list would itself be a PII asset that has to be secured, access-controlled,
retained and deleted under the same policy as the data you are protecting.
You would be creating a new compliance obligation to improve a control.

If it is ever considered, it needs a governance decision and its own
handling rules — not an engineering shortcut.

---

## Format

```
# TSTC / TCODE
VA01
VA02
ME23N
VF04
# DD02L / TABNAME
VBAK
VBAP
LIKP
MARA
# DD03L / FIELDNAME
KUNNR
LIFNR
VBELN
```

Drop the finished file in at `allowlist.txt` (repo root), then re-run
`/v1/selftest`. Expected: recall stays at **100.0**, `over_detections` falls
below 6.
