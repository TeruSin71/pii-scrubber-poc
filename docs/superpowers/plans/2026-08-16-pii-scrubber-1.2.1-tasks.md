# PII Scrubber 1.2.1 — Task Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship image `1.2.1` carrying a build-version stamp the service
reports, and eight evidence-backed glossary entries, through one stop/create
cycle on the 1-pod free tier.

**Architecture:** No new mechanism. The version is a Docker `ARG`→`ENV` read
by `os.getenv` and surfaced through the two endpoints that already exist. The
glossary entries are eight lines of data loaded by the loader that already
loads them, into the suppression set that already exists. Both items add
tests; neither adds a dependency, an endpoint, a code path or a file the
service imports.

**Tech Stack:** Python 3.12 (uv venv), FastAPI + uvicorn, Presidio 2.2.357,
spaCy `en_core_web_sm`, Docker buildx (`linux/amd64`), SAP AI Core BYOM via a
KServe ServingTemplate.

**Spec:** `docs/superpowers/plans/2026-08-16-pii-scrubber-1.2.1-bundle.md` —
read it first. It carries the decision matrix, the risk register and the
three open Gate 0 questions.

## Global Constraints

Every task inherits these. They are not restated per task.

- **Rule 3:** no outbound network calls from inside the boundary. Never
  construct a bare `AnalyzerEngine()` — Presidio's default resolves to
  `en_core_web_lg` and downloads it. Import `app.get_analyzer()` or mirror
  `app.py`'s explicit `NlpEngineProvider`.
- **Rule 7:** no dependency changes. `requirements.txt` is not touched in this
  bundle.
- **Rule 4:** no real ticket text, no mined corpora, no evaluation sets in the
  repo. `holdout_samples.json`, `eval_samples_v2.json`, `holdout_v3.json` and
  both HTML reports stay gitignored.
- **Platform:** always `--platform linux/amd64`, verified with
  `docker buildx imagetools inspect`. This machine is arm64; a digest check
  alone cannot catch a wrong-platform image.
- **Environment:** `source .venv/bin/activate` before anything Python. If the
  venv is missing: `uv venv --python 3.12 --seed .venv` — `--seed` is
  mandatory or `pip install` escapes to system Python 3.14 and the pins fail.
- **`BUILD_VERSION` defaults to `dev`.** Never to a version-shaped string.
- **Do not tune against any evaluation set.** All four are burned. They are
  gates; the only correct reading is "unchanged".
- **Do not run `docker system prune`.** Unrelated `frappe_docker` images are
  present, disk is 90%+ full.
- **Every check prints what it inspected**, not just a verdict. Three false
  passes in this project came from checks that never ran.
- **Do not chain tasks past a gate.** Tasks 5, 6 and 7 each need a fresh
  approval; 6 and 7 mutate a shared corporate BTP account.

---

### Task 0: Baseline capture — Gate 0

Read-only. Nothing is edited. Its output is what every later "unchanged"
claim is measured against, and the bundle plan deliberately does **not**
hardcode these numbers, because a number nobody re-measured is the defect
item 1 exists to prevent.

**Files:**
- Create: none
- Modify: none
- Read: `test_fixes.py`, `test_address.py`, `test_customer_number.py`,
  `test_jargon.py`, `holdout_samples.json`, `eval_samples_v2.json`,
  `holdout_v3.json`

**Interfaces:**
- Consumes: nothing
- Produces: a baseline block pasted into the Gate 0 report — four test counts,
  `over_detections`, four regression scores, and the exact leak list of each
  regression set. Tasks 3 and 4 compare against these.

- [ ] **Step 1: Confirm the tree is clean and on the right commit**

```bash
cd "/Users/terulinsinulingga/Downloads/NER POC"
git status --short
git log --oneline -1
```

Expected: no modified tracked files. `VSCODE-PROMPT-address-recognizer.md`
shows as untracked (`??`) — that is a known, separate housekeeping item, not
a blocker.

- [ ] **Step 2: Capture the four local test counts**

```bash
source .venv/bin/activate
for t in test_fixes test_address test_customer_number test_jargon; do
  echo "=== $t ==="
  python $t.py 2>&1 | tail -3
done
```

Record the pass count and exit status of each. `test_fixes.py` must read
16/16 — the handover asserts it. The other three counts have no asserted
value; whatever they print now **becomes** the baseline.

- [ ] **Step 3: Start a local service and capture the selftest baseline**

```bash
uvicorn app:app --host 0.0.0.0 --port 8080 &
sleep 20
curl -s localhost:8080/v1/selftest | python3 -c "
import json,sys; d=json.load(sys.stdin)
print('recall_pct      ', d['overall']['recall_pct'])
print('redacted        ', d['overall']['redacted'], '/', d['overall']['expected_pii'])
print('missed          ', d['overall']['missed'])
print('over_detections ', d['overall']['over_detections'])
print('build_version   ', d.get('build_version', '<absent - pre-1.2.1>'))
"
```

Expected: `100.0`, `45 / 45`, `0`, `4`, and `<absent>`. The absent
`build_version` is the defect Task 1 fixes — record it as observed, it is the
before-picture.

- [ ] **Step 4: Capture all four regression scores AND their leak lists**

```bash
for f in holdout_samples.json eval_samples_v2.json holdout_v3.json; do
  echo "########## $f"
  SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py $f 2>&1 \
    | grep -E "caught:|RECALL|^  \[" 
done
```

Expected, from the handover: `108/111`, `65/68`, `45/50`.

⚠️ The banner prints `HOLDOUT RESULT` / `HOLDOUT RECALL` for **every** input
file. Two of these three are not holdouts. The banner is a known lie; record
the scores against the filename you passed, never against the banner.

**Copy the leak lines verbatim.** §12 of the bundle plan names the leaks for
two of the three sets and explicitly does not invent `eval_samples_v2.json`'s.
This step is where that list comes from. A count that holds while the leak
list changes is a stop, and only this capture can detect it.

- [ ] **Step 5: Stop the service and write the Gate 0 report**

```bash
kill %1
```

Report, ≤250 words: the four test counts, the five selftest numbers, the
three regression scores with their leak lists, and answers requested for Q1,
Q2 and Q3 in §4 of the bundle plan.

**⛔ GATE 0 — stop here. Do not begin Task 1 without approval.**

---

### Task 1: `BUILD_VERSION` through the service

**Files:**
- Modify: `app.py` (three edits: a constant near line 107, the `FastAPI(...)`
  call at line 192, `/info` at line 473, selftest's return at line 577)
- Modify: `Dockerfile` (two lines, after line 65, before `EXPOSE`)
- Create: `test_build_version.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `app.BUILD_VERSION: str` — read once at import from the
  environment, default `"dev"`. Surfaced as the key `build_version` in both
  `app.info()` and `app.selftest()` return dicts, and as `app.app.version`.
  Task 2 reads `build_version` off the `/info` payload.

- [ ] **Step 1: Write the failing test**

Create `test_build_version.py`:

```python
#!/usr/bin/env python3
"""
BUILD_VERSION -- the image must be able to say which build it is.

From the stale-deployment incident: a script pointed at a deployment that was
live but not the one just shipped, and reported confident numbers for the
wrong artifact. Nothing in any response identified the build.

Two halves are asserted here, and the second is the one that actually breaks:
  1. the value reaches both endpoints and the FastAPI app object
  2. the Dockerfile wiring -- ARG default, and ENV placed after every COPY so
     a version bump does not invalidate the pip and spaCy layers

Run: python test_build_version.py
"""
import os
import sys

os.environ.setdefault("SCRUBBER_ENGINE", "presidio")

import app as A  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    status = "ok  " if cond else "FAIL"
    print(f"  [{status}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


print("Service reports its build")
check("BUILD_VERSION is a non-empty string",
      isinstance(A.BUILD_VERSION, str) and A.BUILD_VERSION != "",
      f"got {A.BUILD_VERSION!r}")
check("default is 'dev' when the env var is unset",
      A.BUILD_VERSION == os.getenv("BUILD_VERSION", "dev"),
      f"env={os.getenv('BUILD_VERSION')!r} constant={A.BUILD_VERSION!r}")
check("FastAPI app version tracks the build, not a hardcoded string",
      A.app.version == A.BUILD_VERSION,
      f"app.version={A.app.version!r} BUILD_VERSION={A.BUILD_VERSION!r}")
check("/info carries build_version",
      A.info().get("build_version") == A.BUILD_VERSION,
      f"info() keys: {sorted(A.info())}")
check("/v1/selftest carries build_version",
      A.selftest().get("build_version") == A.BUILD_VERSION,
      "selftest payload has no build_version key")

# ---------------------------------------------------------------------------
# Dockerfile wiring. A constant the image never populates is worse than no
# constant -- it looks like evidence. Same trap class as the __version__ line
# that printed "presidio unknown" for months.
# ---------------------------------------------------------------------------
print("Dockerfile wiring -- printed, not assumed")

lines = open("Dockerfile").read().splitlines()
arg_lines = [(i, l) for i, l in enumerate(lines) if l.strip().startswith("ARG BUILD_VERSION")]
env_lines = [(i, l) for i, l in enumerate(lines) if l.strip().startswith("ENV BUILD_VERSION")]
copy_lines = [i for i, l in enumerate(lines) if l.strip().startswith("COPY")]

check("Dockerfile declares ARG BUILD_VERSION", bool(arg_lines),
      "no ARG BUILD_VERSION line found")
check("Dockerfile exports ENV BUILD_VERSION", bool(env_lines),
      "no ENV BUILD_VERSION line found")

if arg_lines:
    check("ARG default is 'dev', not a version-shaped string",
          arg_lines[0][1].strip() == "ARG BUILD_VERSION=dev",
          f"line {arg_lines[0][0] + 1}: {arg_lines[0][1].strip()!r}")

if env_lines and copy_lines:
    env_i, last_copy = env_lines[0][0], max(copy_lines)
    check("ENV BUILD_VERSION sits AFTER every COPY (layer-cache guard)",
          env_i > last_copy,
          f"ENV at line {env_i + 1}, last COPY at line {last_copy + 1} -- "
          "an early ENV re-runs pip and the spaCy download on every bump")

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
```

- [ ] **Step 2: Run it to verify it fails**

```bash
source .venv/bin/activate
python test_build_version.py
```

Expected: `AttributeError: module 'app' has no attribute 'BUILD_VERSION'`, or
a `FAILED:` line naming every check. Either is a correct red.

- [ ] **Step 3: Add the constant to `app.py`**

Immediately after the `GLOSSARY_PATH` block (currently line 107):

```python
# Baked at build time by the Dockerfile (ARG -> ENV) and read once here.
# Default "dev" on purpose: an image built without --build-arg must be
# VISIBLY wrong, not plausibly right. From the stale-deployment incident --
# a script measured a live-but-stale deployment and reported confident
# numbers for an artifact nothing in the response identified. Surfaced by
# /info and /v1/selftest so every number carries the build that produced it.
BUILD_VERSION = os.getenv("BUILD_VERSION", "dev")
```

- [ ] **Step 4: Wire it into the three places that report identity**

`app.py:192` — the hardcoded string has read `1.0.0` on every image since,
including the deployed `1.2.0`. It is not missing information, it is wrong
information:

```python
app = FastAPI(title="PII Scrubber (POC)", version=BUILD_VERSION)
```

`app.py:475`, first key of the `/info` dict:

```python
    return {
        "build_version": BUILD_VERSION,
        "engine": ENGINE,
```

`app.py:578`, first key of the selftest return dict:

```python
    return {
        "build_version": BUILD_VERSION,
        "engine": ENGINE,
        "samples_run": len(samples),
```

- [ ] **Step 5: Add the Dockerfile wiring**

After the `ENV SCRUBBER_ENGINE=...` block (currently ends line 65) and
**before** `EXPOSE 8080`:

```dockerfile
# Build identity, passed at build time:
#   docker buildx build --build-arg BUILD_VERSION=1.2.1 ...
#
# Placed HERE, after every COPY, on purpose: an ENV invalidates every layer
# below it, so an early placement would re-run pip and the spaCy download on
# every version bump -- minutes of emulated build, for a string.
#
# The default is "dev" and must stay that way. A version-shaped default makes
# an image built without --build-arg indistinguishable from a correct one,
# which is precisely the incident this exists to prevent.
ARG BUILD_VERSION=dev
ENV BUILD_VERSION=${BUILD_VERSION}
```

- [ ] **Step 6: Run the test to verify it passes**

```bash
python test_build_version.py
```

Expected: `ALL TESTS PASS`, 8 checks, exit 0.

- [ ] **Step 7: Verify the env override actually overrides**

The test file asserts the default; this proves the read is live. A subprocess
is used rather than `importlib.reload` because reloading `app` re-creates the
FastAPI object and re-reads the 3 MB allowlist for no gain:

```bash
BUILD_VERSION=9.9.9-test python3 -c "import app; print(app.BUILD_VERSION, app.app.version)"
python3 -c "import app; print(app.BUILD_VERSION)"
```

Expected: `9.9.9-test 9.9.9-test`, then `dev`.

- [ ] **Step 8: Prove no detection path moved**

Item 1 adds a dict key. If any of these changes, something other than a dict
key changed:

```bash
python test_fixes.py | tail -2          # must still be 16/16
python test_address.py | tail -2        # must equal the Task 0 count
python test_jargon.py | tail -2         # must equal the Task 0 count
```

- [ ] **Step 9: Commit**

```bash
git add app.py Dockerfile test_build_version.py
git commit -m "feat: BUILD_VERSION baked at build time, reported by /info and selftest

Every number now carries the artifact that produced it. From the stale-
deployment incident: a script measured a live-but-stale deployment and
reported confident figures for an image nothing in the response identified.

The hardcoded FastAPI version=1.0.0 is replaced, not supplemented -- it has
read 1.0.0 on every image shipped since, including the deployed 1.2.0, so it
was a false claim rather than a missing one.

ARG default is 'dev' so an image built without --build-arg is visibly wrong.
ENV sits after every COPY so a version bump does not invalidate the pip and
spaCy layers. Both asserted structurally in test_build_version.py."
```

---

### Task 2: The harness stamps the build it measured

Item 1 is only half a fix. The incident was a *script* reporting the wrong
artifact; a version only the endpoint knows changes nothing unless the thing
that prints numbers prints it too. `test_deployed.py` is the single scorer
for every quoted figure, so it is the one place this belongs.

**Files:**
- Modify: `test_deployed.py:58-68` (after `url`/`headers` are built, before
  the sample loop) and `:108-114` (the result header)

**Interfaces:**
- Consumes: `build_version` from the `/info` payload produced by Task 1
- Produces: a `build:` line in the result header. No change to scoring, no
  change to exit codes, no change to the JSON contract.

- [ ] **Step 1: Add the identity fetch**

In `test_deployed.py`, immediately after the `headers` block ends (line 62)
and before `per_type = defaultdict(...)`:

```python
    # Stamp the artifact these numbers came from. Pre-1.2.1 images have no
    # build_version -- say so and carry on rather than aborting, because the
    # 1.2.0 and 1.1.0 rollback images must stay measurable.
    info_url = url.rsplit("/v1/scrub", 1)[0] + "/info"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(info_url, headers=headers), timeout=30) as r:
            build = json.load(r).get("build_version") or "unknown (pre-1.2.1 image)"
    except Exception as e:                      # noqa: BLE001 -- identity is advisory
        build = f"unreachable ({type(e).__name__})"
```

- [ ] **Step 2: Print it in the result header**

`test_deployed.py:112`, between the banner and the counts:

```python
    print(f"build: {build}   target: {url}")
```

- [ ] **Step 3: Run it against the current 1.2.0 image and confirm it says so**

This is the meaningful red-then-green: today's service has no
`build_version`, and the harness must say that rather than inventing one.

```bash
source .venv/bin/activate
git stash                                    # 1.2.0 behaviour, Task 1 changes parked
uvicorn app:app --host 0.0.0.0 --port 8080 &
sleep 20
SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py holdout_v3.json | head -6
kill %1
git stash pop
```

Expected header: `build: unknown (pre-1.2.1 image)`.

- [ ] **Step 4: Run it against the Task 1 service and confirm the stamp**

```bash
BUILD_VERSION=1.2.1-local uvicorn app:app --host 0.0.0.0 --port 8080 &
sleep 20
SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py holdout_v3.json | head -6
kill %1
```

Expected: `build: 1.2.1-local`, and the score still exactly `45/50`.

- [ ] **Step 5 (CONDITIONAL — only if Q1 was answered YES at Gate 0): fix the lying banner**

`test_deployed.py:109` and `:114` print `HOLDOUT RESULT` and
`HOLDOUT RECALL` for **any** input file. Run against `eval_samples_v2.json`
they label a non-holdout as a holdout. Same incident class as item 1:
metadata a human reads as evidence.

```python
    print("SCRUBBER EVALUATION — deployed service, one scorer for all sets")
...
    print(f"RECALL: {recall:.1f}%   ({dt:.0f}s total)")
```

And if Q2 was also YES, extend Step 2's line:

```python
    print(f"build: {build}   samples: {path}   target: {url}")
```

**If Q1 was NO, skip this step entirely and leave the banner alone.**

- [ ] **Step 6: Commit**

```bash
git add test_deployed.py
git commit -m "feat: test_deployed.py stamps the build it measured

The stale-deployment incident was a script reporting confident numbers for
the wrong artifact. A build version only the endpoint knows does not fix
that; the thing that prints the numbers has to print it.

Advisory, never fatal: a pre-1.2.1 image reports 'unknown' and the run
proceeds, so the 1.2.0 and 1.1.0 rollback images stay measurable."
```

---

### Task 3: Eight glossary entries

**Data only.** Any diff to `app.py` or `recognizers.py` in this task means the
mechanism was rebuilt instead of reused — the glossary loads through
`app._load_allowlist()` (`app.py:110-136`) into the same suppression set as
`allowlist.txt`, and therefore already inherits case-sensitive exact match,
whole-span matching and the ±40-char user-context backstop.

**Files:**
- Modify: `glossary.txt` (eight entries into the existing sections, plus the
  header block's PRE-CLEARED list)
- Modify: `test_jargon.py` (append a new numbered section before the final
  `if FAILURES:` block)

**Interfaces:**
- Consumes: `app.ALLOWLIST_EXACT` (the loaded suppression set), and
  `test_jargon.py`'s existing helpers `check(name, cond, detail)`,
  `spans(text)`, `clean(text, token)`, `redacted(text, value)`
- Produces: eight new members of `ALLOWLIST_EXACT`. No new symbols.

- [ ] **Step 1: Write the failing tests**

Append to `test_jargon.py`, after the packaging section (currently ends line
161) and **before** the final `if FAILURES:` block:

```python
# --------------------------------------------------------------------------
# 6. Bundle 1.2.1 -- eight entries, each traced to a blind-batch sample.
#    Six are two or three characters, below the 4-char SAP_USER_ID floor
#    (recognizers.py:108), so they were never user-ID spans: they arrived
#    from the spaCy layer. The assertion is that they leave suppressed.
# --------------------------------------------------------------------------
print("1.2.1 entries -- observed misfires must stop")

STOPS_121 = [
    ("GL   (V3-034)",   "The GL posting failed during the period close run.", "GL"),
    ("FX   (V3-034)",   "Revaluation picked up the wrong FX rate for the period.", "FX"),
    ("WM   (V3-035)",   "Bin determination in WM did not resolve for the depot.", "WM"),
    ("MDG  (V3-038)",   "The record was blocked in MDG pending data steward review.", "MDG"),
    ("MRP  (V3-039)",   "MRP did not generate the planned order for the component.", "MRP"),
    ("OSS  (V3-040)",   "Raised an OSS note with support for the dump.", "OSS"),
    ("CFO  (V3-001)",   "Escalated to the CFO office for the write-off approval.", "CFO"),
    ("Rise (V3-035)",   "Investigating the Rise in failed deliveries this month.", "Rise"),
]

for name, text, token in STOPS_121:
    check(name, clean(text, token), f"spans: {spans(text)}")

# The leak guard, applied to the new entries. An entry may veto a PATTERN,
# never CONTEXT -- this is the group that would show it if that ever broke.
print("1.2.1 leak guard -- context still overrides every new entry")
check("'posted by CFO' still redacts",
      redacted("Adjustment posted by CFO during the close.", "CFO"),
      A.scrub("Adjustment posted by CFO during the close.", "batch")["scrubbed_text"])
check("'requested by MDG' still redacts",
      redacted("Change requested by MDG last Thursday.", "MDG"))

# Rise is BOTH jargon and a street type. The address case is already asserted
# in section 3 (14 Sunrise Rise); this is the other half -- the bare noun.
# If either direction breaks, Rise goes to Appendix A, never to a workaround.
print("1.2.1 Rise -- suppressed as a noun, intact as a street type")
check("bare 'Rise' does not redact", clean(STOPS_121[7][1], "Rise"))
check("'14 Sunrise Rise' still redacts",
      redacted("Depot at 14 Sunrise Rise, Papakura, Auckland.", "14 Sunrise Rise"),
      A.scrub("Depot at 14 Sunrise Rise, Papakura, Auckland.", "batch")["scrubbed_text"])
check("'44 Bellbird Rise' span behaviour unchanged (known v2 ADDRESS gap)",
      "Rise" not in [t for t, _ in spans("Vendor site at 44 Bellbird Rise.")],
      f"spans: {spans('Vendor site at 44 Bellbird Rise.')}")

# Case sensitivity, per entry. A lowercase or all-caps variant must NOT be
# suppressed -- 'gl' and 'rise' are ordinary words, 'RISE' could be an object.
print("1.2.1 leak guard -- case-sensitive exact match holds per entry")
for tok in ("GL", "FX", "WM", "MDG", "MRP", "OSS", "CFO", "Rise"):
    check(f"{tok!r} is an entry", tok in A.ALLOWLIST_EXACT)
for tok in ("gl", "fx", "wm", "mdg", "mrp", "oss", "cfo", "rise", "RISE"):
    check(f"{tok!r} is NOT an entry", tok not in A.ALLOWLIST_EXACT)

# Still-rejected and still-unshipped. These stay out; a future session that
# adds one must delete the assertion deliberately, not by accident.
print("1.2.1 -- pre-cleared but unshipped street types stay out")
for tok in ("Close", "Court", "Terrace", "Drive"):
    check(f"{tok!r} still unshipped (cleared, no observed misfire)",
          tok not in A.ALLOWLIST_EXACT)
print("1.2.1 -- lg-only evidence is not evidence about the shipped config")
for tok in ("SH", "ES_SD_REBATE"):
    check(f"{tok!r} rejected (misfired only under en_core_web_lg)",
          tok not in A.ALLOWLIST_EXACT)
```

- [ ] **Step 2: Run to verify it fails**

```bash
source .venv/bin/activate
python test_jargon.py
```

Expected: the eight `STOPS_121` checks FAIL (the tokens are still redacted),
the eight `is an entry` checks FAIL, and the `is NOT an entry`,
`still unshipped` and lg-rejection checks already PASS. The `14 Sunrise Rise`
address check must already PASS — it is pre-existing behaviour and a failure
here would mean something unrelated broke.

- [ ] **Step 3: Add the eight entries to `glossary.txt`**

Into the **existing** sections — do not create new headings:

Under `# --- modules and technical components ---`, after `RF`:

```
GL		# module
FX		# module
WM		# module
MDG		# module
MRP		# module
OSS		# module
```

Under `# --- process nouns mis-tagged as entities ---`, after `suffix`:

```
Rise		# process
```

Under `# --- roles, facilities, departments ---`, after `Payer`:

```
CFO		# role
```

Separator is a **tab**, and the reason is one word from the fixed vocabulary
(`module | env | doc | table | process | role | facility | dept | shorthand`).
An unexplained entry is the next session's mystery.

- [ ] **Step 4: Update the glossary header block**

Two edits. First, the bundle line (line 1):

```
# SAP jargon glossary — bundle 1.2.0, item 2; extended by 1.2.1, item 2.
```

Second, replace the PRE-CLEARED block (lines 38-42), because `Rise` has left
it:

```
# PRE-CLEARED BUT NOT SHIPPED — street types that passed the safety gate in
# test_jargon.py but have no observed misfire, so they are not entries yet:
#   Close  Court  Terrace  Drive
# "Rise" left this list in 1.2.1: the blind batch produced the missing
# evidence ("the Rise in failed deliveries", V3-035), pairing the clearance
# with an incident. That is the protocol working, not an exception to it —
# prove it safe when you first meet it, ship it when an incident asks.
#
# 1.2.1 additions, each traced to a blind-batch sample. holdout_v3.json is
# gitignored, so these IDs name a file the reader may not have — ask for it
# rather than assuming the entry was unevidenced:
#   GL FX  V3-034    WM Rise  V3-035    MDG  V3-038
#   MRP    V3-039    OSS      V3-040    CFO  V3-001
# All except Rise are 2-3 chars, below the 4-char SAP_USER_ID floor
# (recognizers.py:108), so each was a spaCy-layer over-detection.
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
python test_jargon.py
```

Expected: `ALL TESTS PASS`, exit 0, and a check count equal to the Task 0
baseline **plus 35** (8 stops + 2 context + 2 Rise + 8 present + 9 absent +
4 unshipped + 2 lg-only) — i.e. **74**, since the measured baseline is 39.
The `44 Bellbird Rise` unit check named in an earlier draft is dropped: the
v2 regression gate asserts that value's behaviour directly.

- [ ] **Step 6: Confirm the loader count moved by exactly eight**

The suppression set must grow by eight and by nothing else. This is the
"print what you inspected" step, not a verdict:

```bash
python3 -c "
import os; os.environ.setdefault('SCRUBBER_ENGINE','presidio')
import app as A
print('total suppression tokens:', len(A.ALLOWLIST_EXACT))
print('new eight present:', sorted(t for t in ('GL','FX','WM','MDG','MRP','OSS','CFO','Rise') if t in A.ALLOWLIST_EXACT))
" 2>&1 | grep -v INFO
```

Expected: 257,619 (the 257,611 baseline + 8), and all eight listed. A total
that moved by anything other than 8 means a stray edit or a tab/space defect
in `glossary.txt`.

- [ ] **Step 7: Commit**

```bash
git add glossary.txt test_jargon.py
git commit -m "feat: eight glossary entries, each traced to a blind-batch sample

GL FX (V3-034), WM Rise (V3-035), MDG (V3-038), MRP (V3-039), OSS (V3-040),
CFO (V3-001). All meet the shipping rule -- observed misfire on the SHIPPED
config -- unlike SH and ES_SD_REBATE, which misfired only under lg and stay
out.

Six are 2-3 chars, below the 4-char SAP_USER_ID floor (recognizers.py:108),
so they were spaCy-layer over-detections rather than recognizer hits.

Rise leaves the PRE-CLEARED list: safety-cleared in Appendix A of the 1.2.0
plan, and the blind batch supplied the missing incident. Both directions
asserted -- bare noun suppressed, 14 Sunrise Rise still redacted.

Data only. No app.py or recognizers.py change: the glossary loads through
_load_allowlist into the existing suppression set and inherits case-sensitive
exact match, whole-span matching and the context backstop."
```

---

### Task 4: Regression sweep — the stop gate

**Files:**
- Modify: none. This task measures.

**Interfaces:**
- Consumes: the Task 0 baseline block (four counts, `over_detections`, three
  regression scores **and their leak lists**)
- Produces: the same block, re-measured, plus an itemised diff of any
  `over_detections` change

- [ ] **Step 1: Start a local service, stamped**

```bash
source .venv/bin/activate
BUILD_VERSION=1.2.1-local uvicorn app:app --host 0.0.0.0 --port 8080 &
sleep 20
curl -s localhost:8080/info | python3 -m json.tool | head -4
```

Expected: `"build_version": "1.2.1-local"` as the first key. That line is now
the proof that everything below measured this build.

- [ ] **Step 2: Selftest — 45/45, and account for `over_detections`**

```bash
curl -s localhost:8080/v1/selftest | python3 -c "
import json,sys; d=json.load(sys.stdin)
o=d['overall']
print('build           ', d['build_version'])
print('recall_pct      ', o['recall_pct'])
print('redacted        ', o['redacted'], '/', o['expected_pii'])
print('missed          ', o['missed'])
print('over_detections ', o['over_detections'], '(Task 0 baseline: 4)')
"
```

`recall_pct 100.0` and `45/45` are **hard stops** — anything less is a
detection regression and the bundle halts.

`over_detections` may legitimately fall if one of the eight entries also
misfired inside `samples.json`. It may not rise. **If it changed in either
direction, itemise which span stopped or started being emitted, sample by
sample, before re-asserting the baseline** — exactly as 1.2.0 did for 6 → 4.
An unexplained baseline is the next session's mystery.

- [ ] **Step 3: All three regression sets at exact gate values**

```bash
for f in holdout_samples.json eval_samples_v2.json holdout_v3.json; do
  echo "########## $f"
  SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py $f 2>&1 \
    | grep -E "^build:|caught:|RECALL|^  \["
done
kill %1
```

| Set | Required | Leaks |
|---|---|---|
| `holdout_samples.json` | **exactly 108/111** | `ZHANG`, `Young`, `Mere Tuhoe` |
| `eval_samples_v2.json` | **exactly 65/68** | includes `44 Bellbird Rise` |
| `holdout_v3.json` | **exactly 45/50** | `NAKAMURA`, `Park`, `Adeyemi`, `5591230`, `6620945` |

⛔ **Any deviation is a stop, in either direction.** A score that rises means
detection moved on a burned set nobody was authorised to move. And a count
that holds while the **leak list** changes is the most dangerous shape a
regression takes — two compensating changes summing to zero — which is why
Task 0 captured the lists and not just the counts.

- [ ] **Step 4: Run the whole local suite**

```bash
for t in test_fixes test_address test_customer_number test_jargon test_build_version; do
  echo "=== $t ==="; python $t.py 2>&1 | tail -2
done
```

Expected: all exit 0. `test_fixes.py` 16/16. `test_address.py` and
`test_customer_number.py` at their Task 0 counts, unchanged — item 2 must not
have moved the address recognizer. `test_jargon.py` at baseline + 31.
`test_build_version.py` 8/8.

- [ ] **Step 5: Report and stop**

Report, ≤300 words: every number above next to the command that produced it,
the `over_detections` itemisation if it moved, and an explicit statement that
all three leak lists are unchanged (or exactly what changed).

**⛔ GATE 4 — no image is built without approval.**

---

### Task 5: Build and verify the image

**Files:**
- Modify: none

**Interfaces:**
- Consumes: the Dockerfile wiring from Task 1
- Produces: local image `ghcr.io/terusin71/pii-scrubber:1.2.1`, `linux/amd64`,
  whose `/info` reports exactly `1.2.1`

- [ ] **Step 1: Check disk before starting**

```bash
df -h / | tail -1
docker images ghcr.io/terusin71/pii-scrubber
```

Need ~2.5 GB free. **Do not run `docker system prune`** — unrelated
`frappe_docker` images are present.

- [ ] **Step 2: Build, with the arg**

```bash
docker buildx build --platform linux/amd64 \
  --build-arg BUILD_VERSION=1.2.1 \
  -t ghcr.io/terusin71/pii-scrubber:1.2.1 --load .
```

~3 minutes emulated: pip pulls prebuilt manylinux wheels, so QEMU emulates
almost nothing. If it dies with `lease does not exist: not found`, that is a
corrupted BuildKit lease — `docker pull python:3.11-slim`, then rebuild
unchanged. Not disk, not network.

⚠️ **Forgetting `--build-arg` is the single most likely failure in this
bundle** (risk R1). Step 4 is what catches it.

- [ ] **Step 3: Verify the platform**

```bash
docker buildx imagetools inspect ghcr.io/terusin71/pii-scrubber:1.2.1 2>/dev/null \
  || docker image inspect ghcr.io/terusin71/pii-scrubber:1.2.1 --format '{{.Os}}/{{.Architecture}}'
```

Expected: `linux/amd64`. On this arm64 host an arm64 image round-trips
perfectly and still cannot run on AI Core, so a digest check alone proves
nothing.

- [ ] **Step 4: Run the container and assert the version string exactly**

```bash
docker run --rm -d -p 8080:8080 --name pii121 ghcr.io/terusin71/pii-scrubber:1.2.1
sleep 30
curl -s localhost:8080/info | python3 -c "
import json,sys; d=json.load(sys.stdin)
v=d.get('build_version')
print('build_version:', repr(v))
assert v == '1.2.1', f'EXPECTED 1.2.1, GOT {v!r} -- rebuilt without --build-arg?'
print('OK')
"
```

⛔ A `dev` here means the image was built without `--build-arg`. Rebuild.
Do not push it, and do not talk yourself into "the tag says 1.2.1 anyway" —
that is the exact reasoning the item exists to defeat.

- [ ] **Step 5: In-container selftest must be identical to Task 4**

```bash
curl -s localhost:8080/v1/selftest | python3 -c "
import json,sys; d=json.load(sys.stdin); o=d['overall']
print(d['build_version'], o['recall_pct'], f\"{o['redacted']}/{o['expected_pii']}\", o['missed'], o['over_detections'])
"
docker logs pii121 2>&1 | grep -E "Allowlist loaded|Glossary loaded|ORG un-ignored|Removed UrlRecognizer"
```

Expected: `1.2.1 100.0 45/45 0 <Task 4 value>`, and the glossary line
reporting **36** tokens — the loader logs *newly added unique* tokens, which
was 28 before this bundle, so 28 + 8.

⚠️ **Corrected 2026-08-16.** An earlier draft of this line said the file's
29th entry "already exists in the seed set". It does not. The duplicate is
**`QMEL`, which is in `allowlist.txt`** (mined from DD02L); the allowlist
loads first, so `QMEL` was already in the set and the glossary added nothing
for it. Overlap with the 27-token built-in seed is zero. Entries and
newly-added tokens diverge whenever a hand-curated word collides with the
mined extract — see the reconciliation block at the top of `glossary.txt`.

A glossary that did not reach the image
starts the service **clean, with no error** — the loader logs a skip and
carries on. That log line is the only signal.

- [ ] **Step 6: Run the three regression sets against the container**

```bash
for f in holdout_samples.json eval_samples_v2.json holdout_v3.json; do
  echo "########## $f"
  SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py $f 2>&1 \
    | grep -E "^build:|caught:|RECALL"
done
docker stop pii121
```

Every score identical to Task 4, and every `build:` line reading `1.2.1`.
That pair — same numbers, named artifact — is what this whole bundle was for.

- [ ] **Step 7: Report and stop**

Report, ≤200 words: platform, image size, the six selftest numbers, the three
regression scores, the glossary token count from the logs.

**⛔ GATE 5 — publishing mutates a remote registry. Do not proceed without
approval.**

---

### Task 6: Publish — ⚠️ mutates remote

**Files:**
- Modify: none

- [ ] **Step 1: Confirm the token scope before touching anything**

Pushing needs `write:packages`. The AI Core pull secret needs
`read:packages`. Git sync needs `repo`. **GitHub's 403 distinguishes none of
them** — it reads as an authentication failure when it is authorization. When
ghcr returns 401/403, check the scope before touching the credential.

Credentials are supplied at the moment of use via environment variables. They
are never committed, never echoed into a log, and never embedded in a git
remote URL.

- [ ] **Step 2: Push**

```bash
docker push ghcr.io/terusin71/pii-scrubber:1.2.1
```

- [ ] **Step 3: Pull back and verify platform and version together**

```bash
docker buildx imagetools inspect ghcr.io/terusin71/pii-scrubber:1.2.1
```

Expected: a `linux/amd64` manifest, plus an `unknown/unknown` attestation
manifest, which is normal buildkit provenance and not a second platform.
Record the digest — it goes in the handover.

- [ ] **Step 4: Commit the docs that name the digest**

```bash
git add docs/superpowers/plans/2026-08-16-pii-scrubber-1.2.1-bundle.md
git commit -m "docs: 1.2.1 published, digest recorded"
```

---

### Task 7: Deploy — ⚠️ BTP, user drives

**Files:**
- Modify: `workflows/serving_template.yaml:44` (image tag) and the rollback
  comment above it

- [ ] **Step 1: Point the template at 1.2.1**

```yaml
          # Mutable TAG, not a digest, on purpose: a digest freezes this
          # template to one build, while the tag lets a corrected image flow
          # through with no template change. That was load-bearing when the
          # arm64 image had to be replaced (finding 13).
          # Rollback tag: 1.2.0 (sha256:e8a44575...81ca893).
          image: "ghcr.io/terusin71/pii-scrubber:1.2.1"
```

One-line image change plus the rollback comment. Nothing else in this file
moves — the labels are the accepted shape (`scenarios.ai.sap.com/id` and
`ai.sap.com/version: "1.0"` only), and an extra label or `"1.0.0"` prevents
the scenario appearing at all.

- [ ] **Step 2: Commit and push so git-sync sees it**

```bash
git add workflows/serving_template.yaml
git commit -m "deploy: point the ServingTemplate at 1.2.1"
git push origin deploy/aicore-poc
```

- [ ] **Step 3: Confirm the sync from the API, never the cockpit**

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$AI_API/v2/admin/applications/pii-scrubber-app/status"
```

The cockpit's sync panel reads `Sync Status: Unknown`, `0 synced resources`
**identically on working and broken applications** — it is cosmetic on free
tier. Onboarding `COMPLETED` means "config stored", not "repo reachable".
Only this endpoint names the real rejection.

- [ ] **Step 4: Delete, confirm gone, then create — never stop-then-create**

Quota is **1 pod**. A stop-then-create race marks the new revision failed
**permanently**; Kubernetes never re-drives an admission-rejected revision.

```bash
# what exists now
curl -s -H "Authorization: Bearer $TOKEN" -H "AI-Resource-Group: default" \
  "$AI_API/v2/lm/deployments"

# delete db3d9cc5eea296cd, then POLL until it is gone from that list
# only then create the new deployment
```

- [ ] **Step 5: Verify the deployed build is the one just shipped**

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "AI-Resource-Group: default" \
  "$AI_API/v2/inference/deployments/<NEW_ID>/info"
```

Expected `"build_version": "1.2.1"`. **This is the first deployment in the
project's history where that question has an answer** — the stale-deployment
incident is closed at this line, not before it.

- [ ] **Step 6: Deployed selftest identical to the container**

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "AI-Resource-Group: default" \
  "$AI_API/v2/inference/deployments/<NEW_ID>/v1/selftest" \
  | python3 -m json.tool | head -20
```

Must match Task 5 Step 5 exactly. Any difference means the deployment is not
running the image just verified.

- [ ] **Step 7: Update the handover and close out**

Work §13 of the bundle plan. The new deployment ID replaces
`db3d9cc5eea296cd` in `HANDOVER.md`, in `test_deployed.py:43`, and anywhere
else it appears — **a script pointing at a stale but live deployment reports
confident numbers for the wrong artifact**, which is the incident this whole
release was built around. Do not leave it half-repointed.

```bash
grep -rn "db3d9cc5eea296cd" --include="*.py" --include="*.md" --include="*.html" .
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: 1.2.1 deployed, handover and DEPLOYMENT_ID repointed"
git push origin deploy/aicore-poc
```

---

## Self-review against the spec

- **§4 D1-D10** — D1/D2/D3 in Task 1 Steps 3 and 5; D4/D5/D6 in Step 4;
  D7/D8 in Task 2; D9/D10 in Task 3 Steps 3 and 1 respectively.
- **§4 Q1/Q2** — Task 2 Step 5, explicitly conditional on the Gate 0 answer.
  **Q3 is deliberately unimplemented** — the `LABEL_MAP` warning stays
  backlogged.
- **§9 R1** — Task 5 Step 4 asserts the exact string. **R2** — Task 3 Step 1,
  both directions. **R3** — Task 3 Step 1, case-sensitivity block. **R4** —
  Task 4 Step 2 itemisation. **R5** — Task 1 Step 5 placement, asserted by
  `test_build_version.py`. **R6** — Task 7 Step 4. **R7** — Task 4 Step 4.
  **R8** — Task 4 runs local. **R9** — every verification step prints its
  input.
- **§11/§12** — Task 0 Step 4 captures the leak lists; Task 4 Step 3 compares
  them, not just the counts.
- **Naming consistency** — `BUILD_VERSION` (constant), `build_version` (the
  JSON key and the `/info` field) are used consistently in Tasks 1, 2, 4, 5
  and 7. `STOPS_121` does not collide with the existing `STOPS` in
  `test_jargon.py`.

## Execution handoff

Two options, both requiring a fresh gate at Tasks 0, 4, 5, 6 and 7:

1. **Subagent-driven** (`superpowers:subagent-driven-development`) — a fresh
   subagent per task, review between tasks. Suits Tasks 1-3, which are
   self-contained and locally verifiable.
2. **Inline** (`superpowers:executing-plans`) — batch execution with
   checkpoints. Suits Tasks 5-7, which touch Docker, a remote registry and a
   shared BTP tenant, and where a subagent's missing context is a liability.

Recommended split: subagent-driven for 1-3, inline for 5-7, with Task 4 run
inline because its output is the stop decision.
