# PII Scrubber — GLiNER Bake-off Plan

**Gate 0 deliverable. Nothing in this plan has been executed.**
Authored 2026-08-16 against `429a19b`, after the Rule 7 gate.
Backend is **torch**; the ONNX arm is struck and deferred. Ship candidate is
**frozen** at `pii-scrubber:gliner-cand`.

**Binding process, restated:** the plan is reviewed **before** anything runs.
Per the reviewer at the Rule 7 gate — *"Nothing else runs — no build, no
deployment touch — until that plan is reviewed."* Task 0 is the first thing
that executes, and only after Gate 0 answers §4's questions.

**⚠️ Read §3.5 before anything else.** Two of the conditions under which GLiNER
was measured are properties of the **test invocation**, not of the **shipped
artifact**. If the pod does not reproduce them, none of the measurements
describe production. That is this project's oldest trap wearing new clothes,
and it is cheap to close before the run rather than after.

---

## 1. Executive Summary

**Goal.** Decide — on pre-registered evidence, against one frozen image —
whether GLiNER ships, **on which path** (batch, live, both, neither), and in
which **mode** (`presidio` / `gliner` / `both`). The deliverable is a
**decision plus a pre-registered gate set for the release that would follow**,
not a number anyone quotes.

**Why now, and why it is bounded.** The residual leak class is PERSON, it is
per-token rather than per-frame, and every non-engine lever has been measured
and closed: rules reach ~1/3 of it (`PERSON-CONTEXT-FINDING.md`), and a larger
spaCy model measured net-zero across 179 values. GLiNER is the only open route.
It is also **~113× slower per request than presidio on one vCPU**, so this is a
cost/benefit measurement with a real possibility of a **no-ship** outcome — and
a no-ship is a result, not a failure.

**⛔ This plan produces NO quotable figure, by construction.** All four
evaluation sets are burned. Every recall number below is **engineering
comparison and regression only**. A quotable figure requires blind batch v4,
authored externally, run once. That is a different piece of work and it is
**not** in this plan.

**Success criteria — all measurable, all blocking:**

| # | Criterion | Source |
|---|---|---|
| 1 | **Control arm reproduces exactly.** `presidio` mode returns `108/111`, `65/68`, `45/50`, selftest `100.0 / 45/45 / missed 0 / over_detections 4 / spans 49` | frozen image, local |
| 2 | Each run's engine condition is **read back**, never assumed: `/v1/info` shows the expected `engine` and `gliner_loaded` | `/v1/info` per run |
| 3 | Three modes measured on **one image**, **one corpus set**, **one frozen threshold** | run log |
| 4 | Per-engine over-redaction: every over-detection attributed to `presidio` or `gliner` by the span's own `engine` field | span dump |
| 5 | **Per-path** over-redaction reported separately for batch and live, because it is only a defect on one of them (§2.6) | scrub output, both modes |
| 6 | Pod-fitness gates re-run per mode with measurement conditions **proved, not assumed** (§3.5) | `pod_fitness.py` + `docker stats` |
| 7 | Union-mode coverage regression check: no value redacted in `presidio` mode is left exposed in `both` mode (§3.4, R4) | leak lists, line-by-line |
| 8 | A written recommendation naming the path, the mode, and the pre-registered gates of the release that would follow | this plan's §12 |
| 9 | Nothing pushed, nothing built after the freeze, deployment untouched | `git log`, `docker images` |

**Criterion 1 is the load-bearing one and it is deliberately first.** The
`presidio` arm is a **control**, not a data point — its numbers are already
known to the digit. If the frozen image does not reproduce them, the rig is
wrong and **every GLiNER number taken on it is void**. Measuring the control
first is what stops a rig defect from being read as an engine result.

**Time estimate.**

| Task | Budget | Risk |
|---|---|---|
| 0 — Gate 0 answers + provenance + baseline capture | 45 min | read-only |
| 1 — (conditional) artifact-condition fixes + ONE rebuild, re-freeze | 60 min | ⚠️ rebuild, only if Gate 0 says yes |
| 2 — control arm: `presidio` mode on the frozen image | 30 min | local |
| 3 — `gliner` mode: detection + over-redaction, both paths | 60 min | local, slow |
| 4 — `both` mode: same, plus the coverage-regression check | 60 min | local, slow |
| 5 — pod-fitness per mode, conditions proved | 60 min | local, slow |
| 6 — synthesis, recommendation, release pre-registration | 60 min | writing |
| 7 — ⛔ **REVIEW GATE** | — | nothing ships, nothing pushes |

≈ 6 hours, or ≈ 7 with Task 1. Tasks 3–5 are slow because GLiNER is slow: a
65-sample batch is **47.6 s** against presidio's **0.5 s**, and that cost is
paid several times over.

**Risk posture.** Low on the artifact — no deployment is touched, nothing is
pushed, and the only build is a conditional one that Gate 0 must authorize.
**Higher on inference:** the standing danger in this plan is not breaking
something, it is **concluding something the measurement does not support** —
quoting an emulated latency as the pod's, reading a threshold asymmetry as an
engine difference, or letting a burned-set movement become a claim.

---

## 2. Philosophy and Principles

1. **Evidence before action.** Every fact in §3 carries the command or file
   that produced it, and every inherited fact is marked as inherited.
2. **The control arm validates the rig before the rig produces evidence.**
   `presidio` mode's four exact numbers are known. They are measured first, and
   a deviation voids everything downstream rather than being explained.
3. **Prove the condition, do not assume it.** Every run reads back `engine` and
   `gliner_loaded` from `/v1/info`. A mode is what the service reports, never
   what the command line intended.
4. **A measured condition that lives in the run command is not a property of
   the artifact.** If production must be offline and single-threaded for the
   numbers to hold, the artifact — or the template — must make it so. §3.5.
5. **Thresholds are frozen before the run, not tuned during it.** There is no
   corpus in this project on which a threshold may legitimately be tuned: all
   four are burned. §4/Q5.
6. **Over-redaction is path-dependent and must never be reported as one
   number.** On **batch** it has a real cost — the KB text must stay readable.
   On **live** it costs nothing, because the caller re-maps inside the
   boundary. An engine that over-redacts may be correct for live and wrong for
   batch, and a single blended figure hides exactly that.
7. **No-ship is a permitted, pre-stated outcome**, and so is a split decision
   (GLiNER batch-only, presidio live). The fallback is already registered by
   the reviewer; this plan does not get to discover it later.
8. **Burned sets compare engines; they never measure the product.** Any
   sentence of the form "GLiNER improves recall to X%" is out of scope of every
   number this plan can produce.

---

## 3. Current State — verified ground truth

Measured 2026-08-16 against `429a19b` unless marked **[inherited]**, which
means it comes from `docs/HANDOVER.md` and was **not** re-measured this
session.

### 3.1 The frozen ship candidate

| | | Source |
|---|---|---|
| Tag | `pii-scrubber:gliner-cand` | `docker images` |
| Created | **2026-08-16 13:42:56 +1200** | `docker images` |
| Size, uncompressed | **4.64 GB** | `docker images` |
| Size, compressed | **1.51 GB** | **[inherited]** — `docker save \| gzip \| wc -c`, previous session |
| Superseded | `pii-scrubber:gliner-spike`, 6.76 GB, safe to delete | `docker images` |

⚠️ **The two size figures measure different things and neither is wrong.**
4.64 GB is the uncompressed on-disk sum; 1.51 GB is what a registry pull moves.
**The pod-fitness gate is the compressed figure**, because that is what a
1-pod free tier waits on during a cutover. Any size claim must name its method
— `docker image inspect .Size` has already disagreed with itself once in this
project.

### 3.2 ⚠️ The candidate's provenance is ASSERTED, not STAMPED

The Rule 7 decision says the image *"freezes at b5fbaf6's build"*. That cannot
currently be verified **from the artifact**:

```
image  pii-scrubber:gliner-cand   created  2026-08-16 13:42:56
commit b5fbaf6                    authored 2026-08-16 13:49:08
```

**The image is 6 minutes 12 seconds OLDER than the commit it is said to
freeze.** That ordering is *normal* — build, then commit — and it is not
evidence of a mismatch. It is also not evidence of a match. The image carries
`BUILD_VERSION` (default `dev`) and **no git sha**.

What can be said, and it is circumstantial:

- Every tracked build input (`app.py`, `recognizers.py`, `samples.json`,
  `allowlist.txt`, `glossary.txt`, `requirements.txt`, `Dockerfile`) has an
  mtime **earlier** than the image's creation time.
- The working tree is clean, and the two commits after `b5fbaf6` touched
  **only** `docs/HANDOVER.md`, so the tracked build inputs on disk today are
  byte-identical to those at `b5fbaf6`.

**This project invented `BUILD_VERSION` because artifact identity kept being
inferred instead of read.** Inferring it again for the one image every
subsequent decision rests on would be the same error with a better excuse.
Q1 decides whether to accept the circumstantial argument or spend one rebuild
on a stamp.

### 3.3 The three modes already exist — no code is needed to select them

`SCRUBBER_ENGINE` is read once at import (`app.py:38`) and dispatched in
`detect()` (`app.py:515-537`):

| Mode | What runs | Verified at |
|---|---|---|
| `presidio` | presidio spans only | `app.py:518` |
| `gliner` | GLiNER spans only | `app.py:530` |
| `both` | presidio spans **then** GLiNER spans, appended, then `_merge()` | `app.py:518,530,565` |

**`both` is already the union mode**, by construction rather than by intent —
the two span lists are concatenated and overlap-resolved. So the bake-off's
three modes need **one image and three container runs**, no rebuild and no code
change. `SCRUBBER_ENGINE` is baked as `presidio` (`Dockerfile:91`) and
overridden per run with `-e`.

⚠️ **Mode is process-wide, not per-request.** `scrub()` and the selftest both
call `detect(text, ENGINE)` using the module global. There is no per-call
engine override, so the three arms cannot be interleaved against one running
service — each is a separate container run, and each must read its own
`/v1/info` back.

All ten `GLINER_LABELS` (`app.py:63-67`) resolve through `LABEL_MAP`
(`app.py:70-84`) to a redacting type in `REDACT_TYPES` (`app.py:153-156`):
person, email address, phone number, physical address, organization, customer
number, vendor number, user id, ip address, bank account number. **No GLiNER
label falls through unmapped**, so trap 8 does not apply to this engine.
GLiNER has no label for `DOC_REF`; that type stays presidio-only.

### 3.4 ⚠️ Two mechanisms that will distort a naive comparison

**(a) The threshold policy is asymmetric between the engines.** This is the
single most important finding in this section.

| | Filter applied | Where |
|---|---|---|
| presidio spans | **per-type floors** — `TYPE_THRESHOLDS`, e.g. `PERSON 0.50`, `USER_ID 0.55`, `EMAIL 0.30`; default `0.50` | `app.py:521-523` |
| GLiNER spans | **one global floor** — `GLINER_THRESHOLD`, default `0.4`, applied inside `predict_entities` | `app.py:531-532` |

**`TYPE_THRESHOLDS` is never applied to GLiNER spans.** A GLiNER `PERSON` at
0.45 survives; a presidio `PERSON` at 0.45 is discarded. So a default-settings
three-mode comparison is **not** comparing two engines — it is comparing two
engines *under two different threshold policies*, and any recall or
over-redaction delta silently contains both effects. Q4 decides what to do
about it; §5 registers the consequence either way.

**(b) `_merge` can lose coverage at a span edge when the union adds a span.**
`_merge` (`app.py:568-589`) sorts by *(redacting first, then longer, then
higher score)* and keeps greedily non-overlapping. Adding GLiNER spans to the
input can therefore **evict** a presidio span:

```
presidio span P = [10, 20]   length 10
gliner   span G = [ 5, 18]   length 13   -> G outranks P, P is dropped
characters 18-20 are now unredacted
```

Both are redacting types, so the redaction-first rule does not separate them,
and length decides. **Union can expose the tail of a value that presidio alone
redacted.** This is a mechanism read from the code, not an observed failure —
which is exactly why criterion 7 exists to look for it, and why the leak lists
are compared line-by-line rather than by count.

Related and unresolved: the tie-break's third key is **score**, comparing a
presidio confidence against a GLiNER sigmoid. **The two scales have never been
shown to be comparable**, and nothing in the codebase claims they are.

**One positive, verified:** the allowlist / glossary suppression loop
(`app.py:553-563`) runs **after** both engines and is engine-agnostic, so
GLiNER spans inherit the case-sensitive allowlist, the custom-SAP-object rule
and the ±40-char user-context backstop. The jargon protections are not
presidio-only. ⚠️ But suppression is **exact-token** — a GLiNER span with
different boundaries than the allowlisted token will not match it. See R1.

### 3.5 ⛔ The measurement conditions live in the run command, not the artifact

Both conditions under which GLiNER was validated are supplied from outside the
image:

| Condition | Where it is set today | What the artifact says |
|---|---|---|
| **Offline** (`HF_HUB_OFFLINE=1`) | `docker run -e` in `test_gliner_tokenizer.py:8` | ⛔ Not set in the image. `Dockerfile:10` sets **`TRANSFORMERS_OFFLINE=0`** |
| **Thread cap** (`OMP_NUM_THREADS=1`) | the pod-fitness run command **[inherited]** | ⛔ Not set in the image, not in `Dockerfile` |

Why each matters, concretely:

1. **Offline is the condition the tokenizer finding depends on.** The resolved
   finding is that offline forces a sentencepiece→fast *conversion* (governed
   by the `fix_mistral_regex` heuristic), while online transformers downloads a
   prebuilt `tokenizer.json` and the flag never bites. The handover already
   records the forward half — *"a tokenizer test run with network access
   exercises an artifact production never uses"*. **The converse is the live
   risk: if the pod has egress, production loads an artifact the test never
   exercised.** And a download from inside the compliance boundary is a Rule 3
   violation of exactly the class already fixed once, when presidio's
   `UrlRecognizer` was found fetching `publicsuffix.org` at runtime.
2. **The thread cap is what makes the latency numbers mean anything.** Under a
   1-vCPU cgroup limit, torch does not necessarily see one core — it commonly
   sizes its thread pool from the host's core count and then thrashes against
   the quota. The measured `--cpus=1` figures were taken with threads capped;
   an uncapped pod is a **different and probably worse** machine.

**Neither is a defect in what was measured. Both are a gap between what was
measured and what would ship.** Closing them is two lines in the `Dockerfile`
(or a `ServingTemplate` env block) — but that changes the frozen candidate, so
it must be decided at Gate 0 and done **once, before** any measurement, never
in the middle. Q2 and Q3.

### 3.6 ⚠️ A stale comment block contradicts the shipped requirements

`Dockerfile:73-90` still states that finding 11 is open — *"setting engine=both
takes the deployment down"*, *"Enabling GLiNER needs a huggingface_hub pin
(Rule 7, needs approval) and a rebuild"*. **All of that is false as of
`1faf3e9`**; `requirements.txt` carries the coupled
`huggingface_hub==0.36.2` + `transformers==4.57.6` pin and documents it
correctly.

The block's own last paragraph is the punchline: *"The same false claim was
corrected in README-DEPLOY.html §7 by a9bed3e; this copy was missed."* It is
now the copy that was missed — the **third** occurrence of "a correction
applied in two of three places", the failure recorded in
`REVIEW-1.2.3-session.md` §5.2.

Comments produce no layers, so fixing it **cannot change the image**. It is out
of scope for this plan's measurement and is listed as Q7 rather than silently
folded in.

### 3.7 What the pod-fitness harness actually does

`pod_fitness.py`, verified by reading it:

- Loads texts from **four** corpora (`holdout_samples`, `eval_samples_v2`,
  `holdout_v3`, `samples`) and **prints any it cannot find**. They are used as
  **load**, not as scoring — no detection is measured, so this use does not
  interact with the burned-set rules.
- Warms up first, so the lazy model load is excluded from every gate.
- Gate 1 single-request p50 (n=7, median-length sample) · Gate 2 longest
  document (n=3) · Gate 3 sequential 65-sample batch · Gate 4 four-way
  concurrency probe on 8 requests.
- ⛔ **Does not measure memory.** It says so and tells the operator to read
  `docker stats` from outside, after the run.

⚠️ **Gate 3's batch is `texts[:65]` in file order.** Its composition therefore
depends on which corpora were present. A run missing a gitignored corpus
measures a **different batch** under the same label — so the run log must
record the "corpora read" line, not just the timing.

### 3.8 Inherited measurements — carried, not re-measured

**[inherited]** from `docs/HANDOVER.md`, all on `--cpus=1 --memory=3g`,
threads capped, emulated amd64-on-ARM:

| Gate | presidio | presidio + GLiNER |
|---|---|---|
| Cold load | 3.6 s | 12.7 s |
| p50, median sample | 6 ms | **678 ms** |
| Longest document | 13 ms | 1,038 ms (max 1,309) |
| 65-sample batch | 0.5 s | **47.6 s** |
| 4-way concurrency | 1.13× | **0.48× — contention**, max 6,465 ms |
| Peak RSS | 456 MiB | **2.18 GiB of 3 GiB**, 823 MiB headroom, no OOM |

⛔ **678 ms is an upper bound (emulated) and 44 ms is a lower bound (native,
many-core). Native amd64 on one vCPU is unmeasured and this Mac cannot produce
it.** Per the Rule 7 decision, the live gate is deferred to pod-time
measurement at a GLiNER release's verification step, with the fallback
pre-stated. **Nothing in this plan may quote either bound as the pod's
latency.**

### 3.9 Environment

Unchanged: `uv venv --python 3.12 --seed`, always `--platform linux/amd64`,
`docker builder prune` allowed and `docker system prune` **never**, disk tight
(~12–16 GB free against ~2.5 GB per image, and the candidate is 4.64 GB
uncompressed).

---

## 4. Decision Matrix

| # | Decision | Chosen | Why not the alternative |
|---|---|---|---|
| D1 | How are the three modes produced? | One frozen image, three runs, `-e SCRUBBER_ENGINE=` | No rebuild, no code change, and the arms cannot drift from each other because they are the same bytes (§3.3) |
| D2 | Can the arms share one running service? | **No** — one container run per mode | `ENGINE` is read at import and used process-wide; there is no per-request override (§3.3) |
| D3 | How is a mode's identity established? | Read `engine` + `gliner_loaded` from `/v1/info` each run | The intent of a command line is not evidence. This is the same reason `/v1/info` exists |
| D4 | Control arm | `presidio` mode, measured **first**, must reproduce four exact numbers | A rig defect discovered after the GLiNER numbers would invalidate them retroactively; discovered first, it costs 30 minutes |
| D5 | Which corpora? | All four burned sets, as **engineering comparison + regression only** | They are the only labelled data that exists. Their standing is unchanged and nothing they produce is quotable |
| D6 | Over-redaction attribution | By the span's own `engine` field, per type, **per path** | A blended figure hides the batch/live asymmetry that decides the recommendation (§2.6) |
| D7 | Latency | Re-run `pod_fitness.py` per mode; report as **bounds**, never as the pod's number | The decisive figure is unmeasurable locally; the Rule 7 decision already routes it to pod-time |
| D8 | Memory | `docker stats` outside each run, **after** the batch and concurrency probes | The harness does not measure it, and an unstressed peak is not the peak |
| D9 | What does the plan output? | A recommendation **plus** pre-registered gates for the release that would follow | A bake-off that ends in a number and no gate hands the next session an unpinned target |

### Open at Gate 0 — the reviewer answers these, they are not assumed

| # | Question | Executor's recommendation |
|---|---|---|
| **Q1** | Candidate provenance: accept the circumstantial argument in §3.2, or spend one rebuild to bake a git sha and re-freeze? | **Rebuild once with a sha, before any measurement.** Every downstream decision rests on this image, and this project's history on inferred artifact identity is bad. If rebuilt, do Q2/Q3 in the same build — one rebuild, not three |
| **Q2** | Bake `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` into the image before measuring? | **Yes.** Offline is the condition the tokenizer finding holds under, and Rule 3 should be a property of the artifact, not a hope about the pod (§3.5) |
| **Q3** | Bake a thread cap (`OMP_NUM_THREADS=1` / `torch.set_num_threads`) or put it in the `ServingTemplate`? | **Yes, and state which layer.** Template is the more honest place — it is where "1 vCPU" is declared — but the image default must not contradict it |
| **Q4** | Threshold asymmetry (§3.4a): compare **as-shipped**, or normalize GLiNER under `TYPE_THRESHOLDS`? | **Compare as-shipped for the bake-off**, and report the asymmetry as a named confound. Normalizing is a **detection change** and needs its own pre-registration; it must not enter as a measurement convenience |
| **Q5** | Freeze `GLINER_THRESHOLD` at its default `0.4` for the entire bake-off? | **Yes.** There is no corpus on which it may legitimately be tuned — all four are burned. Tuning waits for blind batch v4, and that ordering is a finding, not an inconvenience |
| **Q6** | If the control arm does **not** reproduce, what happens? | **Stop.** The rig is void, no GLiNER number is read, and the deviation is the deliverable |
| **Q7** | Fix the false `Dockerfile` comment block (§3.6) here, or as its own commit? | **Its own commit**, outside this plan. It is comments-only and cannot change the image, but folding an unrelated correction into a measurement plan is how scope drifts |
| **Q8** | Does this plan end at a recommendation, or carry through to a GLiNER release? | **Ends at the recommendation + the release's pre-registered gates.** The release is a separate plan with its own Gate 0, its own cutover and its own review |

---

## 5. Pre-registration — written before anything runs

**The control arm has registered values. The GLiNER arms deliberately do
not** — their numbers are the unknown this plan exists to measure, and
inventing an expectation for them would be prediction theatre. What *is*
registered for them is the **stop conditions**.

### 5.1 Control arm — `presidio` mode on the frozen image

| Measurement | Registered value | Any other value |
|---|---|---|
| Selftest `recall_pct` / `redacted` | `100.0` / `45/45`, `missed 0` | ⛔ **stop, rig void** |
| Selftest `over_detections` | `4` | ⛔ stop, rig void |
| Selftest `redacting_spans_emitted` | `49` | ⛔ stop, rig void |
| `holdout_samples.json` | `108/111`, leaks `ZHANG` `Young` `Mere Tuhoe` | ⛔ stop, rise or fall |
| `eval_samples_v2.json` | `65/68`, leaks `44 Bellbird Rise` `Okonkwo` `FONTAINE` | ⛔ stop, rise or fall |
| `holdout_v3.json` | `45/50`, leaks `NAKAMURA` `Park` `Adeyemi` `5591230` `6620945` | ⛔ stop, rise or fall |
| `/v1/info` `engine` | `presidio`, `gliner_loaded: false` | ⛔ stop |

**Leak lists are compared line-by-line, never by count.** Two different sets of
three leaks both read `108/111`.

### 5.2 GLiNER arms — stop conditions, not predictions

| # | Condition | Why it is a stop |
|---|---|---|
| S1 | `/v1/info` does not report the expected `engine`, or `gliner_loaded` is `false` in a GLiNER arm | The run measured something other than what it is labelled |
| S2 | **`both` mode leaves exposed any value that `presidio` mode redacted** | The union has lost coverage — the `_merge` eviction mechanism in §3.4b. This is a defect to fix, **not** an engine result to report |
| S3 | A GLiNER arm's over-detections include a type the engine has no label for | Attribution is broken; the `engine` field is not saying what it appears to say |
| S4 | Any arm is measured at a `GLINER_THRESHOLD` other than the frozen one | Cross-arm comparison is void |
| S5 | Peak RSS in any arm exceeds **3 GB**, or the container exits non-zero | Pod-fitness failure — the ceiling is the pod's, not the laptop's |
| S6 | The corpora line printed by `pod_fitness.py` differs between arms | Gate 3 measured different batches under one label (§3.7) |

### 5.3 Registered in advance: what a PASS looks like

So that a good result cannot be assembled after the fact:

- **Ship GLiNER on batch** requires: a measured recall gain on the burned sets
  *attributable span-by-span to GLiNER spans*, **and** batch-path
  over-redaction that does not degrade readability beyond what the reviewer
  accepts at Task 7, **and** compressed image size + stressed peak RSS inside
  the pod's ceiling.
- **Ship GLiNER on live** requires all of the above **plus** the pod-time
  latency gate, which **cannot be answered by this plan** and is routed to a
  release's verification step with the fallback already stated.
- **No-ship** requires nothing. It is the default if the above are not met.

⚠️ **A recall gain on a burned set is not a product improvement.** It is
evidence that GLiNER finds values *these particular sets already taught us
about*. The gain that would matter is on blind batch v4, which does not exist
yet.

---

## 6. Global Constraints

- **Rule 3:** no outbound calls. No bare `AnalyzerEngine()`. Every GLiNER arm
  runs with `HF_HUB_OFFLINE=1` **even if Q2 declines to bake it in** — the run
  condition is not negotiable, only where it is declared.
- **Rule 7:** no dependency changes. The ONNX arm is struck; `optimum` is not
  installed and `gliner` stays at `0.2.16`. Re-opening either re-opens the
  finding-11 pin chain and the tokenizer arbitration.
- **Rule 4:** no real ticket text.
- **The candidate is frozen.** At most **one** rebuild, at Task 1, only if
  Gate 0 authorizes it, before any measurement. If it happens, everything
  measured before it is discarded and re-run — no mixing.
- **Do not tune anything against the four burned sets.**
- **Nothing is pushed. Nothing touches the deployment.** No registry push grant
  exists; the 1.2.3 grant was revoked and grants are per-release, exact-tag, at
  the publish step.
- Every check prints what it inspected — corpora read, engine reported,
  threshold in force — not just a verdict.

---

## 7. Per-task runbook

### Task 0 — Gate 0 answers, provenance, baseline capture (read-only)

1. Record Gate 0's answers to Q1–Q8 verbatim in this file's §12.
2. **Provenance check** (read-only, no build): run the frozen image and hash
   its build inputs, comparing against the git blobs at `b5fbaf6`:
   ```bash
   docker run --rm --entrypoint sh pii-scrubber:gliner-cand -c \
     'sha256sum /app/app.py /app/recognizers.py /app/samples.json \
                /app/allowlist.txt /app/glossary.txt'
   git cat-file blob b5fbaf6:app.py | shasum -a 256
   ```
   Report match or mismatch **per file**. A mismatch is a stop and makes Q1's
   rebuild mandatory regardless of the answer given.
3. Capture the control baseline the four gates will be compared against, and
   record `/v1/info` in full.

**Report ≤300 words.** Approval gate: the reviewer confirms Q1–Q8 and the
provenance result before Task 1 or Task 2 begins.

### Task 1 — CONDITIONAL: artifact-condition fixes, one rebuild, re-freeze

**Only if Gate 0 authorizes it.** Everything Q1/Q2/Q3 approves goes into a
**single** build:

- a git sha baked as a build arg and surfaced on `/v1/info` (Q1),
- `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` (Q2),
- the thread cap, at whichever layer Q3 names (Q3).

Then `test_gliner_tokenizer.py` re-runs in the new image and must still pass
offline and **still fail loudly online** — the arbitration is re-proved on the
artifact that will actually be measured, not inherited from the old one.
Re-tag as the frozen candidate and record the new digest. **No measurement
before this completes.**

### Task 2 — Control arm: `presidio` mode

Run the frozen image, `SCRUBBER_ENGINE=presidio`. Read `/v1/info` back. Run the
selftest and the three gates.

**Every value in §5.1 must match exactly.** Report matches as matches and any
deviation as a **stop**, with the leak-list diff. Report ≤250 words.

### Task 3 — `gliner` mode

Same image, `-e SCRUBBER_ENGINE=gliner -e HF_HUB_OFFLINE=1`. Read `/v1/info`
back and confirm `gliner_loaded: true` **before** trusting any number.

Capture, for both `batch` and `live` modes:

- recall against the four sets, **with leak lists**;
- every over-detection, with its `engine`, `type`, `score` and the covering
  text — so §5.2/S3 can be checked;
- the batch-path readability sample: the scrubbed text of ~10 samples, so the
  reviewer can judge over-redaction rather than read a count of it.

Report ≤400 words plus the span dump as an attachment.

### Task 4 — `both` mode, plus the coverage-regression check

Same as Task 3 with `SCRUBBER_ENGINE=both`, and one addition that is the
reason this task exists separately:

**Diff `both`-mode leak lists against `presidio`-mode leak lists, per set,
line by line.** Any value redacted under `presidio` and exposed under `both` is
**S2 — a stop and a defect**, and the `_merge` eviction in §3.4b is the first
place to look. Record the offending span pair (presidio span, GLiNER span,
their offsets) if it fires.

### Task 5 — Pod-fitness per mode, conditions proved

`pod_fitness.py` against each of the three arms at `--cpus=1 --memory=3g`, with
the thread cap in force, plus `docker stats` **after** the batch and
concurrency probes for a stressed peak.

Record with every run: the "corpora read" line (S6), the thread cap actually in
force, and whether the run was emulated or native. **Report every latency
figure as a bound with its condition attached.** A figure without its condition
is not reportable in this project.

### Task 6 — Synthesis and recommendation

Produce: the three-mode comparison table; the over-redaction analysis split by
path; the named confounds (threshold asymmetry, score incomparability,
emulation); the recommendation (ship / no-ship / split, and on which path); and
**the pre-registered gates for the release that would follow**, so the next
session inherits a pinned target rather than an ambition.

### Task 7 — ⛔ REVIEW GATE

**Nothing has been pushed, nothing built since Task 1, deployment untouched.**
Deliverable: §5's tables with measured beside registered, the S1–S6 checks each
explicitly stated as fired or not, and the recommendation. **The reviewer
decides whether a GLiNER release is opened.**

---

## 8. Risk Register

| # | Risk | L | I | Mitigation | Detection |
|---|---|---|---|---|---|
| R1 | **GLiNER over-redacts SAP jargon that presidio suppresses**, because allowlist suppression is exact-token and GLiNER's span boundaries differ (§3.4) | **High** | **High** — unreadable KB text on the batch path | Over-detections dumped with covering text, per engine; batch readability sample judged by a human at Task 7 | Task 3/4 span dump; jargon terms appearing inside redacted spans |
| R2 | **Measured conditions are not artifact properties** — offline and thread cap live in the run command (§3.5) | **High** | **High** — production loads a different tokenizer artifact, or thrashes threads | Q2/Q3 bake them in at Task 1 | `Dockerfile:10` reads `TRANSFORMERS_OFFLINE=0` today; no `OMP_NUM_THREADS` anywhere |
| R3 | **Candidate provenance is asserted, not stamped** (§3.2) | Medium | **High** — every decision rests on an unidentified image | Q1 rebuild with a git sha; Task 0 hash comparison meanwhile | Task 0 step 2, per file |
| R4 | **Union loses coverage at a span edge** via `_merge` eviction (§3.4b) | Medium | **High** — a value redacted by presidio alone leaks under `both` | S2 stop condition; line-by-line leak diff, never counts | Task 4 diff |
| R5 | **Threshold asymmetry read as an engine difference** (§3.4a) | **High** | Medium — the wrong engine gets credit or blame | Q4 names it as a confound and forbids fixing it mid-measurement | Present by construction; must appear in every reported delta |
| R6 | An emulated latency is quoted as the pod's | Medium | **High** — a live-path decision on a number that describes no machine | §3.8 restates both bounds; Task 5 attaches conditions to every figure | Any figure reported without its condition |
| R7 | A burned-set gain becomes a claim | Medium | **High** — a burned figure escaping into management material | §1, §2.8 and §5.3 all state it; the reviewer holds the quotable-figure boundary | Any sentence pairing a percentage with an engine name |
| R8 | Cross-engine scores are treated as comparable in `_merge`'s tie-break (§3.4b) | Medium | Medium — arbitrary winner on equal-length overlaps | Recorded as a named confound; not fixed here | Equal-length overlapping pairs in the span dump |
| R9 | Gate 3 batches differ between arms because a corpus was absent (§3.7) | Low | Medium — three arms, three different batches, one label | S6; the "corpora read" line is recorded per run | `pod_fitness.py` prints `(absent, skipped: …)` |
| R10 | A GLiNER arm is measured with GLiNER not loaded | Low | **High** — presidio numbers labelled as GLiNER | S1; `gliner_loaded` read back per run | `/v1/info`; a load failure also raises at request time |
| R11 | Disk exhaustion during a conditional rebuild | Medium | Medium | `docker builder prune` only, with a before/after `docker images` diff proving no image was removed | ~12–16 GB free against a 4.64 GB candidate |
| R12 | Scope creeps from "measure" into "improve" | Medium | Medium — an unreviewed detection change enters as a fix | Q4/Q7 both route changes out of this plan; §11 restates it | Any code edit to `app.py` during Tasks 2–5 |

---

## 9. Rollback

**There is almost nothing to roll back, and that is by design.** No push, no
deployment touch, no registry write. Scopes:

| Scope | Action |
|---|---|
| Mid-task | Stop the container. Nothing persists — every arm is `docker run --rm` |
| Conditional rebuild (Task 1) | The previous `gliner-cand` is replaced by tag. **Keep the old image under a dated tag before rebuilding**, so the pre-fix candidate remains reachable |
| Local commits | `git revert`; nothing is pushed before Task 7 |
| Deployment | **Not applicable.** `daedcfe9342d21a7` runs `1.2.3` throughout and is never touched by this plan |

Known-good throughout: deployment `daedcfe9342d21a7` on `1.2.3`, selftest
`1.2.3 / 100.0 / 45/45 / missed 0 / over_detections 4`.

⚠️ **The one irreversible act available in this plan is burning a corpus.**
The four sets are already burned. **Blind batch v4 must not be run, read, or
salted here** — running it against a candidate that is still being measured
would spend the only unburned instrument this project has on an engineering
comparison.

---

## 10. Verification Strategy

| Level | Command / check | Exit criterion |
|---|---|---|
| Identity | `/v1/info` per run | `engine` and `gliner_loaded` as expected; git sha if Q1 approved |
| Tokenizer | `test_gliner_tokenizer.py` in the measured image | Passes offline, **fails loudly online** |
| Control | selftest + three gates, `presidio` mode | Exactly §5.1, leak lists line-by-line |
| Detection | three gates per GLiNER arm | No stop condition S1–S6 fired |
| Coverage | `both` vs `presidio` leak diff | No value newly exposed (S2) |
| Fitness | `pod_fitness.py` + `docker stats` | Peak RSS < 3 GB; every figure carries its condition |
| Hygiene | `git log`, `docker images` | Nothing pushed; only the authorized rebuild exists |

---

## 11. What NOT to do

- **Do not tune `GLINER_THRESHOLD`, `TYPE_THRESHOLDS`, or any recognizer
  against the burned sets.** There is no corpus here on which tuning is
  legitimate (Q5).
- **Do not "fix" the threshold asymmetry mid-measurement.** It is a detection
  change and needs its own pre-registration (Q4).
- **Do not rebuild after Task 1.** Frozen means frozen; a mid-run rebuild
  silently splits the arms across two artifacts.
- **Do not quote any figure this plan produces.** Every set is burned.
- **Do not report a latency without its condition** (emulated/native, thread
  cap, cpu limit).
- **Do not run, read, or salt blind batch v4 here.**
- **Do not touch the deployment, and do not request a registry push grant.**
  A blocked action is a decision point, not an obstacle to route around.
- **Do not fold the `Dockerfile` comment fix (§3.6) into this work** (Q7).
- **Do not conclude "GLiNER is better" from a burned-set delta.** The
  supportable conclusions are about *cost*, *coverage mechanics* and *fitness*.

---

## 12. Answered at Gate 0 — pending

Q1–Q8 in §4 are open and binding once answered. **Record the answers verbatim,
dated and attributed**, per the "Settled" rule in `docs/HANDOVER.md`.

---

## Appendix A — Measurement-conditions ledger

Filled in at Task 0 and updated per run. Its purpose is that no figure in the
final report can be read without the conditions that produced it.

| Run | Image + digest | `engine` read back | `gliner_loaded` | `HF_HUB_OFFLINE` | Thread cap | CPU/mem limit | Emulated or native | Corpora read |
|---|---|---|---|---|---|---|---|---|
| control | | | | | | | | |
| gliner | | | | | | | | |
| both | | | | | | | | |

---

## Appendix B — Quick reference

```bash
# --- one image, three arms. Mode is process-wide, so one run each. ---------
docker run --rm -p 8086:8080 --cpus=1 --memory=3g \
  -e SCRUBBER_ENGINE=presidio \
  pii-scrubber:gliner-cand

docker run --rm -p 8086:8080 --cpus=1 --memory=3g \
  -e SCRUBBER_ENGINE=gliner -e HF_HUB_OFFLINE=1 -e OMP_NUM_THREADS=1 \
  pii-scrubber:gliner-cand

docker run --rm -p 8086:8080 --cpus=1 --memory=3g \
  -e SCRUBBER_ENGINE=both -e HF_HUB_OFFLINE=1 -e OMP_NUM_THREADS=1 \
  pii-scrubber:gliner-cand

# --- prove the arm before trusting it --------------------------------------
curl -s localhost:8086/v1/info | python3 -m json.tool   # engine, gliner_loaded

# --- the four gates, same scorer, against the running arm ------------------
SCRUB_URL=http://localhost:8086/v1/scrub python3 test_deployed.py holdout_samples.json
SCRUB_URL=http://localhost:8086/v1/scrub python3 test_deployed.py eval_samples_v2.json
SCRUB_URL=http://localhost:8086/v1/scrub python3 test_deployed.py holdout_v3.json
curl -s -X POST localhost:8086/v1/selftest | python3 -m json.tool

# --- fitness, then memory from OUTSIDE, AFTER the run ----------------------
python3 pod_fitness.py http://127.0.0.1:8086/v1/scrub
docker stats --no-stream

# --- tokenizer arbitration, re-proved on the measured image ----------------
docker run --rm -e HF_HUB_OFFLINE=1 pii-scrubber:gliner-cand \
  python test_gliner_tokenizer.py     # must pass offline, fail loudly online

# --- image size: only this method is trusted -------------------------------
docker save pii-scrubber:gliner-cand | gzip | wc -c
```

**Baselines that must reproduce in the control arm:**
`108/111` · `65/68` · `45/50` · selftest `100.0 / 45/45 / missed 0 /
over_detections 4 / spans 49`
