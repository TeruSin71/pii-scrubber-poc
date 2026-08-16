# Batch-path readability — union vs presidio, AFTER overlap-aware suppression

**Task 4 deliverable of `GATE0-overlap-suppression-plan.md`, 2026-08-16.** Replaces the
bake-off's ten-sample file. **All 21 zero-PII controls**, which is the metric the
batch path is blocked on — an extra redaction here has a real cost, because the KB
text must stay readable. On the live path it costs nothing.

⛔ **Controls damaged: `both` 7 of 21 (33%) · `presidio` 2 of 21 (9.5%).** Before this
change the union damaged 8. **7/21 is never to be reported without 2/21 beside it**
(Gate 0 Q9): the change is a PASS for the plan and a CONTINUED-BLOCK for batch.

Measured on `pii-scrubber:gliner-cand@sha256:d96edef4…c764912` with the changed
`app.py` and `glossary.txt` mounted over `/app`. `GLINER_THRESHOLD` frozen at 0.4.

---

## Still damaged — 7 of 21

### `TKT-0009` — samples.json

**original**

> Batch determination failing for material in outbound delivery. This one is purely technical - class 023 characteristic mismatch. No customer or contact details involved.

**presidio** — unchanged

**both (union)**

> Batch determination failing for material in outbound delivery. This one is purely technical - class 023 characteristic mismatch. No <PERSON> or contact details involved.

over-redacted by union: `customer` (gliner/PERSON)

---

### `HO-015` — holdout_samples.json

**original**

> PGI failing on plant 4000 deliveries since the morning batch window. No customer or personal data in this one - purely a movement type 601 configuration question.

**presidio** — unchanged

**both (union)**

> PGI failing on <ORG_NAME> <CUSTOMER_NO> deliveries since the morning batch window. No <PERSON> or personal data in this one - purely a movement type 601 configuration question.

over-redacted by union: `plant` (gliner/ORG_NAME), `4000` (gliner/CUSTOMER_NO), `customer` (gliner/PERSON)

---

### `HO-021` — holdout_samples.json

**original**

> When VL02N refuses to post goods issue with 'deficit of stock', first check MMBE for the storage location split, then MB52 for blocked stock. This is config knowledge, no customer specifics required.

**presidio**

> When VL02N refuses to post goods issue with 'deficit of stock', first check MMBE for the storage location split, then MB52 for blocked stock. This is <PERSON>, no customer specifics required.

**both (union)**

> When VL02N refuses to post goods issue with 'deficit of stock', first check MMBE for the storage location split, then MB52 for blocked stock. This is <PERSON>, no customer specifics required.

over-redacted by union: `config knowledge` (presidio/PERSON)

---

### `V2-064` — eval_samples_v2.json

**original**

> Movement type 601 posts against storage location 0001 for plant 4000, and there are 40 open transfer orders on the queue.

**presidio** — unchanged

**both (union)**

> Movement type 601 posts against <ADDRESS> for <ORG_NAME>, and there are 40 open transfer orders on the queue.

over-redacted by union: `storage location 0001` (gliner/ADDRESS), `plant 4000` (gliner/ORG_NAME)

---

### `V3-033` — holdout_v3.json

**original**

> Invoice blocked again, 3 Way match failed against the goods receipt for plant 4100. Tolerance key is fine, no customer data here.

**presidio** — unchanged

**both (union)**

> Invoice blocked again, 3 Way match failed against the goods receipt for <ORG_NAME>. Tolerance key is fine, no customer data here.

over-redacted by union: `plant 4100` (gliner/ORG_NAME)

---

### `V3-034` — holdout_v3.json

**original**

> Postings to GL account 400000 doubled after the FX rate load on Tuesday. TCURR looks fine, config-only question.

**presidio**

> Postings to GL account <CUSTOMER_NO> doubled after the FX rate load on Tuesday. TCURR looks fine, config-only question.

**both (union)**

> Postings to GL account <CUSTOMER_NO> doubled after the FX rate load on Tuesday. TCURR looks fine, config-only question.

over-redacted by union: `400000` (presidio/CUSTOMER_NO)

---

### `V3-040` — holdout_v3.json

**original**

> VF04 collective run picks zero items when the billing block sits at header level. See the OSS note, config only.

**presidio** — unchanged

**both (union)**

> <ORG_NAME> picks zero items when the billing block sits at <ADDRESS>. See the OSS note, config only.

over-redacted by union: `VF04 collective run` (gliner/ORG_NAME), `header level` (gliner/ADDRESS)

---

## Clean — 14 of 21

### `EXP-0001` — samples.json

**original**

> Known issue: when IDoc is in status 51 with 'ship-to party not found', check the customer-material info record (VD51N) and the partner function assignment in the sold-to master. Usually the ship-to (SH) partner is missing on the customer account group. No customer data needed to resolve.

**presidio** — unchanged

**both (union)** — unchanged

---

### `HO-020` — holdout_samples.json

**original**

> Intercompany billing IDoc failed price determination between company codes 4000 and 4100. Purely config - condition ZIC1 missing in the procedure. Nothing sensitive here.

**presidio** — unchanged

**both (union)** — unchanged

---

### `HO-029` — holdout_samples.json

**original**

> FSD ZCO_ALLOC_CYCLE: monthly assessment cycle automation. Pure config documentation - cycle names, segment logic, sender/receiver rules. Contains no personal or customer data by design.

**presidio** — unchanged

**both (union)** — unchanged

✅ **repaired by overlap-aware suppression:** `FSD ZCO_ALLOC_CYCLE` (gliner/ORG_NAME)

---

### `HO-039` — holdout_samples.json

**original**

> Exchange rate type M not updating from the feed since Tuesday. TCURR last entry 12.08. Basis checking the RFC destination. Config-only issue, no personal data.

**presidio** — unchanged

**both (union)** — unchanged

---

### `V2-060` — eval_samples_v2.json

**original**

> Invoice blocked, 3 Way match failed against the goods receipt and the tolerance key is too tight.

**presidio** — unchanged

**both (union)** — unchanged

---

### `V2-061` — eval_samples_v2.json

**original**

> Scan 20 Pallet Rack Row before picking, then check 12 Handling Unit Place assignments in the monitor.

**presidio** — unchanged

**both (union)** — unchanged

---

### `V2-062` — eval_samples_v2.json

**original**

> VF04 collective run fails when NAST has no entry, check MARA and VBAK before raising it with Basis.

**presidio** — unchanged

**both (union)** — unchanged

---

### `V2-063` — eval_samples_v2.json

**original**

> ZSD_REBATE_CALC dumps in the update task and /SOVOSD/RFYTXDISPLAY has the same short dump signature.

**presidio** — unchanged

**both (union)** — unchanged

---

### `V2-065` — eval_samples_v2.json

**original**

> Escalated to Level 3 support and routed to Basis for the ST22 dump, no customer specifics required.

**presidio** — unchanged

**both (union)** — unchanged

---

### `V3-035` — holdout_v3.json

**original**

> Driver could not get dock access yesterday and the Rise in failed deliveries since the WM cutover needs a root cause.

**presidio** — unchanged

**both (union)** — unchanged

---

### `V3-036` — holdout_v3.json

**original**

> Close the stuck transfer orders in LT23 and check MB52 for blocked stock before month end. Level 3 support not required.

**presidio** — unchanged

**both (union)** — unchanged

---

### `V3-037` — holdout_v3.json

**original**

> ST22 shows a TIME_OUT dump in program ZSD_REBATE_CALC, movement type 601 unaffected. Pure configuration question.

**presidio** — unchanged

**both (union)** — unchanged

---

### `V3-038` — holdout_v3.json

**original**

> MARA and MAKT are out of sync after the MDG load, NAST entries missing for output type ZBA0. Basis are aware.

**presidio** — unchanged

**both (union)** — unchanged

---

### `V3-039` — holdout_v3.json

**original**

> ATP check and PGI both fine after the patch, MRP run completes. RFC destination re-tested, no personal data in this one.

**presidio** — unchanged

**both (union)** — unchanged

---
