# PII Scrubber — 1.2.3 Bundle Implementation Plan

**Gate 0 deliverable. Nothing in this plan has been executed.**
Authored 2026-08-16 against `81748ac`. Scope frozen by the reviewer at three
items, one cutover.

**Process change, binding for this release:** the plan is reviewed **before**
anything is pushed. 1.2.2 shipped before review; it cost nothing because that
release was pure diagnostics, but review-before-push is the order that caught
the `/info` RBAC defect. That order is not ceremony.

**One document this time.** 1.2.1 used a bundle plan plus a separate task
plan. Three items of roughly one line each do not need 1,000 lines of
runbook, so §7 carries the TDD steps inline. If the reviewer wants them split,
say so.

---

## 1. Executive Summary

**Goal.** Ship one image, `1.2.3`, carrying three changes through a single
stop/create cycle: make the unmapped-label diagnostic read the config the
engine actually uses, surface its result on `/v1/info`, and **map `FAC` to
`ADDRESS`** — closing a leak class that has had no net at all.

**Why one image.** Unchanged and still binding: free tier allows one pod, and
a stop-then-create race marks the new revision failed permanently. This
release also answers the reviewer's §6.5 note directly — two cutovers happened
in one session for 1.2.1 and 1.2.2; three items in one cutover is the fix.

**Success criteria — all measurable, all blocking:**

| # | Criterion | Source |
|---|---|---|
| 1 | `/v1/info` returns `build_version` exactly `1.2.3` | deployed endpoint |
| 2 | `/v1/info` carries an `unmapped_labels` field | deployed endpoint |
| 3 | After item 3, `unmapped_labels` is **`[]`** and the log reads "LABEL_MAP covers every label the model emits" | deployed + container |
| 4 | `unnumbered street reference redacts` — the class item 3 exists to close | new probe batch |
| 5 | Facility/technical nouns from the controls **do not** redact | new probe batch |
| 6 | Selftest recall stays `100.0`, `45/45`, `missed 0` | deployed |
| 7 | Selftest `over_detections` — **may move; must be itemised span-by-span before the new baseline is asserted** | deployed |
| 8 | Three gates: recall **must not fall**. A rise is expected-and-allowed for item 3 only, and must be attributed value-by-value | local + container |
| 9 | Suites all exit 0 at their stated counts | local |
| 10 | Image `linux/amd64`, in-container `/v1/info` reads exactly `1.2.3` | registry + container |

**Criterion 8 is a change of rule and the reviewer must agree to it.** For
three releases the gates have been "exactly X, any other value is a stop".
Item 3 is a deliberate detection change, so a *rise* is now a legitimate
outcome. It is still a stop if it cannot be attributed to a named value.

**Time estimate.**

| Task | Budget | Risk |
|---|---|---|
| 0 — Gate 0 approval + baseline capture | 20 min | read-only |
| 1 — real `ner_cfg` into `unmapped_labels()` | 30 min | local |
| 2 — `unmapped_labels` on `/v1/info` | 30 min | local |
| 3 — author the FAC probe batch | 40 min | local, no code |
| 4 — map `FAC` → `ADDRESS` | 45 min | **detection change** |
| 5 — full regression + itemisation | 45 min | local |
| 6 — build + in-container verify | 40 min | local |
| 7 — ⛔ **REVIEW GATE** | — | nothing pushed before this |
| 8 — publish + deploy handoff | 60 min | ⚠️ remote, user drives BTP |

≈ 5 hours. Task 7 is a hard stop, not a checkpoint.

**Risk posture.** Higher than 1.2.1 or 1.2.2, and for one reason: **item 3 is
the first change in three releases that can move a number.** Items 1 and 2
cannot — they are diagnostics. Item 3 can be dropped without blocking them;
they cannot be dropped without making item 3 unobservable.

---

## 2. Philosophy and Principles

1. **Evidence before action.** Every claim in §3 carries the command or the
   measurement that produced it.
2. **The plan is the authorization.** Scope is frozen at three items.
3. **Declare movement in advance.** §5 states which baselines may move and in
   which direction, **before** they move. A number that moves inside a
   prediction is a result; a number that moves and then acquires an
   explanation is a rationalisation.
4. **Promotion needs evidence, exactly as suppression does.** The glossary
   rule ("observed misfire on the shipped config") has a mirror image: a label
   is promoted to a redacting type only on an observed class with a measured
   incidence and a measured false-positive rate. §3.2 satisfies it.
5. **Mapping is not redacting.** A label can be mapped and still never redact,
   if its score sits under the type threshold. Assert end to end, never on the
   dict.

---

## 3. Current State — verified ground truth

### 3.1 Deployed

| | |
|---|---|
| Deployment | `da1b1b3e39367c59`, running `1.2.2`, verified on the endpoint |
| Image | `sha256:958bd5c3…b3ff3fa6`, `linux/amd64` |
| Selftest | `100.0 / 45/45 / missed 0 / over_detections 4 / spans 49` |
| Gates | `108/111`, `65/68`, `45/50` — burned, leak lists known |
| Suites | 16 · 39 · 33 · 74 · 17 · 13 |
| Rollback | `1.2.2` `sha256:958bd5c3…`, `1.2.1` `sha256:5ec0f449…`, `1.2.0` `sha256:e8a44575…` |

### 3.2 Item 3 — the FAC evidence, supplied by review

An incidence probe across **all 145 samples** of the three evaluation sets
found **exactly 4 `FAC` spans**:

| Span | Shape |
|---|---|
| `Victoria Street` | street name |
| `Willis Street` | street name |
| `Great South Road` | street name |
| `Foveaux Street` | street name |

**4 of 4 are street names. Zero false positives.** On this corpus `FAC` *is*
the ADDRESS class.

**Why no gate ever showed a FAC leak:** the `street_address` recognizer
independently covers **numbered** street lines, so anything of the form
`48 Rimu Road, Papakura` was already caught by a different path. The exposed
class is street references **without a number** — "the warehouse on Willis
Street" — which today have **no net at all**: spaCy tags them `FAC`, presidio
passes `FAC` through unmapped, `_norm()` returns `"FAC"`, and `REDACT_TYPES`
does not contain it. Detected, then discarded.

This is why the class is invisible in every existing measurement: the burned
sets contain numbered addresses, which the regex catches, and the unnumbered
form was never planted. **A leak class with no test cannot fail a gate.**

### 3.3 Item 1 — the diagnostic reads the wrong config

`get_analyzer()` builds the engine with a modified ignore list:

```python
keep = sorted(default_ignore - {"ORG", "ORGANIZATION"})
ner_cfg = {"labels_to_ignore": keep}
```

`unmapped_labels()` reads `NerModelConfiguration()` fresh — the **default**,
not `keep`. The answer is identical today only because `ORG` maps to
`ORGANIZATION`, which is in `LABEL_MAP`. **That is a coincidence, not an
invariant.** Un-ignore a label whose presidio entity is not mapped and the
diagnostic reports clean while the pipeline drops spans — the same
silent-diagnostic failure the function exists to prevent.

### 3.4 Item 2 — the warning is too quiet to rely on

It fires on first analyzer build, not process start, because model loading is
lazy so `/health` stays instant. A pod created, health-checked and left idle
never logs it. A field on `/v1/info` is always readable, costs nothing, and
`null` before first build is itself informative — it says "no analyzer yet",
not "no problem".

### 3.5 Environment

Unchanged: `uv venv --python 3.12 --seed`, always `--platform linux/amd64`,
never `docker system prune`, disk ~20 GB free against ~2.5 GB per image.

---

## 4. Decision Matrix

| # | Decision | Chosen | Why not the alternative |
|---|---|---|---|
| D1 | How does `unmapped_labels()` learn the real ignore list? | New optional param, passed by `get_analyzer()` | Reading a module global couples it to call order; re-deriving `keep` duplicates the logic §3.3 is about. |
| D2 | Default when the param is absent | Presidio's installed default | Keeps the function callable standalone in tests, and matches today's behaviour exactly. |
| D3 | `/v1/info` field name | `unmapped_labels` | Same name as the function. A field whose name differs from its source is a future mystery. |
| D4 | Value before first analyzer build | `null` | `[]` would claim "nothing unmapped", which is a false negative. `null` means "not yet known". |
| D5 | Does item 2 force an eager analyzer build? | **No** | Lazy loading keeps `/health` instant so readiness probes never time out. That is load-bearing on a 1-pod tier. |
| D6 | `FAC` maps to what? | `ADDRESS` | 4/4 observed spans are street names. `ORG_NAME` would type a street as an organisation and mislead the reviewer-restore step. |
| D7 | Add `FAC` to `LABEL_MAP`, or to the address recognizer? | `LABEL_MAP` | The recognizer is deterministic and regex-based; `FAC` comes from the NLP layer. Fixing it in the recognizer would mean re-implementing NER. |
| D8 | Verify item 3 against which set? | A **new** probe batch, authored this session | All four existing sets are burned, and none plants an unnumbered street. Tuning against a burned set is forbidden; this batch is a *verification* batch, never a figure. |
| D9 | Gate rule under a deliberate detection change | Recall may rise, must not fall, every delta attributed value-by-value | "Exactly X or stop" would make a correct improvement indistinguishable from a regression. |

### Open at Gate 0

| # | Question | Recommendation |
|---|---|---|
| Q1 | Criterion 8 changes the gate rule from "exactly X" to "must not fall, rises attributed". Agreed? | **Yes** — but it is the reviewer's call, because it relaxes the strongest guard this project has. |
| Q2 | The new probe batch is Claude-authored, like `eval_samples_v2.json`. Accept, or must item 3 wait for an externally authored batch? | **Accept as a verification batch.** It verifies a named class, produces no quotable figure, and becomes a gate the moment it is read. |
| Q3 | If `over_detections` rises on the selftest, is a rise acceptable given item 3 is a promotion? | **Yes if itemised**, no otherwise. State the number after Task 5. |

---

## 5. Declared movement — written before anything moves

This section exists so that a moved number cannot acquire an explanation
afterwards.

| Measurement | Prediction | If it moves the other way |
|---|---|---|
| Selftest `recall_pct` / `45/45` | **No change.** Adding a redacting type cannot lose a catch | ⛔ stop — a promotion that loses recall means the merge order changed |
| Selftest `over_detections` (4) | **May rise.** A FAC span overlapping an already-matched value becomes an extra redacting span | Fall is also possible if FAC now covers a value the address regex missed. Either way: itemise |
| Selftest `redacting_spans_emitted` (49) | **May rise** | — |
| `holdout_samples.json` 108/111 | **No change expected** — its addresses are numbered | A rise must name the value; a fall is ⛔ |
| `eval_samples_v2.json` 65/68 | **Watch `44 Bellbird Rise`.** It is the known ADDRESS leak. If spaCy tags it `FAC`, item 3 closes it and this becomes 66/68 | A rise here is the single most likely legitimate movement in the release |
| `holdout_v3.json` 45/50 | **No change expected** — its five leaks are PERSON and CUSTOMER_NO | Any change is ⛔ |
| `test_address.py` 39 | **No change** — recognizer untouched | ⛔ |
| `test_label_map.py` 13 | **Changes by design.** `FAC` moves from "reported" to "not reported" | The existing FAC assertions must be inverted, not deleted |
| Container control samples | **May redact more.** Street names in control text will now redact | Expected; record it |

**The `44 Bellbird Rise` case is the one to watch.** If item 3 closes it, a
burned gate rises for a *correct* reason — exactly the situation criterion 8
was rewritten for.

---

## 6. Global Constraints

- **Rule 3:** no outbound calls. No bare `AnalyzerEngine()`.
- **Rule 7:** no dependency changes.
- **Rule 4:** no real ticket text; the new probe batch is synthetic and
  **gitignored** like every other evaluation set.
- Always `--platform linux/amd64`, verified with `imagetools inspect`.
- `BUILD_VERSION` defaults to `dev`; build with `--build-arg BUILD_VERSION=1.2.3`.
- **Do not tune against any of the four burned sets.**
- **Nothing is pushed before the Task 7 review gate.**
- Every check prints what it inspected.

---

## 7. Per-task runbook

### Task 0 — Gate 0, baseline capture (read-only)

Capture, from a local service and the six suites: the five selftest numbers,
the three gate scores **with leak lists**, all six suite counts, and — new —
the current `unmapped_labels()` output and the four FAC spans reproduced
locally. Report ≤250 words. Answer Q1-Q3.

### Task 1 — real `ner_cfg` into `unmapped_labels()`

**RED.** Extend `test_label_map.py`: a call passing an ignore list that
un-ignores a label whose presidio entity is absent from `LABEL_MAP` must
report that label; the current signature cannot express the test.

**GREEN.**

```python
def unmapped_labels(nlp_engine, labels_to_ignore=None) -> List[str]:
    ...
    ignored = set(labels_to_ignore if labels_to_ignore is not None
                  else (cfg.labels_to_ignore or []))
```

and in `get_analyzer()`, pass the `keep` list it already computed:

```python
unmapped = unmapped_labels(nlp_engine, labels_to_ignore=keep)
```

**Assert the wiring, not just the function** — that `get_analyzer()` passes
the real list is the whole point, and a test that only calls the function
directly would pass with the bug still present.

### Task 2 — `unmapped_labels` on `/v1/info`

**RED.** `/v1/info` payload has no `unmapped_labels` key; before first
analyzer build it must be `null`, after it a sorted list.

**GREEN.** Module-level `_unmapped: Optional[List[str]] = None`, set in
`get_analyzer()` beside the warning, returned by `info()`. No eager load (D5).

**Both routes must show it** — `/info` and `/v1/info` are one handler, already
asserted.

### Task 3 — author the FAC probe batch (no code)

`fac_probe_samples.json`, gitignored, `_provenance` block stating it is
Claude-authored and verification-only. Two halves, both required:

**Must redact** — the class item 3 closes:
- "The warehouse on Willis Street has no dock access."
- "Collection is from the depot on Great South Road."
- "Driver waited outside the site on Foveaux Street."
- numbered forms too, proving no regression of the existing path

**Must NOT redact** — the over-redaction risk D6 accepts:
- plant/DC/technical facility nouns already in the control samples
- `Handling Unit Place`, `The 2 Bin View`, `20 Pallet Rack Row`
- glossary terms in facility-ish positions

**Verify each "must redact" line actually produces a FAC span BEFORE item 3
lands.** A probe line that spaCy does not tag `FAC` tests nothing and would
pass before the feature exists — the exact false-pass that three of eight
1.2.1 glossary frames hit.

### Task 4 — map `FAC` → `ADDRESS`

**RED.** Probe batch fails on the "must redact" half.

**GREEN.** One line in `LABEL_MAP`:

```python
"FAC": "ADDRESS",
```

**Then assert end to end, not on the dict (§2.5).** `TYPE_THRESHOLDS["ADDRESS"]`
is `0.50`. If spaCy's FAC score sits below it, the mapping is a silent no-op
and every dict-level test still passes. Assert `scrub()` output.

**Item 3 silences item 2.** After this, `unmapped_labels()` must return `[]`
and the log must read "LABEL_MAP covers every label the model emits". Invert
the existing FAC assertions in `test_label_map.py` — do not delete them.

### Task 5 — full regression + itemisation

Six suites, selftest, three gates. **Every delta against §5 named
value-by-value before any new baseline is asserted.** Report ≤300 words.

### Task 6 — build + in-container verify

`--build-arg BUILD_VERSION=1.2.3 --platform linux/amd64`. In-container
`/v1/info` must read exactly `1.2.3` and carry `unmapped_labels: []` after a
selftest. Re-run the three gates against the container.

### Task 7 — ⛔ REVIEW GATE

**Nothing has been pushed.** Deliverable: this plan's §5 table with measured
values beside predicted ones, the itemised `over_detections` delta, and the
probe batch results. **The reviewer decides whether 1.2.3 ships.**

### Task 8 — publish + deploy

Only after Task 7. Push image, repoint template to `:1.2.3` (rollback comment
names `1.2.2`), push branch, hand AI Core to the human in finding-16 order:
delete `da1b1b3e39367c59`, poll until gone, create clean.

---

## 8. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **`FAC` → `ADDRESS` over-redacts SAP facility nouns** | Medium | **High** — unreadable KB entries on the batch path | Probe batch's "must NOT redact" half, drawn from real control samples; four burned gates as backstop |
| R2 | Mapping lands but the span never redacts (threshold) | Medium | High — a silent no-op that every dict test passes | Task 4 asserts `scrub()` output end to end |
| R3 | A probe line does not actually produce a FAC span | **High** — three of eight 1.2.1 frames hit this | Medium | Task 3 verifies each line produces FAC *before* item 3 lands |
| R4 | A burned gate rises and gets rubber-stamped as "item 3 working" | Medium | High | §5 predicts direction per set; every delta attributed value-by-value |
| R5 | Item 1's param defaults diverge from what `get_analyzer()` passes | Low | Medium | Test asserts the **call site**, not only the function |
| R6 | `/v1/info` field forces an eager model load | Low | Medium — kills instant `/health` | D5; `null` before first build is the design |
| R7 | Stop/create race on the 1-pod tier | Medium | High | One cutover for three items; delete, confirm gone, create |
| R8 | Something ships before review | Low | High — it happened in 1.2.2 | Task 7 is a hard stop; §6 restates it |

---

## 9. Rollback

Code: `git revert` per task; item 3 alone is one line.
Image: `1.2.2` stays in the registry; the template's mutable tag means
reverting the template commit is the whole rollback. **Blind spot unchanged:**
`BUILD_VERSION` detects template-to-pod drift, not tag mutation — only the
digest catches a re-push of the same tag.

Known-good: `da1b1b3e39367c59` on `1.2.2`, selftest `1.2.2 / 100.0 / 45/45 /
missed 0 / over_detections 4`.

---

## 10. What NOT to do

- **Do not tune against the four burned sets.** Build from the class
  description in §3.2, verify on the fresh probe batch, then re-run the gates.
- **Do not map any label other than `FAC`.** Three items, frozen.
- **Do not delete the FAC assertions in `test_label_map.py`** — invert them.
  A deleted assertion is a lost record of why the code is that way.
- **Do not make the analyzer load eagerly** to make item 2 tidier.
- **Do not push before Task 7.**
- **Do not quote any figure from this release.** All four sets are burned and
  the probe batch is a verification batch. The only work that changes what is
  *known* remains an externally authored blind batch, run once.

---

## 11. Answered at Gate 0 — pending

Q1, Q2 and Q3 from §4 are open and binding once answered.

---

## Appendix A — the FAC incidence probe

Supplied by review, 2026-08-16. Across all 145 samples of
`holdout_samples.json`, `eval_samples_v2.json` and `holdout_v3.json`:

| Span | Class | False positive? |
|---|---|---|
| `Victoria Street` | street name | no |
| `Willis Street` | street name | no |
| `Great South Road` | street name | no |
| `Foveaux Street` | street name | no |

4 spans, 4 street names, **zero false positives**. This is the measured
incidence and false-positive rate that satisfies the promotion rule in §2.4.

**Reproduce before relying on it** (Task 0): the probe is the entire evidence
base for a detection change, and it was measured by someone else. Verified
independently on the pinned stack (presidio 2.2.357 + `en_core_web_sm`): `FAC`
is emitted, unmapped and unignored.

## Appendix B — Quick reference

```bash
source .venv/bin/activate

# baselines
for t in test_fixes test_address test_customer_number test_jargon \
         test_build_version test_label_map; do python $t.py | tail -1; done

BUILD_VERSION=1.2.3-local uvicorn app:app --host 127.0.0.1 --port 8080 &
curl -s localhost:8080/v1/info | python3 -m json.tool | head -6

SCRUB_URL=http://127.0.0.1:8080/v1/scrub python3 test_deployed.py holdout_samples.json  # 108/111
SCRUB_URL=http://127.0.0.1:8080/v1/scrub python3 test_deployed.py eval_samples_v2.json  # 65/68 -- watch this one
SCRUB_URL=http://127.0.0.1:8080/v1/scrub python3 test_deployed.py holdout_v3.json       # 45/50
SCRUB_URL=http://127.0.0.1:8080/v1/scrub python3 test_deployed.py fac_probe_samples.json

# build -- AFTER the review gate
docker buildx build --platform linux/amd64 --build-arg BUILD_VERSION=1.2.3 \
  -t ghcr.io/terusin71/pii-scrubber:1.2.3 --load .
```
