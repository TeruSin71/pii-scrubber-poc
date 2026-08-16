# PII Scrubber — GLiNER Bake-off Plan

**REVISION 1 — 2026-08-16. ✅ GATE 0 IS ANSWERED; findings 1–5 accepted and
ruled on.** Verbatim answers in §12. Nothing in this plan has been executed.
Authored against `429a19b`, revised against `751c082`.

Backend is **torch**; the ONNX arm is struck and deferred.

⚠️ **The freeze is LIFTED for exactly ONE rebuild** (Task 1), then re-applied.
`pii-scrubber:gliner-cand` as it stands today is **not** the artifact that gets
measured — the measured artifact is Task 1's output, which carries a git sha,
the offline vars, the thread cap, and the `_merge` monotonicity fix.

**What changed in revision 1** — every item is a reviewer ruling, not an
executor edit:

| Ruling | Effect on this plan |
|---|---|
| Threshold asymmetry = named confound | Bake-off claims are **configuration-level, never engine-level** (§2.9). Matched-threshold arm is **optional and engineering-only** |
| Union merge = **DEFECT**, not just a risk | Fixed at Task 1 behind a **monotonicity invariant** + property test (§3.4b). S2 demoted to backstop |
| Offline + thread caps | **Baked into image ENV.** Tested artifact = deployed artifact under default invocation |
| Freeze lifted for one rebuild | **Task 1 is MANDATORY**, no longer conditional. Provenance becomes a stamped read afterwards |
| Q5 wording corrected | **Blind batch v4 is NEVER a tuning corpus.** The old text said tuning "waits for v4" and that was wrong (§2.5) |
| Correction commits | New standing rule: they carry a **grep transcript proving zero remaining instances repo-wide** |

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
| 0 — provenance hash check + baseline capture | 45 min | read-only |
| 1 — **MANDATORY**: `_merge` fix + artifact conditions + ONE rebuild, re-freeze | 105 min | ⚠️ code change + rebuild |
| 2 — control arm: `presidio` mode on the frozen image | 30 min | local |
| 3 — `gliner` mode: detection + over-redaction, both paths | 60 min | local, slow |
| 4 — `both` mode: same, plus the coverage-regression check | 60 min | local, slow |
| 5 — pod-fitness per mode, conditions proved | 60 min | local, slow |
| 6 — synthesis, recommendation, release pre-registration | 60 min | writing |
| 7 — ⛔ **REVIEW GATE** | — | nothing ships, nothing pushes |

≈ 7 hours. Tasks 3–5 are slow because GLiNER is slow: a
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
   four are burned. ⛔ **And blind batch v4 is NEVER a tuning corpus either** —
   corrected at Gate 0, because revision 0 of this plan said tuning "waits for
   v4" and that was wrong. A blind set is a **measuring instrument**; tuning
   against it destroys it in the same act that a burned set was destroyed, and
   it is the only unburned instrument the project has. Legitimate tuning needs
   a **separate, purpose-built, openly-readable** corpus — the
   `address_verify_samples.json` pattern — authored for that job and never
   quoted. §4/Q5.
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
9. ⛔ **Every claim this bake-off makes is CONFIGURATION-level, never
   ENGINE-level.** Ruled at Gate 0. The arms differ in threshold policy as well
   as in engine (§3.4a), so a delta is a property of *this configuration versus
   that configuration*, not of *GLiNER versus presidio*. Write
   "`both` at `GLINER_THRESHOLD=0.4` redacted N more values than `presidio` at
   its per-type floors", never "GLiNER is more accurate". The confound is named
   **beside every delta**, not once in a caveats section — a caveat one scroll
   away from a number does not travel with it.

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
redacted.**

⛔ **RULED AT GATE 0: this is a DEFECT, and it is fixed at Task 1 — before any
measurement.** Revision 0 treated it as a risk to *detect*; that was wrong.
Measuring a mode that can silently lose coverage produces numbers describing a
bug, and every downstream comparison would inherit it.

The fix is stated as an **invariant**, not as a patch, because the invariant is
what a future change has to keep:

> **Monotonicity of union coverage.** For any text, the set of characters
> redacted in `both` mode is a **superset** of the set redacted in `presidio`
> mode. Adding an engine may never un-redact a character.

Required at Task 1, all three:

1. The invariant enforced in `_merge` (adding a span may not reduce covered
   characters — a lower-ranked span survives where it covers characters the
   winner does not).
2. A **property test** over generated overlap geometries, not a handful of
   hand-picked pairs. The bug is a geometry class, and examples do not cover a
   class.
3. The **`P=[10,20]` / `G=[5,18]`** case pinned explicitly as a regression
   test, so the exact geometry that motivated the fix can never come back
   silently.

⚠️ **Stop condition S2 stays, demoted to a backstop.** A fixed invariant with
no independent check is one refactor from being fixed in name only — and this
project has been burned by exactly that shape, where the step that would have
caught a defect was written so it always passed.

⚠️ **The fix touches `presidio`-mode output too**, because `presidio` mode also
runs through `_merge`. See §5.1: after the fix, **control-arm movement is a
latent-defect stop, not noise.**

Related and **not** fixed here: the tie-break's third key is **score**,
comparing a presidio confidence against a GLiNER sigmoid. **The two scales have
never been shown to be comparable**, and nothing in the codebase claims they
are. It stays a named confound (R8) — the monotonicity fix removes the
*coverage loss*, not the *arbitrary winner* on equal-length overlaps.

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

### 3.6 ✅ FIXED 2026-08-16 — a stale comment block contradicted the requirements

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

Comments produce no layers, so fixing it **cannot change the image**. It was
listed as Q7 rather than silently folded in.

✅ **Fixed in its own commit, as ruled.** The grep rule that shipped with it
immediately earned itself: the repo-wide search found **two further live false
claims** that the Dockerfile fix alone would have left standing — the `Engine`
row of `docs/HANDOVER.md`'s current-state table, and its `Settled` engine
bullet, both still reading that `both` "is broken" / "does not currently work".
**The correction was going to be applied in one of three places again**, and
the transcript is the only reason it was not.

⚠️ **One substantive fact surfaced while fixing it, and it is not cosmetic:**
the pin fix `1faf3e9` (13:12:43) landed **64 minutes after** the `1.2.3` image
was built (12:08:32). **Every deployed image predates the fix**, so `engine=both`
remains fatal on `1.0.0`–`1.2.3`. Enabling GLiNER is a **new build**, never a
configuration flip on the running pod — which is exactly what the original
false comment claimed it was.

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

### ✅ Answered at Gate 0 — 2026-08-16, BINDING

Reviewer session, relayed by Teru. Verbatim text in §12.

| # | Question | Ruling |
|---|---|---|
| **Q1** | Candidate provenance: accept §3.2's circumstantial argument, or rebuild with a git sha? | ✅ **REBUILD.** One build carrying sha + offline + thread cap + the `_merge` fix. **Task 1 is now MANDATORY.** Provenance becomes a stamped read afterwards; Task 0's per-file hash check **still runs** first, against the pre-rebuild candidate |
| **Q2** | Bake `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` into the image? | ✅ **YES, both vars**, in image `ENV`. Principle: **tested artifact = deployed artifact under default invocation** |
| **Q3** | Thread cap in the image or the `ServingTemplate`? | ✅ **BOTH LAYERS** — image default *and* template declaration. The template is where "1 vCPU" is declared; the image default must agree with it, not contradict it |
| **Q4** | Threshold asymmetry: as-shipped, or normalize GLiNER under `TYPE_THRESHOLDS`? | ✅ **AS-SHIPPED**, with the **confound named beside every delta** (not once, in a caveats section). Claims are configuration-level, never engine-level (§2.9). A matched-threshold arm is **optional and engineering-only** |
| **Q5** | Freeze `GLINER_THRESHOLD` at `0.4`? | ✅ **FROZEN at 0.4.** And the revision-0 wording is **corrected**: ⛔ **v4 is never a tuning corpus** (§2.5) |
| **Q6** | If the control arm does not reproduce? | ✅ **STOP, rig void.** No GLiNER number is read; the deviation is the deliverable. After the `_merge` fix, movement is a **latent-defect stop** (§5.1) |
| **Q7** | The false `Dockerfile` comment block (§3.6)? | ✅ **SETTLED — own commit, approved**, plus a **grep transcript proving zero remaining instances repo-wide** (new standing rule) |
| **Q8** | Recommendation only, or carry through to a release? | ✅ **RECOMMENDATION + pre-registered release gates only.** The release is a separate plan with its own Gate 0 |

---

## 5. Pre-registration — written before anything runs

**The control arm has registered values. The GLiNER arms deliberately do
not** — their numbers are the unknown this plan exists to measure, and
inventing an expectation for them would be prediction theatre. What *is*
registered for them is the **stop conditions**.

### 5.1 Control arm — `presidio` mode on the RE-frozen image (Task 1 output)

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

⛔ **Control-arm movement after the `_merge` fix is a LATENT-DEFECT STOP, not
noise.** Ruled at Gate 0, and it is the sharpest rule in this plan.

`presidio` mode runs through `_merge` too, so the monotonicity fix can move the
control arm. **If it does, the movement is not an artifact of the fix — it is
the fix revealing that presidio-alone was already losing coverage**, silently,
in every release that shipped. The tempting reading is "we changed `_merge`, so
of course the control moved, carry on". That reading is forbidden: it would
convert the discovery of a shipped defect into a rounding note.

On movement: **stop, and report the movement as a finding against the deployed
`1.2.3`**, with the specific values and the span geometry that caused each.
The bake-off does not resume until that finding is dispositioned on its own
terms.

### 5.2 GLiNER arms — stop conditions, not predictions

| # | Condition | Why it is a stop |
|---|---|---|
| S1 | `/v1/info` does not report the expected `engine`, or `gliner_loaded` is `false` in a GLiNER arm | The run measured something other than what it is labelled |
| S2 | **`both` mode leaves exposed any value that `presidio` mode redacted** | **Backstop.** The monotonicity invariant fixed at Task 1 (§3.4b) should make this unreachable — so if it fires, the invariant is not holding and the fix is fixed in name only. Either way it is a defect, never an engine result |
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

- **Rule 3:** no outbound calls. No bare `AnalyzerEngine()`. As of Task 1
  offline is an **image property** (Q2), so the arms inherit it by default —
  but the run commands in Appendix B still pass it **explicitly**. Belt and
  braces is deliberate: an env var that is only ever inherited is one
  `Dockerfile` edit from disappearing without any run failing.
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

### Task 0 — provenance + PRE-FIX baseline capture (read-only)

✅ Gate 0's answers are recorded in §12. Task 0 is now two things.

1. **Capture the PRE-fix `presidio` baseline** on the candidate as it stands
   today — the four gate numbers **with leak lists**, and a span dump.
   ⚠️ **This is not ceremony and it is not the control arm.** It is the
   reference the post-fix control arm gets diffed against, and it is the only
   way to tell a `_merge`-fix movement from a pre-existing difference. Capture
   it **before** Task 1 touches anything, because after the rebuild it is
   unobtainable.
2. **Provenance check** (read-only, no build): run the current candidate and
   hash its build inputs, comparing against the git blobs at `b5fbaf6`:
   ```bash
   docker run --rm --entrypoint sh pii-scrubber:gliner-cand -c \
     'sha256sum /app/app.py /app/recognizers.py /app/samples.json \
                /app/allowlist.txt /app/glossary.txt'
   git cat-file blob b5fbaf6:app.py | shasum -a 256
   ```
   Report match or mismatch **per file**. A mismatch does not change what
   happens next — Task 1 rebuilds either way — but it changes what the
   pre-fix baseline *means*, so it is recorded before that baseline is used.

**Report ≤300 words.** No approval gate here; Gate 0 already cleared the path
to Task 7.

### Task 1 — MANDATORY: the fix, the conditions, ONE rebuild, re-freeze

Four changes, **one build**. Nothing is measured until all four are in and the
image is re-frozen.

**1. `_merge` monotonicity fix** (§3.4b) — the only code change in this plan.

- **RED first:** the property test and the `P=[10,20]`/`G=[5,18]` regression
  case must fail against today's `_merge`. A test that passes before the fix
  tests nothing — three of eight 1.2.1 glossary frames hit exactly that, and
  the GLiNER prefetch step survived three releases because its failure branch
  was `echo`.
- **GREEN:** adding a span may never reduce the covered character set.
- Then re-run the six suites. **They are not expected to move**; if one does,
  it is reported before anything else proceeds.

**2. Git sha** baked as a build arg, surfaced on `/v1/info` beside
`build_version`. ⚠️ Keep `BUILD_VERSION`'s existing property: the default must
stay non-version-shaped, so an unstamped build is distinguishable from a
correct one. `test_build_version.py` asserts that structurally — extend it to
cover the sha rather than working around it.

**3. `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`** in image `ENV`
(`Dockerfile:10` currently sets `TRANSFORMERS_OFFLINE=0`).
⚠️ **Build-time prefetch needs network; runtime must not.** These vars must not
be set so early that they break the weight prefetch at
`Dockerfile:43-51`. Place them **after** the prefetch layer, and confirm the
prefetch still succeeds — a build that silently skips the weights is the
finding-11 failure shape returning.

**4. Thread cap at both layers** (Q3): image `ENV` default, and the
`ServingTemplate` declaration. They must **agree**; the point of both layers is
that neither can silently drift from the pod's real shape.

**Then, before re-freezing:**

- `test_gliner_tokenizer.py` re-runs **in the new image** — must pass offline
  and **still fail loudly online**. The arbitration is re-proved on the
  artifact that gets measured, never inherited from the old one.
  ⚠️ With offline now baked in, confirm the online-failure branch still works —
  a hard-coded offline var could make the guard untriggerable, leaving a test
  that cannot fail where it matters.
- Tag the **pre-fix** candidate under a dated tag first (§9), then re-tag the
  new build as the frozen candidate and **record its digest**.

**No measurement before this completes.** Report ≤350 words: the RED evidence,
the suite results, the tokenizer re-proof both ways, and the new digest.

### Task 2 — Control arm: `presidio` mode on the RE-frozen image

Run the re-frozen image, `SCRUBBER_ENGINE=presidio`. Read `/v1/info` back —
including the new git sha. Run the selftest and the three gates.

**Every value in §5.1 must match exactly**, and the leak lists must match
**Task 0's pre-fix capture line for line**.

Two different failures, and they are not interchangeable:

| Symptom | Reading |
|---|---|
| Numbers differ from §5.1's registered values | **Rig void.** Something other than the four Task 1 changes is in play; stop |
| Numbers match §5.1 but leak lists differ from Task 0's pre-fix capture | **Latent-defect stop (§5.1).** `_merge` was losing coverage on the presidio path in shipped code. Report against deployed `1.2.3`, with the span geometry per value |

Report ≤250 words.

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
| R2 | ✅ **CLOSED at Task 1** — offline and thread cap baked into image `ENV` at both layers (Q2/Q3) | — | — | Was: conditions lived in the run command (§3.5) | Re-proved by the tokenizer test in the new image, both directions |
| R3 | ✅ **CLOSED at Task 1** — git sha baked and surfaced on `/v1/info` (Q1) | — | — | Task 0's per-file hash check still runs against the pre-rebuild candidate | Provenance becomes a stamped read |
| R4 | ✅ **FIXED at Task 1**, not merely detected — `_merge` monotonicity invariant + property test + the pinned geometry (§3.4b) | — | — | S2 retained as backstop, because a fixed invariant with no independent check is one refactor from being fixed in name only | Task 4 diff; S2 |
| **R4b** | **The `_merge` fix moves the presidio path**, revealing coverage loss in shipped code | Medium | **High** — a live defect in deployed `1.2.3` | Task 0 captures the pre-fix baseline **before** the fix exists; there is no other way to attribute the movement | Task 2 leak-list diff vs Task 0 |
| **R4c** | **The `_merge` fix is fixed in name only** — invariant asserted, property test too weak to exercise the geometry | Medium | **High** — measurement resumes on an unfixed union | RED-first is mandatory: the property test and the pinned case must fail against today's `_merge` before the fix lands | Task 1 RED evidence is part of the report |
| **R4d** | **Offline vars break the build-time weight prefetch** — set too early, the prefetch cannot download and the build produces an image with no weights | Medium | **High** — the finding-11 failure shape returning | Place the vars **after** the prefetch layer; the prefetch step already fails the build rather than warning | Task 1 confirms the prefetch succeeded, explicitly |
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
| Mandatory rebuild (Task 1) | The previous `gliner-cand` is replaced by tag. **Tag the pre-fix image with a dated tag BEFORE rebuilding** — it is the only artifact that can reproduce Task 0's pre-fix baseline, and losing it makes the `_merge` movement unattributable |
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
  against the burned sets** — and ⛔ **not against blind batch v4 either, ever**
  (Q5, §2.5). Tuning needs a separate, purpose-built, openly-readable corpus.
- **Do not add the optional matched-threshold arm to any conclusion.** It is
  engineering-only (Q4); it informs the release plan and appears in no
  recommendation as evidence.
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
- ⛔ **Do not write an engine-level claim.** Not "GLiNER is better", not
  "GLiNER improves recall" — the arms differ in threshold policy as well as
  engine, so every claim is **configuration-level** and the confound is named
  beside the number, not in a footnote (§2.9, Q4). The supportable conclusions
  are about *cost*, *coverage mechanics* and *fitness*.

---

## 12. Answered at Gate 0 — 2026-08-16, BINDING

Recorded **verbatim, dated, attributed**, per the "Settled" rule in
`docs/HANDOVER.md`. **Reviewer session (Claude Cowork), relayed by Teru,
2026-08-16.** Quoted in full, not excerpted.

> Findings 1-5: ACCEPTED. Rulings:
> 1. Threshold asymmetry: recorded as a named confound; bake-off claims
>    are configuration-level, never engine-level. Matched-threshold arm
>    optional, engineering-only.
> 2. Union merge: DEFECT. Fix before measurement — monotonicity invariant
>    (union coverage ⊇ presidio-alone coverage) + property test + the
>    [10,20]/[5,18] case. Stop condition stays as backstop.
> 3. Offline env + thread caps: baked into the image ENV. Tested artifact
>    = deployed artifact under default invocation.
> 4. Freeze lifted for ONE rebuild (fixes 2+3 + git-sha stamp), then
>    re-frozen. Task 0 provenance becomes a stamped read.
> 5. Dockerfile comment fix: own commit, approved. New standing rule:
>    correction commits carry a grep transcript proving zero remaining
>    instances repo-wide.
>
> Structure: control-arm-reproduces-first and no-registered-values-on-
> measured-arms both endorsed as designed.

> GATE 0: ANSWERED. Q1 rebuild (sha + offline + thread cap + _merge
> monotonicity fix, ONE build; Task 1 now MANDATORY; control-arm movement
> after the fix = latent-defect stop, not noise). Q2 yes, both vars.
> Q3 both layers — image default + template declaration. Q4 as-shipped,
> confound named per delta. Q5 frozen 0.4; v4 is never a tuning corpus —
> fix the wording. Q6 stop, rig void. Q7 settled — own commit + grep
> transcript. Q8 recommendation + pre-registered release gates only.
>
> Authorized commits: plan revision (one, folding rulings + answers),
> HANDOVER "Settled" entry (verbatim/dated/attributed), Q7 comment fix.
> Push approved for all three iff docs/comments-only.
>
> Execution order: revision + HANDOVER land -> Task 0 (provenance hash
> check still runs, per file) -> Task 1 rebuild + re-freeze + tokenizer
> re-proof -> Tasks 2-6 -> Task 7 review gate. Nothing pushed beyond the
> three named commits, no deployment touch, v4 untouched.

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
