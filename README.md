# PII Scrubber — POC (SAP Incident KB)

Local, in-boundary PII scrubbing for the SAP incident knowledge base.
Deploys to **SAP AI Core** (bring-your-own-model). No Cloud Foundry, no
Generative AI Hub, no third-party LLM ever sees raw data.

## Verified result

**Quote 90.0%.** It is the only figure measured on data the build never saw.

### Blind batch — 40 samples, 50 planted values

Authored outside the build session, never seen before the run, run **once**
against the deployed image. Scoring is end to end: a value counts as caught
only if it no longer appears in the scrubbed output.

| Metric | Value |
|---|---|
| **Blind recall** | **90.0%** (45 / 50) |
| Leaks | 5 — **zero novel failure classes** |
| Measured on | deployed `1.2.0`, deployment `db3d9cc5eea296cd` |

**Every one of the five leaks was already documented before the run.** Three
are the known PERSON classes; two are unpadded customer numbers sitting behind
`client` and `ship-to`, cues deliberately left out of the frozen cue list —
they leaked exactly as that design decision predicted. Nothing failed in a way
the team had not already written down.

Notable positives: ADDRESS **7/7**, including all five street types that were
safety-cleared but unshipped; PHONE **8/8**, including the first AU and GB
numbers ever tested.

### Regression suite — 40 samples, 111 values

| Metric | Value |
|---|---|
| Recall | 97.3% (108 / 111) |
| Leaks | 3 — `ZHANG`, `Young`, `Mere Tuhoe` |

> **This is a regression suite, not a blind figure.** It was the original
> benchmark and read 96.4% on `1.1.0`, but the 1.2.0 work was built against
> its leaks, so it can no longer measure what it shaped. Its job now is to
> fail loudly if a change breaks something — any value other than 108/111 is
> a stop. **Do not quote it as a production estimate.**

### Self-test — 13 tuned-against samples

| Metric | Value |
|---|---|
| Recall | 100% (45/45) |
| Misses | 0 |
| Over-detections | 4 (safe-but-noisy) |
| Engine | `presidio` + custom SAP recognizers |

> This is a **regression baseline, not a result.** The recognizers were tuned
> against these 13 samples, so 100% is close to guaranteed and says nothing
> about production. Its job is to prove packaging and deployment changed
> nothing. **Never present it to management as the expected production
> figure** — quote the holdout instead.

### Known gaps

Two classes, both documented before the blind run confirmed them:

| Class | Blind examples | Note |
|---|---|---|
| PERSON, per-token | `NAKAMURA`, `Park`, `Adeyemi` | **A per-token lottery, not a frame problem.** `VERMEULEN` was caught in the *identical* sentence frame `NAKAMURA` leaked from — confirmed on a third dataset. Not fixable at the spaCy layer; both models fail, merely on different tokens. An engine-level question. |
| Customer number, uncued | `5591230`, `6620945` | Behind `client` and `ship-to`. The cue list is frozen at six words; `ship-to` was excluded deliberately because in delivery text it cues an address more often than an account. These leak by design, not by defect. |

Address coverage is **NZ/AU forms only**. German-style
`Hauptstrasse 12, 80331 Munich` (name before number) is not matched by the
recognizer and relies on incidental locality detection — which does work: both
German forms tested were redacted end to end. A bare ambiguous-type address
with no suburb (`44 Bellbird Rise`) is missed — see `recognizers.py` for why
that trade was made.

**A scrubber at 90% is a filter, not a guarantee.** The residual is what the
human review gate exists to catch, and the glossary is bounded by the corpora
it was mined from — production jargon outside them needs edit-and-redeploy.

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
