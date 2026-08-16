# Overlap-Aware Suppression — Run Log

Execution record for `GATE0-overlap-suppression-plan.md`, Gate 0 answered
2026-08-16. Every entry states what was inspected, not just a verdict.

**Task 6 review-gate deliverable.** Deployment `daedcfe9342d21a7` runs `1.2.3`
(presidio) and was never touched. Blind batch v4 unread, unrun, unsalted.

⚠️ **Updated after the gate:** Task 6 was ACCEPTED and the five commits were
pushed. Origin tip is **`84c4ed1`** (`2ff5802..84c4ed1`). The lines below that
read "nothing pushed" describe the state *at the gate*, which is when they
were true.

---

## Artifact

```
re-frozen  pii-scrubber:gliner-cand@sha256:73994cfcd5d025ae4c6e05527174d7a3f03f3f749815267b04958a7952368314
           build_version gliner-cand-c   git_sha d5b02f1   (== git rev-parse --short HEAD)
preserved  pii-scrubber:gliner-cand-preovlp-2026-08-16@sha256:d96edef4…c764912   <- the bake-off's artifact
preserved  pii-scrubber:gliner-cand-prefix-2026-08-16@sha256:2fa85d67…83fbdebd   <- pre-_merge-fix
compressed 1,509,636,266 bytes = 1.51 GB   (docker save | gzip | wc -c, the only trusted method)
```

Local commits, none pushed: `5a29018` docs correction · `8e2fc34` plan +
corpus · `d5b02f1` the change.

---

## Task 0 — fresh corpus + the two documentation corrections ✅

`jargon_suppression_samples.json` — **24 samples, 12 values, authored BEFORE
the rule existed**, committed and openly readable. Four classes: a-reach 8 ·
b-value 6 · c-person 4 · d-control 6. Validated programmatically — every value
verbatim in its `text`, no annotation text in any `text` field, no duplicate
ids, every sample carrying `id/class/source_type/text/pii/note`.

**This is what keeps the rule off the burned sets.** The readability failures
were observed on burned controls; the rule was developed against this file and
the burned sets were used only as regression gates.

Docs commit `5a29018` carried a repo-wide grep transcript, per the standing
rule. Two defects closed: the over-reaching vocabulary claim in
`TASK6-SYNTHESIS.md` §4 and `docs/HANDOVER.md`, and the stale repo-root
`GATE0-gliner-bakeoff-plan.md` — a copy of the bake-off plan **missing §13,
the verdict** — which was deleted rather than re-synced.

---

## Task 1 — RED first ✅

`test_overlap_suppression.py` run against **unmodified** `app.py`:

```
[FAIL] JS-A01 no longer over-redacts -- got '<ORG_NAME> was signed off before the sprint started.'
[FAIL] JS-A02 no longer over-redacts -- got 'Escalated to <ORG_NAME> for the interface rebuild.'
[FAIL] JS-A05 no longer over-redacts -- got 'Checked the <ORG_NAME> mapping and it is still correct.'
[FAIL] JS-A07 no longer over-redacts -- got 'Raised against <ORG_NAME> during the MDG cutover.'
AttributeError: module 'app' has no attribute '_span_tokens'
```

⚠️ **The plan named `HO-015` as the natural RED candidate and Phase 1
measurement had already ruled it out** — `plant`, `4000` and `customer` are
not in the glossary, so no matching rule reaches it and a test written on it
would be red before and red after. `HO-029` is the reachable control, and the
unit-level RED cases were taken from the fresh corpus instead.

---

## Task 2 — the change, GREEN ✅

ALL-TOKENS semantics in `app._suppress_span`: a span is suppressed when
**every** token is in `ALLOWLIST_EXACT` or matches `is_custom_sap_object`,
**and** every token clears the ±40-char backstop **at its own offsets** (Q5).

`test_overlap_suppression.py` — **38 checks, all green**, including:

- **Non-vacuity of the both-directions case.** The rejected WHOLE rule is
  carried verbatim and proved to drop the value-bearing spans in `JS-B01`,
  `JS-B02`, `JS-B03` while ALL-TOKENS keeps them. Without this section, §2's
  assertions could pass without ever having been at risk.
- **Property test**, 3000 generated geometries, 582 suppressions, zero
  violations — and **non-vacuous**: the pre-change rule disagrees on 309 of
  3000.
- **Single-token equivalence PROVED, not asserted** — the pre-change rule is
  carried verbatim and agrees on every single-token span; 0 divergences. This
  is what holds the registered gate values.
- **Purity guard** — `_suppress_span(text, start, end)` takes no span list, so
  union-coverage monotonicity survives by construction.
- **Ordering guard** — asserted against `inspect.getsource(detect)`, that
  suppression runs before `_merge`.
- **Q6 assertion** — no whitespace-bearing entry in the suppression set.

⚠️ **One of these checks was written so it could not fail and was rewritten
before the suite was trusted.** The ordering guard first read
`A.detect.__doc__ is None or True`. That is this project's named
"verification that cannot fail where it matters" class, committed by the
executor, caught on re-read.

**Six registered suites, zero movement:** `test_fixes` 16 · `test_address` 39
· `test_customer_number` 33 · `test_jargon` 74 · `test_build_version` 29 ·
`test_label_map` 37. Plus `test_merge_monotonicity` 36 and the new suite 38.

`ALLOWLIST_EXACT` unchanged at **257,619** (glossary 36 newly-added) — the
glossary edits were comment-only and the loader strips comments.

**Two findings from the fresh corpus, PRE-EXISTING and deliberately not
fixed** (promotion-side work, out of this plan's scope, pinned as KNOWN so a
change in either direction is visible):

| | |
|---|---|
| `JS-C02` | `Payer` leaks — **`approved by` is not in the frozen cue list** (`approver` is) |
| `JS-C03` | `Way` leaks — **`countersigned by` is not in the frozen cue list** |

---

## Tasks 3–4 — control and union arms ✅ every value on its registered number

Measured with the changed `app.py` / `glossary.txt` bind-mounted over the
frozen candidate, `--cpus=1 --memory=3g`, `GLINER_THRESHOLD` at the image
default `0.4`, corpora line recorded per run (all four present, 158 samples).

| Measurement | Registered §6.1 | Measured |
|---|---|---|
| Selftest, control | `100.0 / 45/45 / missed 0 / od 4 / spans 49` | **identical** ✅ |
| `holdout_samples`, control | `108/111` + leak list | **97.3%**, `ZHANG` `Young` `Mere Tuhoe` ✅ |
| `eval_samples_v2`, control | `65/68` + leak list | **95.6%**, `44 Bellbird Rise` `Okonkwo` `FONTAINE` ✅ |
| `holdout_v3`, control | `45/50` + leak list | **90.0%**, `NAKAMURA` `Park` `Adeyemi` `5591230` `6620945` ✅ |
| Control over-detections | **31 → 30**, `HO-028` only | **30**, removed exactly `HO-028 'FSD ZMM_VENDOR_PORTAL'`, none added ✅ |
| `holdout_samples`, union | `111/111` | **100.0%** ✅ |
| `eval_samples_v2`, union | `68/68` | **100.0%** ✅ |
| `holdout_v3`, union | `50/50` | **100.0%** ✅ |
| Union over-detections | **76 → 74**, `HO-028` + `HO-029` | **74**, removed exactly those two, none added ✅ |
| **Controls damaged** | **8 → 7 of 21** | **7**, repaired `HO-029`, none newly damaged ✅ |

**Leak lists compared line by line, never by count.**

`READABILITY-SAMPLES.md` regenerated across **all 21 controls** — replacing
the bake-off's ten-sample file rather than sitting beside it.

### Q1 deliverable — score distribution, and it answers the successor question

`score_distribution.py`, union arm. **The lever is vocabulary, not
thresholds.**

| engine | type | TP | over | over-detections scoring ≥ the lowest TP |
|---|---|---|---|---|
| gliner | ORG_NAME | 27 | 33 | **21 of 33** |
| gliner | PERSON | 64 | 13 | **10 of 13** |
| gliner | ADDRESS | 28 | 4 | **2 of 4** |
| gliner | CUSTOMER_NO / IBAN / PHONE / USER_ID | — | 1 each | separable, but only one span each |

GLiNER over-detections: median **0.802**, max **0.994**. GLiNER true
positives: median 0.995, **min 0.572**. The distributions interleave on
exactly the three types that carry the damage — `Buyer` scores **0.994** and
`Customer` **0.882**, higher than many real names. **GLiNER is confidently
wrong, so no per-type floor can separate the classes.**

⚠️ **Configuration-level, never engine-level.** presidio spans have already
passed per-type floors before they are counted here; GLiNER spans passed one
global floor and never touch `TYPE_THRESHOLDS`. The confound is in the tool's
own header so it travels with the numbers.

---

## Task 5 — ONE rebuild, sha-stamped, re-frozen ✅

Pre-change candidate tagged **before** the tag moved (§10 precondition).
Build **1.0 s** — every expensive layer cached, only the source `COPY`
rebuilt, so the weight-prefetch layer was inherited rather than re-run.

⚠️ **Because the prefetch was CACHED it did not re-print its success line.**
Not accepted as inherited: the tokenizer gate loads the model offline from
that layer, and it passed, which is the check that would fail if the weights
were absent.

| Check | Result |
|---|---|
| `/v1/info` `git_sha` | **`d5b02f1`** = `git rev-parse --short HEAD`. Provenance is a stamped read |
| Baked conditions, **no `-e` flags** | `HF_HUB_OFFLINE=1` `TRANSFORMERS_OFFLINE=1` `OMP_NUM_THREADS=1` `MKL_NUM_THREADS=1` `GLINER_THRESHOLD=0.4` |
| Tokenizer gate, default invocation | ✅ **ALL TESTS PASS** offline |
| Tokenizer gate, `-e HF_HUB_OFFLINE=0` | ✅ **exit 1, FAILS LOUDLY**, naming the cause. A guard that cannot fail is not a guard |
| Four gates re-run **in the image** | identical to the mounted-source run, leak lists line by line |
| Determinism / artifact equivalence | union arm **span-for-span identical including scores**, 349 spans, 74 over |
| Image inventory | 16 → 16. The one "removed" row is the **tag moving**; `d96edef4` is still present under its dated tag |
| Compressed size | **1.51 GB**, registered ceiling ≤1.6 GB ✅ |

### Pod fitness — the cost claim was asserted in the plan, so it was measured

`--cpus=1 --memory=3g`, thread cap from the **image**, union arm.

| Gate | Bake-off | After the change |
|---|---|---|
| p50, median sample | 702 ms | **695 ms** |
| Longest document | 1,054 ms (max 1,332) | 1,111 ms (max 1,366) |
| 65-sample batch | 48.9 s | **48.2 s** |
| 4-way concurrency | 0.51× | 0.51× (max 6,572 ms) |
| Peak RSS, stressed | 2.175 GiB | **2.066 GiB** of 3 GiB |

**No regression.** The extra work is `k` set lookups per span against a
257,619-token set, `k` ≤ 5 words observed.

⛔ **Every latency figure is an EMULATED amd64-on-ARM UPPER BOUND.** The pod
figure remains unmeasured and unmeasurable here; the live gate is still
answered at a release's verification step with the presidio fallback
pre-stated. **Do not quote 695 ms as the pod's latency.**

---

## Stop conditions — none fired

| | Condition | Result |
|---|---|---|
| S1 | Any recall gate moves | ✅ silent — all four exact on the control arm |
| S2 | Leak list changes while its count does not | ✅ silent — compared line by line, all three identical |
| S3 | Any planted value becomes exposed | ✅ silent — union leaks nothing; `PO Box`/`Rise` values pinned in tests |
| S4 | Over-redaction falls by more than the registered spans | ✅ silent — exactly `HO-028` (control) and `HO-028`+`HO-029` (union) |
| S5 | Monotonicity fails, or the filter reads more than `(span, text)` | ✅ silent — `test_merge_monotonicity` 36 green, purity guard green |
| S6 | The RED case passes before the fix | ✅ silent — four failures recorded, then AttributeError |
| S7 | Determinism differs from the bake-off's | ✅ silent — span-for-span identical including scores |
| S8 | The rule was tuned against a burned set | ✅ silent — corpus authored at Task 0 before the rule existed |

---

## Q9 — answered as pre-stated, not re-read afterwards

**PASS for the plan. CONTINUED-BLOCK for the batch path.**

```
controls damaged   union BEFORE  8 of 21  (38%)
                   union AFTER   7 of 21  (33%)
                   presidio      2 of 21  (9.5%)
```

⛔ **7 of 21 is never to be reported without 2 of 21 beside it.** The change
is correct, landed, and did what it was measured in advance to do. It is
**necessary and not sufficient**: the residual is the vocabulary class —
`customer`, `plant`, `warehouse team`, `service desk`, `buyer` — which is not
in the glossary, and the score distribution shows thresholds cannot reach it
either.

**What this hands on:** the union release inherits a re-frozen sha-stamped
candidate and the union gates above, **and inherits the batch blocker
unchanged**. Blind batch v4 stays HELD for that release's verification.

---

## Appendix — label-subset counterfactual, DERIVED OFFLINE 2026-08-16

Directed at the Task 6 gate, before any successor plan is written. Counterfactual:
**union with `GLINER_LABELS` reduced to its unique-value labels**
(`person`, `physical address`), so GLiNER may only emit `PERSON` / `ADDRESS`.

**No runs, no code, no corpus exposure.** Derived from
`bakeoff-spans-presidio-ovlp.json`, `bakeoff-spans-both-ovlp.json` and
`score-distribution-both-ovlp.json`, all already on disk.

⚠️ **The dumps itemise over-detections in full but record on-value spans only
as counts.** Over-redaction and control damage are therefore derived
**exactly**; recall is derived through the presidio-miss frame and is exact
except where a removed label is the only cover. **Every bounded cell is a
range, never a point estimate.**

### Control damage — the metric batch is blocked on

| | Damaging spans | Under the subset |
|---|---|---|
| `HO-015` | `plant`(g/ORG) `4000`(g/CUST) **`customer`(g/PERSON)** | still damaged |
| `HO-021` | **`config knowledge`(p/PERSON)** | still damaged |
| `TKT-0009` | **`customer`(g/PERSON)** | still damaged |
| `V2-064` | **`storage location 0001`(g/ADDRESS)** `plant 4000`(g/ORG) | still damaged |
| `V3-033` | `plant 4100`(g/ORG) | ✅ **repaired** |
| `V3-034` | **`400000`(p/CUSTOMER_NO)** | still damaged |
| `V3-040` | `VF04 collective run`(g/ORG) **`header level`(g/ADDRESS)** | still damaged |

> **DERIVED: 7 → 6 of 21.** presidio alone is **2 of 21**. No returning
> presidio span lands on a control, so this cell is exact.

### Over-redaction

GLiNER over-detections 54 → **17** retained (PERSON 13 + ADDRESS 4); 37
dropped (ORG_NAME 33, IBAN/CUSTOMER_NO/PHONE/USER_ID 1 each). But **11
presidio over-detections currently lose the merge to a GLiNER span and can
return**:

```
Wellington · Auckland · the Christchurch DC · Brazilian · Australian ×2
Dutch · German · Hanoi · EU · Sydney DC
```

> **DERIVED: 74 → 37–48.** presidio alone is 30.

⛔ **Every returning span is a real city or a nationality adjective — the exact
class `glossary.txt` REJECTED on the record** (`Munich`, `Wellington`,
`Auckland`, `Australian`, `Dutch`, `German`, `European`). **The label subset
does not remove the over-redaction, it relocates it to a class the project has
already decided vocabulary must not touch.**

### Recall

Exactly **11** planted values have no presidio coverage — the presidio-arm
leak lists — and they are the only values whose recall depends on GLiNER.
8 PERSON + 1 ADDRESS are retained labels, and the GLiNER arm leaked **zero**
of either type, so all nine are recovered.

| Corpus | Derived | |
|---|---|---|
| `holdout_samples` | `111/111` | EXACT |
| `eval_samples_v2` | `68/68` | EXACT |
| `holdout_v3` | **`48/50` – `50/50`** | **BOUNDED** — `5591230` / `6620945` sit behind the dropped `customer number` label |

Only **1** GLiNER `CUSTOMER_NO` span sits on a planted value in the union, so
at most one of the two is covered by that label and the other is covered by a
span of a type the dumps do not record. ⚠️ **`holdout_v3` is the
externally-authored corpus — a cost paid there is paid on the only
blind-authored instrument this project has spent.**

### Corollary — ALL-TOKENS caps what vocabulary can reach

Derived by inspection of the same rows, and it is not obvious: **the semantics
chosen for safety makes vocabulary harder, not easier.** Suppressing
`plant 4000` under ALL-TOKENS needs **both** `plant` *and* `4000` as entries,
and bare numerics (`4000`, `0001`, `4100`, `400000`) collide with customer
numbers — they can never be added. Restricting vocabulary to non-numeric
tokens repairs `HO-021`, `TKT-0009` and `V3-040` only:

> **DERIVED ceiling for vocabulary alone: 7 → 4 of 21**, still double
> presidio's 2, and each entry carries its own observed-misfire burden.

### Verdict handed to the successor

| Lever | Control damage | Cost |
|---|---|---|
| overlap-aware suppression (shipped) | 8 → **7** | none — gates exact |
| per-type thresholds | — | ⛔ **measured OUT**: GLiNER's over-detections and true positives interleave |
| label subset | 7 → **6** | relocates over-redaction to rejected place/nationality class; risks `holdout_v3` |
| vocabulary, non-numeric only | 7 → **4** (ceiling) | per-entry evidence burden |
| — | **presidio alone: 2 of 21** | |

**No single lever reaches presidio's 2 of 21, and the two survivors are not
additive in the obvious way** — the label subset removes the ORG_NAME spans
that vocabulary would otherwise target, while returning a class vocabulary is
barred from. The successor plan's real question is whether batch-as-union is
reachable at all, not which of three levers to pull first.
