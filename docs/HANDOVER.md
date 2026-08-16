# PII Scrubber — Handover

**Last updated 2026-08-16, after the Rule 7 gate.** Written for someone picking this
up with zero prior context. **Read the START HERE block below first** — it is
the only section guaranteed current; everything after it is dated record.

---

## 🟢 START HERE — state as of 2026-08-16, after the Rule 7 gate

**Presidio path is ACCEPTED and SHIPPED. GLiNER RUNS, the backend is DECIDED
(torch), and the ship candidate is FROZEN.** Nothing is broken; nothing is
half-applied. The next artifact is the **bake-off plan for Gate 0**; until that
plan is reviewed, **nothing builds and nothing touches the deployment.**

```
deployment   daedcfe9342d21a7   running 1.2.3, read back and VERIFIED
origin       529e590            deploy/aicore-poc — IN SYNC, nothing unpushed
ship cand.   pii-scrubber:gliner-cand    FROZEN at b5fbaf6's build, LOCAL ONLY
images       pii-scrubber:gliner-spike   <- superseded, safe to delete
             ghcr.io/.../1.2.3           <- what is actually deployed
```

⚠️ **No registry push grant exists.** It was granted for 1.2.3 and **revoked**;
grants are per-release, exact-tag, at the publish step, expiring on digest
verification. See "Settled".

### ✅ The Rule 7 decision — MADE 2026-08-16. Backend is torch, ONNX deferred.

Recorded as **verbatim, dated, attributed** words per the "Settled" rule, not
as the executor's paraphrase. **Reviewer session (Claude Cowork), relayed by
Teru, 2026-08-16.** Read "Option 3" as option **C** of the table that was put
to review — the reviewer's own next sentence disambiguates it.

> Tokenizer gate: ACCEPTED, 8003cac. Warning adjudicated wrong by
> measurement; offline hard-fail is a production-parity improvement.
> chmod fix: ACCEPTED, b5fbaf6. 2.46 -> 1.51 GB; the KServe non-root
> rationale is recorded reasoning, not just a diff.
> Pod-fitness: memory gate CLOSED (2.18 GiB peak, stressed). Latency
> honesty accepted: neither number is the pod's answer.
>
> ONNX: Option 3. The ONNX arm is struck from the current sequence and
> recorded as deferred optimization (custom glue + equivalence testing,
> or gliner upgrade with re-arbitrated pins and tokenizer gate re-run).
> Backend = torch. Ship-candidate image freezes at b5fbaf6's build.
>
> Latency pre-registrations:
> - Batch gate: PASSED at upper bound (47.6 s / 65 samples, emulated
>   1 vCPU; batch path is async).
> - Live gate: UNANSWERED, locally unanswerable. Measured on the pod at
>   a GLiNER release's verification step. Fallback pre-stated: fail ->
>   GLiNER batch-only, live stays presidio, residual returns to the
>   management Local-LLM question.
> - Live concurrency policy if ever adopted: single-flight only (0.48x
>   measured).
>
> Push: 8003cac and b5fbaf6 AUTHORIZED (review-before-push satisfied).
>
> Next: bake-off plan for Gate 0 on the frozen torch candidate — three
> modes, threshold policy never tuned on burned sets, per-engine and
> per-path over-redaction metrics, corpus rules (burned = engineering
> comparison + regression only; quotable requires fresh blind batch).
>
> Queue unchanged: mechanism-claims audit (executor), blind batch v4
> (reviewer). Rotation: deferred by decision, trigger not fired.

**Quoted in full, not excerpted** — a partial quote of an authorization is how
one gets read as broader than it was.

**What this changes, in the executor's words and marked as such:**

- **There is a backend and a frozen image.** The bake-off plan is no longer
  writing against a moving target, which is what blocked it.
- **The `optimum` dependency question is closed without being taken.** No new
  dependency, no gliner upgrade, so the finding-11 pin chain
  (`huggingface_hub==0.36.2` + `transformers==4.57.6`) and the tokenizer
  arbitration both stand untouched. Re-opening ONNX later re-opens both.
- ⚠️ **Option C's known cost was accepted, not dodged.** This document recorded
  that choosing C leaves a **native amd64 single-vCPU latency measurement** as
  the missing input, and that this Mac cannot produce it. The decision answers
  that rather than ignoring it: the live gate moves to **pod-time measurement
  at a GLiNER release's verification step**, with the failure branch stated in
  advance. **A pre-stated fallback is what keeps an unmeasurable gate from
  becoming an unbounded one.**
- **The batch gate is passed on the pessimistic figure**, so no better number
  is needed for it. 47.6 s is the emulated-amd64 upper bound; the batch path is
  async, so it is affordable there. **This does not transfer to the live path** —
  see the two-bounds warning below.

### What GLiNER actually is now — measured, not assumed

**Finding 11 is FIXED.** The cause was **two** unbounded dependencies, not one:
gliner declares `huggingface_hub>=0.21.4` with no upper bound, and
`transformers 5.x` requires `hub>=1.5.0` — which drags the hub back over the
1.0 line where `_from_pretrained` stops receiving `proxies`/`resume_download`.
Measured: hub `0.24.7`–`0.36.2` work, `1.0.1`+ do not. **Raise either pin and
GLiNER breaks again.**

```
huggingface_hub==0.36.2      transformers==4.57.6
```

GLiNER loads, runs, and `SCRUBBER_ENGINE=both` no longer takes the pod down.
Detail lives in the sections below: pod-fitness gates, the tokenizer
arbitration, and the ONNX blocker.

**The headline from the gates: memory is fine, latency is the problem.**
On the real pod shape (`--cpus=1 --memory=3g`, threads capped) GLiNER is
**~113× slower per request** than presidio — p50 678 ms vs 6 ms, a 65-sample
batch 47.6 s vs 0.5 s, and 4-way concurrency *degrades* to 0.48×. Peak RSS
2.18 GiB of 3 GiB with 823 MiB headroom after a stressed run: **no OOM.**

⚠️ **Do not quote 678 ms or 44 ms as the pod's latency.** 678 ms is emulated
amd64-on-ARM (upper bound); 44 ms was native but many-core (lower bound).
**Native amd64 on one vCPU is unmeasured and is the only figure that decides
the live path.**

### What was delivered

| | |
|---|---|
| Service | Presidio + 9 custom SAP recognizers, inside the compliance boundary. No third-party model sees raw data |
| Deployed | `pii-scrubber:1.2.3`, deployment `daedcfe9342d21a7`, verified end to end |
| **Quotable figure** | **90.0% blind** (`holdout_v3`, externally authored, run once, zero novel failure classes) |
| Benchmark | 97.3% — **burned, regression-only, never quotable** |
| For management | `holdout-evaluation-report.html`, `scrubber-options-for-management.html` — ready, local-only |

### Queued, in order

1. ✅ ~~Rule 7 decision~~ — **MADE 2026-08-16**, recorded above. Backend torch.
2. ✅ ~~Bake-off plan for Gate 0 review~~ — **WRITTEN and ANSWERED
   2026-08-16.** `docs/superpowers/plans/2026-08-16-pii-scrubber-gliner-bakeoff.md`,
   revision 1. Gate 0 rulings and Q1–Q8 are verbatim in its §12; the standing
   rules they produced are in "Settled" above.
3. **← YOU ARE HERE. Execute the bake-off**, in the authorized order:
   Task 0 (pre-fix baseline + per-file provenance hash) → **Task 1, MANDATORY**
   (`_merge` monotonicity fix + git sha + both offline vars + thread cap at
   both layers, **ONE** build, re-freeze, tokenizer re-proof) → Tasks 2–6 →
   **Task 7 review gate**.
   ⚠️ **The freeze is lifted for exactly one rebuild.** The candidate that gets
   measured is Task 1's output, not today's `pii-scrubber:gliner-cand`.
   ⚠️ **No deployment touch, nothing pushed beyond the three authorized
   commits, blind batch v4 untouched.**
4. **Mechanism-claims audit** (executor) — authorized, its own scoped session.
   Ledger every claim of mechanism here as *exercised / observed / asserted,
   never executed*, then scratch-container probes for the third bucket. Both
   of this project's recent errors came from that bucket.
5. **Blind batch v4** (reviewer) — reframed: it **sizes an open leak**, it does
   not verify a fix. ⛔ **And it is never a tuning corpus** — see "Settled".

⚠️ **Not queued, deliberately:** more review rounds. 1.2.2 and 1.2.3 changed
zero detection between them and the blind figure has not moved since the
1.2.0-era measurement. Correct for what those releases were, but the loop had
begun feeding on itself.

### The known residual — inherit this knowingly

Roughly one in ten planted values survives, **almost all person names**. The
leak is **per-token, not per-frame**: `VERMEULEN` is caught in the identical
sentence `NAKAMURA` leaks from. Rules reach about a third of it; a larger
spaCy model measured net-zero. Separately, **unnumbered street and facility
references redact nothing at all** ("the warehouse on Willis Street") — open
at the **recognizer** layer, not `LABEL_MAP`.

**Batch path: tolerable**, a human gate sees the output. **Live path: no human
gate, so ~90% is final** — and that is the trade that was accepted.

### Checklist — deferred to ACTUAL project completion, i.e. after GLiNER

⚠️ The rotation trigger is **project completion**, and the project is not complete — GLiNER is outstanding. The trigger has **not** fired. It fires when GLiNER is either shipped or formally abandoned by decision.

Owner: Teru. Listed here so the checklist exists and is complete, **not** as a prompt to act now.

- [ ] **Rotate the AI Core service key** (`~/aicore-key.json`) — transited chat 2026-08-15
- [ ] **Rotate the GitHub PAT** — transited chat 2026-08-15; also used for the 1.2.3 image push
- [ ] Delete the two stale "PII Scrubber" configurations (7:19 PM / 7:33 PM) in AI Launchpad
- [ ] Decide the fate of deployment `daedcfe9342d21a7` — **leaving it running holds the free tier's single pod and keeps a live endpoint reachable with the pre-rotation registry secret.** Delete it, or re-create it after rotation
- [ ] Send the two HTML reports to management

---

## What this is

A **PII scrubber for an SAP incident knowledge base**. It redacts personal data
out of ticket text, functional specs and expert notes before that material
enters a KB corpus or reaches a triage LLM. It runs entirely inside the
compliance boundary — no third-party model ever sees raw data.

The folder is called `NER POC`, which undersells it. This is not a general
named-entity-recognition experiment; it is compliance tooling with a hard
no-leak requirement, running on **SAP AI Core (bring-your-own-model)** on BTP
Free Tier. No Cloud Foundry, no Generative AI Hub.

Two paths through the service:

- **batch** — scrub source material on its way into the KB corpus. Replaces
  values with `<TYPE>`. Output must stay readable, so over-redaction has a cost.
- **live** — tokenize an incident payload before triage. Replaces with
  `<TYPE_n>` and returns a `token_map` so the caller re-maps *inside the
  boundary* after the answer comes back. Over-redaction costs nothing here.

---

## ✅ 1.2.3 — SHIPPED, CUT OVER, VERIFIED END TO END (2026-08-16)

```
origin/deploy/aicore-poc  39fda53   in sync, nothing unpushed
image                     ghcr.io/terusin71/pii-scrubber:1.2.3
digest                    sha256:9fcc4337...58d080735   linux/amd64 + attestation
template                  -> :1.2.3   rollback comment names 1.2.2
deployment                daedcfe9342d21a7   replaces da1b1b3e39367c59 (deleted)
```

**Read back on the deployment, not inferred:**

| Check | Deployed result |
|---|---|
| `/v1/info` `build_version` | **`1.2.3`** exact |
| `unmapped_labels` before first build | `null` |
| `unmapped_labels` after selftest | `["FAC"]` |
| `unmapped_labels_semantics` | present in **both** responses |
| `presidio_loaded` | `false` → `true` |
| `/v1/selftest` | `1.2.3 / 100.0 / 45/45 / missed 0 / over_detections 4 / spans 49` |
| `holdout_samples.json` | **108/111**, leaks `ZHANG` `Young` `Mere Tuhoe` |
| `eval_samples_v2.json` | **65/68**, leaks `44 Bellbird Rise` `Okonkwo` `FONTAINE` |
| `holdout_v3.json` | **45/50**, leaks `NAKAMURA` `Park` `Adeyemi` `5591230` `6620945` |

Identical to the container and to the local run, field for field. Every gate
exact, leak lists compared line-by-line. Each gate run printed `build: 1.2.3`
itself — the stamp is per-run, not read once and assumed.

**1.2.3 produced no quotable figure and could not have.** All four sets remain
burned. The quotable number is still **90.0% blind (v3)**.

### ⚠️ Trap hit during this verification — a stale env var beat the file default

The three gates first returned `HTTP 404: Deployment not found` while `curl`
against the same ID, in the same shell, seconds earlier, had worked.

Cause: `DEPLOYMENT_ID` was exported in that shell as **`d08c99a19640540f`** —
the **1.2.1** deployment, dead for two releases. `test_deployed.py` reads
`os.environ.get("DEPLOYMENT_ID", <default>)`, so **the environment silently
outranked the file**, and repointing the default in the repo did nothing for
a shell that already had the variable set.

Two lessons, both general:

1. **Repointing a default does not repoint a session.** The ID was corrected
   in `test_deployed.py` and committed; the shell ignored it. Any long-lived
   terminal carries the previous release's exports. `export DEPLOYMENT_ID=`
   explicitly before a gate run, or `unset` it and let the file win.
2. **404 ≠ 401, and the harness's own hint says otherwise.** The abort text
   reads `(401 = token expired; re-mint and re-run)` regardless of status, so
   a 404 arrives wearing a 401's explanation and points the reader at the
   token — which was valid. ⛔ **Not fixed in 1.2.3**, deliberately: the gates
   above were produced by the harness exactly as it stands, and editing the
   file that produced a just-verified number breaks the tie between the two.
   Registered as the first item of the next release: make the abort print the
   actual status and the resolved URL.

| Item | State |
|---|---|
| 1 — `unmapped_labels()` reads the engine's real ignore list | ✅ shipped, `24eaef3` |
| 2 — `unmapped_labels` surfaced on `/v1/info` | ✅ shipped, `3adaeaa` |
| 3 — map `FAC` → `ADDRESS` | ⛔ **WITHDRAWN. It does nothing — see below** |
| 4 (replacement) — correct three wrong descriptions | ✅ shipped, `7b545e8` |
| 5 — regression gates | ✅ exact, zero movement, leak lists line-by-line |
| 5b — self-describing payload, corrections pinned, registration re-pinned | ✅ shipped, `3940981` |
| 6 — build + in-container verify | ✅ `1.2.3`, `linux/amd64`, gates re-run in-container |
| 7 — review gate | ✅ passed; nothing was pushed before it |
| 8 — publish, cut over, verify on the deployment | ✅ `42c3829` / `39fda53`, `daedcfe9342d21a7` |

**5b was not in the original three.** It came out of the review of Task 4 and
answers the three defects that review found: the payload shipped a bare
`["FAC"]` with its caveat nowhere a reader would see it; no test could fail if
the corrections were reverted; and §5's suite registration had gone stale two
commits earlier without anyone noticing. Its assertions were proved by
**mutation** — each correction reverted in turn, each producing a red suite,
each file restored byte-identical — because a check that has never failed is
a check that has not been shown to work.

### ⛔ 1.2.3 is CLOSED. (Sequence below is SUPERSEDED — see START HERE.)

⚠️ **This ordering was set before GLiNER was unblocked and is kept as record,
not instruction.** It concerns the **FAC recognizer plan**, which is a
different piece of work from the **GLiNER bake-off plan** now in front. The
current ordering is in the START HERE block: Rule 7 decision → bake-off plan →
audit ∥ blind batch v4. The FAC recognizer plan sits behind all of them.

Set at review, 2026-08-16. **Two pieces run in parallel; the recognizer plan
starts only when both are in.**

```
  ┌─ AUDIT  (executor)  ─────────────┐
  │  HANDOVER mechanism-claims       │
  │  ledger                          ├──►  RECOGNIZER PLAN
  ├─ BLIND BATCH v4  (reviewer)  ────┤     Gate 0, informed by both
  │  now DUE — 1.2.3 is deployed     │
  │  and verified, target exists     │
  └──────────────────────────────────┘
```

**1. The mechanism-claims audit — its own scoped session, executor.**
Authorized because *two consecutive rounds found the previous round's central
factual claim wrong*: the FAC incidence probe measured the wrong layer, and the
ORG precedent never fires. Both were written here as settled, in confident
prose. The corrections are good news; the base rate is not.

Deliverable: a **ledger of every claim of mechanism in this document**, each
tagged with its evidence class —

| Class | Meaning |
|---|---|
| **exercised** | a test actually runs this path |
| **observed** | measured once, on the record, but nothing guards it |
| **asserted, never executed** | written down as how it works; no evidence anyone ran it |

Then **scratch-container probes for the third bucket** — the bucket both of
this project's recent errors came from. Not one release at a time; all at once,
deliberately.

**2. Blind batch v4 — reviewer, now due.** Purpose reframed: it **sizes an
open leak**, it does not verify a fix. Its number feeds the recognizer plan's
justification. Salting spec in `REVIEW-1.2.4-session.md` §7.2.

**3. Recognizer plan Gate 0** — written only after both land, and opening with
the Phase 0 spike below.

⚠️ **Not in this sequence, and deliberately:** more review rounds. 1.2.2 and
1.2.3 changed **zero detection** between them, and the blind figure has not
moved since the 1.2.0-era measurement. That was correct for what those releases
were, but the loop had started feeding on itself. The audit is the last piece of
inward-facing work before something that can move a number.

### ⛔ Why item 3 was withdrawn — the finding this release actually produced

**`FAC` never reaches `LABEL_MAP`.** It is dropped a layer earlier:
`SpacyRecognizer.supported_entities` is
`['ORGANIZATION','LOCATION','AGE','EMAIL','PHONE_NUMBER','ID','PERSON','DATE_TIME','NRP']`
— no `FAC` — so presidio emits no result and `analyze()` returns empty.
Proved directly in the pinned container:

```
BEFORE  detect(): []
AFTER FAC->ADDRESS in LABEL_MAP: []
```

The evidence that justified item 3 — an incidence probe finding `FAC` spans in
the corpora, 4 then 8 — was measured with **raw spaCy**, not through the
pipeline. Correct about spaCy, irrelevant to the scrubber. This is the new
**"true measurement taken at the wrong layer"** trap class, recorded in the
trap list below. Full record: `fac_probe_validation.md`.

### Three descriptions were known wrong — ✅ CORRECTED (replacement Task 4)

Docs and strings only. No behaviour change, no measurement moved. Scope
confirmed by the reviewer: item 3 withdrawn, original Task 4 dead, no
detection surface, and **no `supported_entities` modelling** — the
over-reporting is documented, not fixed.

1. ✅ **The 1.2.2 warning** said unmapped labels are "DETECTED and then
   silently dropped". For `FAC` the drop *precedes* detection. The shipped
   log line now states that the check does not model `supported_entities`
   and that a listed label may be dropped after detection *or* never reach
   the pipeline. `app.py`, `get_analyzer()`.
2. ✅ **This handover's trap-8 entry** said `FAC` "reaches `_norm()` raw". It
   does not. Corrected in place as "Correction 2", with the superseded
   mechanism kept beside it.
3. ✅ **`unmapped_labels()` documented semantics** — it models
   `labels_to_ignore` and the entity mapping but **not**
   `supported_entities`, so its output is a **superset of the leak list**,
   not the leak list. Stated in the docstring, at the call site, in the log
   line, and in trap 8. Modelling `supported_entities` stays deferred to the
   recognizer plan.

Also corrected, same claims restated in a third file: `test_label_map.py`'s
module docstring and its live-case comment. A correction applied in two of
three places is how a document starts disagreeing with itself — the failure
recorded in `REVIEW-1.2.3-session.md` §5.2.

### The leak class is real and still open

Unnumbered street and facility references redact nothing — confirmed on five
lines in the pinned container:

```
'the warehouse on Willis Street'   detect() = []
'the depot on Great South Road'    detect() = []
'Auckland International Airport'   detect() = []
```

**The correct layer is the recognizer, not `LABEL_MAP`.** Adding `FAC` is
**materially larger than one line** — it needs its own plan, its own
pre-registration, correct-layer incidence evidence, and the probe batch
re-run against a FAC-registered build.

### 📌 Registered for the recognizer plan — 2026-08-16, verified at the pin

Three facts the plan must start from. All measured on presidio 2.2.357 +
`en_core_web_sm`, through `app.get_analyzer()` (never a bare `AnalyzerEngine`).

**1. Provenance of the nine-element `supported_entities` list — one line:**
the registered `SpacyRecognizer.supported_entities` is exactly the set of
**distinct values of presidio's `NerModelConfiguration.model_to_presidio_entity_mapping`**
(`AGE DATE_TIME EMAIL ID LOCATION NRP ORGANIZATION PERSON PHONE_NUMBER`) —
**not** the class attribute `SpacyRecognizer.ENTITIES`, which is only five
(`DATE_TIME NRP LOCATION PERSON ORGANIZATION`). The registry builds the
recognizer from what the NLP mapping can produce. `FAC` is in neither, and
that is *why*: `FAC` is not a value in the mapping, so it can never be a
supported entity by that route.

**2. ⚠️ TWO-CONDITION GUARD — verify BOTH, separately.** A span survives only
if the entity is *supported* **and** *requested*. Registering `FAC` satisfies
condition (a) alone, and a plan that verifies only (a) will produce another
correct-and-unreachable change:

| | Condition | How it fails silently |
|---|---|---|
| (a) | The entity is in the registered recognizer's `supported_entities` | No `RecognizerResult` is ever produced — today's `FAC` case |
| (b) | The entity is in the entities **requested** at `analyze()` time | Supported but filtered out at the call; the recognizer runs and its result is discarded |

Measured today, both fail: `analyze()` unfiltered returns `[]`, and
`analyze(entities=["ADDRESS","LOCATION"])` also returns `[]`.
**Assert on `scrub()` output end to end, never on either list.**

**3. ⚠️ The cited precedent is DORMANT — do not lean on it.** This document
and `fac_probe_validation.md` both said "`get_analyzer()` already
re-registers `SpacyRecognizer` with `ORGANIZATION` added, so adding `FAC` is
the analogous fix". **At this pin that branch never executes.** `ORGANIZATION`
is already in the class `ENTITIES` and in the mapping values, so the guard
`if "ORGANIZATION" not in ents` is false and the log reads
`SpacyRecognizer already supports ORGANIZATION` — confirmed in the run log.
The 1.2.0 ORG fix works **entirely** through the NLP-layer `labels_to_ignore`
change; the re-registration is dead code kept for presidio versions where the
entity is missing. **So the FAC change would be the first time that path ever
fires, not a repeat of a proven one.** Same error shape as the release that
produced this note: a mechanism assumed to work because code for it exists.

**Independently confirmed at the pin by review, 2026-08-16.** Facts 1-3 are
not the executor's word alone.

### ✅ GLiNER tokenizer question — RESOLVED 2026-08-16, empirically

Loading GLiNER emits a transformers 4.57 warning claiming *"This will lead to
incorrect tokenization. You should set `fix_mistral_regex=True`"*. Taken at
face value that would invalidate every GLiNER measurement before one was
taken. **Resolved by token-ID diff and round-trip decode, not by reading the
warning.**

**The warning is wrong for this model. The default is correct. Do not obey it.**

| `HF_HUB_OFFLINE` | flag OFF (default) | flag ON |
|---|---|---|
| **`1` — the shipped condition** | 0 UNK, round-trip byte-perfect | **7 UNK, word boundaries destroyed** |
| `0` | 0 UNK, ok | 0 UNK, ok |

`fix_mistral_regex` advertises a Mistral-specific fix through an over-broad
heuristic; applied to mdeberta-v3 (sentencepiece) it shreds the tokenization:
`'Escalated by NAKAMURA...'` → `'EscalatedbyNAKAMURA...'`.

⚠️ **Second finding, and the more general one: the tokenizer artifact depends
on network reachability.** Offline forces a sentencepiece→fast *conversion*,
which the regex governs. Online, transformers downloads a prebuilt
`tokenizer.json` and the flag never bites. **A tokenizer test run with network
access therefore exercises an artifact production never uses** — it passes for
the wrong reason. Production is offline by design (Rule 3; the UrlRecognizer
boundary guard exists for the same reason), so offline is the only condition
worth asserting in.

**Pinned by assertion, not by a flag** — the winning value *is* the default, so
there is no config line to set. `test_gliner_tokenizer.py` runs in the image
with `HF_HUB_OFFLINE=1`, asserts clean round-trips, re-runs the arbitration,
and **hard-fails if it is not actually offline**. Verified: passes offline,
fails loudly online. Together with the `transformers==4.57.6` pin, that is
what holds the finding in place.

### 📊 GLiNER pod-fitness gates — measured 2026-08-16 on the POD shape

`--cpus=1 --memory=3g`, `OMP_NUM_THREADS=1`, image `pii-scrubber:gliner-cand`,
against all 158 real corpus samples. **This is the Starter plan's actual
shape**; every earlier latency figure was taken on many cores and is void.

| Gate | presidio | **presidio + GLiNER** |
|---|---|---|
| Cold load (first call) | 3.6 s | 12.7 s |
| p50 latency, median sample (118 ch) | **6 ms** | **678 ms** |
| Longest document (307 ch) | 13 ms | 1,038 ms (max 1,309) |
| Gate-sized batch, 65 samples | 0.5 s | **47.6 s** (mean 733 ms) |
| 4-way concurrency | 1.13× | **0.48× — contention**, max **6,465 ms** |
| Peak RSS | 456 MiB (14.8%) | **2.18 GiB (72.6%)** |
| OOM at 3 GB? | no | **no** — alive, exit 0 |

**GLiNER is ~113× slower per request than presidio on one vCPU.**

⚠️ **Both bounds are known and the true pod figure is neither.** 678 ms is
emulated amd64-on-ARM, so it is an **upper** bound; 44 ms was native but on
many cores, so it is a **lower** bound. **Nobody has measured native amd64 on
one vCPU, and that is the only number that decides the live path.** Do not
quote either figure as the pod's latency.

**Memory is the good news and it is now stressed, not assumed:** 2.18 GiB peak
*after* a 65-sample batch and a concurrency probe, 823 MiB headroom, no OOM.
The 3 GB ceiling is not the blocker. Latency is.

**Image size after the `chmod` layer fix:** compressed **2.46 GB → 1.51 GB**,
−950 MB (39%). `docker image inspect .Size` disagreed with itself across the
two builds (6.76 GB vs 1.51 GB); **only `docker save | gzip | wc -c` is
trusted here.**

### ✅ ONNX — DECIDED 2026-08-16: struck from the sequence, deferred optimization

**Decision recorded in START HERE; this section is the technical why.** The arm
is **not** cancelled and **not** blocked-and-forgotten — it is a deferred
optimization with two named re-entry routes: custom glue plus equivalence
testing, or a gliner upgrade with re-arbitrated pins and the tokenizer gate
re-run. **Either route re-opens work this project already paid for**, which is
the reason it was deferred rather than taken now.

Everything below is the analysis that produced the decision, kept as the
record of what was traded away.

The size-and-latency lever cannot be pulled at the current pin:

- `GLiNER.from_pretrained` has **no ONNX parameter**; the source does not
  mention onnx at all. `gliner.onnx.model` exists but is not wired into the
  loading API in this version.
- `onnxruntime 1.28.0` **is** already installed (no new dep there), but
  `optimum` — the export tooling — is **not**.

So ONNX needs either a **gliner upgrade** (which re-opens the entire
finding-11 pin chain: gliner's unbounded `huggingface_hub>=0.21.4` is what
broke it, and the fix is a coupled hub+transformers pin) or **`optimum` as a
new dependency**. Both are Rule 7. **Not taken unilaterally.**

✅ **Outcome: neither was taken.** The dependency surface is unchanged —
`optimum` is still absent, `gliner==0.2.16` still pinned, and the coupled
`huggingface_hub==0.36.2` + `transformers==4.57.6` pin still holds finding 11
closed. **The cheapest property of this decision is that it moved nothing**:
no re-resolve, no re-arbitration of the tokenizer, no new failure surface in
an image that was about to be frozen.

### 🔬 Phase 0 of the recognizer plan — mechanism-selection spike, REQUIRED

Directed at review, 2026-08-16. **Before any pre-registration is written**,
execute **both** candidate paths in a **scratch container** and observe which
one actually puts a `FAC` span through `scrub()`:

| Candidate | Mechanism |
|---|---|
| A | Add `FAC` as a **`NerModelConfiguration` mapping key**, so the entity becomes a mapping value and the registry-built recognizer supports it by the normal route |
| B | **Re-register `SpacyRecognizer`** with `FAC` appended to `supported_entities` — the path §4.1 just proved is dead code today |

Neither is assumed. Both are executed, both results recorded, and the winner
is chosen on observed `scrub()` output — **not** on which one looks analogous
to something already in the codebase. That reasoning is exactly what produced
item 3 and the dormant-precedent error.

Two further requirements of that plan, both non-negotiable:

- **Modelling `supported_entities` in `unmapped_labels()` is a REQUIRED
  item**, not an optional tidy-up. It is the fence in "Settled" coming down.
- The spike runs in a **scratch container, never against the live pod**.

⚠️ **`fac_probe_validation.md`'s "0 of 12 control fires" is NOT safety
evidence for that change.** `FAC` could not fire on any line, so the controls
were never exercised. The over-redaction risk is entirely unmeasured.

---

## 1.2.2 — shipped, cut over, verified end to end (2026-08-16)

| | |
|---|---|
| Deployment | ✅ **`da1b1b3e39367c59`** — replaces `d08c99a19640540f` (1.2.1), deleted not stopped |
| Image | ✅ `ghcr.io/terusin71/pii-scrubber:1.2.2`, `linux/amd64`, `sha256:958bd5c3…b3ff3fa6` |
| ServingTemplate | ✅ points at `:1.2.2`, labels untouched |
| Verified **in-container** | `/v1/info` → exactly `1.2.2`; trap-8 warning logged; `100.0 / 45/45 / missed 0 / over_detections 4 / spans 49`; gates `108/111`, `65/68`, `45/50` unchanged |
| Verified **on the deployment** | ✅ `/v1/info` → `1.2.2` in **one cheap call**; `/v1/selftest` → `1.2.2`, `100.0`, `45/45`, missed 0, `over_detections 4`, spans 49 — **identical to the container** |

**Contents:** `@app.get("/v1/info")` — identity through the route the gateway
actually proxies — and the trap-8 warning naming labels `LABEL_MAP` drops.
Neither changes detection, and none of the four gates moved.

**Item 1 proved itself in the act of verifying it.** Answering "which build is
this?" on the deployment now costs one request. Under 1.2.1 the same question
required a 13-sample selftest, because `/info` is not proxied — which is why
nobody asked it casually, which is how a stale deployment goes unnoticed.

The deployed `/v1/info` also returned `"presidio_loaded": false`, confirming on
the real deployment that model loading is lazy — and therefore that the trap-8
warning had not fired yet at that point. See the caveat below.

`type_mismatches: 4` is the unchanged baseline: `BJOHNSON`→PERSON,
`KMUELLER`→ORG_NAME, `MTANAKA`→ORG_NAME, `Hauptstrasse 12, 80331 Munich`→
PERSON. All four are **redacted**, merely mistyped. Log only, not a leak.

⚠️ **`/info` (no `/v1`) is NOT reachable through the gateway.** Confirmed on
`d08c99a19640540f`, not predicted:

```
GET $AI_API/v2/inference/deployments/d08c99a19640540f/info  ->  RBAC: access denied
```

Only `/v1/*` is proxied — which is exactly why `/v1/info` had to be added.
**An identity check that passes locally proves nothing about the deployment:**
the first implementation read `/info` alone, was green on every local run, and
would have printed `unreachable` forever in production.

⚠️ **The trap-8 warning fires on FIRST ANALYZER BUILD, not at process start.**
Model loading is lazy so `/health` stays instant and readiness probes never
time out. A pod that has only answered health checks has not logged it yet —
look after the first `/v1/scrub` or `/v1/selftest`, not immediately after
`RUNNING`.

### 1.2.1 — shipped and verified end to end (superseded, kept for the record)

Deployment `d08c99a19640540f`, image `sha256:5ec0f449…08ef6b39`. Deployed
`/v1/selftest` echoed `build_version 1.2.1`, `100.0`, `45/45`, missed 0,
`over_detections 4` — identical to the container; harness `108/111` with the
leak list unchanged. Contents: `BUILD_VERSION` baked and echoed; eight
glossary entries (`GL` `FX` `WM` `MDG` `MRP` `OSS` `CFO` `Rise`);
`test_deployed.py` stamping the build and the sample set it measured, in place
of a banner that announced `HOLDOUT RESULT` for any file it was handed.

**Every deployed number now carries the build that produced it.** That was the
release, and it is closed.

Rollback stays cheap: revert the template commit and `:1.2.1` comes back with
no image work — but read the build-stamp blind spot under **Settled** first.

---

## Current state — deployed and running

| Area | State |
|---|---|
| Deployment | ✅ **`daedcfe9342d21a7`** on SAP AI Core — running `1.2.3`, **read back and verified**, all four measurements exact. See the 1.2.3 block at the top |
| Image | ✅ `ghcr.io/terusin71/pii-scrubber:1.2.3`, **linux/amd64**, `sha256:9fcc4337…58d080735` (1.2.2 `sha256:958bd5c3…b3ff3fa6` is the rollback) |
| GitHub | ✅ `https://github.com/TeruSin71/pii-scrubber-poc` — **private**, branch `deploy/aicore-poc` |
| AI Core Git sync | ✅ application `pii-scrubber-app` → repo `pii-scrubber-poc`, **path `workflows`**, revision `deploy/aicore-poc` |
| Scenario | ✅ `pii-scrubber`, version `1.0`, executable `pii-scrubber` |
| Allowlist | ✅ 257,583 (`TSTC` + `DD02L`) **+ 36 glossary tokens** = 257,619. The file holds **37 entries**; `QMEL` is also in `allowlist.txt`, which loads first, so it adds nothing. Entries ≠ tokens — see the reconciliation block atop `glossary.txt` |
| **Blind batch** | ✅ 40 samples / 50 values, **90.0%**, **zero novel failure classes** |
| Regression suite | ✅ 108/111 (97.3%) — a gate, **not** a quotable figure |
| Engine | `presidio` only. **`both` is broken — see finding 11.** |

Rollback images, all three still in the registry:

- `1.2.0` (`sha256:e8a44575…81ca893`) — no `BUILD_VERSION`, 8 glossary entries short
- `1.1.0` (`sha256:070dea2c…f38290`) — customer-number fix and glossary absent
- `1.0.0` (`sha256:8e779fde…f026a1b`) — also lacks the street-address recognizer

⚠️ **The deployment ID changes on every release.** `d5e6ea76217ed207` was
1.1.0; `db3d9cc5eea296cd` was 1.2.0; `d08c99a19640540f` was 1.2.1;
`da1b1b3e39367c59` was 1.2.2; **`daedcfe9342d21a7` is 1.2.3.** Each
predecessor is deleted, not stopped — the 1-pod quota forces
delete-then-create and Kubernetes never re-drives an admission-rejected
revision. `test_deployed.py` now defaults to `daedcfe9342d21a7`.

A script pointing at a dead ID fails loudly. A script pointing at a *stale but
live* one reports confident numbers for the wrong artifact, silently — that is
the incident behind `BUILD_VERSION`, and **as of 1.2.1 it is detectable**:
every `test_deployed.py` run prints the `build_version` the service returned,
so a mismatch between the ID you meant and the build that answered is visible
in the header instead of being invisible in the numbers.

---

## The numbers, and which one to quote

**Quote 90.0%. Never quote 100%. Never quote 97.3% either — see below.**

| Measurement | Value | What it means |
|---|---|---|
| **Blind batch** — 40 samples, 50 values, `holdout_v3.json` | **90.0%** (45/50) | **The quotable figure.** Authored outside the build session, unseen before the run, run **once** against deployed `1.2.0`. **Zero novel failure classes** — all five leaks were documented before the run. |
| Regression suite — 40 samples, 111 values, `holdout_samples.json` | 97.3% (108/111) | **Burned. A gate, not a measurement.** It read 96.4% on `1.1.0` and was the honest figure then; the 1.2.0 work was built against its leaks, so it can no longer measure what it shaped. Any value but 108/111 is a stop. |
| Verification batch v2 — 65 samples, 68 values | 95.6% (65/68) | Also burned, same reason. Gate value: exactly 65/68. |
| Self-test — 13 samples, 45 values | 100.0% (45/45) | A **regression baseline, not a result.** The recognizers were tuned against these 13 samples, so 100% is near-guaranteed. |

The self-test's job is to prove that packaging, rebuilding and deploying did not
degrade detection. It is asserted, not targeted: if `/v1/selftest` returns below
`100.0`, that is a regression to report, never a number to tune toward. Lowering
a threshold, deleting a recognizer, relaxing `REDACT_TYPES`, or editing
`samples.json` to make output match are all forbidden.

`over_detections: 4` on the self-test is the asserted baseline from 1.2.0
(down from 6 — the glossary removed `IBAN` and one `PO`). Itemised in the
`f2064f3` commit message. It is asserted, so a change in either direction is
reportable.

**Do not present 100% to management.** That instruction is in
`README-DEPLOY.html`, `README.md` and the evaluation report, and it exists
because the figure describes how well the rules fit their own training data.

### What the blind batch actually found — 2026-08-16

The point of the run was never the number; it was whether anything failed in a
way nobody had written down. **Nothing did.**

| Leak | Class | Status before the run |
|---|---|---|
| `NAKAMURA`, `Park`, `Adeyemi` | PERSON, per-token | documented |
| `5591230` behind `client` | cue not in the frozen list | documented design decision |
| `6620945` behind `ship-to` | cue **deliberately excluded** | documented design decision |

`ship-to` was left out of the cue list on purpose: in delivery text it cues an
address more often than an account. That value leaked exactly as predicted —
the design was not wrong, it was **bounded**, and the blind batch found the
boundary where it was drawn.

**The per-token lottery is now confirmed on a third dataset.** `VERMEULEN` was
caught in the *identical sentence frame* that `NAKAMURA` leaked from. Same
frame, same shape, opposite outcome. This is what closes the model-size
argument for good: it is not frames, it is tokens, and a bigger spaCy model
only relocates which tokens lose.

Positives worth keeping: **ADDRESS 7/7**, including all five street types that
were safety-cleared but left unshipped — they behave correctly in real
addresses, exactly as Appendix A predicted. **PHONE 8/8**, including the first
AU and GB numbers ever tested. `WAGNER` held against the allowlist. `AADEYEMI2`
was caught but typed `ORG_NAME` — redacted, mistyped, log only.

---

## Settled — do not relitigate

- **Engine:** Presidio + 9 custom SAP recognizers. GLiNER stays optional behind
  `SCRUBBER_ENGINE=both` — but see finding 11, it does not currently work.
- **Licensing:** Apache 2.0 / MIT only. Piiranha screened out deliberately
  (CC-BY-NC-ND, non-commercial).
- **Deployment path:** SAP AI Core BYOM via a KServe `ServingTemplate` at
  `workflows/serving_template.yaml`.
- **`USR02` is refused as an allowlist source.** A gazetteer of real user IDs
  would improve recall, but the list would itself become a PII asset requiring
  the same access control, retention and deletion policy as the data it
  protects. Governance decision, not an engineering shortcut.
- **`holdout_samples.json` is gitignored on purpose.** A holdout anyone can read
  while tuning is not a holdout. Same for the two HTML reports.
- ⛔ **Scope and authorization changes are recorded ONLY as verbatim, dated,
  attributed human words.** Never as the executor's paraphrase, and never as
  an inference from tone, satisfaction, or momentum. If the human did not say
  it in words that can be quoted, it was not authorized. `40f1da0` is the
  template: the decision, who made it, the date, the trigger, and the accepted
  risk. Established 2026-08-16 after the executor read "90% is fine, let's not
  waste time" as "the project is complete" and wrote GLiNER into a table of
  cancelled work. See the trap list: **authorization inferred from ambient
  signal**.
- **`docker builder prune` is allowed; `docker system prune` is NOT.** The
  ban exists to protect the rollback images -- every shipped tag is still in
  the local daemon and `system prune` would take them. **Build cache is
  regenerable and images are not**, so the two are not the same operation.
  When pruning build cache, capture `docker images` before and after and diff
  them, proving no image was removed. Authorized and exercised 2026-08-16:
  10.71 GB of build cache reclaimed, 14 images before, 14 after, diff empty.
- ⛔ **No permission is granted as a side effect of the executor being
  blocked.** A blocked action is a decision point, not an obstacle to route
  around. Established 2026-08-16 after the 1.2.3 registry push: the harness
  refused the push, the executor asked for a grant mid-release to save a round
  trip, and the project's trust boundary moved without review. Scoping it to
  one repository limited the blast radius but did not make it a reviewed
  decision. **If an action is blocked, report it and stop** — the correct
  outputs are a decision request or a command the human runs, never a
  standing capability acquired in passing.
- ⛔ **Publishing rights are per-release and expire on verification.** Registry
  push is granted at the publish step, for **the exact tag being published**,
  and **revoked once the digest is verified**. Never a wildcard, never
  persistent across sessions. The 1.2.3 grant
  (`Bash(docker push ghcr.io/terusin71/pii-scrubber:*)`) was **REVOKED** at
  review; a wildcard that outlives its release is a standing capability
  nobody re-authorised.
- ⛔ **No automation consumes `unmapped_labels` until `supported_entities` is
  modelled.** The field is a **superset of the leak list**, not the leak list —
  it reports `["FAC"]` for a label that cannot reach the pipeline at all. It is
  safe for a human reading `/v1/info`, because the payload now carries its own
  semantics; it is **not** safe for a monitor, an alert, a dashboard or any
  rule of the form "non-empty means a leak". 1.2.3 fixed the human reader and
  left the machine reader wrong, deliberately and with the scope frozen.
  **Modelling `supported_entities` is a REQUIRED item of the recognizer plan.**
  If a machine reader appears before then, the trade flips and **the field
  comes out** rather than being documented around.
- **A registered number is re-pinned in the SAME COMMIT that moves it.** Any
  task that deliberately changes a pre-registered value updates the
  registration alongside the change, so **"registered" always means
  "registered as of HEAD"**. Established at 1.2.3 Task 5b, after §5 of the
  1.2.3 plan sat at the 1.2.2 suite baseline (`17 · 13`) while items 1 and 2
  had already moved it to `22 · 23`. That row was in breach from `24eaef3`
  onward and went unnoticed through two commits and a handover — it surfaced
  only because the gate compared against the *written registration* rather
  than the previous run. **A stale registration is worse than none:** it
  silently downgrades an exact gate to "compare against whatever printed last
  time", which is the precise failure exact gates exist to prevent. Applies to
  every place a number is written down — the release plan's §5 **and** the
  evaluation block near the end of this document.
- **Advisory code must be unable to break the pipeline it advises on.** A
  diagnostic that can take down the thing it diagnoses has **negative value**:
  it converts a reporting gap into an outage. Any block that only reports —
  logging, counting, labelling, version stamping — is wrapped so no exception
  from it can reach the path it observes. Established at 1.2.3 Task 1, where
  wiring the engine's real ignore list into `unmapped_labels()` made a failure
  in an *optional* configuration step raise straight out of `get_analyzer()`.
  Before that change the same failure degraded gracefully. **Note the shape:
  the bug was in the error path of an optional feature, not in the feature** —
  the feature worked; what broke was what happened when its input did not
  exist. Pinned by a test that forces the diagnostic to raise and asserts
  detection still works.
- **A deliberate detection change pre-registers the SPECIFIC values it
  expects to flip — from measurement, before the run.** A pre-registered flip
  is a pass. An **unregistered flip is a stop, including a rise**, exactly as
  a fall is. The tempting relaxation — "a rise is fine as long as it is
  attributed afterwards" — was proposed and **rejected** at Gate 0 of 1.2.3:
  it lets a moved number acquire its explanation retroactively, which is the
  one thing pre-registration exists to prevent. The exact-gate rule
  (`108/111`, `65/68`, `45/50`, `45/45`) therefore survives detection changes
  intact; what changes is that the plan must say in advance which values, if
  any, are allowed to move and why.
- **The build stamp detects template-to-pod drift, NOT tag mutation.** Know
  the difference before relying on it. If the pod is running an image other
  than the one the template names, `build_version` says so. But a **re-push of
  `:1.2.1` with the same `--build-arg` stamps identically** — the tag now
  points at different bytes and every response still reads `1.2.1`. Only the
  **digest** catches that. `BUILD_VERSION` narrowed the blind spot; it did not
  close it, and no amount of build-time stamping can, because the stamp is an
  input to the build rather than a property of the artifact.
- **ServingTemplate uses a mutable tag, not a digest.** A digest freezes the
  template to one build; the tag lets a corrected image flow through with no
  template change. This was load-bearing when the arm64 image had to be
  replaced (finding 13).

### 📌 Established at the bake-off Gate 0 — 2026-08-16

Five standing rules, each from a ruling recorded **verbatim** in
`docs/superpowers/plans/2026-08-16-pii-scrubber-gliner-bakeoff.md` §12.
**Reviewer session (Claude Cowork), relayed by Teru, 2026-08-16.**

- ⛔ **A correction commit carries a grep transcript proving ZERO remaining
  instances repo-wide.** Verbatim: *"New standing rule: correction commits
  carry a grep transcript proving zero remaining instances repo-wide."* This
  project has now recorded **three** occurrences of one correction applied in
  two of three places — `README-DEPLOY.html` §7 vs the `Dockerfile` copy, the
  1.2.3 trap-8 text across three files, and the `Dockerfile` finding-11 block
  that was still false a day after `requirements.txt` was fixed. Each was found
  by accident. **A claim corrected in one file is a document disagreeing with
  itself**, and the only reliable proof of completeness is the search itself,
  attached to the commit that claims it.
- ⛔ **The tested artifact must equal the deployed artifact under default
  invocation.** Verbatim: *"Offline env + thread caps: baked into the image
  ENV. Tested artifact = deployed artifact under default invocation."* If a
  measurement depends on a condition (`HF_HUB_OFFLINE=1`, a thread cap), that
  condition belongs to the **artifact**, not to the command someone remembered
  to type. A condition supplied by the invocation makes every number true of a
  machine that only exists on the tester's laptop.
- ⛔ **A blind set is NEVER a tuning corpus.** Verbatim: *"v4 is never a tuning
  corpus — fix the wording."* Tuning against a blind set destroys it in the
  same act that burned the other four, and it is the only unburned instrument
  this project has. Legitimate tuning needs a **separate, purpose-built,
  openly-readable** corpus — the `address_verify_samples.json` pattern. The
  burned-set rule and this rule are **not** the same rule, and an earlier draft
  conflated them by saying tuning "waits for v4".
- ⛔ **When configurations differ, claims are CONFIGURATION-level, never
  ENGINE-level.** Verbatim: *"bake-off claims are configuration-level, never
  engine-level."* Presidio spans pass per-type floors; GLiNER spans pass one
  global floor and never touch `TYPE_THRESHOLDS`. Any delta between them
  contains both effects, so "GLiNER is more accurate" is unsupportable by
  construction. **The confound is named beside every number, not once in a
  caveats section** — a caveat one scroll away from a figure does not travel
  with it.
- ⛔ **A defect found while planning is FIXED before measurement, never
  measured around.** Verbatim: *"Union merge: DEFECT. Fix before measurement."*
  The plan had proposed detecting it with a stop condition; that was wrong.
  Measuring a path that can silently lose coverage produces numbers describing
  a bug, and every downstream comparison inherits it. The corollary the ruling
  forces: because the fix touches shared code, **any movement it causes in an
  already-shipped path is a latent-defect stop** — the fix revealing an
  existing defect — and never "we changed the code, so of course it moved".

---

## Open findings

Numbered as they appear in
`docs/superpowers/plans/2026-08-15-pii-scrubber-task-list.md`, which holds the
full text of all 18.

### ✅ Finding 11 — CLOSED 2026-08-16. GLiNER loads; `engine=both` runs.

**Read this heading, not the historical text below it.** Fixed by
`1faf3e9`: a coupled `huggingface_hub==0.36.2` + `transformers==4.57.6` pin,
plus a Dockerfile prefetch that can now fail the build. Verified in-container:
`SCRUBBER_ENGINE=both` starts, loads, scrubs, and does **not** take the pod
down. Full detail in START HERE.

⚠️ **Two lessons this entry taught, both about itself:**

1. **The cause was TWO unbounded dependencies, not one.** Everything below
   says "pin `huggingface_hub`". That alone would have been undone on the next
   resolve, because `transformers 5.x` requires `hub>=1.5.0` and drags it back
   over the 1.0 line. A fix path recorded from a diagnosis nobody executed was
   half a fix path.
2. **The ✅ below is about the DOCUMENTATION, not the defect.** "Resolved
   2026-08-15 by `a9bed3e`" corrected `README-DEPLOY.html`; GLiNER still could
   not load for another day. A green tick beside an open defect is how this
   entry stayed unread. If you are skimming for ⛔, you would have skipped a
   live blocker.

Everything from here down is the pre-fix record, kept because the two lessons
above only make sense against it.

#### Historical record — the defect as it stood until 2026-08-16

```
TypeError: GLiNER._from_pretrained() missing 2 required
keyword-only arguments: 'proxies' and 'resume_download'
```

`gliner==0.2.16` is incompatible with the `huggingface_hub` version pip
resolves. The failing call is `GLiNER.from_pretrained`, which is exactly what
`get_gliner()` calls at runtime — so setting the AI Core `engine` parameter to
`both` takes the deployment down, and no weights are baked in either.

**The shipped `1.1.0` image cannot run `engine=both`.** Fix path: pin
`huggingface_hub` in `requirements.txt` (Rule 7, needs approval) and rebuild.
Owner: the **GLiNER bake-off session**, which is a separate session.

✅ **Resolved 2026-08-15 by commit `a9bed3e`** — `README-DEPLOY.html` was
corrected in five places, including §7 (`engine = both` now marked blocked,
with the traceback and fix path) and §3 (template path now `workflows/`). The
paragraph that stood here said the runbook had deliberately *not* been edited;
that was true when written and stopped being true the same day. If you are
reading a claim about `README-DEPLOY.html` anywhere in this file, check
`git log -- README-DEPLOY.html` before acting on it.

### The 4 holdout leaks — the tuning backlog

| Sample | Type | Value | Class |
|---|---|---|---|
| Sample | Type | Value | Class | Diagnosed cause (2026-08-15) |
|---|---|---|---|---|
| HO-001 | PERSON | `ZHANG` | all-caps surname | cue enumeration — **solvable by rules** |
| HO-018 | PERSON | `Young` | bare surname, sentence-initial | cue-free subject position — **needs POS/dependency parsing** |
| HO-031 | PERSON | `Mere Tuhoe` | full name spaCy missed | strict adjacency + `sm` frame sensitivity — **needs a window, and the model** |
| HO-009 | CUSTOMER_NO | `1045567` | keyed without leading zeros | **no pattern matches at all** — both require 10 digits, the value has 7 |

### ⛔ The `en_core_web_lg` item is CLOSED, not deferred — 2026-08-15

Evaluated as item 3 of the 1.2.0 bundle, measured, and **dropped before
shipping**. Two records, both load-bearing:

> **Model swaps are global changes.** The lg promotion was decided on a
> PERSON-only slice; the full leak guard later found two ORG regressions (one
> span typed FAC with no LABEL_MAP entry, one span not emitted at all). Net
> effect across both sets: zero. Never evaluate a model change on one entity
> type.

> **The lg item is closed, not deferred:** both spaCy models exhibit per-token
> frame sensitivity, they merely fail on different tokens. The residual
> PERSON/ORG gap is not addressable at the spaCy layer. Anything further on
> this class is an engine-level question (GLiNER bake-off or the Local LLM
> option), not a model-size question.

The measurement, for anyone tempted to re-open it:

| | holdout | v2 | total |
|---|---|---|---|
| `en_core_web_sm` | 108/111 | 65/68 | **173/179** |
| `en_core_web_lg` | 107/111 | 66/68 | **173/179** |

lg recovered `Mere Tuhoe` and `FONTAINE`, and lost `Shenzhen Precision`
(no entity emitted at all) and `Harbour Freight` (typed `FAC`). It costs
433 MB of image and takes peak RSS from 421 MB to 920 MB for that.

**These are three person classes, not one — and only one of the three is a
rule problem.** A rule-based context promoter was built, measured and
**reverted** on 2026-08-15: it fired zero times on these 40 samples, once with
one more cue word. See `PERSON-CONTEXT-FINDING.md` for the full negative
result, including why the remaining two classes need the NLP layer rather than
more rules. Do not re-attempt a regex promoter without reading it first.

### Over-redaction of SAP jargon — one layer up from where it was fixed

`Handling Unit Place` and `The 2 Bin View` are still redacted as `<ORG_NAME>` by
the spaCy layer. The street-address recognizer correctly declines both; the same
street-type ambiguity resurfaces in the NLP layer. Fixing the recognizer alone
does not close this class — it needs the P3 jargon glossary.

**Widened 2026-08-15 by the v2 batch.** The class is not only street-type
ambiguity, and the mistyping is inconsistent:

```
"raising it with Basis"  -> <ORG_NAME>
"routed to Basis"        -> <ADDRESS>      same word, different type
"Driver could not find"  -> <ORG_NAME>
"3 Way match"            -> 3 <ORG_NAME> match
```

`Basis` is an SAP module and `Driver` an ordinary role noun, so the glossary
needs role and module vocabulary, not just street types. `3 Way match` is the
clean demonstration that this lives above the recognizers: `test_address.py`
asserts the ADDRESS recognizer declines it, and `Way` still comes out
`<ORG_NAME>`.

**Addressed in 1.2.0 by `glossary.txt`** — 29 entries, loaded through the same
loader into the same suppression set as `allowlist.txt`, so it inherits
case-sensitive exact match, the ±40-char user-context backstop and whole-span
matching rather than reimplementing them.

**Shipping criterion is "observed misfire", not "proven safe."** Every entry
traces to an incident — a redacting span that covered no expected value in
`samples.json`, `holdout_samples.json` or `eval_samples_v2.json`. Words that
pass the safety gate but have never misfired stay **unshipped**: `Rise`,
`Close`, `Court`, `Terrace` and `Drive` are cleared in Appendix A of the
1.2.0 plan, with the analysis already done, and become a one-word add the
moment evidence appears. This is what keeps the glossary auditable — every
line answers "which incident put you here?"

⚠️ **Glossary coverage is bounded by the corpora it was mined from.**
Production jargon outside those three files is not covered, and adding it
means edit-and-redeploy — a code change, a rebuild and a stop/create cycle on
a 1-pod free tier. That is the standing argument for a **reviewer-restore
step** when the BPA flow is designed: the glossary handles the head of the
distribution, a human reviewer handles the tail. Do not attempt to close the
tail by growing the glossary speculatively — that trades an auditable list
for an unauditable one and reintroduces exactly the leak risk each rejection
in Appendix A was recorded to avoid.

### Address coverage limits, accepted deliberately

- **NZ/AU forms only.** German-style `Hauptstrasse 12, 80331 Munich` (name
  before number) is not matched by the recognizer and relies on incidental
  locality detection. ⬇️ **Downgraded 2026-08-15:** the v2 batch put two German
  forms through end to end — `Hauptstrasse 12, 80331 Munich` and
  `Industriestrasse 45, 70565 Stuttgart` — and **both were redacted.** The
  incidental path works. This is a weaker gap than it reads, and it should not
  be used to justify a recognizer rewrite on its own.
- **Bare ambiguous-type addresses are missed.** `44 Bellbird Rise` with no
  suburb does not match, because street types that are also ordinary logistics
  words require a trailing comma-locality. That rule is what stops
  `20 Pallet Rack Row` and `12 Handling Unit Place` being eaten. Confirmed as
  the **only** ADDRESS leak in the v2 batch (13/14) — the tradeoff is behaving
  exactly as designed.

---

## Traps that cost real time — read before debugging anything

All of these **fail silently**. None announced itself.

**SAP AI Core, free tier:**

1. **Application "Path in Repository" must be a real subdirectory.** `.` syncs
   nothing. Ours is `workflows`.
2. **Onboarding status `COMPLETED` means "config stored", not "repo
   reachable".** It never validates credentials. The sync panel
   (`Sync Status: Unknown`, `0 synced resources`) reads **identically on working
   and broken applications** — it is cosmetic on free tier.
3. **The ServingTemplate must match the accepted shape**: only
   `scenarios.ai.sap.com/id` and `ai.sap.com/version` as labels. An
   `executables.ai.sap.com/id` label, or version `"1.0.0"` instead of `"1.0"`,
   prevented the scenario appearing at all.
4. **Two credentials, two scopes.** Git sync needs `repo`; the
   `docker-registry-secret` needs `read:packages`; pushing an image needs
   `write:packages`. **GitHub's 403 distinguishes none of them** — it reads as
   an authentication failure when it is authorization.
5. **Quota is 1 pod.** A stop-then-create race marks the new revision failed
   **permanently** — Kubernetes never re-drives an admission-rejected revision.
   Delete the old deployment and create cleanly with nothing else in existence.

**Never diagnose AI Core from the cockpit.** Go to the API:

```
GET $AI_API/v2/admin/repositories
GET $AI_API/v2/admin/applications/{name}/status     <- names the real rejection
GET $AI_API/v2/lm/scenarios                          (AI-Resource-Group: default)
```

**Verification traps, general:**

⛔ **AUTHORIZATION INFERRED FROM AMBIENT SIGNAL — named 2026-08-16.** The
executor treats tone, satisfaction, impatience or momentum as if it were
scope. Two instances in two rounds: a registry-push grant requested mid-release
"to save a round trip" after being blocked, and — worse — "90% is fine, let's
not waste time" read as *the project is complete*, which put GLiNER into a
table of **cancelled** work in the durable record. It was caught only because
the human said "this project is include Gliner"; otherwise the handover would
now record a blocked item as a dropped one.

The tell is that the executor can never quote the authorization, only
characterise it. **The rule is in "Settled": scope and authorization changes
are recorded only as verbatim, dated, attributed human words**, with `40f1da0`
as the template. A blocked action is a decision point, not an obstacle to
route around, and a satisfied human is not a finished project.

6. **A check that reports "clean" may not have run.** Three times this project:
   BSD `grep -v '[^ -~]'` silently failed to match a `0xa7` byte and reported
   the file pure ASCII; an unquoted `gh api "…?recursive=1"` was glob-eaten by
   zsh and the downstream grep passed against empty input; a wrapper's trailing
   `echo` made a failed `docker build` look like exit 0. **Make checks print
   what they inspected**, not just a verdict.
7. **Assert recognizer negatives against the RAW recognizer, not merged
   output.** `_merge` can hand an overlap to a longer span of another type,
   hiding a false positive. This produced a false pass on
   `4 Goods Receipt Close` during the address work.
8. **`LABEL_MAP` silently drops unknown entity labels — ✅ now ANNOUNCED
   (1.2.2). This entry has been wrong twice; both corrections are kept below,
   because what it got wrong is more instructive than what it got right.** An
   entity label with no `LABEL_MAP` entry falls through `_norm()`'s
   `label.upper()` default, lands outside `REDACT_TYPES`, and is discarded —
   *for any label that actually reaches `_norm()`.* That qualifier is the
   second correction, and it is load-bearing.

   ⚠️ **Correction 1, measured 2026-08-16.** This entry used to say the defect
   was "only reachable through lg, which is not shipped". **False. `FAC` is
   unmapped on `en_core_web_sm` today.** spaCy `sm` emits `FAC`; presidio
   neither maps it to a presidio entity nor lists it in `labels_to_ignore`.
   The gap was never latent on the shipped config — nobody had looked.

   ⚠️ **Correction 2, measured 2026-08-16 at Task 3 of 1.2.3 — this entry's
   own mechanism was wrong.** Correction 1 went on to say `FAC` "arrives at
   `_norm()` raw, has no `LABEL_MAP` entry, and is dropped". **It does not
   reach `_norm()`.** `SpacyRecognizer` declares support only for
   `DATE_TIME`/`NRP`/`LOCATION`/`PERSON`/`ORGANIZATION`, so it never emits a
   `RecognizerResult` for `FAC` and the span is gone one layer earlier, at the
   recognizer, before `LABEL_MAP` is consulted at all. Verified in the pinned
   container: `detect()` returns `[]`, and adding `FAC: "ADDRESS"` to
   `LABEL_MAP` changes nothing. Full record: `fac_probe_validation.md`.

   **Consequence for the diagnostic: `unmapped_labels()` over-reports, by
   construction.** It models `labels_to_ignore` and the entity mapping but
   **not** `supported_entities`, so its output is a **superset** of the labels
   that can leak — every unmapped label, whether or not the pipeline can ever
   produce one. `FAC` is a true entry in that superset and a false entry in a
   leak list. The report is still worth making (both cases are gaps, neither
   redacts), but **do not read the field as a leak list.** Modelling
   `supported_entities` is deferred to the recognizer plan; 1.2.3 corrected
   the documentation and the log line only, and moved no detection.

   `unmapped_labels()` computes this from **presidio's own configuration**
   rather than a reimplemented mapping, and `get_analyzer()` logs it. Current
   text, as corrected in 1.2.3:

   ```
   WARNING LABEL_MAP has no entry for: FAC -- these labels have no redacting
   type, so they are never redacted. This check does not model recognizer
   supported_entities: a label listed here may be dropped AFTER detection, or
   may never reach the pipeline at all (FAC is the latter) (trap 8)
   ```

   The 1.2.2 text it replaced said the spans were "DETECTED and then silently
   dropped, never redacted". Accurate for a label that reaches `_norm()`,
   wrong for the only label the check has ever reported.

   ⚠️ **It fires on first analyzer build, NOT at process start** — model
   loading is lazy so `/health` stays instant and readiness probes never time
   out. A pod that has only ever answered health checks has not logged it yet.
   Look after the first `/v1/scrub` or `/v1/selftest`, not immediately after
   `RUNNING`. Verified in-container on 1.2.2: absent at boot, present after
   the selftest. This is a property of the lazy load, which stays.

   **This announces the drop; it does not stop it.** Mapping `FAC` to a
   redacting type is a detection change and needs its own evidence — an
   over-redaction risk in SAP prose, where facility-ish nouns are common.
   That is a separate item, deliberately not smuggled in here. Asserted by
   `test_label_map.py`.

**True measurement taken at the wrong layer — a class of its own, found
2026-08-16.** A number can be correct, reproducible, independently confirmed,
and still describe something the product never sees.

The `FAC` promotion (1.2.3 item 3) was justified by an incidence probe: `FAC`
spans in the corpora, 4 found by the reviewer, 8 after the executor rescanned.
Both probes were right. Both used **raw spaCy** — `nlp(text).ents` — and the
pipeline does not. `SpacyRecognizer.supported_entities` has no `FAC`, so
presidio emits no result and `analyze()` returns empty. The spans are real in
spaCy and invisible to the scrubber. Mapping `FAC` in `LABEL_MAP` would have
changed nothing:

```
BEFORE  detect(): []
AFTER FAC->ADDRESS in LABEL_MAP: []
```

**Independent reproduction did not catch it, because both parties measured the
same wrong layer.** Agreement is not validity; two people can confirm each
other's answer to a question the system was never asked. What caught it was
**container validation against the real call path** (`app.detect()`), which is
why Q2 required probes to fire in the pinned container rather than the venv.

The tell is a measurement taken with a *library* the product depends on rather
than through the *entry point* the product actually calls. Whenever evidence
comes from `nlp(...)`, `spacy.load(...)`, a recognizer constructed by hand, or
any direct model call, ask which layers sit between it and `scrub()` — and
measure through those instead. **A leak class can be simultaneously real and
unreachable by the fix proposed for it.**

**Metadata-as-payload — hit three times, so treat it as a class.** Something
that reads as *outside* the measurement turns out to be *inside* it. The tell
is always the same: a label, banner or annotation that a human parses as
commentary and the machine parses as data.

| Instance | What happened |
|---|---|
| Annotation prefixes in eval samples | `"DOCUMENTED GAP — ..."` and `"Control — ..."` were written into the `text` field. The scrubber redacted words out of the annotations — `jargon` and `Basis` as `<ORG_NAME>` — corrupting the input and inflating the over-redaction count 3 → 4. Fixed: labels moved to a `note` field the harness never transmits. |
| The `__version__` line | `getattr(presidio_analyzer, "__version__", "unknown")` printed `presidio unknown` on every run for months. It reads like version evidence; it reported nothing. The docs' `2.2.357` came from pip, not from the line that claimed it. |
| The `HOLDOUT RESULT` banner | `test_deployed.py` prints that header for **any** input file. Run against `eval_samples_v2.json` it prints `HOLDOUT RECALL: 92.6%` for a set that is explicitly not a holdout. Nothing is wrong with the scorer; the banner is a lie the caller must not repeat. |

**Rule: anything that will be scored, transmitted, or read as a result must be
kept structurally separate from anything that describes it.** Put commentary in
a field the pipeline does not consume, and never let a shared harness name the
thing it is measuring — the caller does that. When quoting a number, quote the
source file with it.
8. **Never construct a bare `AnalyzerEngine()`.** Presidio's default resolves to
   `en_core_web_lg` and **downloads it** — an outbound call, forbidden by Rule
   3, and any figure produced that way is measured against the wrong model.
   Mirror `app.py`: explicit `NlpEngineProvider` pinned to `SPACY_MODEL`, or
   import `app.get_analyzer()`.
9. **This machine is Apple Silicon; AI Core is x86_64.** Always build
   `--platform linux/amd64` and verify with `docker buildx imagetools inspect`.
   A digest check alone cannot catch this — on an arm64 host, an arm64 image
   round-trips perfectly and still cannot run. Emulated builds are cheap here
   (~3 min): pip installs prebuilt manylinux wheels, so QEMU emulates almost
   nothing.

---

## Three defects fixed early — leave them alone

Each is commented in `app.py` and each would have been painful to diagnose from
inside a deployment:

1. **Outbound call from inside the boundary.** Presidio's `UrlRecognizer`
   fetches the public suffix list from `publicsuffix.org` at runtime. Removed.
2. **Case-insensitive regex.** Presidio applies `IGNORECASE` by default, so the
   SAP user-ID pattern matched ordinary words ("stuck", "status", "sales") —
   249 spans against 45 real values. Fixed with explicit case-sensitive flags.
3. **A leak caused by span ranking.** spaCy labels `172.16.4.8` as `DATE_TIME`
   (0.85), outranking `IP_ADDRESS` (0.60) — and DATE is not redacted, so the IP
   passed through in cleartext. Merge order now always prefers a redacting span
   over a non-redacting one, regardless of confidence.

A fourth, found during deployment: **`presidio-analyzer==2.2.357` ignores spaCy's
`ORG` label** at the NLP-engine layer, making unsuffixed company names
undetectable. `get_analyzer()` rebuilds `labels_to_ignore` minus
`ORG`/`ORGANIZATION`. The documented "100% / over_detections 6" baseline had
been measured on 2.2.364 installed unpinned — always install from
`requirements.txt` when producing a number anyone will quote.

---

## Detectors

Presidio built-ins (spaCy `en_core_web_sm`) with `UrlRecognizer` removed, plus
nine deterministic SAP recognizers in `recognizers.py`:

`sap_customer_number` · `sap_vendor_number` · `sap_user_id` ·
`sap_document_ref` · `permissive_email` · `company_suffix` ·
**`street_address`** · `phone_extension` · `bank_account`

`street_address` (added 2026-08-15, closed the P1 gap 0/3 → 3/3) has two rules
keeping SAP prose out: a capitalised name word is **mandatory** between the
number and the street type, so `3 Way match` cannot match; and ambiguous street
types (`Place`, `Court`, `Close`, `View`, `Row`, `Track`, `Way`, …) additionally
require a trailing comma-locality.

The allowlist is matched **case-sensitively** on purpose: `MARA` the table is
allowlisted, `Mara` the person is still redacted. `detect()` additionally
refuses to suppress a pure-alpha token when user-context words ("posted by",
"user", "author") appear within ±40 characters.

---

## How to resume

**Start here if you are picking up 1.2.3 (the open work):**

- **`docs/superpowers/plans/2026-08-16-pii-scrubber-1.2.3-bundle.md`** — the
  live plan. §5 is the pre-registration (all gates exact, nothing moves), §4
  holds the answered Gate-0 questions, Appendix A holds the FAC evidence and
  the 4→8 correction. **Item 3 in that plan is withdrawn**; the top of this
  handover says why.
- **`fac_probe_validation.md`** — the Task 3 record and the finding that
  withdrew item 3. Read the vacuity note before reusing any of its numbers.
- **`fac_probe_samples.json`** — the probe batch. Committed on purpose:
  burned sets are hidden because visibility destroys them, a development
  verification set is committed because visibility is its purpose.
- **The immediate next action** is replacement Task 4 (three description
  corrections, docs and strings only), which is **gated on Teru confirming
  the release scope change**: 1.2.3 = items 1-2 + corrections, item 3 gone.
  Then Task 5 gates at exact-zero movement, then build, then the review gate,
  then publish. **Nothing is pushed until the review gate.**

**Historical, for context:**

1. `docs/superpowers/plans/2026-08-15-pii-scrubber-task-list.md` — the run
   sheet. Closed at Gate 5, then reopened and re-closed twice for 1.2.1 and
   1.2.2. Three releases verified live; all 18 findings in full.
2. `docs/superpowers/plans/2026-08-15-pii-scrubber-1.2.0-bundle.md` — the
   two-item bundle: plan, decisions, risk register, and Appendix A's glossary
   rejections with the reason each was refused.
3. `docs/superpowers/plans/2026-08-15-pii-scrubber-aicore-deployment.md` — the
   detailed runbook, commands and rollbacks.
4. `holdout_v3.json` — **the blind batch, 90.0%.** Authored outside the build
   session, run once against `db3d9cc5eea296cd`, now burned and readable.
   Gitignored — keep it that way. Its successor must also be authored
   externally; a batch this session can see before the run is not blind.
5. The two HTML reports — current as of Gate 5, gitignored, local only.
6. `PERSON-CONTEXT-FINDING.md` — why the rule-based person promoter was built
   and then **not shipped**. Read before touching the PERSON class.
7. `VSCODE-PROMPT-address-recognizer.md` — the prompt that produced the address
   work; a good template for the remaining backlog items.
8. `eval_samples_v2.json` — 65-sample synthetic verification batch, gitignored
   and local only. Scored by the same harness:
   `SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py eval_samples_v2.json`.
   Read its `_provenance` block before quoting anything from it; each
   gap-targeting sample carries a `note` field explaining what it probes, and
   that field is never sent to the service.

## ~~Next release — 1.2.1~~ ✅ SHIPPED 2026-08-16

Both items landed and are verified on the deployment. `BUILD_VERSION` is baked
and echoed by `/info` and `/v1/selftest`; all eight glossary entries shipped
(`GL` `FX` `WM` `MDG` `MRP` `OSS` `CFO` `Rise`), each traced to a blind-batch
sample. `Rise` left the PRE-CLEARED list because the blind batch supplied the
missing incident — clearance and evidence pairing up, which is how that
protocol was designed to work.

Measured effect: no gate moved, and over-redactions on the `holdout_v3`
controls fell **8 → 1**. `over_detections` on the self-test held at 4.

---

## Next release — 1.2.2, scoped at two items

Both approved 2026-08-16 at the 1.2.1 close-out review. Scope is frozen at
two; a third is a new plan.

**1. `@app.get("/v1/info")` on the existing `info()` handler.** One decorator
line, matching the idiom already in `app.py` where `/health`, `/v1/health` and
`/` stack on one function. No new handler, no new payload.

The reason is **not** the selftest cost. It is that **identity should be cheap
enough to check reflexively.** Today, reading the build off a deployment means
running a 13-sample selftest, because `/info` is not proxied — so nobody checks
casually, and an identity check people avoid is an identity check that does not
happen. This makes "which build answered?" a free question.

**2. `LABEL_MAP` unknown-label warning.** Latent defect, deferred twice. An
entity label with no `LABEL_MAP` entry maps nowhere and never becomes a
redacting type — no warning, no log line, the value leaks in cleartext. Found
via `en_core_web_lg`, which types `Harbour Freight` as `FAC` where `sm` types
it `ORG`. Only reachable through `lg` today, **but any future model or spaCy
upgrade can introduce new labels and the failure is silent.** A startup-time
warning listing the model's labels absent from `LABEL_MAP` is a one-liner and
turns a silent drop into a visible one.

Both are small. Neither changes detection on the shipped config, so the four
burned gates should read exactly `108/111`, `65/68`, `45/50`, `45/45` — and a
change in any of them means something unintended moved.

**Backlog, roughly in value order:**

| | Item | Note |
|---|---|---|
| ~~P1~~ | ~~street addresses~~ | ✅ **closed 2026-08-15** — 0/3 → 3/3 |
| ~~P2~~ | ~~person-context promoter~~ | ⛔ **closed 2026-08-15 as a negative result** — built, measured, reverted. Reaches ~1/3 of the residual PERSON class. `PERSON-CONTEXT-FINDING.md` |
| ~~P2~~ | ~~unpadded customer number~~ | ✅ **shipped in 1.2.0** — twelve cue-gated lookbehind patterns. Blind batch confirmed the *bound*, not a defect: `5591230` behind `client` and `6620945` behind `ship-to` leak because those cues are outside the frozen list, `ship-to` deliberately so. Widening the list is a live option, and `client` is the strongest candidate |
| ~~P3~~ | ~~SAP jargon glossary~~ | ✅ **shipped in 1.2.0** — 29 entries; **8 more shipped in 1.2.1**, total 37 entries / 36 tokens. `Close` `Court` `Terrace` `Drive` stay pre-cleared-but-unshipped until evidence appears |
| ~~—~~ | ~~`BUILD_VERSION` / artifact identity~~ | ✅ **shipped in 1.2.1** — baked at build time, echoed by `/info` and `/v1/selftest`, printed by `test_deployed.py`. Detects template-to-pod drift, **not** tag mutation — see Settled |
| ~~P2~~ | ~~`en_core_web_lg` upgrade~~ | ⛔ **CLOSED 2026-08-15, not deferred.** Measured net zero (173/179 either way), two new ORG regressions, 433 MB and 2.2× RSS. The residual class is an engine-level question, not a model-size one — see the finding above |
| ~~1.2.2~~ | ~~`@app.get("/v1/info")`~~ | ✅ **built 2026-08-16** — one decorator on the existing handler, same stacking idiom as `/health`. Identity is now free to check |
| ~~1.2.2~~ | ~~`LABEL_MAP` unknown-label warning~~ | ✅ **built 2026-08-16** — and it corrected trap 8: `FAC` is live on the SHIPPED `sm` model, not lg-only as recorded. Announces the drop, does not change detection |
| — | map `FAC` to a redacting type? | **opened by the 1.2.2 warning.** Needs its own evidence: `FAC` covers facilities, and SAP prose is full of facility-ish nouns, so this is an over-redaction risk, not a free win. Do not fold into a release without a measured case |
| ~~—~~ | ~~expand the sample set to 50–100~~ | ✅ **done 2026-08-15** — `eval_samples_v2.json`, 65/68. Synthetic and Claude-authored; now burned as a gate at exactly 65/68 |
| — | GLiNER bake-off / Local LLM | **the only open route for the residual PERSON class.** Blocked on finding 11. Not a model-size question — the per-token lottery is confirmed on three datasets |
| — | real anonymised ticket shapes | every evaluation set to date is synthetic. The blind batch removed the *authorship* bias, not the *synthetic* one |

Every task ends at an approval gate with a stated deliverable and word limit.
Do not chain phases unattended — this runs against a shared corporate BTP
account with finite free-tier quota.

---

## Environment notes for this machine

- **System Python is 3.14.3**, which cannot install the pinned `torch==2.5.1` /
  `spacy==3.8.3` — no cp314 wheels. The pins do not change; the interpreter
  does. Use `uv venv --python 3.12 --seed .venv`. The `--seed` flag is
  mandatory: without it the venv has no pip, `pip install` escapes to the system
  Python, and `python -m spacy download` fails the same way.
- **Docker** running (server 29.2.1, 10 CPUs, 8.2 GB).
- **Disk is tight** — roughly 12–16 GB free on a 90%+ full volume, against
  ~2.5 GB per image. Do **not** run `docker system prune`; an unrelated
  `frappe_docker` container and its images are present.
- If a build dies with `lease does not exist: not found`, that is a corrupted
  BuildKit lease, not disk or network. `docker pull` the base image, then
  rebuild unchanged.

---

## Running the evaluations

```bash
source .venv/bin/activate

# Six suites. The counts are the baseline -- a change in ANY of them is
# reportable, in either direction.
python test_fixes.py            # 16  three fixed defect classes + recall invariant
python test_address.py          # 39  street-address recognizer, both directions
python test_customer_number.py  # 33  cue-gated lookbehind patterns
python test_jargon.py           # 74  glossary: suppression under the context backstop
python test_build_version.py    # 29  build identity, /v1/info + payload semantics, routes
python test_label_map.py        # 37  unmapped-label diagnostic, failure isolation, corrections pinned

# The four burned gates, all exact. Any movement either way is a stop.
#   holdout_samples.json  108/111   eval_samples_v2.json  65/68
#   holdout_v3.json        45/50    /v1/selftest          45/45, over_detections 4

# against the deployment (DEPLOYMENT_ID defaults to daedcfe9342d21a7)
export AI_API=... TOKEN=...
python3 test_deployed.py holdout_samples.json

# or against a local service, same scorer
SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py holdout_samples.json
```

**Do not tune recognizers against `holdout_samples.json`.** The moment a rule is
adjusted to make a specific holdout sample pass, the set stops measuring
anything. Build from a class description, verify on a fresh batch
(`address_verify_samples.json` is the worked example), and only then re-run the
holdout.

---

## Credentials

### 📌 Rotation DEFERRED to project completion — decided by Teru, 2026-08-16

The AI Core service key and the GitHub PAT **both transited chat on
2026-08-15** and are still live. Rotation was raised at four consecutive
review rounds and is now **deliberately deferred to the end of the project**,
as an accepted risk, by the person who owns it. **This is a decision, not an
oversight — do not re-raise it as an open finding each round.**

Recorded so it survives the deferral:

| | |
|---|---|
| **Exposed** | AI Core service key (`~/aicore-key.json`), GitHub PAT |
| **How** | pasted into chat, 2026-08-15 |
| **Blast radius** | one free-tier AI Core tenant; one private repo + its GHCR images |
| **Owner** | Teru |
| **Trigger** | project completion — **not** a date, so it cannot quietly lapse |
| **Also then** | delete the two stale "PII Scrubber" configurations (7:19 PM / 7:33 PM) in AI Launchpad |

**The trigger is the risk.** A deferral tied to an event only closes if
someone checks at that event, so this is the last thing on the completion
checklist, not a background intention.

None are stored in this repository, and none should ever be. Registry tokens,
GitHub tokens and BTP client secrets are supplied at the moment of use via
environment variables and never committed, echoed into logs, or embedded in a
git remote URL. The AI Core `docker-registry-secret` is created in the AI
Launchpad cockpit by a human, not by tooling.

The registry secret targets **`https://ghcr.io`** — not
`https://index.docker.io`, which is what the runbook's example shows:

```json
{".dockerconfigjson":"{\"auths\":{\"https://ghcr.io\":{\"username\":\"TeruSin71\",\"password\":\"<PAT>\"}}}"}
```

Mint bearer tokens yourself and hand over only the token, never the client
secret — the token expires, the secret mints unlimited new ones.
