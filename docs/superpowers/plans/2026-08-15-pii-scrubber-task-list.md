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
| U2 | Task 4 | Registry: Docker Hub (needs separate Docker Hub credentials) or `ghcr.io` (reuses the PAT, but it needs **Packages: write**). **Answered `ghcr.io` 2026-08-15 — but see finding 12: the credential actually present on this machine lacks `write:packages`.** |
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

## Task 2 — Allowlist + packaging decision · ✅ · ~60 min · local only · **conditional**

> **Completed 2026-08-15.** Both Tier 1 exports verified against `CHECKSUMS.txt`, field 2
> extracted only, counts reproduced the source README exactly (147,048 / 111,388 /
> 257,584 union / 5 short). Final: **257,578 tokens** (5 under 3 chars + 1 non-ASCII
> dropped), `allowlist.txt` 3.0 MB, pure ASCII. Author cross-check re-run
> independently: 87 distinct IDs, **0 collisions**. `recall_pct` held at **100.0**;
> `over_detections` **unchanged at 6** — see finding 7 for why that is expected here.
> Step 3b (corpus miner) **skipped** — U7 unanswered, no corpus and no named reviewer.

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

## Task 3 — Docker build + in-container verification · ✅ · ~90 min · local only

> **Completed 2026-08-15.** Image `pii-scrubber:1.0.0`, **2.17 GB**. `/info` as expected
> (`presidio`, `en_core_web_sm`, `last_load_error null`, 10 redact types).
> `Allowlist loaded: 257583 tokens` — matches local exactly, not the seed fallback.
> Step 5b: `['en_core_web_sm']` only, `lg` absent. Self-test **IDENTICAL** to the
> Task 2 reference. Step 8 proof obtained (see finding 10 for the confound).
> First build attempt failed on a BuildKit lease error — finding 9.
> GLiNER prefetch failed as tolerated, **but see finding 11: it is not merely cosmetic.**

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

## Task 4 — Publish · ◐ · ~45 min · ⚠️ **mutates remote** · needs U1–U4

> **Half done 2026-08-15. Code published; image blocked on a token scope.**
>
> ✅ 4.1 U1/U2/U3 answered · 4.2 secret scan clean (working tree **and** full history)
> · 4.3 **`https://github.com/TeruSin71/pii-scrubber-poc`** created **private**,
> branch `deploy/aicore-poc` pushed, default branch set to it. Remote URL carries **no
> embedded credential**. Remote tree verified: **21 blobs, matching the 21 tracked
> locally**, none of `.venv/`, `hfcache/`, `corpus/`, candidates or `.env`.
>
> ⛔ 4.4–4.6 **blocked — finding 12.** `docker login ghcr.io` **succeeded** (credentials
> valid), but `docker push ghcr.io/terusin71/pii-scrubber:1.0.0` returned
> `permission_denied: The token provided does not match expected scopes.` Evidence, not
> inference. Unblock: user runs `gh auth refresh -s write:packages` (interactive browser
> flow — cannot be done from this session), then 4.4–4.6 resume unchanged.
>
> **U4 remains open and now gates Task 5, not Task 4.** The repo decision was made
> independently of it, so publishing code was unaffected. But Task 5's ServingTemplate
> commit must land in whatever repo AI Core's Git sync actually watches — a newly
> created repo cannot be watched until it is onboarded.

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
3. **`ES_SD_REBATE` uncovered** — ✅ **MOOT, closed at Task 2.** The over-detections were enumerated on current code and `ES_SD_REBATE` is **not among them** — it is not over-detected at all, so the concern never materialised. `TADIR` (Tier 2) would not help and is not needed. The actual 6 are listed in finding 7.

7. **The Tier 1 allowlist cannot reduce `over_detections` on this sample set** — ℹ️ **EXPECTED, not a defect.** After loading 257,578 Tier 1 tokens, `over_detections` stayed at **6**. Enumerated, they are: `PO` ×2 (ADDRESS), `Invoice IDoc` (ORG_NAME), `Bill` (PERSON), `IBAN` (ORG_NAME), `Munich` (ADDRESS). **None is an SAP technical token**, so no transaction-code/table-name list can touch them:
   - `PO` is 2 characters — excluded by assembly rule 2 as too collision-prone, correctly.
   - `Invoice IDoc` is a two-word span; the allowlist matches single tokens and structurally cannot match it.
   - `Bill`, `Munich` are spaCy mislabelling ordinary English; `Bill` is genuinely ambiguous (`Bill Johnson` is real PII in TKT-0002), so redacting it is the safe error.
   - `IBAN` is not in `TSTC`/`DD02L` by nature.

   The allowlist is still load-bearing — it protects transaction codes and table names in *real* corpus text. These 13 synthetic samples simply contain no over-detected SAP token for it to fix. Per the plan, this is reported, **not** worked around by hand-adding entries. Revisit when the sample set expands to 50–100 real-shaped samples.

8. **Export tokens are Latin-1 and one is non-ASCII** — ⚠️ **OPEN, re-read before any re-extraction.** `MC1§` (byte `0xa7`) is the single non-ASCII token in the 257,584-token union. Dropped rather than transcoded: `_load_allowlist()` opens with the default codec and catches only `FileNotFoundError`, and the container sets no `LANG`, so a locale-dependent fallback to ASCII would crash the service at import — in the one environment that matters. A pure-ASCII allowlist loads identically under any locale; the cost is one transaction code.

   **The trap that nearly shipped:** BSD `grep -v '[^ -~]'` did **not** match the byte and the resulting "file is pure ASCII: 0" check reported clean while the token was still present. Verify encoding by byte inspection in Python (`b>127`), never by a `grep` character-class. Caught only because the Step 4 clash check then failed to decode the file.

9. **BuildKit `lease does not exist` on first build** — ✅ **RESOLVED, recurrence likely.** The first `docker build` spent 19 minutes and failed at `FROM python:3.11-slim` with `failed to resolve source metadata … lease does not exist: not found`. Not a disk or network fault: build cache was 8 kB and `docker pull python:3.11-slim` then succeeded immediately. It is a corrupted lease in the `desktop-linux` BuildKit builder's content store. **Fix that worked, and the one to try first:** `docker pull <base image>` to materialise it locally, then re-run the build unchanged. Do **not** reach for `docker system prune` — forbidden here, unrelated `frappe_docker` images are present.

10. **The Step 8 network-severed test is confounded from the host** — ⚠️ **AMENDED IN THE PLAN.** `docker network disconnect bridge` also removes the **published port mapping**, so a host-side `curl localhost:8081` fails regardless of the boundary. Measured: exit **56** (recv failure), not 28. Reading that as a Rule 3 breach would be wrong; reading it as "test passed" would be worse. The real proof is `docker exec` against `localhost:8080` **inside** the container, with `docker inspect` first confirming an empty network list. Both forms are now in the runbook, with the in-container one marked as the actual evidence. Result on this image: networks empty, scrub returned `contact <PERSON> <EMAIL> at <IP_ADDRESS>` exit 0, no resolver errors in the logs.

11. **GLiNER cannot load at all — `engine=both` is broken, not merely unbuilt** — ⛔ **OPEN, contradicts a settled decision.** The prefetch failure is tolerated by the Dockerfile, but the cause is not cosmetic:

    ```
    TypeError: GLiNER._from_pretrained() missing 2 required
    keyword-only arguments: 'proxies' and 'resume_download'
    ```

    `gliner==0.2.16` is incompatible with the `huggingface_hub` version pip resolves (unpinned in `requirements.txt`, transitively current). The failing call is `GLiNER.from_pretrained`, which is **exactly what `get_gliner()` calls at runtime** — so setting `SCRUBBER_ENGINE=both` would raise the same `TypeError` and take the deployment down, with no weights baked in either.

    **This invalidates the plan's standing claim that "switching to `both` is a configuration change, not a rebuild."** On this dependency set it is neither.

    **⛔ The shipped `pii-scrubber:1.0.0` image cannot run `engine=both`.** Setting the
    AI Core `engine` parameter to `both` against this image raises the `TypeError`
    above at first `get_gliner()` call and takes the deployment down. There are also no
    GLiNER weights baked in, because the prefetch that would have cached them is the
    step that failed. Deploy `engine=presidio` only, which is what the ServingTemplate
    already defaults to.

    **Fix path (deferred, do NOT attempt in this session):** pin `huggingface_hub` in
    `requirements.txt` to a version whose `hub_mixin.from_pretrained` matches
    `gliner==0.2.16`'s `_from_pretrained` signature, then rebuild the image. Pinning a
    dependency is **Rule 7 work and needs explicit approval**; the rebuild is a further
    ~20 minutes and a new image tag. Owner: the **GLiNER bake-off session**, which is
    already out of scope here (`README-DEPLOY.html` §7).

    ⚠️ **`README-DEPLOY.html` §7 is now inaccurate** — it states "Create a second
    configuration with `engine = both` … No rebuild needed." That is false on this
    dependency set. Not edited here: the runbook is the authorization document
    (Rule 1) and amending it is the bake-off session's call, not this one's. Flagged so
    nobody follows §7 straight into a crash-loop.

    Presidio-only, which is what Tasks 4–6 deploy, is entirely unaffected.

12. **The available GitHub credential lacks `write:packages`** — ⛔ **OPEN, blocks the `ghcr.io` push.** Checked before attempting anything remote, so this is a prediction rather than a post-mortem. `gh auth status` reports account **TeruSin71**, authenticated via keyring, token scopes **`gist`, `read:org`, `repo`** — no `write:packages`. Also on this machine: **no git remote** configured, **no** token-shaped environment variable present, and `~/.docker/config.json` has **no registry logins** (`credsStore: desktop`).

    U2 was answered "ghcr.io, PAT has Packages: write", but the credential actually reachable here does not have it. A `docker push ghcr.io/…` would 403 — which the runbook itself predicts is a scope problem, not an auth problem. Three ways out, all the user's call: re-run `gh auth refresh -s write:packages`, supply a separate classic PAT with `write:packages` via env at point of use, or switch to Docker Hub. Do not attempt the push until one is settled.
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
| 2026-08-15 | Task 3 | 3 ✅ | **Image built and verified.** `.dockerignore` added (context 864 MB → ~10 MB; `.venv` alone was 858 MB). First build failed after 19 min on a BuildKit lease error, fixed by `docker pull python:3.11-slim` then rebuilding unchanged (finding 9). Image **2.17 GB**, disk 16 GB free. `/info` as expected; `Allowlist loaded: 257583 tokens` matches local. Step 5b: `lg` absent. Self-test **IDENTICAL** to the Task 2 reference (`100.0`, `45/45`, `over_detections 6`). Step 8: networks empty, in-container scrub returned `contact <PERSON> <EMAIL> at <IP_ADDRESS>`, no resolver errors — Rule 3 proven; host-side form confounded (finding 10). GLiNER prefetch failed → **finding 11, `engine=both` is broken on this dependency set**. Build warnings all benign |
| 2026-08-15 | Task 2 | 2 ✅ | **Allowlist populated.** Checksums verified. Field 2 only; counts matched the export README exactly. **257,578 tokens** (TSTC 147,042 + DD02L 110,536 after removing 852 overlaps; dropped `BP CD CM FW V` as <3 chars and `MC1§` as non-ASCII). `allowlist.txt` 3.0 MB, pure ASCII, `Allowlist loaded: 257583 tokens` (file + 5 unique seed entries). Author cross-check re-verified: 87 IDs, 0 collisions. Clash check OK — `MARA`/`LIPS` allowlisted, `Mara` not, no ground-truth value allowlisted. `recall_pct 100.0` held; `over_detections` **6 → 6**, enumerated and explained in finding 7; finding 3 closed as moot. Step 3b skipped (U7). `COPY` line verified at `Dockerfile:40`. No corpus or candidates file staged |
| 2026-08-15 | Task 1 | 1 ✅ | **Cleared after the ORG fix.** `recall_pct 100.0` · `45/45` · `missed 0` · `over_detections 6` · `redacting_spans_emitted 51` · `test_fixes.py` **17/17** · `Allowlist loaded: 27 tokens`. Log confirms `ORG un-ignored at NLP layer (11 labels still ignored)` and `Removed UrlRecognizer`. `Pacific Traders` redacts end-to-end as `<ORG_NAME>`. Diff audited: only `get_analyzer()` changed; `samples.json`/`requirements.txt`/`recognizers.py`/`allowlist.txt` byte-identical. Seed-count doc error `28→27` corrected in 3 files. Noted: the fix's `SpacyRecognizer` half is a no-op on 2.2.357 |
| 2026-08-15 | Task 1 | 1 ⛔ | **Stopped — recall regression.** Deps + `en_core_web_sm` 3.8.0 installed clean on 3.12.13. `recall_pct 97.8`, `redacted 44/45`, `missed 1` = `Pacific Traders` (`ORG_NAME`, `TKT-0005`). `over_detections 4`, not the documented 6. `test_fixes.py` FAILED 3/15. Steps 5–7 pass (surname guard holds, `UrlRecognizer` removed, batch/live correct). `Allowlist loaded: 27 tokens` — docs say 28. Root causes → findings 5 and (self-inflicted, reverted) 4. **Nothing tuned; tree clean.** Re-verified after `lg` removal: numbers identical, `/info` reports `spacy_model: en_core_web_sm` |
