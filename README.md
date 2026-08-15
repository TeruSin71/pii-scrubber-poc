# PII Scrubber — POC (SAP Incident KB)

Local, in-boundary PII scrubbing for the SAP incident knowledge base.
Deploys to **SAP AI Core** (bring-your-own-model). No Cloud Foundry, no
Generative AI Hub, no third-party LLM ever sees raw data.

## Verified result

Self-test against 13 labelled synthetic SAP samples:

| Metric | Value |
|---|---|
| Recall | **100%** (45/45 planted PII redacted) |
| Misses | 0 |
| Over-detections | 6 (safe-but-noisy) |
| Engine | `presidio` + custom SAP recognizers |

> Caveat: 13 synthetic samples, tuned against them. A sanity check, not a
> production figure. Expand to 50–100 real-shaped samples before quoting.

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
