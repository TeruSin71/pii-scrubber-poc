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

## Task 0 — Environment remediation · ☐ · ~30 min · local only

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

## Task 1 — Local verification · ☐ · ~45 min · local only

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

**Assert (Rule 2):** `recall_pct 100.0` · `expected_pii 45` · `redacted 45` · `missed 0`
**Confirm:** `over_detections 6` — re-verified on current code by the fix drop's author (`FIXES-2026-08-15.md`); Task 1 confirms it on this machine.

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
- [ ] 3.6 In-container `/v1/selftest` → `/tmp/selftest-container.json`
- [ ] 3.7 Diff vs the correct local reference (allowlist run if it exists, else Task 1)
- [ ] 3.8 **Network-severed scrub** — disconnect bridge, scrub must still succeed
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

---

## Session log

| Date | Task | Gate | Result |
|---|---|---|---|
| 2026-08-15 | Pre-flight | — | Repo read, plan written, `app.py` + `ALLOWLIST-EXTRACTION.md` updated, plan rewritten and resequenced |
| 2026-08-15 | Pre-flight | — | `mine_allowlist.py` added; DD03L dropped; U6 answered (TSTC + DD02L in hand); candidates-merge defect found and mitigated in Task 2.3b |
| 2026-08-15 | Pre-flight | — | Fix drop applied (`FIXES-2026-08-15.md` + `test_fixes.py`): all 3 findings fixed at source. Task 2.6 resolved as Option A; finding 1 closed, 2 downgraded; Task 1 gains `test_fixes.py` step. Statically verified here; runtime 15/15 pending Task 1 |
| | | | |
