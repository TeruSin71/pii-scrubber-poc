# PII Scrubber — SAP AI Core Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the PII Scrubber source in this repo to a RUNNING deployment on SAP AI Core (BTP Free Tier) whose `/v1/selftest` returns `recall_pct: 100.0`, without weakening detection.

**Architecture:** FastAPI service wrapping Microsoft Presidio + 8 custom SAP recognizers, with two non-model suppression layers — a case-sensitive technical allowlist and a deterministic customer-namespace rule. Packaged as a CPU-only Docker image with weights baked in (zero runtime network egress), deployed to AI Core as a KServe `ServingTemplate` on the `starter` resource plan. GLiNER stays dormant behind `SCRUBBER_ENGINE=presidio` for the first deploy; flipping to `both` is a configuration change, not a rebuild.

**Tech Stack:** Python 3.12, FastAPI 0.115.6, Presidio 2.2.357, spaCy 3.8.3 (`en_core_web_sm`), GLiNER 0.2.16 + torch 2.5.1 (CPU), Docker, SAP AI Core / AI Launchpad, KServe v1beta1.

**Revision:** rewritten 2026-08-15 after `app.py` gained the custom-object rule and case-sensitive allowlist, and `ALLOWLIST-EXTRACTION.md` was added. Two findings from those changes **resequenced the plan** — see *What changed and why the order moved*.

**Revision 2 (2026-08-15, later):** all three defects this plan identified are now **fixed at source** — see `FIXES-2026-08-15.md`. The Dockerfile ships `allowlist.txt` (Task 2 Step 6 is resolved as Option A), `_load_allowlist()` strips inline comments (the Step 3b `sed` workaround is now optional), and `detect()` gained a user-context backstop for the all-caps collision. New file `test_fixes.py` pins all three defect classes plus the recall invariant; Task 1 runs it. The drop's author reports 15/15 tests passing and `over_detections: 6` re-verified on the current code — Task 1 confirms both on this machine.

---

## What changed and why the order moved

Three substantive updates landed in the repo, and two of them have consequences beyond their own task.

**1. `app.py` gained two detection changes.** Verified by diff against the previous version:

- A deterministic **custom-object rule** (`is_custom_sap_object`, `CUSTOM_OBJ_RE`, `NAMESPACE_RE`, `ZY_SURNAME_GUARD`, toggled by `CUSTOM_OBJECT_RULE`). Spans shaped like `Z*`/`Y*` technical objects or `/NAMESPACE/OBJECT` are suppressed before merge.
- The allowlist match moved from **case-insensitive to case-sensitive** — `ALLOWLIST_LOWER` (lowercased comparison) was replaced by `ALLOWLIST_EXACT` (exact-case set membership).

**Consequence: the documented baseline is now unverified.** `README.md` and `README-DEPLOY.html` both still state `over_detections: 6`. That figure was measured against the *previous* `app.py`. The custom-object rule exists specifically to suppress over-detections, so the number should fall — but no one has run it. Under Hard Rule 8, this plan does not assert 6 as an expected value anywhere. Recall is still asserted at 100.0, because Hard Rule 2 makes that non-negotiable.

A standalone replication of the two new regexes against the tokens that actually appear in `samples.json` confirms the rule fires where intended and, importantly, does **not** touch the ground-truth values:

| Token | Suppressed | Source |
|---|---|---|
| `ZSD_REBATE_001`, `ZSD_REBATE_CALC` | yes | FSD-0001 |
| `ZMM_INV_APPROVAL` | yes | FSD-0002 |
| `ES_SD_REBATE` | **no** — no `Z`/`Y` prefix | FSD-0001 |
| `ZHANG`, `Zhang`, `YOUNG`, `Young` | no — surname guard holds | trap cases |
| `BJOHNSON`, `KMUELLER`, `MTANAKA`, `svc_inv_bot` | no | ground-truth USER_IDs |

That is a sanity check on the rule's shape, not a substitute for running `/v1/selftest`. The real numbers come from Task 1.

**2. `ALLOWLIST-EXTRACTION.md` was added** — a tiered extraction spec (Tier 1 `TSTC`/`DD02L`/`DD03L`, Tier 2 `TFDIR`/`T100`/`TADIR`, Tier 3 domain codes), with assembly rules and an explicit governance refusal of `USR02`. This replaces the old one-table "populate from TSTC" instruction and rewrites the allowlist task substantially.

**3. The Dockerfile does not ship the allowlist — and this is the finding that moved the plan.**

```
Dockerfile:36   COPY app.py recognizers.py samples.json ./
```

`allowlist.txt` is **not** copied into the image. `ALLOWLIST_PATH` defaults to `/app/allowlist.txt`, which will not exist, so `_load_allowlist()` hits `FileNotFoundError` and falls back to the 28-token built-in seed. Every token extracted per `ALLOWLIST-EXTRACTION.md` would be present locally and absent in production.

Two consequences:

- **Sequencing.** Building the image before the allowlist is settled means building, pushing, deploying, then discovering the allowlist never shipped — and redoing the build, push and deploy. So the allowlist task now runs **before** the Docker build, not after it. Tasks renumbered accordingly.
- **A decision is required** (Task 2 Step 6): either add `allowlist.txt` to the `COPY` line, or accept that the deployment runs on the built-in seed. The first is a Dockerfile edit and needs approval under Hard Rule 1.

**Verified untouched:** `samples.json` still holds 13 samples and 45 labelled PII values; `recognizers.py`, `requirements.txt`, `allowlist.txt`, `Dockerfile` and `serving_template.yaml` are byte-identical to their previous state.

---

## Global Constraints

Every task's requirements implicitly include this section. Copied in force from `VSCODE-PROMPT-pii-scrubber-deploy.md` and `README-DEPLOY.html`.

1. **The runbook is the authorization.** Anything not in `README-DEPLOY.html` requires a stop + ask. No scope expansion.
2. **Never weaken detection to make a test pass.** If `/v1/selftest` drops below `recall_pct: 100.0`, that is a regression to report, not a number to tune toward. Do not lower thresholds, delete recognizers, relax assertions, or edit `samples.json`.
3. **No outbound network calls from the running container** at inference time.
4. **Synthetic data only.** Never place real customer PII in this repo, a test, a log, or a container.
5. **No git ops without explicit approval.** `push`, `push --force`, `reset --hard`, `branch -D`, `clean -f` need per-command sign-off. Local commits on a feature branch are fine.
6. **No BTP or AI Core mutation without approval.**
7. **No dependency changes without approval.** `requirements.txt` is pinned deliberately.
8. **No fabrication.** Verify every file, command output, and endpoint response referenced.
9. **No secrets in the repo.** Credentials come from env vars or the user at the moment of use.

**Ground-truth invariant:** `samples.json` — 13 samples, 45 labelled PII values (verified). Never modified.

**Baseline status — ESTABLISHED on this machine 2026-08-15 (Task 1, post-ORG-fix).** `recall_pct: 100.0`, `expected_pii: 45`, `redacted: 45`, `missed: 0`, `over_detections: 6`, `redacting_spans_emitted: 51`, `test_fixes.py` 17/17, `Allowlist loaded: 27 tokens`. Reference file: `/tmp/selftest-local.json`. Tasks 2, 3 and 6 diff against this. It required the `labels_to_ignore` fix in `get_analyzer()` (open finding 5) — the pre-fix pinned stack scored 97.8 / over_detections 4.

**Reporting cadence:** At each gate, the stated deliverable within the stated word limit, numbers verbatim from command output. On failure: the failing command, the actual error, one best hypothesis. Mid-task silence is fine. Blocked >20 minutes on one error → stop and report.

---

## Task List

| # | Task | Mutates | Gate | Budget |
|---|---|---|---|---|
| 0 | Environment remediation — git, Python 3.12, Docker daemon | local | 0 | 30 min |
| 1 | Local verification — re-baseline the changed `app.py` | local | 1 | 45 min |
| 2 | Allowlist build + image-packaging decision *(conditional)* | local | 2 | 60 min |
| 3 | Docker build + in-container verification | local | 3 | 90 min |
| 4 | Publish to GitHub + container registry | **remote** | 4 | 45 min |
| 5 | Point ServingTemplate at published image | local commit | 5 | 30 min |
| 6 | AI Core deployment + deployed self-test | **BTP** | 6 | 60 min |

Task 2 runs **only** if the TSTC/DDIC export is available. If it is not, Task 2 collapses to its Step 6 decision alone (does `allowlist.txt` ship in the image?) and the plan proceeds to Task 3.

**Out of scope (separate session):** the GLiNER bake-off — a second AI Core configuration with `engine = both`, compared against the `presidio` deployment (`README-DEPLOY.html` §7). Do not start it here.

---

## File Structure

| File | Responsibility | Touched by |
|---|---|---|
| `app.py` | Service, detection pipeline, allowlist + custom-object suppression, self-test | **read only** |
| `recognizers.py` | 8 SAP-specific Presidio recognizers | **read only** |
| `samples.json` | Ground truth — 13 samples / 45 PII values | **never modified** |
| `allowlist.txt` | Technical tokens never redacted, matched exact-case | Task 2 only |
| `ALLOWLIST-EXTRACTION.md` | Which SAP tables to extract and how to assemble them | reference |
| `mine_allowlist.py` | Dev tool — mines allowlist candidates from a corpus; replaces the DD03L extract. Not shipped in the image, correctly. | Task 2 Step 3b |
| `test_fixes.py` | Regression tests for the three fixed defect classes + recall invariant | Task 1 Step 3b |
| `FIXES-2026-08-15.md` | Reconciliation record: what was fixed at source and its plan impact | reference |
| `requirements.txt` | Pinned dependencies | **never modified** (Rule 7) |
| `Dockerfile` | CPU-only image, weights baked in | Task 2 Step 6 — one line, **if approved** |
| `workflows/serving_template.yaml` | AI Core ServingTemplate. **Moved from the repo root 2026-08-15** — AI Core's Application *Path in Repository* must be a real subdirectory (`workflows`); `.` syncs nothing, silently. See finding 14. | Task 5 — exactly one line |
| `.gitignore` | Keeps `.venv/`, `hfcache/`, `.DS_Store` out of the repo | Task 0 — created |
| `.python-version` | Pins the interpreter for `uv` | Task 0 — created |

No detection logic is modified anywhere in this plan.

---

## Task 0: Environment remediation

The spec's sanity check assumes a working environment. Three blockers, all verified:

- **Not a git repository.** Tasks 4–5 assume `git remote add`, `git commit`, `git diff`.
- **Python 3.14.3 is the only interpreter.** The spec says "Python 3.11+", which 3.14 satisfies literally, but `torch==2.5.1` and `spacy==3.8.3` publish no cp314 wheels. `pip install` will fail. Rule 7 forbids bumping the pins, so the interpreter changes.
- **Docker daemon.** Now confirmed running (server 29.2.1, 10 CPUs, 8.2 GB). Step 6 is a re-verify, not a fix.

`uv` (`/opt/homebrew/bin/uv`) can provision a managed 3.12 without touching the system Python.

**Files:** Create `.gitignore`, `.python-version`.

**Interfaces:**
- Produces: a git repo on branch `deploy/aicore-poc` with a baseline commit; a `python3.12` resolvable by `uv`; a verified Docker daemon. Tasks 1–6 consume these.

- [ ] **Step 1: Initialize the repository**

Local state only — no remote, no push. Authorized under Rule 5.

```bash
cd "/Users/terulinsinulingga/Downloads/NER POC"
git init
git checkout -b deploy/aicore-poc
```

Expected: `Initialized empty Git repository`, then `Switched to a new branch 'deploy/aicore-poc'`.

- [ ] **Step 2: Write `.gitignore`**

The rule "do not commit `.venv/`, `hfcache/`" is unenforceable without this file, so it is authorized by implication.

```gitignore
.venv/
hfcache/
__pycache__/
*.pyc
.DS_Store
.env
*.log
# mine_allowlist.py inputs and outputs — may contain real ticket text or
# unreviewed tokens mined from it. Rule 4: neither belongs in this repo.
corpus/
allowlist-candidates.txt
```


- [ ] **Step 3: Pin the interpreter**

```bash
echo "3.12" > .python-version
```

- [ ] **Step 4: Verify a 3.12 interpreter resolves**

```bash
uv python install 3.12
uv python find 3.12
```

Expected: a path ending in `.../python3.12`. If `uv python install` fails (proxy, no network), fall back to `brew install python@3.12` and report the substitution at the gate.

- [ ] **Step 5: Baseline commit**

```bash
git add -A
git status --short
git commit -m "chore: baseline PII scrubber POC source"
```

Expected: `git status --short` lists the source files plus `.gitignore`, `.python-version`, `ALLOWLIST-EXTRACTION.md` and `docs/`, and does **not** list `.venv/` or `hfcache/`. If it lists either, stop — `.gitignore` is not taking effect.

- [ ] **Step 6: Re-run the spec's sanity check**

```bash
pwd && git log --oneline -1 && ls
uv run --python 3.12 python --version
docker info --format 'server={{.ServerVersion}} cpus={{.NCPU}}'
```

Expected: repo root contains `app.py`, `recognizers.py`, `samples.json`, `allowlist.txt`, `Dockerfile`, `serving_template.yaml`, `requirements.txt`, `README.md`, `README-DEPLOY.html`, `ALLOWLIST-EXTRACTION.md`. Python `3.12.x`. Docker reports a server version.

- [ ] **Step 7: Check disk headroom**

The image will be several GB and the host volume was measured at 90% full / ~20 GB free.

```bash
df -h /System/Volumes/Data | tail -1
docker system df
```

Expected: at least 15 GB free before starting Task 3. If below that, report and stop — **do not** run `docker system prune`; an unrelated `frappe_docker` container and its images are present and pruning is the user's call.

> **Approval gate 0.** Report blocker resolution status, the interpreter version provisioned, the baseline commit SHA, and free disk. Under 120 words. Wait for sign-off. Do not chain tasks unattended.

---

## Task 1: Local verification — re-baseline the changed `app.py`

**Goal:** establish what the *current* code actually scores. The previously documented `over_detections: 6` predates the custom-object rule, so this task measures rather than confirms.

**Files:** Create `.venv/` (gitignored). Test: `GET /v1/selftest` on `localhost:8080`.

**Interfaces:**
- Consumes: `python3.12` and the git repo from Task 0.
- Produces: `/tmp/selftest-local.json` — the reference baseline. Tasks 2, 3 and 6 all diff against it.

- [ ] **Step 1: Create the virtualenv and install pinned dependencies**

```bash
cd "/Users/terulinsinulingga/Downloads/NER POC"
uv venv --python 3.12 --seed .venv
source .venv/bin/activate
python --version && which pip
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
```

Expected: `Python 3.12.x`, `pip` resolving to `.venv/bin/pip`, then a successful install of all 8 pinned packages. The `--extra-index-url` mirrors the Dockerfile and pulls CPU-only torch.

**`--seed` is required, not optional.** A bare `uv venv` creates the environment without pip, so `pip install` would either fail outright or silently hit the system pip outside the venv. Step 2's `python -m spacy download` breaks the same way — it shells out to pip internally. If `which pip` does not point inside `.venv/`, stop and recreate the venv rather than proceeding.

If install fails on `torch` or `spacy` with `no matching distribution`, the interpreter is wrong — re-check Task 0 Step 4. **Do not edit `requirements.txt`** (Rule 7).

- [ ] **Step 2: Download the spaCy model**

```bash
python -m spacy download en_core_web_sm
```

Expected: `✔ Download and installation successful`. A build-time download, not a runtime one — Rule 3 is not engaged.

- [ ] **Step 3: Start the service**

```bash
uvicorn app:app --port 8080 > /tmp/scrubber-local.log 2>&1 &
sleep 20
curl -s localhost:8080/health
```

Expected: `{"status":"ok","engine":"presidio"}`. `/health` does not load models, so a non-answer means the process died — check `/tmp/scrubber-local.log`.

- [ ] **Step 3b: Run the regression tests**

```bash
python test_fixes.py
```

Expected: `ALL TESTS PASS` (15 checks — Dockerfile ships the allowlist, inline comments stripped, context backstop on pure-alpha suppression, surname guard, recall invariant). Costs seconds and pins all three defect classes from the plan review. Any failure is a stop-and-report; these tests encode the fixes, so a failure means the drop did not apply cleanly.

- [ ] **Step 4: Run the self-test — the deliverable**

```bash
curl -s localhost:8080/v1/selftest | python -m json.tool > /tmp/selftest-local.json
python -c "import json;print(json.dumps(json.load(open('/tmp/selftest-local.json'))['overall'],indent=2))"
```

**Required — these are Rule 2 assertions:**

```
expected_pii : 45
redacted     : 45
missed       : 0
recall_pct   : 100.0
```

**Measured — record, do not assert:** `over_detections` and `redacting_spans_emitted`. The documented value was 6 under the previous code. The custom-object rule should reduce it. Whatever comes back is the new baseline.

**If `recall_pct` is below 100.0 — do NOT tune.** Report `misses[]` verbatim and stop. Two candidate causes worth naming in the report: a different spaCy/Presidio patch version, or the new custom-object rule suppressing a legitimate span. Both are findings. Lowering a threshold, removing a recognizer, or editing `samples.json` are Rule 2 violations.

- [ ] **Step 5: Confirm the two new suppression layers are live**

The custom-object rule has no startup log line, so probe it behaviourally.

```bash
curl -s -X POST localhost:8080/v1/scrub -H 'Content-Type: application/json' \
  -d '{"text":"Author Daniel O'"'"'Connor changed ZSD_REBATE_CALC and /SOVOSD/RFYTXDISPLAY. Reviewer Zhang approved."}' \
  | python -m json.tool
```

Expected: `Daniel O'Connor` redacted as `<PERSON>`; `ZSD_REBATE_CALC` and `/SOVOSD/RFYTXDISPLAY` left in cleartext; **`Zhang` still redacted** — the surname guard is the safety property here, and a `Zhang` that survives unredacted is a leak, not a tidier output.

- [ ] **Step 6: Confirm the boundary guard and allowlist load**

```bash
grep -E "Removed UrlRecognizer|PhoneRecognizer regions|Allowlist loaded|No allowlist file" /tmp/scrubber-local.log
```

Expected: `Removed UrlRecognizer (prevents outbound call)`, `PhoneRecognizer regions: ['NZ','AU','GB','DE','US','PL']`, and an allowlist line reporting the built-in seed (28 tokens) — `allowlist.txt` currently holds only comments. Absence of the `Removed UrlRecognizer` line is a Rule 3 finding: report and stop.

- [ ] **Step 7: Spot-check both scrub modes**

```bash
curl -s -X POST localhost:8080/v1/scrub -H 'Content-Type: application/json' \
  -d '{"text":"Customer 0001045567, contact Aroha Ngata aroha.ngata@x.co.nz","mode":"batch"}' | python -m json.tool
curl -s -X POST localhost:8080/v1/scrub -H 'Content-Type: application/json' \
  -d '{"text":"Customer 0001045567, contact Aroha Ngata aroha.ngata@x.co.nz","mode":"live"}' | python -m json.tool
```

Expected: `batch` yields `<CUSTOMER_NO>`, `<PERSON>`, `<EMAIL>` with an empty `token_map`; `live` yields `<CUSTOMER_NO_1>`, `<PERSON_1>`, `<EMAIL_1>` with a populated `token_map`.

- [ ] **Step 8: Stop the service, confirm nothing was modified**

```bash
pkill -f "uvicorn app:app" || true
git status --short
```

Expected: empty. Task 1 changes no tracked file.

**Rollback:** none needed. To reset: `rm -rf .venv`.

> **Approval gate 1.** Report the `overall` block verbatim, explicitly stating the new `over_detections` value against the documented 6, and the Step 5 probe result. Under 150 words. Wait for sign-off. Do not chain tasks unattended.

---

## Task 2: Allowlist build + image-packaging decision *(conditional)*

Runs in full only if the export is available. **Step 6 runs regardless** — the packaging decision must be made before the image is built.

This is the only detection-affecting change authorized in this plan. It runs **before** the Docker build so the result ships in the image rather than requiring a rebuild.

**Files:** Modify `allowlist.txt` (append only). Possibly modify `Dockerfile:36` (Step 6, needs approval).

**Interfaces:**
- Consumes: the Task 1 baseline and the running local service.
- Produces: a populated `allowlist.txt` and a settled answer to "does the allowlist ship in the image?". Task 3 builds on both.

- [ ] **Step 1: Confirm the export contains no PII**

Rule 4. Per `ALLOWLIST-EXTRACTION.md`, all Tier 1–3 tables are Customizing/DDIC metadata and contain no personal data — but verify the actual file before it enters the repo.

```bash
head -20 <EXPORT_PATH>
wc -l <EXPORT_PATH>
```

Every line must be a technical token. Stop and ask if any line looks like a person, email, or customer reference.

**If the user offers a `USR02` extract, decline it.** `ALLOWLIST-EXTRACTION.md` refuses it by design: user IDs are personal data, so the list would itself become a PII asset requiring the same access control, retention and deletion policy as the data being protected — a new compliance obligation created in order to improve a control. It needs a governance decision, not an engineering shortcut.

- [ ] **Step 2: Record the pre-change baseline**

```bash
python -c "import json;d=json.load(open('/tmp/selftest-local.json'))['overall'];print(d['recall_pct'], d['over_detections'])"
```

Expected: `100.0` and whatever Task 1 measured.

- [ ] **Step 3: Assemble the tokens per the extraction spec**

Three sources, per the revised `ALLOWLIST-EXTRACTION.md`:

| Source | Status | Note |
|---|---|---|
| `TSTC` / `TCODE` | user **has** the export | transaction codes |
| `DD02L` / `TABNAME` | user **has** the export | filter `AS4LOCAL='A'` and `TABCLASS='TRANSP'` |
| ~~`DD03L` / `FIELDNAME`~~ | **dropped** | ~200k distinct names, impractical — `mine_allowlist.py` replaces it |

Four assembly rules, all load-bearing:

1. **Preserve case exactly** — the match is case-sensitive. Uppercase `MARA` is allowlisted; the person `Mara` is still redacted. Do not upper- or lower-case the export.
2. **Drop tokens shorter than 3 characters** — `OR`, `TA`, `AG` are too collision-prone.
3. **Deduplicate** — the same token appears across several tables.
4. **Annotate with `#` comments** so each block's source table is traceable.

```bash
cd "/Users/terulinsinulingga/Downloads/NER POC"
cp allowlist.txt /tmp/allowlist.before

# one block per source; repeat per export, changing the label and path
printf '\n# TSTC / TCODE\n' >> allowlist.txt
tr -d '\r' < <TSTC_EXPORT> | awk 'NF && length($0) >= 3 && $0 !~ /^#/' | sort -u >> allowlist.txt

printf '\n# DD02L / TABNAME\n' >> allowlist.txt
tr -d '\r' < <DD02L_EXPORT> | awk 'NF && length($0) >= 3 && $0 !~ /^#/' | sort -u >> allowlist.txt

wc -l allowlist.txt
tail -5 allowlist.txt
```

`awk` filters on length ≥ 3 and drops blanks; `sort -u` deduplicates within the block. Case is never altered.

- [ ] **Step 3b: Mine the corpus for the tokens DD03L would have supplied** *(optional, needs a corpus)*

`mine_allowlist.py` runs the scrubber over ticket/spec text, collects every span it *would* redact that has technical shape, and ranks by frequency.

```bash
source .venv/bin/activate
python mine_allowlist.py ./corpus --out allowlist-candidates.txt --min-count 2
```

The corpus may contain **real ticket text** — the script runs locally inside the boundary and writes only tokens. But neither the corpus nor the candidates file may be committed (Rule 4); Task 0's `.gitignore` covers both. Verify with `git status --short` before committing anything in Step 7.

**Human review is mandatory, not advisory.** `ALLOWLIST-EXTRACTION.md` records that on a test corpus the miner proposed `VBAK`, `KUNNR`, `WERKS`, `EKKO`, `BSEG` — correct — alongside `BJOHNSON`, `KMUELLER`, `MTANAKA`, which are **real user IDs** and are three of the ground-truth USER_ID values in `samples.json`. The miner surfaces exactly the tokens that collide, by construction: it proposes what the scrubber *would have redacted*. A human deletes the personal entries before anything is merged.

**Merging the candidates file:** `_load_allowlist()` now strips inline comments (`line.split('#',1)[0]` — fixed at source, `test_fixes.py` Defect 2), so raw `TOKEN   # count=N` lines load as bare tokens. The `sed` strip below is therefore **optional** — kept because it also drops the counts, leaving `allowlist.txt` cleaner to review later:

```bash
printf '\n# mined from corpus (reviewed)\n' >> allowlist.txt
sed 's/#.*//' allowlist-candidates.txt | awk 'NF && length($1) >= 3 {print $1}' | sort -u >> allowlist.txt
```

Run the merge only **after** the review pass has deleted the personal entries. The loader fix makes the format safe; it does nothing about the content.

- [ ] **Step 4: Verify no ground-truth value got allowlisted**

A direct guard against the failure mode that matters: an allowlist entry that silently suppresses real PII.

```bash
python - <<'PY'
import json
gt = {p["value"] for s in json.load(open("samples.json"))["samples"] for p in s["pii"]}
allow = {l.strip() for l in open("allowlist.txt") if l.strip() and not l.startswith("#")}
clash = sorted(v for v in gt if v in allow)
print("CLASH:", clash) if clash else print("OK — no ground-truth value is allowlisted")
PY
```

Expected: `OK`. Any clash means the export contains a token identical to a labelled PII value — remove that token and report it; do not proceed.

- [ ] **Step 5: Restart and re-run the self-test**

The allowlist is read once at import (`app.py:166`), so a restart is required.

```bash
pkill -f "uvicorn app:app" || true
source .venv/bin/activate
uvicorn app:app --port 8080 > /tmp/scrubber-allowlist.log 2>&1 &
sleep 20
grep "Allowlist loaded" /tmp/scrubber-allowlist.log
curl -s localhost:8080/v1/selftest | python -m json.tool > /tmp/selftest-allowlist.json
python -c "import json;d=json.load(open('/tmp/selftest-allowlist.json'))['overall'];print(d['recall_pct'], d['over_detections'])"
```

Expected: `Allowlist loaded: <N> tokens` with N far above 28, then `100.0` and an over-detection count at or below the Task 1 baseline.

**Two mandatory conditions:**

- `recall_pct` is still exactly `100.0`. If it dropped, the allowlist is suppressing a real detection — revert immediately (`git checkout allowlist.txt` or restore `/tmp/allowlist.before`) and report which values appear in `misses[]`. A larger allowlist is never worth a leak (Rule 2).
- `over_detections` fell. If unchanged, the export lacked the tokens driving the noise — report the unchanged count rather than hand-adding entries to force it down.

- [ ] **Step 6: Verify the allowlist ships in the image — RUNS EVEN IF STEPS 1–5 ARE SKIPPED**

**RESOLVED as Option A at source** (`FIXES-2026-08-15.md`): the Dockerfile's `COPY` line now includes `allowlist.txt`, so deployed behaviour matches local. No approval-gated edit remains — the step collapses to verification:

```bash
grep -n "^COPY app.py" Dockerfile
```

Expected: `COPY app.py recognizers.py samples.json allowlist.txt ./`. If `allowlist.txt` is missing from that line, the drop did not apply — stop and report. (`test_fixes.py` Defect 1 checks the same thing.)

- [ ] **Step 7: Commit**

```bash
git add allowlist.txt Dockerfile
git commit -m "feat: populate technical allowlist from SAP DDIC export"
git log --oneline -1
```

Include `Dockerfile` only if Option A was approved.

**Rollback:**

```bash
git checkout allowlist.txt Dockerfile   # uncommitted
git revert HEAD --no-edit               # committed
```

Then restart and re-verify `recall_pct: 100.0`.

> **Approval gate 2.** Report tokens added, `recall_pct`, before/after `over_detections`, the Step 4 clash check, and the Step 6 decision with its rationale. Under 150 words. Wait for sign-off. Do not chain tasks unattended.

---

## Task 3: Docker build + in-container verification

**Goal:** an image whose self-test matches the local baseline, with no outbound network at inference time.

**Files:** Read `Dockerfile` (modified only if Task 2 Step 6 Option A was approved). Test: `localhost:8081`.

**Interfaces:**
- Consumes: the settled `allowlist.txt`/`Dockerfile` state from Task 2; the Task 1 baseline; a running Docker daemon.
- Produces: local image `pii-scrubber:1.0.0`. Task 4 tags and pushes exactly this image.

- [ ] **Step 1: Build the image**

Large by design — torch and model weights are baked in so nothing downloads at runtime (Rule 3). Expect 15–40 minutes on first build.

```bash
cd "/Users/terulinsinulingga/Downloads/NER POC"
time docker build -t pii-scrubber:1.0.0 . 2>&1 | tee /tmp/docker-build.log
```

Expected: `naming to docker.io/library/pii-scrubber:1.0.0 done`.

A failure at the **GLiNER prefetch** is **tolerated** — the Dockerfile's `|| echo "WARN: GLiNER prefetch skipped"` makes it non-fatal by design and the image runs Presidio-only. Report it and continue.

A failure at `pip install` is **not** tolerated. Report and stop; do not edit `requirements.txt` (Rule 7).

- [ ] **Step 2: Record the image size — a deliverable**

```bash
docker images pii-scrubber --format '{{.Repository}}:{{.Tag}}  {{.Size}}'
df -h /System/Volumes/Data | tail -1
```

Record both. Size determines whether the Task 4 push is feasible on the available uplink and disk.

- [ ] **Step 3: Run the container**

```bash
docker run -d --name pii-test -p 8081:8080 pii-scrubber:1.0.0
sleep 45
curl -s localhost:8081/health
```

Expected: `{"status":"ok","engine":"presidio"}`.

- [ ] **Step 4: Capture `/info` — a deliverable**

```bash
curl -s localhost:8081/info | python -m json.tool
```

Expected: `engine: "presidio"`, `gliner_model: null`, `spacy_model: "en_core_web_sm"`, `last_load_error: null`, and `redact_types` listing all 10: ADDRESS, CUSTOMER_NO, EMAIL, IBAN, IP_ADDRESS, ORG_NAME, PERSON, PHONE, USER_ID, VENDOR_NO. A non-null `last_load_error` means a model failed to load — report it verbatim.

- [ ] **Step 5: Confirm the allowlist loaded from file**

The Dockerfile ships `allowlist.txt` (resolved at source), so the seed fallback must never appear.

```bash
docker logs pii-test 2>&1 | grep -E "Allowlist loaded|No allowlist file"
```

Expected: `Allowlist loaded: <N> tokens`, N matching the local run. The line `No allowlist file at /app/allowlist.txt -- using built-in seed (27)` means the image was built from a stale Dockerfile — report and stop. (The seed literal holds **27** tokens, counted; `28` was a doc error repeated across several files and corrected 2026-08-15.)

- [ ] **Step 5b: Confirm `en_core_web_lg` is not in the image — a deliverable**

Two things at once: an image-bloat check (the model is 400 MB) and evidence that no
bare-default Presidio construction — which resolves to `en_core_web_lg` and
**downloads it over the network** — is reachable in the built image. See open
finding 4.

```bash
docker exec pii-test python -c "import spacy; print(spacy.util.get_installed_models())"
docker exec pii-test sh -c 'ls /app/../usr/lib/python3*/site-packages 2>/dev/null | grep -i en_core || true'
docker exec pii-test pip list 2>/dev/null | grep -i en_core
```

Expected: exactly `['en_core_web_sm']`, and `en_core_web_sm` as the only `en_core_*`
package. Any `en_core_web_lg` present is a **stop**: it means something in the image
constructed a default analyzer at build time, which is a Rule 3 finding (build-time
here, but the same code path would fire at inference time on a cache miss).

- [ ] **Step 6: Run the in-container self-test — the deliverable**

```bash
curl -s localhost:8081/v1/selftest | python -m json.tool > /tmp/selftest-container.json
python -c "import json;print(json.dumps(json.load(open('/tmp/selftest-container.json'))['overall'],indent=2))"
```

Expected: `recall_pct: 100.0`, `redacted: 45`, `missed: 0`.

- [ ] **Step 7: Diff container against the correct local reference**

```bash
python - <<'PY'
import json, os
ref = '/tmp/selftest-allowlist.json' if os.path.exists('/tmp/selftest-allowlist.json') else '/tmp/selftest-local.json'
a = json.load(open(ref))['overall']
b = json.load(open('/tmp/selftest-container.json'))['overall']
diff = {k: (a.get(k), b.get(k)) for k in set(a) | set(b) if a.get(k) != b.get(k)}
print("reference:", ref)
print("IDENTICAL" if not diff else json.dumps(diff, indent=2))
PY
```

Expected: `IDENTICAL` — the image ships the same `allowlist.txt` the local run used, so there is no legitimate source of drift. Any difference is a defect: in `recall_pct`/`redacted`/`missed` it is a detection regression; in `over_detections` alone it most likely means the image was built before the allowlist was finalised — rebuild rather than explain it away.

- [ ] **Step 8: Confirm no outbound network at inference time — a deliverable**

Sever the container's network and re-run detection. Success with no network proves nothing was phoning out.

```bash
docker logs pii-test 2>&1 | tail -30
docker network disconnect bridge pii-test
curl -s --max-time 30 localhost:8081/v1/scrub -H 'Content-Type: application/json' \
  -d '{"text":"contact Aroha Ngata aroha.ngata@x.co.nz at 172.16.4.8","mode":"batch"}' | python -m json.tool
docker network connect bridge pii-test
```

Expected: the scrub succeeds with the network down, redacting `<PERSON>`, `<EMAIL>`, `<IP_ADDRESS>`.

**This step is the empirical proof of Rule 3** — the only one in the plan that tests
the boundary rather than reasoning about it. Everything else (removing
`UrlRecognizer`, Step 5b's model check) is evidence that a known outbound path was
closed; this is the test that catches an *unknown* one. Treat it accordingly:

- A **hang or timeout is a hard stop** (`curl` exit **28**). Do not retry with a longer
  `--max-time`, do not reconnect the network and re-run to "confirm it works" — a scrub
  that needs the network is the exact failure this project exists to prevent. Report the
  hang, the container logs, and stop.
- A non-timeout error is **not** a boundary finding. See the caveat below.

⚠️ **Caveat measured 2026-08-15 — the host-side curl above is confounded.**
`docker network disconnect bridge` also tears down the **published port mapping**, so
`localhost:8081` becomes unreachable from the host for reasons unrelated to the
compliance boundary. Observed: `curl` exit **56** (recv failure), not 28. Exit 7 or 56
here means *the port mapping went away*, which proves nothing either way.

**Run the in-container form as the actual proof** — it is not confounded, because it
never crosses the host boundary:

```bash
docker network disconnect bridge pii-test
docker inspect -f 'networks: {{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' pii-test   # must print empty
docker exec pii-test curl -s --max-time 30 localhost:8080/v1/scrub \
  -H 'Content-Type: application/json' \
  -d '{"text":"contact Aroha Ngata aroha.ngata@x.co.nz at 172.16.4.8","mode":"batch"}'
docker network connect bridge pii-test
docker logs pii-test 2>&1 | grep -iE "publicsuffix|urlopen|Max retries|Temporary failure in name resolution"
```

Expected: the `inspect` prints an empty network list, the scrub returns
`contact <PERSON> <EMAIL> at <IP_ADDRESS>` with exit 0, and the log grep finds nothing.
That combination — no networks attached, detection still correct, no resolver errors —
is the proof. **Always reconnect the bridge**, including on failure.

- [ ] **Step 9: Tear down the test container**

```bash
docker rm -f pii-test
```

The image is retained — Task 4 needs it.

**Rollback (mid-task):**

```bash
docker rm -f pii-test
docker rmi pii-scrubber:1.0.0
```

**Budget escape:** at 90 minutes still debugging, run the rollback, post partial findings, stop.

> **Approval gate 3.** Report image size, `/info`, which allowlist loaded, the self-test `overall`, the diff result, the network-severed confirmation, and any build warnings. Under 200 words. Wait for sign-off. Do not chain tasks unattended.

---

## Task 4: Publish to GitHub + container registry

**This task mutates remote state.** The user has given standing authorization for this session, so per-command sign-off is waived — but Steps 1 and 2 still run first.

**Files:** none modified.

**Interfaces:**
- Consumes: the local image from Task 3; the git repo from Task 0.
- Produces: `<REGISTRY>/<NAMESPACE>/pii-scrubber:1.0.0`. Task 5 writes exactly this string into `serving_template.yaml`.

- [ ] **Step 1: Collect the inputs still outstanding**

Do not guess:

1. The GitHub repository URL — or confirmation to create one. (The URL supplied so far, `https://github.com/settings/personal-access-tokens`, is the token settings page, not a repo.)
2. The registry target: Docker Hub (needs separate Docker Hub credentials) **or** GitHub Container Registry `ghcr.io` (reuses the existing PAT, but the token needs `Packages: write`).
3. Private or public — private recommended for corporate SAP work.
4. Which branch AI Core's Git sync watches. This repo's branch is `deploy/aicore-poc`; the spec assumed `main`.

- [ ] **Step 2: Pre-push secret scan**

Rule 9. The session PAT must never enter a commit.

```bash
git grep -nEi "(ghp_|github_pat_|password|passwd|secret|token|client_id|client_secret|dockerconfigjson|BEGIN [A-Z ]*PRIVATE KEY)" -- . ':!docs/' ':!README-DEPLOY.html' ':!VSCODE-PROMPT-pii-scrubber-deploy.md'
```

Expected: no output, or only the `docker-registry-secret` **name** in `serving_template.yaml:39` (a Kubernetes secret name, not a value — safe). Any real credential is a stop-and-report.

- [ ] **Step 3: Add the remote and push**

Pass the PAT via environment at the moment of use so it never lands in `.git/config` or a log.

```bash
git remote add origin https://github.com/<OWNER>/<REPO>.git
GIT_ASKPASS=true git -c credential.helper='!f(){ echo "username=<OWNER>"; echo "password=$GH_PAT"; };f' \
  push -u origin deploy/aicore-poc
git remote -v          # confirm no credential is embedded in the URL
```

Expected: `branch 'deploy/aicore-poc' set up to track 'origin/deploy/aicore-poc'`, and `git remote -v` showing a clean URL with no token in it.

- [ ] **Step 4: Log in to the registry**

Never echo the token (Rule 9).

```bash
# ghcr.io
echo "$GH_PAT" | docker login ghcr.io -u <OWNER> --password-stdin
# or Docker Hub
echo "$DOCKERHUB_TOKEN" | docker login docker.io -u <DOCKERHUB_USER> --password-stdin
```

Expected: `Login Succeeded`. A 403 on `ghcr.io` most likely means the PAT lacks `Packages: write` — that reads like an auth failure but is a permissions failure.

- [ ] **Step 5: Tag and push the image**

```bash
docker tag pii-scrubber:1.0.0 <REGISTRY>/<NAMESPACE>/pii-scrubber:1.0.0
docker push <REGISTRY>/<NAMESPACE>/pii-scrubber:1.0.0
```

Expected: `1.0.0: digest: sha256:... size: ...`. A multi-GB push can exceed the 45-minute budget; if it does, report and let the user decide between waiting and building the slim Presidio-only variant (a `requirements.txt` change — separate approval under Rule 7).

- [ ] **Step 6: Verify the image is pullable — a deliverable**

```bash
docker rmi <REGISTRY>/<NAMESPACE>/pii-scrubber:1.0.0
docker pull <REGISTRY>/<NAMESPACE>/pii-scrubber:1.0.0
docker inspect --format '{{index .RepoDigests 0}}' <REGISTRY>/<NAMESPACE>/pii-scrubber:1.0.0
```

Expected: a successful pull and a `sha256:` digest. This proves AI Core can fetch it. Do not skip — a push that "succeeded" into a namespace AI Core cannot read is the most common failure at this stage.

**Note for Task 6:** if the image is in a **private** `ghcr.io` namespace, the AI Core `docker-registry-secret` must point at `https://ghcr.io` with the PAT as the password — not `https://index.docker.io` as the runbook's example shows. Flag this at the gate.

**Rollback (GitHub):** `git remote remove origin`, then delete the remote repo via the GitHub UI. Do not force-push to fix it.
**Rollback (registry):** delete the tag via the registry UI. No programmatic deletion.

> **Approval gate 4.** Report the repo URL, the fully-qualified image reference, the pulled digest, and the registry chosen. Under 100 words. Wait for sign-off. Do not chain tasks unattended.

---

## Task 5: Point ServingTemplate at published image

**Goal:** `serving_template.yaml` ready to sync, nothing deployed yet.

**Files:** Modify `serving_template.yaml:45` — the `image:` value, nothing else.

**Interfaces:**
- Consumes: the image reference from Task 4.
- Produces: a local commit. Task 6 pushes it, which is what triggers the AI Core Git sync.

- [ ] **Step 1: Make the one-line edit**

Change line 45 from:

```yaml
          image: "docker.io/YOUR_DOCKER_USER/pii-scrubber:1.0.0"
```

to the Task 4 reference, e.g.:

```yaml
          image: "ghcr.io/<OWNER>/pii-scrubber:1.0.0"
```

**Do not touch:** the labels `scenarios.ai.sap.com/id: "pii-scrubber"`, `executables.ai.sap.com/id: "pii-scrubber-serve"`, `ai.sap.com/version: "1.0.0"`; the `ai.sap.com/resourcePlan: starter` label; the `docker-registry-secret` name; the `engine`/`glinerThreshold` parameters; the resource requests/limits. These all match what AI Core expects, and a stray edit to a label silently breaks scenario discovery in a way that is painful to diagnose from the cockpit.

- [ ] **Step 2: Verify the diff is exactly one line — a deliverable**

```bash
git diff --stat serving_template.yaml
git diff serving_template.yaml
```

Expected: `1 file changed, 1 insertion(+), 1 deletion(-)` (or 2/2 if the placeholder comment was removed). More than that — revert and redo.

- [ ] **Step 3: Validate the YAML still parses**

```bash
source .venv/bin/activate
python -c "
import yaml
d=yaml.safe_load(open('serving_template.yaml'))
assert d['kind']=='ServingTemplate', d['kind']
assert d['metadata']['labels']['scenarios.ai.sap.com/id']=='pii-scrubber'
assert d['metadata']['labels']['executables.ai.sap.com/id']=='pii-scrubber-serve'
spec=yaml.safe_load(d['spec']['template']['spec'])
img=spec['predictor']['containers'][0]['image']
assert 'YOUR_DOCKER_USER' not in img, 'placeholder still present'
print('OK:', img)
"
```

Expected: `OK: <REGISTRY>/<NAMESPACE>/pii-scrubber:1.0.0`. If `pyyaml` is absent, install it into the venv only — a local validation tool, not a service dependency; `requirements.txt` stays untouched.

- [ ] **Step 4: Commit — do NOT push**

Pushing triggers the AI Core Git sync, which is a BTP mutation and belongs to Task 6.

```bash
git add serving_template.yaml
git commit -m "Point ServingTemplate at published image"
git log --oneline -1
```

**Rollback:** `git revert HEAD --no-edit`

> **Approval gate 5.** Show the one-line diff and the commit SHA. Under 80 words. Wait for sign-off. Do not chain tasks unattended.

---

## Task 6: AI Core deployment + deployed self-test

**Goal:** a RUNNING deployment returning `recall_pct: 100.0`.

**You do not have BTP credentials and must not ask for them.** The user performs every cockpit step. Your job is exact instructions, then verification.

**Files:** none modified.

**Interfaces:**
- Consumes: the Task 5 commit; the image reference from Task 4.
- Produces: a deployed `overall` block to compare against the Task 1/2 local baseline.

- [ ] **Step 1: Resolve the Git-sync question before anything else**

`README-DEPLOY.html` §3 says the template goes in "the repo already onboarded under *Git Repositories* — the same mechanism your `sd-analytics` scenario uses." If AI Core is syncing from a *different* repo than the one created in Task 4, the template must go **there**, and Task 5's commit is in the wrong place.

Ask the user to check *AI Launchpad → Administration → Git Repositories* and confirm which repo and branch are onboarded. Resolve this before pushing.

- [ ] **Step 2: Hand the user the cockpit runbook**

From `README-DEPLOY.html` §§2–6:

1. **Push the Task 5 commit** so AI Core syncs (~3 min).
2. **Create the Docker Registry Secret** if not present: *AI Core Administration → Docker Registry Secrets → Add*, named `docker-registry-secret` to match `serving_template.yaml:39`. Shape:
   ```json
   {".dockerconfigjson":"{\"auths\":{\"https://index.docker.io\":{\"username\":\"USER\",\"password\":\"TOKEN\"}}}"}
   ```
   **Substitute the registry host** — `https://ghcr.io` if Task 4 used GitHub Container Registry. The user enters this in the cockpit; never ask them to paste the token into a terminal or file (Rule 9).
3. **Confirm the scenario appears**: *ML Operations → Scenarios* → `pii-scrubber`, alongside `late-delivery` and `my-first-scenario`. If absent after ~5 minutes, the Git sync has not picked up the commit — re-check Step 1.
4. **Create a Configuration**: scenario `pii-scrubber`, executable `pii-scrubber-serve`, parameter `engine = presidio`. Leave `glinerThreshold` at `0.4`.
5. **Create a Deployment** from it. Wait for **RUNNING**.
6. **Provide `$DEPLOYMENT_URL` and a bearer token**, obtained by the user via:
   ```bash
   curl -X POST "$AICORE_AUTH_URL/oauth/token?grant_type=client_credentials" -u "$CLIENT_ID:$CLIENT_SECRET"
   ```

- [ ] **Step 3: Verify the deployment is reachable**

```bash
curl -s "$DEPLOYMENT_URL/health" \
  -H "Authorization: Bearer $TOKEN" -H "AI-Resource-Group: default"
```

Expected: `{"status":"ok","engine":"presidio"}`. 401/403 → expired token, ask for a fresh one. 404 → wrong URL or not yet RUNNING.

- [ ] **Step 4: Capture the deployed `/info`**

```bash
curl -s "$DEPLOYMENT_URL/info" \
  -H "Authorization: Bearer $TOKEN" -H "AI-Resource-Group: default" | python -m json.tool
```

Expected: `engine: "presidio"`. If it reports `both`, the configuration parameter did not take — stop and report before running the self-test, since `both` on the `starter` plan is the documented crash-loop cause.

- [ ] **Step 5: Run the deployed self-test — the deliverable**

```bash
curl -s "$DEPLOYMENT_URL/v1/selftest" \
  -H "Authorization: Bearer $TOKEN" -H "AI-Resource-Group: default" \
  | python -m json.tool > /tmp/selftest-deployed.json
python -c "import json;print(json.dumps(json.load(open('/tmp/selftest-deployed.json'))['overall'],indent=2))"
```

Expected: `recall_pct: 100.0`, `redacted: 45`, `missed: 0`.

- [ ] **Step 6: Diff deployed against the container baseline**

```bash
python - <<'PY'
import json
a = json.load(open('/tmp/selftest-container.json'))['overall']
c = json.load(open('/tmp/selftest-deployed.json'))['overall']
diff = {k: (a.get(k), c.get(k)) for k in set(a) | set(c) if a.get(k) != c.get(k)}
print("IDENTICAL" if not diff else json.dumps(diff, indent=2))
PY
```

Compare against the **container** result, not the local one — the container is what was deployed. Expected: `IDENTICAL`. Any delta is a deployment-environment finding. Report it; do not tune.

- [ ] **Step 7: If the deployment crash-loops**

Documented most-likely cause is memory on the free-tier `starter` plan. In order:

1. Confirm the configuration parameter is `engine = presidio`, not `both`.
2. Ask the user for the pod logs from AI Launchpad; report them verbatim.
3. Stop.

**Do not raise the resource plan** — cost implications, user's call (Rule 6).

**Rollback:** the user stops or deletes the deployment in AI Launchpad. Do not attempt to delete BTP resources yourself.

> **Approval gate 6.** Report the deployed `overall` block and any discrepancy from the container run. Under 150 words. **Stop.** The GLiNER bake-off is a separate session.

---

## Open findings — status after the 2026-08-15 fix drop

**1. Documentation staleness — CLOSED.** `README.md`'s configuration table now lists `CUSTOM_OBJECT_RULE` and the suppression backstop; `README-DEPLOY.html`'s over-detections section names the rule as the first of four reduction paths and marks the 6 as re-verified on current code.

**2. The all-caps USER_ID collision — DOWNGRADED, not closed.** `detect()` now refuses to suppress a pure-alpha token (`KLEIN`, `MARA`, `VBAK`) when user-context words ("posted by", "user", "author"…) appear within ±40 characters — an automated backstop where there was none, regression-tested in `test_fixes.py` 3a–3b. Unambiguous shapes (underscore/digit/namespace) still suppress unconditionally, which a surname-style user ID cannot take.

**The residual case:** a collision token appearing with *no* user-context word inside the window — e.g. a bare signature line — is still suppressed, so the mandatory human review of mined candidates remains the controlling mitigation, now as defence-in-depth rather than the only line. The two longer-term options stand: shape-based exclusion on `DD02L`/mined tokens, or real-shaped collision cases when the sample set is expanded to 50–100.

**3. `ES_SD_REBATE` — UNCHANGED.** No `Z`/`Y` prefix, so `CUSTOM_OBJ_RE` does not match it and the context backstop is irrelevant to it. If it appears among the remaining over-detections after Task 1, `TADIR` (Tier 2, currently optional) is the intended fix.

**4. Bare `AnalyzerEngine()` auto-downloads `en_core_web_lg` — OPEN, standing session rule.**
Found 2026-08-15 during Task 1 diagnosis, by causing it: a throwaway
`AnalyzerEngine()` with no `nlp_engine` argument resolved Presidio's default model and
pulled `en_core_web_lg` (400 MB) over the network. Uninstalled immediately; verified
`spacy.util.get_installed_models()` back to `['en_core_web_sm']`.

**The rule, binding for the rest of this project:** never construct a bare
`AnalyzerEngine()`. Any diagnostic must mirror `app.py`'s construction — an explicit
`NlpEngineProvider` pinned to `SPACY_MODEL` — either by importing `app.get_analyzer()`
or by repeating the provider block. This is not a tidiness preference: the default
path performs an **outbound network call to fetch a model**, which is precisely what
Rule 3 forbids inside the container.

Audited: the only `AnalyzerEngine(` in the repository is `app.py:209`, which passes an
explicit `nlp_engine`. No shipped code has this hazard — the exposure was the
diagnostic, not the product. Task 3 Step 5b verifies the built image stays that way.

**5. `ORG_NAME` had no working detection path for suffix-less organisations — FIXED 2026-08-15.**
Measured at Task 1: `recall_pct: 97.8`, one miss — `Pacific Traders` (`ORG_NAME`,
sample `TKT-0005`). Two-part cause, both verified against the pinned stack:

- `presidio-analyzer==2.2.357` ships a default `NerModelConfiguration.labels_to_ignore`
  containing **`ORG` and `ORGANIZATION`**. spaCy *does* tag `Pacific Traders` as `ORG`,
  but the NLP engine discards the label before it reaches `app.py`'s
  `ORG`/`ORGANIZATION` → `ORG_NAME` map, which is therefore dead code on the spaCy path.
- The only surviving `ORG` source is `recognizers.py:102`
  (`company_suffix_recognizer`), which requires a legal suffix (GmbH/Ltd/Pty/…).
  `Pacific Traders` has none.

So the value was **undetectable in that configuration** — not a threshold that could be
lowered, and not a regression introduced by the 2026-08-15 fix drop.

**The fix** (`FIX-GATE1-ORG.md`, applied to `get_analyzer()` only): rebuild
`labels_to_ignore` from the installed default minus `ORG`/`ORGANIZATION`. It reads
installed values rather than hardcoding, so it is correct on 2.2.357 and a no-op on
2.2.364. **This raises recall by restoring a detection path the library was
suppressing — the inverse of stop-condition 3**, which exists to prevent *weakening*
detection to make a test pass. Audited by diff: no threshold, recogniser,
`REDACT_TYPES`, `CUSTOM_OBJECT_RULE`, `ZY_SURNAME_GUARD` or `samples.json` touched.

Re-verified here on the pinned stack: `recall_pct 100.0` · `45/45` · `missed 0` ·
`over_detections 6` · `redacting_spans_emitted 51` · `test_fixes.py` **17/17**. New log
line `ORG un-ignored at NLP layer (11 labels still ignored)`. Pinned against regression
by `test_fixes.py` Defect 4.

⚠️ **Correction to the fix note.** It claims `ORGANIZATION` is absent from
`SpacyRecognizer.supported_entities` on 2.2.357 and re-registers the recogniser to add
it. On this install `SpacyRecognizer.ENTITIES` already contains `ORGANIZATION` and the
service logs `SpacyRecognizer already supports ORGANIZATION` — that half is a **no-op**.
Harmless, but the load-bearing change is the `labels_to_ignore` rebuild alone.

**Provenance, now resolved.** `over_detections` came back **4** pre-fix, not the 6 the
fix drop recorded. Both numbers moving together identified the cause: the documented
`100.0 / 6` were measured on `presidio-analyzer 2.2.364`, installed unpinned rather
than from `requirements.txt`. Post-fix both reproduce exactly on the pinned stack.
**Standing lesson:** any number that will be quoted must come from a
`requirements.txt` install, never an unpinned one.

---

## What NOT to do

- Do not redesign the engine, swap models, or "improve" the recognizers. You are executing, not designing.
- Do not edit `samples.json` for any reason. It is ground truth; changing it invalidates every recall number in the project.
- Do not tune thresholds, remove recognizers, or relax `REDACT_TYPES` to make output look cleaner. Over-detection is safe; under-detection is a leak.
- Do not disable `CUSTOM_OBJECT_RULE` or trim `ZY_SURNAME_GUARD` to change a number. The guard is a leak prevention, not a tuning knob.
- Do not accept a `USR02` extract into the allowlist. It is refused by design in `ALLOWLIST-EXTRACTION.md`.
- Do not add Piiranha or any CC-BY-NC / non-commercial model. Apache/MIT only.
- Do not chain tasks without the approval gate output.
- Do not create BTP resources, raise resource plans, or enable Kyma.
- Do not run `docker system prune` — unrelated containers are present on this machine.
- **Do not construct a bare `AnalyzerEngine()`** in a diagnostic, a test, or a scratch script. Presidio's default resolves to `en_core_web_lg` and downloads it — an outbound call, forbidden by Rule 3. Mirror `app.py`: explicit `NlpEngineProvider` pinned to `SPACY_MODEL`, or import `app.get_analyzer()`. See open finding 4.
- Do not commit `.venv/`, `hfcache/`, image layer artifacts, or the session PAT.
- Do not put real ticket text, real customer names, or real vendor numbers anywhere in this repo.

---

## Standing caveat on the 100% figure

Carry this into any report that quotes the number. From `README-DEPLOY.html`:

> It is 13 synthetic samples that I wrote — a sanity check, not proof. The sample set is small, and the recognizers were tuned against it, so some over-fitting is likely. Expect lower recall on real ticket text. **Do not present 100% to management as the expected production figure.**

What this plan verifies is a **regression baseline** — that packaging and deployment did not degrade detection. It is not a production accuracy claim. Expanding to 50–100 real-shaped synthetic samples is the work that produces a quotable number, and it is out of scope here.
