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
| 8 | Three gates **exactly** `108/111`, `65/68`, `45/50`. **Any movement, either direction, is a stop** | local + container |
| 9 | Suites all exit 0 at their stated counts | local |
| 10 | Image `linux/amd64`, in-container `/v1/info` reads exactly `1.2.3` | registry + container |

**Criterion 8 keeps the exact-gate rule intact.** An earlier draft proposed
relaxing it to "must not fall, rises attributed afterwards". **Rejected at
Gate 0, and the reason is better than the proposal:** independent probes show
no gate should move at all (§5, Appendix A), so no relaxation is needed — and
"attributed afterwards" would have reintroduced precisely what §5 exists to
prevent, a number acquiring its explanation after it moved.

⚠️ **Item 3's observable effect on every existing gate is ZERO by design.**
This is not a weak result and not an anticlimax — it is the predicted pass.
Item 3's value is the **unnumbered-street class** ("the warehouse on Willis
Street"), which **no current evaluation set contains**. Blind batch v4 will
salt it. A release whose correctness criterion is "nothing moved" is exactly
what a promotion looks like when its target class is absent from every set
you already own.

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
3. **Pre-register the specific values, not the direction.** A deliberate
   promotion names **which values it expects to flip**, derived from
   measurement, **before the run**. A pre-registered flip is a pass. An
   unregistered flip is a stop — *including a rise*, exactly as a fall is.
   "Rises are fine if attributed afterwards" is rejected: it lets a moved
   number acquire its explanation retroactively, which is the failure this
   principle exists to prevent. Established at Gate 0 of 1.2.3; applies to
   every future promotion.
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

**Corrected at Task 0. The incidence is 8 spans, not 4.**

| Corpus | Sample | FAC span | Nested inside (already redacted) |
|---|---|---|---|
| `holdout_samples` | HO-006 | `Willis Street` | `22 Willis Street` |
| `holdout_samples` | HO-033 | `Great South Road` | `Unit 7, 156 Great South Road, Otahuhu, Auckland 1062` |
| `eval_samples_v2` | V2-001 | `Kauri Street` | `27 Kauri Street, Onerahi, Whangarei 0110` |
| `eval_samples_v2` | V2-003 | `Victoria Street West` | `Private Bag 92019, Victoria Street West, Auckland 1142` |
| `eval_samples_v2` | V2-004 | `Kaiwharawhara Road` | `44 Kaiwharawhara Road, Wellington` |
| `eval_samples_v2` | V2-059 | `Kauri Street` | `27 Kauri Street, Onerahi` |
| `holdout_v3` | V3-026 | `Foveaux Street` | `45 Foveaux Street, Surry Hills NSW 2010` |
| `samples.json` | TKT-0002 | `Victoria Street` | `44 Victoria Street, Wellington 6011` |

**8 of 8 are street names. 8 of 8 are nested inside an already-planted,
already-redacted ADDRESS value. Zero appear in a control sample. Zero false
positives.** On these corpora `FAC` *is* the ADDRESS class.

### A.1b — provenance of the 4 → 8 correction

The original probe reported 4 spans and described the scan as covering all
145 samples of the three evaluation sets. It in fact covered **3 of the 4
corpora**: `eval_samples_v2.json` is gitignored and local-only, so it was
never in the reviewer's sandbox — and v2 holds **exactly the 4 spans that
were missing** (`Kauri Street` ×2, `Victoria Street West`,
`Kaiwharawhara Road`). The original 4 are precisely the spans *outside* v2,
which is what makes the gap self-explaining rather than mysterious.

`Victoria Street` was also attributed to the evaluation sets; it is in
`samples.json`, the 13-sample selftest corpus.

**The conclusion strengthened rather than survived.** The merge argument was
made from one span and now holds for all eight: every FAC span in every
corpus is nested inside a value the address recognizer already covers, so
mapping `FAC` creates no new redacting span anywhere. Verified span-by-span,
not sampled.

**The lesson is about scan scope, not arithmetic.** A scan that cannot see a
gitignored corpus is not a complete scan, however carefully it is run — and
the corpora deliberately kept out of the repo are exactly the ones a reviewer
lacks. Any incidence claim must name the corpora it read.

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
| D9 | Gate rule under a deliberate detection change | **Exact gates, unchanged.** Pre-register the specific values expected to flip; here, none | The proposed relaxation assumed a gate would legitimately rise. Measurement says none will, so relaxing the rule would trade the project's strongest guard for nothing. |

### Answered at Gate 0 — 2026-08-16, binding

| # | Question | Answer |
|---|---|---|
| Q1 | Relax the gate rule to "must not fall, rises attributed"? | ⛔ **REJECTED.** Probes show no gate should move, so the relaxation buys nothing and would let a moved number acquire its explanation retroactively. **Exact gates stand.** The general rule it produced is now principle §2.3: a promotion pre-registers the *specific values* expected to flip, from measurement, before the run — an unregistered rise is a stop, same as a fall. |
| Q2 | Is a Claude-authored FAC probe batch acceptable? | ✅ **YES** — a **development verification set**, same standing as the Gate-2 address verify batch: fine to build against, **never quotable**. R3 applies with a tightening: each probe line must produce a `FAC` span **in the pinned container**, not merely in the venv, before it counts as a test. |
| Q3 | Is an `over_detections` change acceptable? | ✅ **YES, itemised, with a tightening.** Any new over-detection must be **`ADDRESS`-typed and traceable to the mapping**. A new over-detection of **any other type is a stop.** Expected per the probes: no change. |

---

## 5. Pre-registration — every value, written before anything runs

**The registered prediction is: nothing moves.** Not "probably nothing" —
nothing, on every existing measurement, derived from probes rather than
optimism.

| Measurement | Registered value | Any other value |
|---|---|---|
| Selftest `recall_pct` / `redacted` | `100.0` / `45/45`, `missed 0` | ⛔ stop |
| Selftest `over_detections` | **`4`** — unchanged | see the tightening below |
| Selftest `redacting_spans_emitted` | **`49`** — unchanged | ⛔ stop |
| `holdout_samples.json` | **`108/111`**, leaks `ZHANG` `Young` `Mere Tuhoe` | ⛔ stop, rise or fall |
| `eval_samples_v2.json` | **`65/68`**, leaks `44 Bellbird Rise` `Okonkwo` `FONTAINE` | ⛔ stop, rise or fall |
| `holdout_v3.json` | **`45/50`**, five known leaks | ⛔ stop, rise or fall |
| Suites | **16 · 39 · 33 · 74 · 29 · 37** — re-pinned at Task 5b, see below | ⛔ stop |
| `test_label_map.py` | ~~`FAC` flips from *reported* to *not reported*; `unmapped_labels()` → `[]`~~ | ~~**This is the one registered flip in the release**~~ ⛔ **CANCELLED — see below** |

### 🔁 SUITE COUNTS RE-PINNED — 2026-08-16, Task 5b

**This row was stale, and the exact-gate rule did not catch it.**

| Pinned | Value | Why it moved |
|---|---|---|
| Gate 0 (original) | `16 · 39 · 33 · 74 · 17 · 13` | the 1.2.2 baseline |
| after items 1-2 (`24eaef3`, `3adaeaa`) | `16 · 39 · 33 · 74 · 22 · 23` | +5 `/v1/info` and wiring tests, +10 diagnostic tests — **by design, and never re-pinned here** |
| **after Task 5b (current)** | **`16 · 39 · 33 · 74 · 29 · 37`** | +7 payload-semantics assertions, +14 correction-pinning assertions |

The Gate-0 row stayed at `17 · 13` while items 1 and 2 had already moved it to
`22 · 23`. It was in breach from `24eaef3` onward and went unnoticed through
two commits and a handover. It surfaced only at Task 5 because the gate
compared against **this written registration** rather than against the
previous run — which is the entire argument for writing registrations down.

**Standing rule adopted (HANDOVER, "Settled"):** a registered number is
re-pinned in the **same commit** that moves it, so *registered* always means
*registered as of HEAD*. A stale registration is worse than none — it silently
downgrades an exact gate to "compare against whatever printed last time".

⚠️ **The four evaluation gates below were never stale and have not moved:**
`108/111 · 65/68 · 45/50 · selftest 100.0 / 45/45 / 0 / 4 / spans 49`. Suite
counts move when tests are added deliberately; **gate values do not move at
all.** The two are different kinds of number and the rule change does not
soften the second.

### ⛔ CANCELLATION of the one registered flip — 2026-08-16, reviewer-confirmed

**The `["FAC"] → []` flip registered above is CANCELLED, together with item 3.**

Scope of 1.2.3 was reduced by the reviewer, confirmed by Teru, to **Tasks 1-2
plus corrections**. Item 3 (`FAC → ADDRESS` in `LABEL_MAP`) is **withdrawn**;
the original Task 4 that would have landed it is **dead**. The flip was
registered *against the mapping commit*, and with no mapping commit there is
nothing to flip.

**The registered value is therefore now: `unmapped_labels()` stays `["FAC"]`,
and `/v1/info` ships `["FAC"]`.** `FAC` remains *reported* in
`test_label_map.py`. Both were already true before this release; the release
does not move them.

**Why it was withdrawn — the mapping was measured to be a no-op, not merely
unproven.** `FAC` never reaches `LABEL_MAP`: `SpacyRecognizer` does not
declare support for the entity, so the span is dropped at the recognizer.
Proven ephemerally in the pinned container — `detect()` returns `[]` both
before and after the mapping. Record: `fac_probe_validation.md`, commit
`250cdf8`.

**This cancellation is recorded rather than deleted, deliberately.** The
original registration stays struck through above. A pre-registration that
quietly disappears when its change is dropped is indistinguishable from one
that was never made, and the record of *what was predicted and why it was
withdrawn* is the only thing that makes the next pre-registration credible.

**Nothing else in this table changes.** All four measurements below remain
registered exact, and the withdrawal of item 3 strengthens rather than
weakens that prediction: the release now contains no detection surface at all.

### Why `44 Bellbird Rise` does NOT move

An earlier draft called it "the single most likely legitimate movement".
**Wrong, and the probe says so:** on the pinned stack `sm` emits no `FAC` span
for that sentence at all — it yields `Driver`/ORG, `44`/CARDINAL, `DC`/GPE.
Its leak was never a FAC drop, so item 3 cannot close it. It stays leaked, and
the gate stays `65/68`.

⚠️ **Task 0 must re-probe this from the actual `eval_samples_v2.json`** — the
sentence behind the probe was reconstructed from run output, not read from the
file. If the real sample differs, this prediction is void and the plan returns
to Gate 0.

### Why the selftest does not move

`samples.json` contains exactly one `FAC` span — `Victoria Street` in
`TKT-0002` — and it sits **inside** the planted value
`44 Victoria Street, Wellington 6011`, which is already redacted by the
address recognizer. Post-mapping the two spans **merge** rather than adding
one. Hence `over_detections 4` and `spans 49`, both unchanged.

### The over-detection tightening (Q3)

If `over_detections` moves at all, the new detection must be **`ADDRESS`-typed
and traceable to the mapping**. A new over-detection **of any other type is a
stop** — nothing else in this release changes detection, so another type
moving means something unintended shipped.

### What item 3 actually buys, given nothing moves

The **unnumbered-street class**: "the warehouse on Willis Street". It exists in
no current evaluation set, which is exactly why no gate has ever failed on it
and why the defect survived three releases. It is measured by the Task 3 probe
batch now, and **blind batch v4 will salt it** — that is where the class earns
a real number, authored externally and run once.

---

## 6. Global Constraints

- **Rule 3:** no outbound calls. No bare `AnalyzerEngine()`.
- **Rule 7:** no dependency changes.
- **Rule 4:** no real ticket text. The probe batch is synthetic and
  **COMMITTED — not gitignored.** ⚠️ *Amended 2026-08-16 at Task 3; the
  original line said gitignored and was wrong.* Burned and blind sets are
  kept out of the repo because **visibility destroys them** — a holdout
  anyone can read while tuning stops measuring anything. A **development
  verification set is the opposite: visibility is its purpose.** It exists to
  be built against and re-run, so hiding it defeats it. The precedent is
  `address_verify_samples.json`, the Gate-2 address batch, which is tracked —
  and Q2 assigned this batch "the same standing". The original error came
  from pattern-matching "evaluation set → gitignore" without asking which
  kind of set it is.
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

`fac_probe_samples.json`, **committed** (see the amended Rule 4 in §6), with a
`_provenance` block stating it is agent-authored and verification-only. Two
halves, both required.

⚠️ **Control sourcing amended 2026-08-16.** The original text sourced
negative controls from "the control samples" — i.e. the burned corpora. Task
3 keeps those **closed**, so controls come instead from **(a)** `HANDOVER.md`'s
named trap list, **(b)** `glossary.txt`, **(c)** `test_address.py` /
`test_jargon.py`, and **(d)** fresh authorship in business-document register.
**Every control records its provenance, and none may claim corpus-observed
provenance** — the burned sets were not read.

This is a smaller loss than it looks: **a control's evidence is the container
observation, not where its string came from.** Corpus-string coverage is
already held, with stronger standing, by the Task-5 exact gates — which run
against all four corpora and must not move.

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
lands, IN THE PINNED CONTAINER.** A probe line that spaCy does not tag `FAC`
tests nothing and would pass before the feature exists — the exact false-pass
that three of eight 1.2.1 glossary frames hit. The venv and the image are not
guaranteed to agree; the image is what ships, so the image is what counts.

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
| R2 | Mapping lands but the span never redacts (threshold) | **Low** | High — a silent no-op that every dict test passes | Presidio's spaCy recognizer assigns a fixed NER strength (~0.85), which clears the `0.50` ADDRESS floor. **Likelihood downgraded on that basis, but Task 4 still proves it on `scrub()` output** — an inherited assurance is not a measurement, and this project has been wrong about inherited assurances before |
| R3 | A probe line does not actually produce a FAC span | **High** — three of eight 1.2.1 frames hit this | Medium | Task 3 verifies each line produces FAC *before* item 3 lands, **in the pinned container** — venv agreement is not container agreement (Q2) |
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

### A.2 — two probes that predict ZERO gate movement

Both supplied by review on the pinned stack. Together they are why §5
registers "nothing moves" rather than "something might".

| Probe | Result | Consequence |
|---|---|---|
| **`44 Bellbird Rise`** (the known v2 ADDRESS leak) | **No `FAC` span at all.** `sm` yields `Driver`/ORG, `44`/CARDINAL, `DC`/GPE | Its leak was never a FAC drop. Item 3 **cannot** close it. `eval_samples_v2.json` stays `65/68` |
| **`Victoria Street`** (`samples.json`, `TKT-0002`) | The only `FAC` span in the selftest corpus, and it sits **inside** the planted `44 Victoria Street, Wellington 6011`, already redacted | Post-mapping the spans **merge** instead of adding one. `over_detections 4` and `spans 49` unchanged |

⚠️ **The Bellbird sentence was reconstructed from run output, not read from
the file.** Task 0 re-probes it from the actual `eval_samples_v2.json`. If the
real sample differs, §5's registration is void and this plan returns to
Gate 0 — a pre-registration built on a remembered sentence is not a
pre-registration.

### A.3 — what the evidence does NOT say

It does not say `FAC` is worth mapping *because a gate improves*. No gate
improves. It says `FAC` on this corpus is the ADDRESS class with a 4/4 hit
rate and no false positives, and that the class it protects — unnumbered
street references — is **absent from every set currently owned**. The
promotion is justified by incidence and precision, not by a moved number.

**Reproduce before relying on any of it** (Task 0). This is the entire
evidence base for a detection change and it was measured by someone else.
Independently confirmed so far on the pinned stack (presidio 2.2.357 +
`en_core_web_sm`): `FAC` is emitted, unmapped and unignored.

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
