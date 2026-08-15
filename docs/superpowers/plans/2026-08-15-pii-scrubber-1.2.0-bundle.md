# PII Scrubber — 1.2.0 Bundle Implementation Plan

**Gate 0 deliverable. Nothing in this plan has been executed.**
Authored 2026-08-15 against `e1d46a9`. Scope frozen by the user at three items.

---

## 1. Executive Summary

**Goal.** Ship one image, `1.2.0`, carrying three changes — an unpadded
customer-number fix, a hand-curated SAP jargon glossary, and a default model
change to `en_core_web_lg` — through a single stop/create cycle on the
1-pod free tier.

**Why one image.** Free tier allows one pod. Every deployment change costs a
stop/create cycle, and a stop-then-create race marks the new revision failed
**permanently** (finding: Kubernetes never re-drives an admission-rejected
revision). Three deploys is three chances to hit that. One is one.

**Success criteria — all measurable, all blocking:**

| # | Criterion | Source of truth |
|---|---|---|
| 1 | `/v1/selftest` returns `recall_pct 100.0`, `45/45`, `missed 0`, `over_detections 6` | deployed endpoint |
| 2 | `test_fixes.py` 16/16 exit 0 | local + in-container |
| 3 | `test_address.py` 39/39 exit 0 | local + in-container |
| 4 | `test_customer_number.py` all pass (new) | local |
| 5 | `test_jargon.py` all pass (new) | local |
| 6 | Holdout regression **exactly 109/111**, leaks exactly `ZHANG` and `Young` | regression check only — see §12 |
| 7 | v2 regression **exactly 66/68** | regression check only — see §12 |
| 8 | Container survives `--memory=3g` with `SPACY_MODEL=en_core_web_lg` | §7 Task 5 |
| 9 | Image is `linux/amd64`, verified by `docker buildx imagetools inspect` | registry |
| 10 | Deployment reaches `RUNNING` on one clean create | AI Core API |

**Time estimate.**

| Task | Budget | Risk |
|---|---|---|
| 0 — Gate 0 approval | — | none |
| 1 — customer-number fix | 45 min | local |
| 2 — jargon glossary | 90 min | local |
| 3 — `SPACY_MODEL` default | 15 min | local |
| 4 — invariant + regression | 30 min | local |
| 5 — Docker build + 3 GB container test | 60 min | local, ~3 min build |
| 6 — publish image | 30 min | ⚠️ mutates remote |
| 7 — deploy handoff | 45 min | ⚠️ BTP, user drives |

Total ≈ 5 hours across at least two sessions. Tasks 6 and 7 do not start in
the same session that finished Task 5 without a fresh gate.

**Risk posture.** Conservative. Items 1 and 2 change detection behaviour and
can over-redact; item 3 doubles memory. Any one of the three can be dropped
from the bundle without blocking the other two — see §5.

---

## 2. Philosophy and Principles

1. **Evidence before action.** Every claim in §3 was verified at authoring
   time with a shown command. A number without a command next to it is a
   guess and must be re-measured before use.
2. **The plan is the authorization.** Steps outside this document need a new
   gate. Scope is frozen at three items; a fourth is a new plan.
3. **The floor does not move.** `DEFAULT_THRESHOLD` and `TYPE_THRESHOLDS`
   govern every recognizer. Admitting one entity type by lowering a global
   floor admits every sub-threshold span in the pipeline, and a
   type-specific test would never reveal it.
4. **Suppression is more dangerous than detection.** The glossary makes the
   scrubber redact *less*. Every entry is a potential leak. Entries are
   proved individually, not assumed as a list.
5. **Red path is honorable.** If the 3 GB container OOMs, item 3 drops and
   the bundle ships as two items. That is a success, not a failure.
6. **Burned sets are regression checks, not measurements.** See §12. Numbers
   from `holdout_samples.json` and `eval_samples_v2.json` after this bundle
   are pass/fail gates against an exact expected value, never quotable
   figures.
7. **One stop/create cycle.** Stop and delete old, confirm empty, create
   config, create deployment — in that order, nothing else in existence.

---

## 3. Current State — verified ground truth

All verified 2026-08-15 against `e1d46a9` unless stated.

### 3.1 Deployed

| Item | Value |
|---|---|
| Deployment | `d5e6ea76217ed207`, RUNNING |
| Image | `ghcr.io/terusin71/pii-scrubber:1.1.0`, `linux/amd64`, `sha256:070dea2c…f38290` |
| Rollback image | `1.0.0`, `sha256:8e779fde…f026a1b` |
| Scenario / executable | `pii-scrubber`, version `1.0` |
| ServingTemplate | `workflows/serving_template.yaml`, **mutable tag** (deliberate) |

### 3.2 Baselines that must not move

```
/v1/selftest      recall_pct 100.0 · 45/45 · missed 0 · over_detections 6
test_fixes.py     exit 0, 16 ok, 0 FAIL
test_address.py   exit 0, 39 ok, 0 FAIL
```

### 3.3 Item 1 — the customer-number cause was misdiagnosed

**Correction.** Earlier notes in `docs/HANDOVER.md` and the Gate brief state
that `sap_customer_ctx` scores 0.35 against a 0.50 floor. **That is not the
failure mode.** Verified today with the raw recognizer:

```
'Sales order rejected for customer 2298871 ...'  -> NO MATCH
'Credit block for account 0001045567 ...'        -> [('0001045567', 0.85)]
'Customer 1045567 short-dumping in VA02.'        -> NO MATCH
```

`recognizers.py:19-29` holds exactly two patterns:

```python
Pattern(name="sap_customer_padded", regex=r"\b000\d{7}\b", score=0.85)
Pattern(name="sap_customer_ctx",    regex=r"\b\d{10}\b",   score=0.35)
```

Both require **ten** digits. Every known unpadded value is **seven**:

| Value | Digits | Source |
|---|---|---|
| `1045567` | 7 | HO-009 |
| `2298871` | 7 | V2-028 |
| `4471902` | 7 | V2-029 |

**Nothing matches, so there is no score to raise.** The instruction "raise
`sap_customer_ctx`'s own score when its context gate matches" cannot be
executed as written — the gate never fires. The *intent* of the constraint
(never move the global floor) is preserved and hardened in §2.3 and in the
implementation below.

### 3.4 Item 2 — the jargon class, as measured

From the v2 batch controls (which must redact nothing):

```
"raising it with Basis"   -> <ORG_NAME>
"routed to Basis"         -> <ADDRESS>     same word, different type
"Driver could not find"   -> <ORG_NAME>
"3 Way match"             -> 3 <ORG_NAME> match
```

The allowlist is matched **case-sensitively on the span text**, in
`app.py detect()`, and suppression is refused when `_in_user_context` matches.
Critically: the token compared is the **whole span**, not a word inside it.
Whether allowlisting `Rise` affects a span reading `Bellbird Rise` is
therefore an empirical question — Task 2 proves it, does not assume it.

### 3.5 Item 3 — the lg evidence, measured today

15 PERSON values (12 from v2, 3 from the holdout), original sentences, full
pipeline, one model per process:

```
sm 10/15 · lg 12/15 · recovered 2 · regressed 0
recovered: Mere Tuhoe (HO-031), FONTAINE (V2-038)
still leaking under both: ZHANG, Young, Okonkwo
```

Cost, measured on this machine:

| Model | Peak RSS | Cold load | On disk |
|---|---|---|---|
| `en_core_web_sm` | 421 MB | 3.1 s | 15 MB |
| `en_core_web_lg` | 920 MB | 3.4 s | 433 MB |

Starter plan is **1 vCPU / 3 GB** (user, per SAP docs). 920 MB fits with
margin on paper. Task 5 proves it in a capped container before push.

### 3.6 Environment

- System Python 3.14.3 cannot install the pins. Use `uv venv --python 3.12 --seed .venv`.
- `.venv` present, Python 3.12.13, `en_core_web_sm` **and** `en_core_web_lg` installed.
- Disk: 14 GB available of 228 GB. `docker system prune` is **forbidden** —
  an unrelated `frappe_docker` stack is present.
- Apple Silicon host, AI Core is x86_64. Always `--platform linux/amd64`.

---

## 4. Decision Matrix

| # | Condition, observed at | Action |
|---|---|---|
| D1 | Task 1 unit tests pass but selftest `over_detections` > 6 | Customer pattern is over-firing. Tighten the cue list; do not accept a new baseline. |
| D2 | Task 2: allowlisting a street-type word suppresses a real ADDRESS span | That word **does not enter the glossary.** Record it in the plan appendix as proven-unsafe. |
| D3 | Task 2 glossary lands but `over_detections` drops below 6 | Expected and good, but the self-test invariant asserts recall not over-detection — record the new number, do not treat as failure. |
| D4 | Task 2 glossary causes any selftest recall loss | **Stop.** A suppression entry has created a leak. Bisect the glossary. |
| D5 | Task 5 container OOMs or is killed at `--memory=3g` | **Item 3 drops from the bundle.** Revert `SPACY_MODEL` default to `sm`, rebuild, continue with two items. |
| D6 | Task 5 passes but cold start exceeds the readiness probe | Raise the probe delay in `serving_template.yaml`, do not shrink the model. |
| D7 | Task 4 holdout ≠ 109/111 or v2 ≠ 66/68 | **Stop and report.** Any deviation, in either direction, is unexplained behaviour. |
| D8 | Build dies with `lease does not exist: not found` | Corrupted BuildKit lease. `docker pull` the base image, rebuild unchanged. Not disk, not network. |
| D9 | Registry push 403 | Scope problem, not auth. Pushing needs `write:packages`; the pull secret needs `read:packages`. GitHub's 403 distinguishes neither. |

---

## 5. Bundle composition and drop order

Each item is independently revertible **before** Task 5. Drop order if
anything forces a reduction:

1. **Item 3 (lg)** drops first — biggest cost, smallest measured benefit
   (+2 of 15 on a hard slice; +0.9 pts on the holdout). Pure config change,
   one line.
2. **Item 2 (glossary)** drops second — it makes the scrubber redact less,
   which is the direction that can create leaks.
3. **Item 1 (customer fix)** never drops — it closes the only remaining leak
   class rules can reach, and it only makes the scrubber redact *more*.

---

## 6. Global Constraints

- **Rule 1** — the plan authorizes; steps outside it need a new gate.
- **Rule 3** — no outbound calls from inside the boundary at inference time.
  `en_core_web_lg` must be **baked into the image**, never downloaded at
  runtime. Never construct a bare `AnalyzerEngine()`.
- **Rule 4** — no real ticket text or mined tokens in the repo.
- **Rule 7** — dependency pins change only with approval. Item 3 adds a model
  package to the image, which **is** a dependency change and is covered by
  this plan's approval, not by a later ad-hoc decision.
- `samples.json`, `REDACT_TYPES`, `TYPE_THRESHOLDS`, `DEFAULT_THRESHOLD` and
  `ZY_SURNAME_GUARD` are **not touched by this bundle.**

---

## 7. Per-Task Runbook

### Task 0 — Gate 0 · this document

**Approval gate:** user approves scope, the §3.3 correction, and the item-1
implementation shape below. No code until then.

---

### Task 1 — Unpadded customer numbers · ~45 min · local

**Goal.** Detect 6–9 digit customer numbers when, and only when, a customer
cue immediately precedes them.

**Why not a bare `\d{6,9}` pattern.** SAP text is full of 6–9 digit
technical numbers — material numbers, delivery numbers, document numbers. A
bare pattern would over-redact heavily and the self-test would catch some of
it, but not all.

**Why not Presidio's `context=` enhancer.** It boosts by a fixed amount
anywhere in the sentence. Too loose for a number this generic.

**Why not a post-pass in `app.py`.** Tried for the person promoter and
recorded as a negative result (`PERSON-CONTEXT-FINDING.md`). Keep detection
in the recognizer layer.

**Shape: one Pattern per cue, each with a fixed-width lookbehind.** Python's
`re` allows a lookbehind only if it is fixed width, but each *pattern* can
carry its own. This keeps the cue out of the redacted span — the failure
that forced the person promoter out of the recognizer layer.

```python
# Sketch for review, not final code.
_CUST_CUES = ["customer ", "sold-to ", "sold to ", "payer ", "bill-to ",
              "ship-to ", "debtor ", "kunnr ", "account "]
patterns += [
    Pattern(name=f"sap_customer_unpadded_{i}",
            regex=rf"(?<={re.escape(c)})\d{{6,9}}\b",
            score=0.75)
    for i, c in enumerate(_CUST_CUES)
]
```

Score 0.75 clears the 0.50 `CUSTOMER_NO` floor on its own. **The floor is not
touched.** Presidio's default `IGNORECASE` makes the cue case-insensitive,
which is wanted here (`Customer` / `customer`).

**Steps**

1. Write `test_customer_number.py` **first**. Positives: the three known
   unpadded values in fresh sentences plus at least four new ones across
   different cues. Negatives, asserted against the **raw recognizer** (not
   merged output — trap 7): `movement type 601`, `plant 4000`,
   `Storage location 0001`, `Order 4500001234 Line 10`, `material 1234567`
   with no customer cue, `40 open transfer orders`.
2. Run it. Confirm it **fails**.
3. Implement in `recognizers.py`.
4. Run it. Confirm it passes.
5. `test_fixes.py` 16/16, `test_address.py` 39/39, selftest `45/45` and
   `over_detections 6`.

**Approval gate:** report new-test result, the three invariants, and
`over_detections`. Wait before Task 2.

---

### Task 2 — SAP jargon glossary · ~90 min · local

**Goal.** Stop redacting SAP module names, role nouns and technical jargon
as `<ORG_NAME>` / `<ADDRESS>`, without creating a leak.

**Mechanism.** Append to `allowlist.txt`, which is already case-sensitive
exact-match and already vetoed by `_in_user_context` — so
`posted by Driver` still redacts while `Driver could not find` does not.
No code change if the existing mechanism suffices; prove that first.

**Steps**

1. Write `test_jargon.py` **first**, with three groups:
   - **must stop redacting**: `Basis`, `Driver`, `3 Way match`, plus the v2
     control sentences verbatim.
   - **must still redact** (leak guard): a person named `Driver` in an agent
     slot; `posted by BASIS`; every positive in `test_address.py` re-asserted.
   - **street-type safety**: for each candidate street-type word, assert that
     a real address containing it still redacts end to end —
     `14 Sunrise Close, Papakura`, `19 Kereru Court, Rotorua`,
     `8 Harbour Way, Whangarei 0110`, `48 Rimu Road, Papakura`, and the
     documented-gap `44 Bellbird Rise` (which is expected to stay unmatched;
     assert it does not *newly* break anything else).
2. Curate 100–200 entries by category: module names (`Basis`, `ABAP`,
   `Fiori`, `HANA`), role nouns (`Driver`, `Planner`, `Buyer`, `Picker`),
   process nouns (`Way`, `Match`, `Batch`, `Wave`, `Bin`, `Rack`), and
   document nouns. **Each entry is added, tested, kept or rejected — one at
   a time for the ambiguous ones.**
3. **Street-type words are guilty until proven innocent.** `Way`, `Rise`,
   `Close`, `Court`, `Terrace`, `Drive`, `Place`, `View`, `Row` enter the
   glossary only if step 1's street-type group still passes with them in.
   Any that breaks an address is recorded in Appendix A as proven-unsafe and
   left out.
4. Run the full suite plus selftest.

**Approval gate:** report entries added, entries rejected as unsafe with the
address they broke, the three invariants, and the new `over_detections`.

---

### Task 3 — `SPACY_MODEL` default → `en_core_web_lg` · ~15 min · local

**Steps**

1. `app.py:38` default `en_core_web_sm` → `en_core_web_lg`.
2. `Dockerfile`: bake `en_core_web_lg`. Rule 3 — it must be in the image,
   never downloaded at runtime. Keep `en_core_web_sm` installed as the
   documented fallback for D5.
3. Re-run the three invariants under the new default. **`over_detections`
   is expected to change** — lg types differently (`Anne-Sophie Bouchard`
   ORG_NAME → PERSON, `MBEKI` ORG_NAME → ADDRESS). Record the new number;
   recall is the invariant, not over-detection.

**Approval gate:** report the three invariants and both `over_detections`
values, sm and lg.

---

### Task 4 — Invariant + regression measurement · ~30 min · local

Run against a **local** service, not the deployment.

```bash
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8080 --workers 1 &
SCRUB_URL=http://127.0.0.1:8080/v1/scrub .venv/bin/python test_deployed.py holdout_samples.json
SCRUB_URL=http://127.0.0.1:8080/v1/scrub .venv/bin/python test_deployed.py eval_samples_v2.json
```

**Expected, exactly:**

| Set | Expected | Leaks expected |
|---|---|---|
| holdout | **109/111** | `ZHANG`, `Young` — nothing else |
| v2 | **66/68** | `44 Bellbird Rise`, `Okonkwo` — nothing else |

Any deviation **in either direction** is a stop (D7). A higher number is as
suspicious as a lower one.

**Approval gate:** report both, exact leak lists, and stop if either differs.

---

### Task 5 — Docker build + memory-capped container test · ~60 min · local

```bash
docker build --platform linux/amd64 -t pii-scrubber:1.2.0 .
docker buildx imagetools inspect ...            # confirm amd64, not arm64
docker run --rm --memory=3g --memory-swap=3g \
  -e SPACY_MODEL=en_core_web_lg -p 8080:8080 pii-scrubber:1.2.0
```

Then, against the container: `/health`, `/v1/selftest` (must be `100.0`,
`45/45`), `test_fixes.py`, `test_address.py`, and a handful of scrubs
covering each of the three changed behaviours. Watch for OOM-kill —
`docker inspect` exit code `137`.

A digest check cannot catch the arch problem: on an arm64 host an arm64
image round-trips perfectly and still cannot run on x86_64.

**Approval gate:** report platform, selftest, suite results, peak container
memory, and OOM status. **If OOM: D5 fires, item 3 drops, rebuild as
two items and re-run this task.**

---

### Task 6 — Publish · ~30 min · ⚠️ mutates remote

Tag and push `ghcr.io/terusin71/pii-scrubber:1.2.0`. Verify platform from the
registry, not locally. Credentials by env var at the moment of use; never
committed, echoed, or embedded in a git remote URL.

**Approval gate:** report the pushed digest and platform.

---

### Task 7 — Deploy · ~45 min · ⚠️ BTP · user drives

Same handoff as 1.1.0. ServingTemplate uses a mutable tag, so no template
change is needed. Order is **non-negotiable** — quota is 1 pod and a
stop-then-create race marks the new revision failed permanently:

1. Stop and **delete** the old deployment.
2. Confirm nothing is in existence.
3. Create the configuration.
4. Create the deployment.

Diagnose from the API, never the cockpit — the sync panel reads identically
on working and broken applications.

---

## 8. Acceleration Playbook

Ordered by leverage:

1. **Bundle the rebuild.** Already the plan's core: three changes, one
   stop/create cycle.
2. **Test-first on all three items** — the failing test is faster than
   diagnosing a passing one that proves nothing
   (`tests-from-same-model-as-code`).
3. **Emulated amd64 builds are cheap here (~3 min).** pip installs prebuilt
   manylinux wheels, so QEMU emulates almost nothing. Do not optimise this.
4. **Categorise the glossary before curating.** Module / role / process /
   document nouns, then batch-test per category; only the ambiguous
   street-type set needs one-at-a-time treatment.
5. **Reuse `test_deployed.py` for both regression sets.** One scorer, two
   files, no new tooling.

---

## 9. Risk Register

| # | Risk | L | I | Mitigation | Detection | Rollback |
|---|---|---|---|---|---|---|
| R1 | Glossary entry suppresses a real PII span → **leak** | M | **H** | One-at-a-time for ambiguous entries; leak-guard test group | selftest recall < 100.0; holdout ≠ 109/111 | Remove the entry from `allowlist.txt`, rebuild |
| R2 | Street-type words break address detection | **H** | M | Task 2 step 3 proves each one; guilty until proven innocent | `test_address.py` < 39 | Leave the word out; record in Appendix A |
| R3 | lg OOMs the 3 GB pod | L | **H** | Task 5 capped-container test **before** push | Exit code 137, or pod CrashLoop | D5: drop item 3, rebuild as two items |
| R4 | Customer pattern over-fires on technical numbers | M | M | Cue-gated lookbehind, not a bare digit pattern; raw-recognizer negatives | `over_detections` > 6; v2 controls gain redactions | Tighten `_CUST_CUES`, rebuild |
| R5 | Cue captured inside the redacted span | M | M | Fixed-width lookbehind per cue, asserted in the new test | `customer <CUSTOMER_NO>` becomes `<CUSTOMER_NO>` | Same shape as the person-promoter failure; see `PERSON-CONTEXT-FINDING.md` |
| R6 | arm64 image pushed | M | **H** | `--platform linux/amd64` + `imagetools inspect` from the registry | `exec format error` at pod start | Rebuild amd64, re-push same tag (mutable tag is why) |
| R7 | Stop/create race burns the pod quota permanently | M | **H** | Delete → confirm empty → create config → create deployment | Revision marked failed, never re-driven | Delete everything, start the cycle clean |
| R8 | lg cold start exceeds readiness probe | M | M | Measured 3.4 s locally, ~0.3 s over sm | Probe timeout in pod events | D6: raise probe delay, do not shrink the model |
| R9 | Registry 403 mistaken for auth failure | M | L | Scope checklist: `write:packages` to push, `read:packages` to pull | 403 on push or image resolution | Re-mint PAT with the right scope |
| R10 | Regression numbers quoted as measurements | M | **H** | §12; both sets marked burned in the handover | A report citing 109/111 as a result | Correct the doc; re-run the blind batch |
| R11 | `over_detections` treated as a target | L | M | §2.3 and D3 — recall is the invariant | A commit tuning toward a lower number | Revert the tuning commit |
| R12 | Disk exhausted mid-build | M | M | 14 GB free vs ~2.5 GB/image; **never** `docker system prune` | Build failure, no space | Remove only pii-scrubber images by digest |
| R13 | Model downloaded at runtime instead of baked | L | **H** | Rule 3; Dockerfile bakes lg; no bare `AnalyzerEngine()` | Outbound call from the pod | Rebuild with the model baked |

---

## 10. Rollback Runbook

Four scopes. Under stress, "rollback" without a scope is useless.

**Mid-task, nothing committed**
```bash
git checkout -- recognizers.py app.py allowlist.txt Dockerfile
```

**Branch-level, committed but not pushed**
```bash
git reset --hard e1d46a9        # the Gate 0 baseline
```

**Post-push, image published but not deployed** — no action needed. `1.2.0`
sitting unused in the registry costs nothing. Do not delete it; a published
digest is evidence.

**Post-deploy, 1.2.0 is live and wrong**
The ServingTemplate uses a **mutable tag**, which is exactly why:
1. Rebuild the corrected image, push as `1.2.0`, redeploy — no template change; **or**
2. Fall back to `1.1.0` (`sha256:070dea2c…f38290`) or `1.0.0`
   (`sha256:8e779fde…f026a1b`), both still in the registry.
Either path is one stop/create cycle. Observe the Task 7 ordering.

---

## 11. Verification Strategy

| Level | Command | Exit criterion |
|---|---|---|
| Unit — new | `python test_customer_number.py`, `python test_jargon.py` | exit 0 |
| Unit — regression | `python test_fixes.py`, `python test_address.py` | exit 0, **16/16** and **39/39** |
| Tuned-set invariant | `/v1/selftest` | `100.0`, `45/45`, `missed 0` |
| Regression sets | `test_deployed.py` × 2 against local | **exactly** 109/111 and 66/68 |
| Container | `docker run --memory=3g` + selftest + suites | no OOM (exit ≠ 137), selftest `100.0` |
| Platform | `docker buildx imagetools inspect` | `linux/amd64` |
| Deployed | `/v1/selftest` via AI Core | `100.0`, `45/45` |

**Make every check print what it inspected.** Three times this project a
check reported clean without running. A verdict with no evidence is not a
verification.

---

## 12. Verification honesty — plan for this now

**After 1.2.0, `holdout_samples.json` and `eval_samples_v2.json` are burned
for this bundle.** lg was chosen partly from their outputs; the
customer-number fix was built against their leaks. Neither can measure the
thing that was shaped by it.

Their role after this bundle is **regression gate only**: pass/fail against
an exact expected value (109/111, 66/68), never a quotable figure.

**The quotable number comes from a fresh blind batch authored outside this
session, which the executor must not see before the run.** Do not author one.
Do not expand v2 to serve this purpose. Any report from this bundle states
the regression numbers as regression numbers and leaves the headline figure
blank until the blind batch runs.

---

## 13. Close-out Checklist

- [ ] All ten success criteria green, with output pasted
- [ ] `docs/HANDOVER.md` updated: new image, new baselines, `over_detections`
- [ ] §3.3 correction propagated — the "0.35 vs 0.50 floor" claim removed
      from `docs/HANDOVER.md` wherever it appears
- [ ] Appendix A filled with proven-unsafe glossary entries
- [ ] `PERSON-CONTEXT-FINDING.md` unchanged (still accurate)
- [ ] Rollback images `1.0.0` and `1.1.0` confirmed still in the registry
- [ ] Blind batch run recorded separately, with its own provenance note
- [ ] Memory file written if a new durable lesson emerged

---

## 14. What NOT to do

- **Do not lower `DEFAULT_THRESHOLD` or any `TYPE_THRESHOLDS` entry.** Not
  for customer numbers, not for anything. It governs every recognizer.
- **Do not edit `samples.json`** to make the self-test pass. The self-test is
  asserted, never targeted.
- **Do not add a fourth item.** Scope is frozen at three.
- **Do not run `docker system prune`.** An unrelated `frappe_docker` stack is
  on this machine.
- **Do not download the spaCy model at runtime.** Bake it. Rule 3.
- **Do not construct a bare `AnalyzerEngine()`** — it resolves to
  `en_core_web_lg` and downloads it, and any figure from it is measured
  against the wrong configuration.
- **Do not tune against `holdout_samples.json` or `eval_samples_v2.json`.**
  They are regression gates now.
- **Do not chain Task 6 or 7 into the session that finished Task 5.**
- **Do not quote 109/111 or 66/68 as a result.**

---

## 15. Open Questions for User Review

1. **§3.3 correction** — the customer-number instruction was premised on a
   misdiagnosis I supplied. Confirm the cue-gated-lookbehind shape is
   acceptable, or specify a different one.
2. **Glossary size** — 100–200 was specified. If the safe set lands nearer
   60 after street-type words are rejected, ship the smaller set or widen
   the categories?
3. **`over_detections` after lg** — it will change, and the self-test asserts
   recall only. Do you want a *new* asserted over-detection number recorded
   as a baseline, or left as an observed value?
4. **`en_core_web_sm` in the image** — keep it installed as the D5 fallback
   (+15 MB) or strip it once lg passes?
5. **Task 6/7 session split** — same session with a gate between, or a fresh
   session for the remote-mutating tasks?
6. **Blind batch timing** — does it run against the deployed 1.2.0, or
   against a local 1.2.0 before push?

---

## Appendix A — Proven-unsafe glossary entries

*Filled during Task 2. Each row: entry, the address or PII value it broke,
and the test that caught it. Empty at Gate 0 by design.*

| Entry | Broke | Caught by |
|---|---|---|
| *(pending Task 2)* | | |

## Appendix B — Quick reference

```bash
# environment
uv venv --python 3.12 --seed .venv && source .venv/bin/activate

# the three invariants
python test_fixes.py            # 16/16
python test_address.py          # 39/39
# selftest: 100.0 / 45/45 / over_detections 6

# regression sets (local service, not the deployment)
SCRUB_URL=http://127.0.0.1:8080/v1/scrub python3 test_deployed.py holdout_samples.json
SCRUB_URL=http://127.0.0.1:8080/v1/scrub python3 test_deployed.py eval_samples_v2.json

# build + capped container
docker build --platform linux/amd64 -t pii-scrubber:1.2.0 .
docker run --rm --memory=3g --memory-swap=3g -e SPACY_MODEL=en_core_web_lg -p 8080:8080 pii-scrubber:1.2.0

# AI Core, from the API only
GET $AI_API/v2/admin/applications/{name}/status
GET $AI_API/v2/lm/scenarios                       # AI-Resource-Group: default
```
