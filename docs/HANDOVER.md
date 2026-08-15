# PII Scrubber — Handover

**As of 2026-08-15, end of day.** Written for someone picking this up with zero
prior context.

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

## ⏳ 1.2.3 — IN PROGRESS, NOT SHIPPED. Read this first.

**7 commits exist locally and NONE is pushed.** The remote and the deployment
are both at `1.2.2`, which is correct and running. Nothing here is live.

```
origin/deploy/aicore-poc  9734841   (1.2.2 close-out)
local HEAD                2ca8c77   7 commits ahead, review-before-push in force
deployment                da1b1b3e39367c59, running 1.2.2, healthy
```

| Item | State |
|---|---|
| 1 — `unmapped_labels()` reads the engine's real ignore list | ✅ built, `24eaef3` |
| 2 — `unmapped_labels` surfaced on `/v1/info` | ✅ built, `3adaeaa` |
| 3 — map `FAC` → `ADDRESS` | ⛔ **WITHDRAWN. It does nothing — see below** |
| 4 (replacement) — correct three wrong descriptions | ⏸ **authorized, gated on Teru's confirmation of the scope change** |
| 5 — regression gates | not started; gates must be **exact-zero movement** |
| 6-8 — build, review gate, publish | not started |

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

### Three descriptions are now known wrong (replacement Task 4)

Docs and strings only. No behaviour change, no measurement moves.

1. **The 1.2.2 startup warning** says unmapped labels are "DETECTED and then
   silently dropped". For `FAC` the drop *precedes* detection.
2. **This handover's trap-8 entry** says `FAC` "reaches `_norm()` raw". It
   does not.
3. **`unmapped_labels()` documented semantics** — it models `labels_to_ignore`
   and the entity mapping but **not** `supported_entities`, so it
   over-reports. Modelling `supported_entities` is deferred to the recognizer
   plan; only the documentation is corrected now.

### The leak class is real and still open

Unnumbered street and facility references redact nothing — confirmed on five
lines in the pinned container:

```
'the warehouse on Willis Street'   detect() = []
'the depot on Great South Road'    detect() = []
'Auckland International Airport'   detect() = []
```

**The correct layer is the recognizer, not `LABEL_MAP`.** Precedent exists:
`get_analyzer()` already re-registers `SpacyRecognizer` with `ORGANIZATION`
added, for the 1.2.0 ORG defect. Adding `FAC` is the analogous fix and is
**materially larger than one line** — it needs its own plan, its own
pre-registration, correct-layer incidence evidence, and the probe batch
re-run against a FAC-registered build.

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
| Deployment | **`da1b1b3e39367c59`** on SAP AI Core — deployed check not yet read, see the block above |
| Image | ✅ `ghcr.io/terusin71/pii-scrubber:1.2.2`, **linux/amd64**, `sha256:958bd5c3…b3ff3fa6` |
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
**`da1b1b3e39367c59` is 1.2.2.** Each predecessor is deleted, not stopped —
the 1-pod quota forces delete-then-create and Kubernetes never re-drives an
admission-rejected revision. `test_deployed.py` now defaults to
`da1b1b3e39367c59`.

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

---

## Open findings

Numbered as they appear in
`docs/superpowers/plans/2026-08-15-pii-scrubber-task-list.md`, which holds the
full text of all 18.

### ⛔ Finding 11 — GLiNER cannot load; `engine=both` would crash the deployment

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
   (1.2.2), and the old assessment of it was wrong.** An entity label with no
   `LABEL_MAP` entry falls through `_norm()`'s `label.upper()` default, lands
   outside `REDACT_TYPES`, and is discarded — the span was detected and then
   thrown away, which is indistinguishable from never detecting it.

   ⚠️ **Correction, measured 2026-08-16.** This entry used to say the defect
   was "only reachable through lg, which is not shipped". **False. `FAC` is
   live on `en_core_web_sm` today.** spaCy `sm` emits `FAC`; presidio neither
   maps it to a presidio entity nor lists it in `labels_to_ignore`, so it
   arrives at `_norm()` raw, has no `LABEL_MAP` entry, and is dropped. The
   defect was never latent on the shipped config — nobody had looked.

   `unmapped_labels()` now computes this from **presidio's own configuration**
   rather than a reimplemented mapping, and `get_analyzer()` logs it:

   ```
   WARNING LABEL_MAP has no entry for: FAC -- spans carrying these labels are
   DETECTED and then silently dropped, never redacted (trap 8)
   ```

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
python test_build_version.py    # 22  build identity, /v1/info, gateway-reachable routes
python test_label_map.py        # 23  unmapped-label diagnostic + its failure isolation

# The four burned gates, all exact. Any movement either way is a stop.
#   holdout_samples.json  108/111   eval_samples_v2.json  65/68
#   holdout_v3.json        45/50    /v1/selftest          45/45, over_detections 4

# against the deployment (DEPLOYMENT_ID defaults to da1b1b3e39367c59)
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
