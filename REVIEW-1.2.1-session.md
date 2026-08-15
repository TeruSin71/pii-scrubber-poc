# PII Scrubber 1.2.1 — Session Summary for Review

**Session date:** 2026-08-16
**Branch:** `deploy/aicore-poc`
**Base commit:** `0687fc0` → **HEAD:** `7f62188`
**Status:** stopped at Gate 4. **Nothing built, nothing pushed, nothing deployed.**
**Reviewer:** please read §8 first — it lists what I most want challenged.

---

## 1. What was asked

Three user turns, in order:

1. *"read project handover and let me know what is the next action and stand down"*
2. *"make your working plan and task plan in details for the next action and use
   /superpowers:using-superpowers /caveman /ponytail and do not re invent"*
3. *"proceed and approve"*

Turn 3 is the only authorization to change code. I read it as approving Gate 0
plus the three recommendations I had put in front of the user (§3 below), and
as **not** extending to Tasks 5-7, which the plan gates separately because they
build an image, mutate a remote registry, and mutate a shared corporate BTP
tenant. I stopped at Gate 4.

## 2. Context, for a reviewer with none

The repo is a **PII scrubber for an SAP incident knowledge base** — compliance
tooling with a hard no-leak requirement, running on SAP AI Core (bring-your-own-
model) on BTP Free Tier. Presidio + spaCy `en_core_web_sm` + nine deterministic
SAP recognizers. Release 1.2.0 is live as deployment `db3d9cc5eea296cd`.

The handover named the next release as **1.2.1, two items, scope frozen**:

1. `BUILD_VERSION` baked into the image and echoed by `/v1/selftest` — from an
   incident where a script measured a live-but-stale deployment and reported
   confident numbers for the wrong artifact.
2. Eight glossary entries (`GL`, `FX`, `WM`, `MDG`, `MRP`, `OSS`, `CFO`,
   `Rise`), all observed misfiring on the shipped config.

## 3. Decisions the user approved

I surfaced three open questions and recommended answers; the user's "approve"
covered them:

| | Question | Answer taken | Consequence |
|---|---|---|---|
| Q1 | `test_deployed.py` prints a `HOLDOUT RESULT` banner for *any* input file — fix it in the same pass? | **Yes** | Banner retired, see §5.3 |
| Q2 | Also print the input filename beside the build version? | **Yes** | `samples: <path>` added |
| Q3 | Fold in the backlogged `LABEL_MAP` unknown-label warning while rebuilding anyway? | **No** | Remains backlogged, untouched |

**Reviewer check:** Q1/Q2 widened scope from two items to arguably three. I
judged it in-class (same "metadata read as evidence" defect as item 1, in a file
item 1 already had to touch). Challenge this if you disagree.

## 4. Deliverables

### 4.1 Two planning documents (committed)

- `docs/superpowers/plans/2026-08-16-pii-scrubber-1.2.1-bundle.md` (542 lines) —
  the argument: scope, decision matrix with 10 decisions, verified ground truth,
  9-item risk register, rollback runbook, verification-honesty section, and an
  appendix tracing every glossary entry to a sample ID.
- `docs/superpowers/plans/2026-08-16-pii-scrubber-1.2.1-tasks.md` (1079 lines) —
  the runbook: Tasks 0-7 as TDD checkbox steps with real code, gates marked.

Both mirror the existing `2026-08-15-pii-scrubber-1.2.0-bundle.md` structure
rather than inventing a new one.

### 4.2 Code (4 commits, 8 files, +1901 / -7)

```
5a6feb6  feat: BUILD_VERSION baked at build time, reported by /info and selftest
5956de1  feat: test_deployed.py stamps the build and the set it measured
b163fa1  feat: eight glossary entries, each traced to a blind-batch sample
7f62188  docs: 1.2.1 bundle plan
```

```
 Dockerfile              |  14 +
 app.py                  |  24 +-
 glossary.txt            |  32 +-
 test_build_version.py   | 119 +++   (new)
 test_deployed.py        |  22 +-
 test_jargon.py          |  76 ++
 + 2 plan docs
```

## 5. What changed, in detail

### 5.1 `app.py` — four edits, no new mechanism

```python
# new constant, beside the existing ALLOWLIST_PATH / GLOSSARY_PATH block
BUILD_VERSION = os.getenv("BUILD_VERSION") or "dev"

# was: version="1.0.0"  -- hardcoded, and wrong on every image since
app = FastAPI(title="PII Scrubber (POC)", version=BUILD_VERSION)

# added as the first key of both return dicts
"build_version": BUILD_VERSION,      # in /info
"build_version": BUILD_VERSION,      # in /v1/selftest
```

No new endpoint, no new dependency, no new code path, no detection logic touched.

### 5.2 `Dockerfile` — two functional lines

```dockerfile
ARG BUILD_VERSION=dev
ENV BUILD_VERSION=${BUILD_VERSION}
```

Placed after every `COPY` and before `EXPOSE`, deliberately: an `ENV`
invalidates every layer below it, so early placement would re-run pip and the
spaCy download on every version bump. Default is `dev` so an image built without
`--build-arg` is *visibly* wrong rather than plausibly right. Both properties
are asserted structurally by the test, not left to convention.

### 5.3 `test_deployed.py` — identity stamp + banner fix

```python
info_url = url.rsplit("/v1/scrub", 1)[0] + "/info"
try:
    with urllib.request.urlopen(
            urllib.request.Request(info_url, headers=headers), timeout=30) as r:
        build = json.load(r).get("build_version") or "unknown (pre-1.2.1 image)"
except Exception as e:  # identity is advisory, never fatal
    build = f"unreachable ({type(e).__name__})"
```

Header now reads:

```
SCRUBBER EVALUATION — one scorer, caller names the set
build: 1.2.1-local   samples: holdout_v3.json
target: http://127.0.0.1:8080/v1/scrub
```

The old banner said `HOLDOUT RESULT` / `HOLDOUT RECALL` for every input file —
run against `eval_samples_v2.json` it announced a holdout result for a set that
is explicitly not a holdout. Deliberately non-fatal on a missing key: the 1.2.0
and 1.1.0 rollback images must stay measurable.

### 5.4 `glossary.txt` — eight lines of data, zero code

Entries went into the **existing** sections (`modules`, `process nouns`,
`roles`), through the **existing** loader (`app._load_allowlist()`), into the
**existing** suppression set — so they inherit case-sensitive exact match,
whole-span matching and the ±40-char user-context backstop without
reimplementing any of it.

Header block updated: `Rise` moved out of PRE-CLEARED (it now has an observed
misfire), sample-ID evidence recorded, and a note that all but `Rise` are 2-3
chars — below the 4-char `SAP_USER_ID` floor at `recognizers.py:108` — so none
was ever a recognizer hit. They arrive from the spaCy layer, inconsistently
typed: `WM` and `MRP` as `ADDRESS`, the rest as `ORG_NAME`.

### 5.5 `test_jargon.py` — 35 new checks (39 → 74)

8 misfire-stops · 2 context-backstop guards · 2 `Rise` both-directions ·
8 present · 9 absent (case variants) · 4 still-unshipped street types ·
2 lg-only rejections.

### 5.6 `test_build_version.py` — new, 12 checks

7 runtime (constant, default, `or`-form, FastAPI version, key-presence and
value-match on both endpoints) + 5 structural Dockerfile-wiring checks.

## 6. Evidence — every number with the command that produced it

### 6.1 Baseline, captured before any edit (Task 0)

| Suite | Baseline |
|---|---|
| `test_fixes.py` | 16 |
| `test_address.py` | 39 |
| `test_customer_number.py` | 33 |
| `test_jargon.py` | 39 |
| `/v1/selftest` | `100.0`, `45/45`, missed 0, `over_detections 4`, spans 49, **no `build_version` key** |

The plan deliberately did **not** hardcode the three unasserted counts; the
handover gave none, and a number nobody re-measured is the exact defect item 1
exists to prevent.

### 6.2 Gates after the change — all exact, leak lists unchanged

```bash
BUILD_VERSION=1.2.1-local uvicorn app:app --host 127.0.0.1 --port 8080 &
SCRUB_URL=http://127.0.0.1:8080/v1/scrub python3 test_deployed.py <set>
```

| Set | Gate | Measured | Leaks |
|---|---|---|---|
| `holdout_samples.json` | 108/111 | **108/111** | ZHANG, Young, Mere Tuhoe |
| `eval_samples_v2.json` | 65/68 | **65/68** | 44 Bellbird Rise, Okonkwo, FONTAINE |
| `holdout_v3.json` | 45/50 | **45/50** | NAKAMURA, Park, Adeyemi, 5591230, 6620945 |
| `/v1/selftest` | 45/45 | **100.0 / 45/45 / missed 0 / over_det 4 / spans 49** | — |

Leak lists were captured in Task 0 and compared line by line, not just counts —
a count that holds while the leak list changes is two compensating regressions
summing to zero, and a count-only check is blind to it.

`over_detections` did not move, so there is no delta to itemise. Predicted: none
of the eight tokens appears in `samples.json`.

### 6.3 Suites after the change

| Suite | Before | After |
|---|---|---|
| `test_fixes.py` | 16 | **16** |
| `test_address.py` | 39 | **39** |
| `test_customer_number.py` | 33 | **33** |
| `test_jargon.py` | 39 | **74** |
| `test_build_version.py` | — | **12** |

All exit 0.

### 6.4 Suppression-set delta — exactly eight

```
Allowlist loaded: 257556 tokens (total 257583)
Glossary loaded:  36 tokens (total 257619)      # was 28 / 257611
```

**Count reconciliation (review finding, resolved 2026-08-16).** Two records
disagreed: this section says the glossary "was 28", the 1.2.0 close-out says it
shipped 29 entries. **Both are true and neither is a phantom** — they measure
different things. Measured at `0687fc0`: the file holds **29 entries**, of which
**28 were newly-added tokens**, because `QMEL` also appears in `allowlist.txt`
(mined from DD02L) and the allowlist loads first, so `QMEL` added nothing.
Overlap with the 27-token built-in seed is **zero**.

The record that was actually wrong is one I authored: the task plan's note
attributed the duplicate to *the seed set*. It is `allowlist.txt`. Corrected in
the plan, and a reconciliation block naming `QMEL` now sits at the top of
`glossary.txt` so the two numbers cannot drift apart again. Rule: quote the
loader line for set size, the file for provenance, never one as the other.

### 6.5 What item 2 actually bought (no gate moved, readability did)

Over-redactions on the `holdout_v3` control samples: **8 → 1**.

```
V3-034  before: <ORG_NAME> account <CUSTOMER_NO> ... <ORG_NAME> rate load  (3)
        after:  GL account <CUSTOMER_NO> ... FX rate load                  (1)
V3-001  before: Release approval sits with the <ORG_NAME> office
        after:  Release approval sits with the CFO office
V3-035, V3-038, V3-039, V3-040   before: 1-2 redactions each → after: clean
```

The residual `<CUSTOMER_NO>` in V3-034 is the unpadded-customer-number
recognizer firing on a 7-digit account number. Pre-existing, unrelated, untouched.

## 7. Three defects I introduced or nearly introduced, and caught

These are the most review-worthy part of the session.

### 7.1 A crash, not a mislabel — `BUILD_VERSION=""` stopped the service booting

Wiring `FastAPI(version=BUILD_VERSION)` made an empty value **fatal**:

```
AssertionError: A version must be provided for OpenAPI, e.g.: '2.1.0'
```

`os.getenv("BUILD_VERSION", "dev")` returns `""` when the variable is set but
empty, so `--build-arg BUILD_VERSION=` would not have mislabelled the image — it
would have crash-looped it. On a 1-pod free tier where an admission-rejected
revision is **permanent**, that is far worse than a wrong string.

Fixed at root: `os.getenv("BUILD_VERSION") or "dev"`, which covers unset *and*
empty. Found by running a service with an empty value, not by reasoning.
Pinned at source by a test check.

### 7.2 A tautological test that reported PASS against unmodified code

First draft:

```python
check("/info carries build_version",
      A.info().get("build_version") == getattr(A, "BUILD_VERSION", None))
```

Both sides are `None` when neither exists, so `None == None` → **PASS** against
an untouched `app.py`. This is the project's own documented trap 6 ("a check
that reports clean may not have run"), instance four. Caught by reading the
output rather than the exit code. Rewritten to assert **key presence before
value equality**, using a sentinel rather than `None`.

### 7.3 Three planned test sentences did not actually misfire

The task plan specified paraphrased sentences for each glossary entry. Before
adding the entries I checked that each frame *currently* misfires. Three did not:

```
GL    "The GL posting failed during the period close run."      → no span
MRP   "MRP did not generate the planned order for the component." → no span
Rise  "Investigating the Rise in backorders reported this month." → no span
```

They would have shipped as three checks that passed before the feature existed —
the `tests-from-same-model-as-code` failure mode. **The misfire is
frame-sensitive, not token-sensitive:** `GL` fires in "Postings to the GL
account" but not "The GL posting failed". Replaced with frames verified to
misfire, each recorded in the test with the type it fires as.

## 8. What a reviewer should challenge

1. **Scope.** Q1/Q2 took the release from two items to three. In-class, or scope
   creep? The handover was emphatic that 1.2.0's scope stayed frozen.
2. **Test sentences are paraphrases.** `holdout_v3.json` is gitignored on
   purpose; copying its text into `test_jargon.py` would readmit it to the repo.
   So the committed tests use paraphrases of frames verified to misfire. This is
   deliberate but it means the test does not assert the *literal* observed
   incident. Is that the right trade?
3. **Two-character glossary entries.** `GL`, `FX`, `WM` are two chars in a
   case-sensitive whole-span exact-match set. I argue the blast radius is
   confined to spans whose entire text is exactly `GL`. Verify that reasoning
   against the `_merge`/`detect` path independently.
4. **`Rise` is both jargon and a street type.** Both directions are asserted
   (bare noun suppressed; `14 Sunrise Rise` still redacts). `44 Bellbird Rise`
   still leaks — but it leaked *before* this change too, as the known accepted v2
   ADDRESS gap. Confirm the entry did not *cause* it.
5. **Committing directly to `deploy/aicore-poc`.** That is this repo's default
   branch and every prior commit went to it directly; AI Core git-sync watches
   that revision. I did not branch. Nothing is pushed.
6. **`over_detections` unchanged at 4.** Expected, since none of the eight
   tokens appears in `samples.json` — but the baseline is asserted, so an
   independent check that it *should* be unchanged is worthwhile.

## 9. Known gaps — stated, not hidden

- **The `unknown (pre-1.2.1 image)` fallback is unverified end to end.**
  Producing a pre-1.2.1 service locally means running the previous commit's
  image. The other two identity branches (present, unreachable) are exercised.
  It will show for real the first time the harness is pointed at the live 1.2.0
  deployment.
- **Local `/info` success does not predict gateway behaviour.** The AI Core
  inference gateway proxies `/v1/*` only; `GET
  $AI_API/v2/inference/deployments/<id>/info` returns `RBAC: access denied`.
  The first version of the identity stamp read `/info` alone, so it would have
  worked on every local run and silently printed `unreachable` on every
  deployed one — failing precisely in the environment the stale-deployment
  incident happened in. Fixed 2026-08-16 (review finding): the stamp now tries
  `/info`, then falls back to `/v1/selftest`, which is proxied and carries the
  same field. Still non-fatal. **No local test can catch this class** — the
  guard is structural (`test_build_version.py` asserts the fallback route
  exists), and the real proof only arrives on the first deployed run.
- **No image has been built.** Task 5 (`--build-arg BUILD_VERSION=1.2.1`,
  `--platform linux/amd64`, in-container `/info` must read exactly `1.2.1`) has
  not run. Risk R1 in the bundle plan — forgetting `--build-arg` — is therefore
  still live and unmitigated in practice.
- **Nothing pushed or deployed.** Tasks 6-7 need BTP credentials I do not have;
  the user drives those.
- **No quotable figure comes out of this release.** All four evaluation sets are
  burned (each has been read during a build session), so the only correct
  reading of any of them is "unchanged". A new number needs an externally
  authored blind batch, run once — a separate piece of work.
- **`VSCODE-PROMPT-address-recognizer.md` is still untracked.** Pre-existing
  from the prior session; the handover cites it as a resume item, so it exists
  only on this machine. Not addressed — out of scope, flagged twice.
- **Plan-vs-reality drift, corrected:** the task plan predicted `test_jargon`
  would reach 75 checks; the actual is 74 (I dropped one redundant check that
  the v2 regression gate already covers). The plan document was corrected in the
  same commit rather than left to disagree with the code.

## 10. State at handoff

```
branch     deploy/aicore-poc
HEAD       7f62188
base       0687fc0
pushed     nothing
built      nothing
deployed   unchanged -- db3d9cc5eea296cd still runs 1.2.0
tree       clean except ?? VSCODE-PROMPT-address-recognizer.md (pre-existing)
next       Task 5, build the image -- gated, needs approval
```

Rollback for everything in this session is `git revert` of four commits; no
remote or deployed state was touched.
