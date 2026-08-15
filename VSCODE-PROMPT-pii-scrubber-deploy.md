# VS Code Session Prompt — PII Scrubber: build, verify, deploy to SAP AI Core

Paste this whole file into the Claude agent in VS Code, with the
`pii-scrubber-poc` repo open as the workspace root.

---

## Goal

Take the already-tested PII Scrubber code in this repo from source to a
**RUNNING deployment on SAP AI Core (BTP Free Tier)** whose `/v1/selftest`
endpoint returns `recall_pct: 100.0` — without changing detection behaviour.

---

## Context the agent needs

Read these before doing anything, in this order:

1. `README.md` — what this service is, endpoints, configuration table.
2. `README-DEPLOY.html` — the deployment runbook. **This is the authorization.**
   Every step you take should map to a step in there.
3. `app.py` — the service. Note the three commented defect fixes; they are
   load-bearing, not stylistic.
4. `recognizers.py` — SAP-specific detectors.
5. `serving_template.yaml` — the AI Core ServingTemplate you will edit.
6. `samples.json` — 13 labelled synthetic samples. Ground truth for the self-test.

**Design status: SETTLED.** Engine choice (Presidio + custom SAP recognizers,
GLiNER optional behind `SCRUBBER_ENGINE=both`), licensing (Apache/MIT only),
and the AI Core BYOM deployment path were all decided in a prior session after
benchmark research. You are executing, not designing.

---

## Hard Rules

1. **The runbook is the authorization.** Anything not in `README-DEPLOY.html`
   requires a stop + ask. No scope expansion.
2. **Never weaken detection to make a test pass.** If `/v1/selftest` drops
   below `recall_pct: 100.0`, that is a **regression to report**, not a number
   to tune toward. Do not lower thresholds, delete recognizers, relax
   assertions, or edit `samples.json` to make output match. Recall *is* the
   product.
3. **No outbound network calls from the running container.** This service sits
   inside a compliance boundary. `UrlRecognizer` was removed for exactly this
   reason (it fetched publicsuffix.org at runtime). If you add a dependency or
   recognizer that phones out at inference time, stop and report.
4. **Synthetic data only.** Never place real customer PII in this repo, in a
   test, in a log, or in a container. Free tier has no SLA and is resettable.
5. **No git ops without explicit approval.** `push`, `push --force`,
   `reset --hard`, `branch -D`, `clean -f` all need per-command sign-off.
   Local commits on a feature branch are fine.
6. **No BTP or AI Core mutation without approval.** Creating configurations,
   deployments, or secrets consumes quota on a shared corporate account.
7. **No dependency changes without approval.** `requirements.txt` is pinned
   deliberately. A version bump is plan-authorized work only.
8. **No fabrication.** If a file, command output, or endpoint response is
   referenced, verify it. If it does not exist or does not respond, report the
   gap — do not describe what it "should" return.
9. **No secrets in the repo.** Docker tokens, BTP client secrets, and service
   keys come from env vars or the user at the moment of use. Never commit them,
   never echo them into logs.

---

## Sanity check before starting

Run this first. If any line disagrees with the expected output, **stop and
report** rather than proceeding.

```bash
pwd && git log --oneline -1 && ls
python3 --version
docker --version
```

Expected: repo root contains `app.py`, `recognizers.py`, `samples.json`,
`allowlist.txt`, `Dockerfile`, `serving_template.yaml`, `requirements.txt`,
`README.md`, `README-DEPLOY.html`. Python 3.11+. Docker present and daemon
running.

If Docker is absent or the daemon is down, stop — Phases 2 onward are blocked.

---

## Phase Structure

### Phase 1 — Local verification (no Docker, no network, no cost)

**Goal:** reproduce the 100% recall result on this machine.
**Budget: 45 minutes.**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn app:app --port 8080 &
sleep 20
curl -s localhost:8080/health
curl -s localhost:8080/v1/selftest | python -m json.tool | head -40
```

**Deliverable:** the `overall` block from `/v1/selftest`, verbatim.

**Expected:** `recall_pct: 100.0`, `redacted: 45`, `expected_pii: 45`,
`missed: 0`, `over_detections: 6`.

If recall is below 100.0 — do **not** tune. Report which values are in
`misses[]` and stop. A different spaCy or Presidio patch version is the most
likely cause and that is a finding worth knowing.

**Rollback:** none needed (read-only).

> **Approval gate 1.** Report the `overall` block and any deltas from the
> expected numbers, under 150 words, and wait for user sign-off before
> starting Phase 2. Do not chain phases unattended.

---

### Phase 2 — Docker build + in-container verification (local only)

**Goal:** a working image whose self-test passes inside the container.
**Budget: 90 minutes** (the image is large — torch and model weights are baked in).

```bash
docker build -t pii-scrubber:1.0.0 .
docker run -d --name pii-test -p 8081:8080 pii-scrubber:1.0.0
sleep 45
curl -s localhost:8081/health
curl -s localhost:8081/info | python -m json.tool
curl -s localhost:8081/v1/selftest | python -m json.tool | head -40
docker logs pii-test 2>&1 | tail -30
```

**Deliverable:** image size (`docker images pii-scrubber`), the `/info` output,
the `/v1/selftest` `overall` block, and confirmation that container logs show
**no outbound network attempts** at inference time.

If the build fails on the GLiNER prefetch, that is tolerated — the Dockerfile
falls back to Presidio-only mode by design. Report it and continue.

**Rollback (mid-phase):**
```bash
docker rm -f pii-test
docker rmi pii-scrubber:1.0.0
```

**Budget escape:** if you hit 90 minutes still debugging the build, run the
rollback, post partial findings, and stop.

> **Approval gate 2.** Report image size, self-test result, and any build
> warnings, under 200 words, and wait for user sign-off before starting
> Phase 3. Do not chain phases unattended.

---

### Phase 3 — Publish (GitHub + container registry)

**Goal:** code on GitHub, image in a registry AI Core can pull.
**Budget: 45 minutes.**
**This phase mutates remote state. Every command below needs approval before
you run it.**

Ask the user for: the GitHub remote URL, the registry namespace, and whether
the repo should be private (recommended — this is corporate SAP work).

```bash
git remote add origin <URL_FROM_USER>
git push -u origin main

docker tag pii-scrubber:1.0.0 <REGISTRY>/<NAMESPACE>/pii-scrubber:1.0.0
docker push <REGISTRY>/<NAMESPACE>/pii-scrubber:1.0.0
```

**Deliverable:** the repo URL and the fully-qualified image reference.

**Rollback (GitHub, if pushed in error):**
```bash
git remote remove origin
# Delete the remote repo via the GitHub UI — do NOT force-push to fix it.
```

**Rollback (registry):** delete the tag via the registry UI. Do not attempt
programmatic deletion.

> **Approval gate 3.** Report the repo URL and image reference, under 100
> words, and wait for user sign-off before starting Phase 4. Do not chain
> phases unattended.

---

### Phase 4 — Prepare AI Core artifacts (local edit only)

**Goal:** `serving_template.yaml` ready to sync, nothing deployed yet.
**Budget: 30 minutes.**

Edit exactly one line in `serving_template.yaml` — the `image:` value — to the
fully-qualified reference from Phase 3. Change nothing else: the labels
(`scenarios.ai.sap.com/id`, `executables.ai.sap.com/id`, `ai.sap.com/version`),
the `starter` resource plan, and the `docker-registry-secret` name all match
what AI Core expects.

```bash
git diff serving_template.yaml
git add serving_template.yaml
git commit -m "Point ServingTemplate at published image"
```

Do **not** push yet — pushing triggers the AI Core Git sync, which is a BTP
mutation.

**Deliverable:** the one-line diff.

**Rollback:**
```bash
git revert HEAD --no-edit
```

> **Approval gate 4.** Show the diff, under 80 words, and wait for user
> sign-off before starting Phase 5. Do not chain phases unattended.

---

### Phase 5 — AI Core deployment (BTP mutation — user drives)

**Goal:** a RUNNING deployment returning `recall_pct: 100.0`.
**Budget: 60 minutes.**

**You do not have BTP credentials and must not ask for them.** The user
performs the cockpit steps. Your job is to hand them exact instructions and
then verify the result.

Steps for the user (from `README-DEPLOY.html`, sections 2–6):
1. Push the Phase 4 commit so AI Core syncs the template (~3 min).
2. Create the `docker-registry-secret` in AI Launchpad if not present.
3. Confirm scenario `pii-scrubber` appears under ML Operations → Scenarios.
4. Create a Configuration: scenario `pii-scrubber`, executable
   `pii-scrubber-serve`, parameter `engine = presidio`.
5. Create a Deployment from it. Wait for status RUNNING.
6. Provide you with `$DEPLOYMENT_URL` and a bearer token.

Then you verify:

```bash
curl -s "$DEPLOYMENT_URL/v1/selftest" \
  -H "Authorization: Bearer $TOKEN" \
  -H "AI-Resource-Group: default" | python -m json.tool | head -40
```

**Deliverable:** the deployed `/v1/selftest` `overall` block.

**If the deployment crash-loops:** the most likely cause is memory on the
free-tier `starter` plan. Confirm `SCRUBBER_ENGINE=presidio` (not `both`),
report the pod logs, and stop. Do not raise the resource plan — that has
cost implications and is the user's call.

**Rollback:** the user stops/deletes the deployment in AI Launchpad. Do not
attempt to delete BTP resources yourself.

> **Approval gate 5.** Report the deployed self-test result and any
> discrepancy from the local run, under 150 words. Stop. Phase 6 is a separate
> session.

---

## What NOT to do

- Do not redesign the engine, swap models, or "improve" the recognizers.
  Benchmark research already settled this.
- Do not edit `samples.json` for any reason. It is ground truth; changing it
  invalidates every recall number in the project.
- Do not tune thresholds, remove recognizers, or relax `REDACT_TYPES` to make
  output look cleaner. Over-detection is safe; under-detection is a leak.
- Do not add `Piiranha` or any CC-BY-NC / non-commercial model. Licensing was
  screened deliberately; Apache/MIT only.
- Do not chain phases without the approval gate output.
- Do not create BTP resources, raise resource plans, or enable Kyma.
- Do not commit `.venv/`, `hfcache/`, or any image layer artifacts.
- Do not put real ticket text, real customer names, or real vendor numbers
  anywhere in this repo.

---

## Reporting Cadence

- **At each approval gate:** the stated deliverable, within the stated word
  limit. Numbers verbatim from command output — never paraphrased or recalled.
- **On any failure:** the failing command, the actual error, and your single
  best hypothesis. One hypothesis, not a list of five.
- **Mid-phase:** silence is fine. Do not narrate progress.
- **If blocked >20 minutes on one error:** stop and report rather than
  continuing to try variations.

---

## Open item to expect

The user is sourcing SAP table **TSTC** (field `TCODE`) to populate
`allowlist.txt` — the technical-token list that stops transaction codes
(`VF04`, `ME23N`) being redacted as PII. If they hand you that export during
the session: append one token per line to `allowlist.txt`, re-run
`/v1/selftest`, and confirm recall stays at 100.0 while `over_detections`
falls below 6. That is the only detection-affecting change authorized in this
session.
