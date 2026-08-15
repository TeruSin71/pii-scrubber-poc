# PII Scrubber — Execution Task List

> Companion to `2026-08-15-pii-scrubber-aicore-deployment.md`. That document is the **authority** — full commands, expected outputs, and rollbacks live there. This is the run sheet: what to do next, what it depends on, and when to stop.
>
> **Execution skill:** `superpowers:executing-plans` (this session). If subagents were permitted, `superpowers:subagent-driven-development` would be the better fit — a fresh agent per task with review between. They are not, so this runs inline with a hard stop at every gate.

**Status legend:** ☐ not started · ▶ in progress · ✅ done · ⛔ blocked · ⏭ skipped (conditional)

---

## Pre-flight — verified 2026-08-15

| Check | Result |
|---|---|
| Repo files present (13) | ✅ incl. `ALLOWLIST-EXTRACTION.md` and `mine_allowlist.py` |
| `samples.json` ground truth | ✅ 13 samples / 45 PII values |
| Docker daemon | ✅ running, server 29.2.1, 10 CPUs, 8.2 GB |
| Disk free | ⚠️ ~20 GB (90% full) — gate at Task 0 Step 7 |
| Git repository | ⛔ absent → Task 0 |
| Python interpreter | ⛔ 3.14.3 only; pins need 3.12 → Task 0 |

---

## Blocked on the user — nothing else waits on these

These gate Tasks 4–6 only. **Tasks 0 through 3 can run start to finish without any of them.**

| # | Needed for | Question |
|---|---|---|
| U1 | Task 4 | GitHub repo URL, or "create it". The URL supplied so far is the PAT settings page, not a repo. |
| U2 | Task 4 | Registry: Docker Hub (needs separate Docker Hub credentials) or `ghcr.io` (reuses the PAT, but it needs **Packages: write**). |
| U3 | Task 4 | Private or public. Private recommended. |
| U4 | Tasks 4, 6 | Which repo/branch AI Core's Git sync already watches (*AI Launchpad → Administration → Git Repositories*). If it isn't the new repo, Task 5's commit lands in the wrong place. |
| U5 | Task 6 | BTP cockpit work + `$DEPLOYMENT_URL` and bearer token. User drives; agent never holds BTP credentials. |
| ~~U6~~ | Task 2 | ~~TSTC/DDIC export~~ — **answered 2026-08-15**: `TSTC` and `DD02L` marked "Have it". `DD03L` dropped as impractical; `mine_allowlist.py` replaces it. Hand over the two export files at Task 2. |
| U7 | Task 2 Step 3b | Is there a corpus of ticket/spec text to mine, and who does the mandatory review pass? The miner proposes real user IDs by construction — review is the only control. |

---

## Task 0 — Environment remediation · ✅ · ~30 min · local only

Fixes the two hard blockers. Nothing here touches a remote.

- [ ] 0.1 `git init` + branch `deploy/aicore-poc`
- [ ] 0.2 Write `.gitignore` (`.venv/`, `hfcache/`, `__pycache__/`, `.DS_Store`, `.env`, `*.log`)
- [ ] 0.3 `echo "3.12" > .python-version`
- [ ] 0.4 `uv python install 3.12` → verify `uv python find 3.12` resolves
- [ ] 0.5 Baseline commit — confirm `.venv/`/`hfcache/` absent from `git status --short`
- [ ] 0.6 Re-run the spec's sanity check (`pwd`, `git log`, `ls`, python, docker)
- [ ] 0.7 Disk gate: **≥15 GB free** or stop. Never `docker system prune` — unrelated `frappe_docker` present.

**🚦 Gate 0** — blockers resolved, interpreter version, commit SHA, free disk. ≤120 words. **Stop.**

---

## Task 1 — Local verification · ✅ · ~45 min · local only

> **Stopped 2026-08-15 at `recall_pct 97.8`, then cleared the same day.** The stop was
> correct: the miss (`Pacific Traders` / `ORG_NAME` / `TKT-0005`) was real and the
> documented baseline was measured on `presidio-analyzer 2.2.364`, not the pinned
> `2.2.357`. Fixed at source in `get_analyzer()` (`FIX-GATE1-ORG.md`) — see finding 5.
> **Re-verified on the pinned stack:** `recall_pct 100.0` · `45/45` · `missed 0` ·
> `over_detections 6` · `test_fixes.py` **17/17**. No threshold, recognizer,
> `REDACT_TYPES`, `samples.json` or guard-list was touched — diff confirmed.

Re-baselines the changed `app.py`. This is a **measurement**, not a confirmation.

- [ ] 1.1 `uv venv --python 3.12 --seed .venv` → install pinned deps (CPU torch index)
      ⚠️ `--seed` is mandatory; without it there is no pip in the venv and 1.2 breaks too
- [ ] 1.2 `python -m spacy download en_core_web_sm`
- [ ] 1.3 Start service on :8080, confirm `/health`
- [ ] 1.3b `python test_fixes.py` → expect `ALL TESTS PASS` (15 checks pinning the three fixed defect classes + recall invariant)
- [ ] 1.4 **`/v1/selftest` → `/tmp/selftest-local.json`** ← the reference baseline
- [ ] 1.5 Probe both new suppression layers (Z-objects suppressed, `Zhang` still redacted)
- [ ] 1.6 Confirm `Removed UrlRecognizer` + phone regions + allowlist load in the log
- [ ] 1.7 Spot-check `batch` and `live` scrub modes
- [ ] 1.8 Stop service; `git status --short` must be empty

**Assert (Rule 2):** `recall_pct 100.0` · `expected_pii 45` · `redacted 45` · `missed 0` — ✅ **met 2026-08-15 on the pinned stack, post-ORG-fix.**
**Confirm:** `over_detections 6` — ✅ **confirmed 6 on this machine.** `redacting_spans_emitted 51`. Note the pre-fix run measured 4; the two missing detections were ORG-labelled false positives, restored by the same fix. Also confirmed: `test_fixes.py` **17/17**, `Allowlist loaded: 27 tokens` (correct — the seed literal holds 27; `28` was a doc error, corrected across `Dockerfile`, `FIXES-2026-08-15.md` and this plan).

**If recall < 100.0:** report `misses[]` verbatim and **stop**. Do not tune. Name one hypothesis: patch-version drift, or the new rule suppressing a legitimate span.

**🚦 Gate 1** — `overall` verbatim, new `over_detections` vs the documented 6, probe result. ≤150 words. **Stop.**

---

## Task 2 — Allowlist + packaging decision · ☐ · ~60 min · local only · **conditional**

Runs before the build so the result ships in the image. **Step 6 runs regardless of everything else.**

Sources: `TSTC` ✅ have it · `DD02L` ✅ have it · ~~`DD03L`~~ dropped → `mine_allowlist.py`

- [ ] 2.1 Confirm exports contain no PII. **Decline `USR02`** — refused by design in the extraction spec.
- [ ] 2.2 Record pre-change baseline from Task 1
- [ ] 2.3 Assemble TSTC + DD02L blocks: preserve case exactly · drop <3 chars · dedupe · `#` block comments
- [ ] 2.3b *(optional, needs U7)* Mine corpus → **human review deletes personal entries** → merge (the `sed 's/#.*//'` strip is now optional — the loader strips inline comments at source — but still recommended for a cleaner file)
- [ ] 2.4 Clash check — no ground-truth value may appear in `allowlist.txt`
- [ ] 2.5 Restart, re-run self-test: `recall_pct` still **100.0** *and* `over_detections` fell
- [ ] 2.6 **Verify the `COPY` line ships `allowlist.txt` — runs even if 2.1–2.5 are skipped**
- [ ] 2.7 Commit — verify corpus and candidates file are **not** staged

⚠️ **2.3b's remaining trap is content, not format.** The miner proposes real user IDs by design (`BJOHNSON`, `KMUELLER`, `MTANAKA` on the test corpus) — human review is mandatory. The format trap (inline comments surviving as inert tokens) was fixed at source; `test_fixes.py` Defect 2 pins it.

### 2.6 — RESOLVED at source as Option A

The Dockerfile now reads `COPY app.py recognizers.py samples.json allowlist.txt ./` (`FIXES-2026-08-15.md`). Deployed behaviour matches local; no approval-gated edit remains. The step is now a one-line verification: `grep -n "^COPY app.py" Dockerfile` must show `allowlist.txt`. If it doesn't, the drop didn't apply — stop.

**🚦 Gate 2** — tokens added, recall, before/after over-detections, clash check, decision + rationale. ≤150 words. **Stop.**

---

## Task 3 — Docker build + in-container verification · ☐ · ~90 min · local only

- [ ] 3.1 `docker build -t pii-scrubber:1.0.0 .` (15–40 min; GLiNER prefetch failure is **tolerated**, pip failure is **not**)
- [ ] 3.2 Record image size + remaining disk
- [ ] 3.3 Run container on :8081, confirm `/health`
- [ ] 3.4 Capture `/info` — expect `engine presidio`, `last_load_error null`, 10 redact types
- [ ] 3.5 **Confirm `Allowlist loaded: <N> tokens`** — the seed-fallback line means a stale image; stop
- [ ] 3.5b **Confirm `en_core_web_lg` absent from the image** — `docker exec pii-test python -c "import spacy; print(spacy.util.get_installed_models())"` must return exactly `['en_core_web_sm']`. Dual purpose: 400 MB bloat check, and evidence no bare-default Presidio path (which downloads `lg`) is baked in. Present = stop. See finding 4.
- [ ] 3.6 In-container `/v1/selftest` → `/tmp/selftest-container.json`
- [ ] 3.7 Diff vs the correct local reference (allowlist run if it exists, else Task 1)
- [ ] 3.8 **Network-severed scrub** — disconnect bridge, scrub must still succeed. **This is the empirical proof of Rule 3.** A hang or timeout is a **hard stop** — no longer `--max-time`, no reconnect-and-retry to show it works. Report the hang plus container logs and stop.
- [ ] 3.9 `docker rm -f pii-test` (keep the image)

Expected diff: `IDENTICAL` — the image ships the same allowlist the local run used. Any delta is a defect; an `over_detections`-only delta most likely means the image predates the final allowlist (rebuild).

**Budget escape:** 90 min still debugging → rollback, post partial findings, stop.

**🚦 Gate 3** — size, `/info`, allowlist loaded, `overall`, diff, network proof, warnings. ≤200 words. **Stop.**

---

## Task 4 — Publish · ☐ · ~45 min · ⚠️ **mutates remote** · needs U1–U4

Standing authorization granted for this session; per-command sign-off waived. Steps 1–2 still run first.

- [ ] 4.1 Collect U1–U4
- [ ] 4.2 **Secret scan** — `ghp_`, `github_pat_`, password/token/secret patterns. The session PAT must never enter a commit.
- [ ] 4.3 `git remote add` + push `deploy/aicore-poc`; PAT via env at point of use; verify `git remote -v` has no embedded token
- [ ] 4.4 Registry login via `--password-stdin` (never echo). A `ghcr.io` 403 usually means missing **Packages: write**, not bad auth.
- [ ] 4.5 Tag + push image
- [ ] 4.6 **Pull it back and confirm the digest** — proves AI Core can fetch it

⚠️ If the image lands in a **private `ghcr.io`** namespace, the Task 6 `docker-registry-secret` must target `https://ghcr.io`, not `https://index.docker.io` as the runbook example shows.

**🚦 Gate 4** — repo URL, image reference, digest, registry chosen. ≤100 words. **Stop.**

---

## Task 5 — Point ServingTemplate at the image · ☐ · ~30 min · local commit

- [ ] 5.1 Edit `serving_template.yaml:45` — the `image:` value only
- [ ] 5.2 `git diff --stat` must show **exactly one line changed**
- [ ] 5.3 YAML parse + assert labels intact and placeholder gone
- [ ] 5.4 Commit — **do not push** (push is a BTP mutation, belongs to Task 6)

Do not touch: scenario/executable/version labels · `resourcePlan: starter` · `docker-registry-secret` name · parameters · resource limits.

**🚦 Gate 5** — one-line diff + commit SHA. ≤80 words. **Stop.**

---

## Task 6 — AI Core deployment · ☐ · ~60 min · ⚠️ **BTP** · user drives · needs U4, U5

- [ ] 6.1 **Resolve the Git-sync question first (U4)** — if AI Core watches a different repo, Task 5's commit is misplaced
- [ ] 6.2 Hand the user the cockpit runbook (push → registry secret → scenario → configuration → deployment → URL + token)
- [ ] 6.3 Verify `/health` reachable
- [ ] 6.4 Capture `/info` — if it reports `both`, **stop before the self-test** (documented crash-loop cause on `starter`)
- [ ] 6.5 Deployed `/v1/selftest` → `/tmp/selftest-deployed.json`
- [ ] 6.6 Diff vs **container** baseline, not local
- [ ] 6.7 If crash-looping: confirm `engine=presidio` → request pod logs → stop. **Never raise the resource plan.**

**🚦 Gate 6** — deployed `overall` + any discrepancy. ≤150 words. **Stop. GLiNER bake-off is a separate session.**

---

## Stop conditions — non-negotiable

Stop and report rather than working around any of these:

1. `recall_pct` < 100.0 anywhere. It is a regression to report, never a number to tune toward.
2. Any outbound network attempt at inference time.
3. A build/push/deploy failure whose fix would touch `requirements.txt`, `samples.json`, thresholds, recognizers, `CUSTOM_OBJECT_RULE`, or `ZY_SURNAME_GUARD`.
4. Blocked >20 minutes on a single error.
5. A task's stated time budget exhausted.
6. Any step whose fix is not covered by `README-DEPLOY.html` (Rule 1 — stop + ask).

---

## Open findings — status after the 2026-08-15 fix drop

1. **Docs stale vs code** — ✅ **CLOSED.** README config table + README-DEPLOY updated at source.
2. **All-caps USER_ID collision** — ⬇️ **DOWNGRADED.** `detect()` now refuses pure-alpha suppression within ±40 chars of user-context words ("posted by", "user", "author"…); `test_fixes.py` 3a–3b pin it. Residual: a collision token with *no* context word in the window still suppresses — the mandatory review of mined candidates remains the controlling mitigation.
3. **`ES_SD_REBATE` uncovered** — unchanged. No Z/Y prefix; `TADIR` (Tier 2, optional) is the intended fix if it survives in the over-detections.
4. **Bare `AnalyzerEngine()` downloads `en_core_web_lg`** — ⚠️ **OPEN, standing session rule.** Presidio's default model resolution fetches `lg` (400 MB) over the network. Found by causing it during Task 1 diagnosis; uninstalled, `['en_core_web_sm']` confirmed restored. **Never construct a bare `AnalyzerEngine()`** — mirror `app.py` (explicit `NlpEngineProvider` on `SPACY_MODEL`) or import `app.get_analyzer()`. Rule 3 hazard, not a style point. Repo audited: only `app.py:209`, which passes `nlp_engine` explicitly. Task 3.5b verifies the image.
5. **`ORG_NAME` undetectable for suffix-less organisations** — ✅ **FIXED 2026-08-15** (`FIX-GATE1-ORG.md`). `presidio-analyzer==2.2.357` default `labels_to_ignore` contains `ORG`/`ORGANIZATION`, so spaCy's ORG label was dropped at the **NLP-engine layer, before any recognizer ran**; the only other path, `recognizers.py:102`, needs a legal suffix (GmbH/Ltd/…), which `Pacific Traders` lacks. `get_analyzer()` now rebuilds the ignore list from the installed default minus `ORG`/`ORGANIZATION` — reading installed values, so it is a no-op on 2.2.364. **This raises recall by restoring a suppressed detection path; it is the inverse of stop-condition 3, which forbids weakening detection.** Verified here: `100.0` / `45/45` / `over_detections 6`, log line `ORG un-ignored at NLP layer (11 labels still ignored)`. Pinned against regression by `test_fixes.py` Defect 4.

   ⚠️ **One claim in the fix note does not hold on this install.** It states `ORGANIZATION` is absent from `SpacyRecognizer.supported_entities` on 2.2.357 and adds it back. Measured here, `SpacyRecognizer.ENTITIES` already contains `ORGANIZATION`, and the service logs `SpacyRecognizer already supports ORGANIZATION` — that half of the fix is a **no-op**. Harmless (the code reads installed values rather than hardcoding), but the working fix is the `labels_to_ignore` rebuild alone. Do not cite the SpacyRecognizer half as load-bearing.

6. **Root-cause provenance of the documented baseline** — ✅ **RESOLVED.** The `100.0` / `over_detections 6` figures were measured on `presidio-analyzer 2.2.364` (installed unpinned), not the pinned `2.2.357`. Both numbers now reproduce on the pinned stack post-fix, which independently confirms the diagnosis. Lesson worth keeping: install from `requirements.txt`, never unpinned, when producing a number anyone will quote.

---

## Session log

| Date | Task | Gate | Result |
|---|---|---|---|
| 2026-08-15 | Pre-flight | — | Repo read, plan written, `app.py` + `ALLOWLIST-EXTRACTION.md` updated, plan rewritten and resequenced |
| 2026-08-15 | Pre-flight | — | `mine_allowlist.py` added; DD03L dropped; U6 answered (TSTC + DD02L in hand); candidates-merge defect found and mitigated in Task 2.3b |
| 2026-08-15 | Pre-flight | — | Fix drop applied (`FIXES-2026-08-15.md` + `test_fixes.py`): all 3 findings fixed at source. Task 2.6 resolved as Option A; finding 1 closed, 2 downgraded; Task 1 gains `test_fixes.py` step. Statically verified here; runtime 15/15 pending Task 1 |
| 2026-08-15 | Task 0 | 0 ✅ | Repo initialised on `deploy/aicore-poc`, baseline commit `0c15601`. `.gitignore` + `.python-version` created. uv provisioned CPython 3.12.13. Docker re-verified 29.2.1 / 10 CPU / 8.2 GB. Disk 18 GB free — above the 15 GB gate, thin. Approved |
| 2026-08-15 | Task 1 | 1 ✅ | **Cleared after the ORG fix.** `recall_pct 100.0` · `45/45` · `missed 0` · `over_detections 6` · `redacting_spans_emitted 51` · `test_fixes.py` **17/17** · `Allowlist loaded: 27 tokens`. Log confirms `ORG un-ignored at NLP layer (11 labels still ignored)` and `Removed UrlRecognizer`. `Pacific Traders` redacts end-to-end as `<ORG_NAME>`. Diff audited: only `get_analyzer()` changed; `samples.json`/`requirements.txt`/`recognizers.py`/`allowlist.txt` byte-identical. Seed-count doc error `28→27` corrected in 3 files. Noted: the fix's `SpacyRecognizer` half is a no-op on 2.2.357 |
| 2026-08-15 | Task 1 | 1 ⛔ | **Stopped — recall regression.** Deps + `en_core_web_sm` 3.8.0 installed clean on 3.12.13. `recall_pct 97.8`, `redacted 44/45`, `missed 1` = `Pacific Traders` (`ORG_NAME`, `TKT-0005`). `over_detections 4`, not the documented 6. `test_fixes.py` FAILED 3/15. Steps 5–7 pass (surname guard holds, `UrlRecognizer` removed, batch/live correct). `Allowlist loaded: 27 tokens` — docs say 28. Root causes → findings 5 and (self-inflicted, reverted) 4. **Nothing tuned; tree clean.** Re-verified after `lg` removal: numbers identical, `/info` reports `spacy_model: en_core_web_sm` |
