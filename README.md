# PII Scrubber — POC (SAP Incident KB)

Local, in-boundary PII scrubbing for the SAP incident knowledge base.
Deploys to **SAP AI Core** (bring-your-own-model). No Cloud Foundry, no
Generative AI Hub, no third-party LLM ever sees raw data.

## Verified result

**Quote the holdout number, not the self-test number.**

### Holdout — 40 unseen samples, 111 planted values

The honest figure. These samples were never used to tune the recognizers, and
scoring is end to end: a value counts as caught only if it no longer appears
in the scrubbed output.

| Metric | Value |
|---|---|
| **Holdout recall** | **96.4%** (107 / 111) |
| Leaks | 4 — see "Known gaps" |
| Measured on | deployed image `1.1.0`, SAP AI Core |

Per type: ADDRESS, EMAIL, IBAN, IP_ADDRESS, ORG_NAME, PHONE, USER_ID and
VENDOR_NO all **100%**; PERSON 89.3% (25/28); CUSTOMER_NO 85.7% (6/7).

> Superseded: **93.7%** (104/111) was the pre-fix baseline, measured before
> the street-address recognizer existed. It is kept here only as the
> before-figure — do not quote it as current.

### Self-test — 13 tuned-against samples

| Metric | Value |
|---|---|
| Recall | 100% (45/45) |
| Misses | 0 |
| Over-detections | 6 (safe-but-noisy) |
| Engine | `presidio` + custom SAP recognizers |

> This is a **regression baseline, not a result.** The recognizers were tuned
> against these 13 samples, so 100% is close to guaranteed and says nothing
> about production. Its job is to prove packaging and deployment changed
> nothing. **Never present it to management as the expected production
> figure** — quote the holdout instead.

### Known gaps

Four values leak on the holdout, in three classes, none yet addressed:

| Class | Example | Note |
|---|---|---|
| All-caps / bare surname | `ZHANG`, `Young` | person-context promotion |
| Full name missed by NER | `Mere Tuhoe` | a plain spaCy miss, not a context problem |
| Unpadded customer number | `1045567` | keyed without leading zeros |

Address coverage is **NZ/AU forms only**. German-style
`Hauptstrasse 12, 80331 Munich` (name before number) is not matched by the
recognizer and relies on incidental locality detection. A bare ambiguous-type
address with no suburb (`44 Bellbird Rise`) is also missed — see
`recognizers.py` for why that trade was made.

## Quick start

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn app:app --port 8080

curl localhost:8080/v1/selftest
curl -X POST localhost:8080/v1/scrub \
  -H 'Content-Type: application/json' \
  -d '{"text":"Customer 0001045567, contact Aroha Ngata aroha.ngata@x.co.nz","mode":"batch"}'
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Instant readiness (does not load models) |
| GET | `/info` | Engine + model configuration |
| POST | `/v1/scrub` | Scrub one text. `mode`: `batch` \| `live` |
| POST | `/v1/models/pii-scrubber:predict` | KServe-style wrapper |
| GET | `/v1/selftest` | Run labelled samples, return recall per PII type |

**Modes.** `batch` replaces with `<TYPE>` (build path, into the KB corpus).
`live` replaces with `<TYPE_n>` and returns a `token_map` so the caller
re-maps **inside the boundary** after triage.

## Detectors

Presidio's built-ins (PERSON, LOCATION, DATE_TIME via spaCy `en_core_web_sm`,
plus IBAN and phone) with `UrlRecognizer` **removed** — it fetched the public
suffix list from `publicsuffix.org` at runtime, an outbound call from inside
the compliance boundary.

On top of those, nine deterministic SAP recognizers in `recognizers.py`:

| Recognizer | Catches |
|---|---|
| `sap_customer_number` | 10-digit customer numbers, zero-padded |
| `sap_vendor_number` | 10-digit vendor numbers, zero-padded |
| `sap_user_id` | uppercase user IDs, service accounts (`svc_*`) |
| `sap_document_ref` | change requests, transport IDs |
| `permissive_email` | addresses on internal/unusual TLDs the strict one under-scores |
| `company_suffix` | organisations by legal suffix (GmbH, Ltd, Pty …) |
| **`street_address`** | **NZ/AU street addresses, `PO Box`, `Private Bag`** |
| `phone_extension` | `ext 4471`, `x4471`, DDI forms |
| `bank_account` | account-shaped strings Presidio's IBAN validator rejects |

**`street_address` notes.** Two rules keep SAP prose out. A capitalised name
word is mandatory between the number and the street type, so `3 Way match`
cannot match. Street types that are also ordinary logistics words — `Place`,
`Court`, `Close`, `View`, `Row`, `Track`, `Way` and similar — additionally
require a trailing comma-locality, because `20 Pallet Rack Row` and
`12 Handling Unit Place` are structurally identical to an address without it.
The cost is that a bare `44 Bellbird Rise` with no suburb is missed.
Regression-tested in `test_address.py`, which asserts negatives against the
**raw recognizer** rather than merged output — a post-merge check gives false
passes, because `_merge` can hand an overlap to a longer span of another type
and hide the false positive.

## Configuration

| Env var | Default | Notes |
|---|---|---|
| `SCRUBBER_ENGINE` | `presidio` | `presidio` \| `gliner` \| `both` |
| `GLINER_MODEL` | `urchade/gliner_multi_pii-v1` | Apache 2.0 |
| `SPACY_MODEL` | `en_core_web_sm` | `en_core_web_lg` improves ORG/PERSON |
| `PHONE_REGIONS` | `NZ,AU,GB,DE,US,PL` | Default US-only misses NZ numbers |
| `ALLOWLIST_PATH` | `./allowlist.txt` | Populate per `ALLOWLIST-EXTRACTION.md` (TSTC + DD02L; DD03L replaced by `mine_allowlist.py`). Inline `#` comments are stripped on load. |
| `CUSTOM_OBJECT_RULE` | `true` | Deterministic Z*/Y*//NAMESPACE/ suppression with surname guard |

**Suppression safety backstop.** Pure-alpha suppressible tokens (`KLEIN`,
`MARA`, `VBAK`) are *not* suppressed when user context ("posted by", "user",
"author"…) appears within ±40 chars — an allowlist may veto a pattern, never
context. Unambiguous shapes (underscore/digit/namespace) suppress
unconditionally. Regression-tested in `test_fixes.py`.

## Deployment

See `README-DEPLOY.html` for the full AI Core runbook.

## Licensing

All components Apache 2.0 / MIT — commercially clean.
Presidio (MIT), spaCy (MIT), GLiNER (Apache 2.0).
Deliberately **not** Piiranha (CC-BY-NC-ND, non-commercial).
