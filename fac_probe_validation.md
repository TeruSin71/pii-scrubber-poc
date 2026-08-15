# FAC Probe Batch — Container Validation Record

**Task 3, release 1.2.3.** Measured 2026-08-16. Every claim below is backed by
container output captured during this session.

## Environment

| | |
|---|---|
| Image | `ghcr.io/terusin71/pii-scrubber:1.2.2` |
| Full digest | `sha256:958bd5c3cd7051bd86df5905d072d5342ffd7268d7ae482dae7546f4b3ff3fa6` |
| Platform | `linux/amd64` |
| presidio-analyzer | **2.2.357** (pinned; not the 2.2.364 that caused the Gate-1 incident) |
| spaCy | 3.8.3 |
| Model | `en_core_web_sm` 3.8.0 |
| Read via | `app.detect(text, "presidio")` in-container |

Burned corpora (`samples.json`, `holdout_samples.json`, `eval_samples_v2.json`,
`holdout_v3.json`) were **not read** in this task.

## Counts

```
lines authored                  21   (9 positive candidates, 12 controls)
positive probes KEPT             0   <-- none produced a FAC span
positive candidates DROPPED      9   (7 unprotected-class, 2 valid as regression lines)
FAC fires on controls            0   of 12  (stated affirmatively)
control provenance               trap-list 2 · test-file 2 · glossary 2 · authored 6
structural validation            PASS (planted values verbatim; no note/provenance/kind text in any `text`)
```

## ⛔ The finding: item 3 as specified is a NO-OP

**`FAC` never reaches `LABEL_MAP`. It is dropped one layer earlier, at the
recognizer.**

```
SpacyRecognizer.ENTITIES:
  ['DATE_TIME', 'NRP', 'LOCATION', 'PERSON', 'ORGANIZATION']

registered SpacyRecognizer supported_entities:
  ['ORGANIZATION', 'LOCATION', 'AGE', 'EMAIL', 'PHONE_NUMBER', 'ID',
   'PERSON', 'DATE_TIME', 'NRP']
```

`FAC` is in neither list. spaCy tags the span; presidio's `SpacyRecognizer`
only emits entities it declares support for, so no `RecognizerResult` is ever
produced. `analyze()` returns **empty**:

```
presidio analyze() results:      (none)
detect() spans: []
```

Direct proof, run ephemerally in-container (nothing in the repo modified):

```
BEFORE  detect(): []
AFTER FAC->ADDRESS in LABEL_MAP: []
scrubbed: The warehouse on Willis Street was closed for stocktake.
```

**Adding `FAC: "ADDRESS"` to `LABEL_MAP` changes nothing.** The mapping is
correct and unreachable.

## What that means for the evidence base

The 8-span incidence probe — the reviewer's original 4 and my Task 0 rescan to
8 — was measured with **raw spaCy** (`nlp(text).ents`), **not through the
pipeline**. Raw spaCy does emit `FAC`, including on unnumbered references:

```
Willis Street       UNNUMBERED [('Willis Street','FAC')]   NUMBERED [('22','CARDINAL'),('Willis Street','FAC')]
Great South Road    UNNUMBERED [('Great South Road','FAC')] NUMBERED [('156','CARDINAL'),('Great South Road','FAC')]
Foveaux Street      UNNUMBERED [('Foveaux Street','FAC')]   NUMBERED [('45','CARDINAL'),('Foveaux Street','FAC')]
Kauri Street        UNNUMBERED [('Kauri Street','FAC')]     NUMBERED [('27','CARDINAL'),('Kauri Street','FAC')]
```

So the spans are real in spaCy and invisible to the scrubber. **Both the
original probe and my reproduction measured a layer the pipeline does not
use.** The agreement between them was agreement about spaCy, not about the
product.

This also revises *why* no gate ever showed a FAC leak. The recorded reason —
"the address regex independently covers numbered street lines" — is true but
not the operative one. The operative reason is that **`FAC` never enters the
pipeline at all**, numbered or not. Both explanations predict "no gate moves";
only one of them tells you item 3 does nothing.

## Consequences for already-shipped work

1. **The 1.2.2 trap-8 warning text is inaccurate.** It reads "spans carrying
   these labels are DETECTED and then silently dropped, never redacted". For
   `FAC` the drop happens at the recognizer, before `LABEL_MAP`, so it is not
   detected by the pipeline in the first place. `unmapped_labels()`
   **over-reports**: it models `labels_to_ignore` and the entity mapping, but
   not `SpacyRecognizer.supported_entities`.
2. **The handover's trap-8 correction is wrong on the same point.** It states
   `FAC` "reaches `_norm()` raw and is dropped". It does not reach `_norm()`.
3. Neither is a leak, and neither changes any measurement. Both are **wrong
   descriptions of a real gap**, which is the class of error 1.2.2 was
   written to eliminate.

## The leak class is real, and still open

The unnumbered-street class is genuinely unprotected — confirmed, not assumed:

```
FACP-01  'the warehouse on Willis Street was closed for stocktake'   detect() = []
FACP-02  'the depot on Great South Road'                             detect() = []
FACP-04  'the branch on Kaiwharawhara Road'                          detect() = []
FACP-06  'Auckland International Airport'                            detect() = []
FACP-07  'the Harbour Bridge'                                        detect() = []
```

Nothing redacts. The class item 3 was meant to close is exactly as exposed as
believed — **the proposed mechanism simply does not touch it.**

The correct layer is the recognizer, and there is precedent in this codebase:
`get_analyzer()` already re-registers `SpacyRecognizer` with `ORGANIZATION`
added, for the 1.2.0-era ORG defect. Adding `FAC` (mapped onward to `ADDRESS`)
would be the analogous fix — a materially larger change than one `LABEL_MAP`
line, with its own over-redaction risk, and it needs its own plan and
evidence. **Not smuggled into 1.2.3.**

## Per-line results

### Positive candidates — 0 kept

| id | line | detect() spans | outcome |
|---|---|---|---|
| FACP-01 | warehouse on Willis Street | `[]` | dropped — unprotected class |
| FACP-02 | depot on Great South Road | `[]` | dropped — unprotected class |
| FACP-03 | site on Foveaux Street | `[('forty minutes','DATE')]` | dropped — unprotected class |
| FACP-04 | branch on Kaiwharawhara Road | `[]` | dropped — unprotected class |
| FACP-05 | store on Ponsonby Road | `[('Fridays','DATE')]` | dropped — unprotected class |
| FACP-06 | Auckland International Airport | `[]` | dropped — unprotected class |
| FACP-07 | Harbour Bridge | `[('three hours','DATE')]` | dropped — unprotected class |
| FACP-08 | `27 Kauri Street, Onerahi, Whangarei 0110` | `[('27 Kauri Street, Onerahi, Whangarei 0110','ADDRESS')]` | **redacts** — existing recognizer path, valid regression line |
| FACP-09 | `19 Kereru Court, Rotorua` | `[('19 Kereru Court, Rotorua','ADDRESS')]` | **redacts** — existing path, valid regression line |

FACP-08/09 confirm the numbered path is intact and independent of `FAC`.

### Controls — zero FAC fires on 12 of 12

| id | provenance | detect() spans | FAC? |
|---|---|---|---|
| FACC-01 | trap-list | `[('Handling Unit Place','ORG_NAME')]` | no |
| FACC-02 | trap-list | `[]` | no |
| FACC-03 | test-file | `[('Scanner','PERSON')]` | no |
| FACC-04 | test-file | `[]` | no |
| FACC-05 | glossary | `[]` | no |
| FACC-06 | glossary | `[]` | no |
| FACC-07 | authored | `[]` | no |
| FACC-08 | authored | `[('the Court of enquiry','ORG_NAME')]` | no |
| FACC-09 | authored | `[('Storage Location Yard','ORG_NAME'), ('Plant Building','ORG_NAME')]` | no |
| FACC-10 | authored | `[('Christchurch','ORG_NAME'), ('overnight','DATE')]` | no |
| FACC-11 | authored | `[]` | no |
| FACC-12 | authored | `[('North Island','ADDRESS')]` | no |

**Zero FAC fires across all 12 controls, stated affirmatively.**

Six controls redact via **other, pre-existing paths** — `Handling Unit Place`,
`Scanner`, `the Court of enquiry`, `Storage Location Yard`, `Plant Building`,
`Christchurch`, `North Island`. **None is caused by `FAC` and none is caused by
anything in 1.2.3.** They are recorded because they are real over-redactions
the batch happened to surface; `Scanner`→PERSON and `North Island`→ADDRESS
look like the most useful new glossary candidates, on a future release's
evidence rules, not this one's.

## Lines whose behaviour surprised me

All nine positives. I expected the unnumbered class to fire `FAC` through
`detect()` because the incidence probe said `FAC` was live on the shipped
model. It is live in spaCy and absent from the pipeline. **The surprise was
not that my sentences were wrong — the pair test shows they were right — but
that the measurement everyone had been reasoning from was taken at the wrong
layer.**
