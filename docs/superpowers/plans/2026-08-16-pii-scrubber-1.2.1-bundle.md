# PII Scrubber — 1.2.1 Bundle Implementation Plan

**Gate 0 deliverable. Nothing in this plan has been executed.**
Authored 2026-08-16 against `0687fc0`. Scope frozen by the handover at two
items. The executable step-by-step lives in
`2026-08-16-pii-scrubber-1.2.1-tasks.md`; this document is the argument.

---

## 1. Executive Summary

**Goal.** Ship one image, `1.2.1`, carrying two changes — a build-version
stamp returned by the service, and eight glossary entries — through a single
stop/create cycle on the 1-pod free tier.

**Why one image.** Unchanged from 1.2.0 and still the binding constraint:
free tier allows one pod, every deployment change costs a stop/create cycle,
and a stop-then-create race marks the new revision failed **permanently**
because Kubernetes never re-drives an admission-rejected revision. Item 2 is
a data-only change to `glossary.txt` and would be trivially shippable alone —
that is precisely why it must not ship alone.

**Why item 1 goes first.** From the stale-deployment incident: a script
pointed at a deployment that was live but not the one just shipped, and
reported confident numbers for the wrong artifact. Nothing in any response
identifies which build answered. Item 1 makes every subsequent measurement
auditable, including the ones taken in this very plan — so it lands before
item 2 changes any behaviour worth measuring.

**Success criteria — all measurable, all blocking:**

| # | Criterion | Source of truth |
|---|---|---|
| 1 | `/info` and `/v1/selftest` both return `build_version` exactly `1.2.1` | deployed endpoint |
| 2 | `/v1/selftest` returns `recall_pct 100.0`, `45/45`, `missed 0` | deployed endpoint |
| 3 | `over_detections` equals the Task 0 baseline, or the delta is itemised sample-by-sample before it is re-asserted | deployed endpoint |
| 4 | `test_fixes.py` 16/16, exit 0 | local + in-container |
| 5 | `test_address.py` exit 0, check count equal to Task 0 baseline | local + in-container |
| 6 | `test_customer_number.py` exit 0, count equal to Task 0 baseline | local |
| 7 | `test_jargon.py` exit 0, count = Task 0 baseline **+ the new checks** | local |
| 8 | `holdout_samples.json` regression **exactly 108/111**, same three leaks | regression gate — §11 |
| 9 | `eval_samples_v2.json` regression **exactly 65/68**, same three leaks | regression gate — §11 |
| 10 | `holdout_v3.json` regression **exactly 45/50**, same five leaks | regression gate — §11 |
| 11 | Image is `linux/amd64`, verified by `docker buildx imagetools inspect` | registry |
| 12 | Deployment reaches `RUNNING` on one clean create | AI Core API |

Criterion 10 is new. `holdout_v3.json` was the blind batch; it has been read,
so it is burned and joins the other two as a gate. Its value is 45/50 and any
other value is a stop.

**Time estimate.**

| Task | Budget | Risk |
|---|---|---|
| 0 — Gate 0 approval + baseline capture | 20 min | local, read-only |
| 1 — `BUILD_VERSION` through the service | 40 min | local |
| 2 — harness stamps the build it measured | 20 min | local |
| 3 — eight glossary entries | 60 min | local |
| 4 — regression sweep, all four sets | 30 min | local |
| 5 — Docker build + in-container verify | 40 min | local, ~3 min build |
| 6 — publish image | 30 min | ⚠️ mutates remote |
| 7 — deploy handoff | 45 min | ⚠️ BTP, user drives |

Total ≈ 4 hours across at least two sessions. Tasks 6 and 7 do not start in
the same session that finished Task 5 without a fresh gate.

**Risk posture.** Lower than 1.2.0. Item 1 adds a field and changes no
detection path. Item 2 makes the scrubber redact *less*, which is the
dangerous direction, but eight entries against a protocol that already has a
safety gate and a rejection appendix. Either item can be dropped without
blocking the other — see §5.

---

## 2. Philosophy and Principles

Carried forward unchanged from the 1.2.0 bundle, because they are what kept
that release honest:

1. **Evidence before action.** Every claim in §3 was verified at authoring
   time with a shown command. A number without a command next to it is a
   guess and must be re-measured before use.
2. **The plan is the authorization.** Steps outside this document need a new
   gate. Scope is frozen at two items; a third is a new plan.
3. **The floor does not move.** `DEFAULT_THRESHOLD` and `TYPE_THRESHOLDS`
   govern every recognizer. Neither item in this bundle has any business
   touching them.
4. **Suppression is more dangerous than detection.** The glossary makes the
   scrubber redact *less*. Every entry is a potential leak. Entries are
   proved individually, not assumed as a list.
5. **New for 1.2.1 — a version string is a claim like any other.** The whole
   point of item 1 is that a stale artifact once reported confident numbers.
   A `BUILD_VERSION` that is baked wrong, or defaulted to something
   real-looking, reproduces that incident with a false sense of coverage.
   The default is `dev`, deliberately — see §6.

---

## 3. Current State — verified ground truth

Everything below was measured on 2026-08-16 against the working tree at
`0687fc0`, with the command shown.

### 3.1 Deployed

| | |
|---|---|
| Deployment | `db3d9cc5eea296cd`, RUNNING |
| Image | `ghcr.io/terusin71/pii-scrubber:1.2.0`, `linux/amd64`, `sha256:e8a44575…81ca893` |
| Rollback | `1.1.0` (`sha256:070dea2c…f38290`), `1.0.0` (`sha256:8e779fde…f026a1b`) |
| Blind figure | 90.0% (45/50) — the quotable number |
| Regression suite | 108/111, burned |

### 3.2 Baselines that must not move

`over_detections: 4` is the asserted 1.2.0 baseline. Item 2 can only lower it
(it suppresses), and the handover's protocol says a change in **either**
direction is reportable. Task 0 captures the pre-change value from the
running service so the delta is measured, not assumed.

Test counts are **captured in Task 0, not asserted here.** The handover gives
`test_fixes.py` as 16/16; it gives no count for `test_address.py`,
`test_customer_number.py` or `test_jargon.py`, and the 1.2.0 plan's `39/39`
for `test_address.py` predates later edits. Writing a number here that nobody
re-measured is exactly the failure this bundle's item 1 exists to prevent.

### 3.3 Item 1 — nothing in the service identifies the build

```
$ grep -n "version" app.py | head
192:app = FastAPI(title="PII Scrubber (POC)", version="1.0.0")
```

That is the only version string in the service, it is hardcoded, and it has
read `1.0.0` on every image since — including the `1.2.0` currently deployed.
It is not merely absent information; it is **wrong** information, and it is
the same trap class as the `__version__` line that printed `presidio unknown`
for months and the `HOLDOUT RESULT` banner that prints for any input file.
Metadata that a human parses as evidence and the machine never populated.

`/info` (`app.py:473`) already exists and already returns engine, model and
`redact_types` — it is the natural home for identity, and it needs no new
endpoint, no new mechanism and no new dependency.

`/v1/selftest` (`app.py:527`) returns a flat dict at `app.py:577-599`. The
handover's own wording is "return it in the selftest payload", so that is
where the number-carrying copy goes.

### 3.4 Item 2 — the eight entries, each traced to a sample

Every entry must answer "which incident put you here?". Verified today:

```
$ python3 - <<'EOF'   # locate each token in the corpora
...  re.search(rf"\b{t}\b", s["text"])  for each sample
EOF
samples.json          -
holdout_samples.json  -
eval_samples_v2.json  {'Rise': ['V2-008']}
holdout_v3.json       {'GL': ['V3-034'], 'FX': ['V3-034'], 'WM': ['V3-035'],
                       'MDG': ['V3-038'], 'MRP': ['V3-039'], 'OSS': ['V3-040'],
                       'CFO': ['V3-001'], 'Rise': ['V3-035']}
```

All eight occur, each in a named sample. **The evidence lives in a gitignored
file.** `holdout_v3.json` is local-only by design, so a future reader without
it cannot open `V3-034`. The sample IDs are recorded in the glossary comment
block anyway — an ID that cannot be opened is still better than a bare
assertion, and it tells the next session which file to ask for.

**None of the eight is already suppressed:**

```
$ for t in GL FX WM MDG MRP OSS CFO Rise; do grep -cx "$t" allowlist.txt; done
0 0 0 0 0 0 0 0
```

**None collides with a ground-truth value — except `Rise`, and that one
matters:**

```
$ ... re.search(rf"\b{t}\b", value) over every sample's pii[].value
eval_samples_v2.json  {'Rise': ['44 Bellbird Rise']}
```

`44 Bellbird Rise` is ground truth in `V2-008` and is the **known, accepted
ADDRESS leak** — the handover records it as the only ADDRESS miss in the v2
batch (13/14), caused deliberately by the rule that ambiguous street types
require a trailing comma-locality. So the value is already not caught, and
shipping `Rise` cannot un-catch it. The residual risk is narrower and stated
in §9 R2: whole-span matching means a glossary entry vetoes a span whose text
is exactly `Rise`, not one reading `44 Bellbird Rise` — that is the
assumption Task 3 must prove rather than assume.

**The 4-char floor is why these leaked as ORG, not as user IDs:**

```
app.py / recognizers.py:108
Pattern(name="sap_uid_upper", regex=r"\b[A-Z]{4,12}\b", score=0.3)
```

`GL`, `FX`, `WM`, `MDG`, `MRP`, `OSS` and `CFO` are two and three characters,
below that floor, so they can never have been `SAP_USER_ID` spans. They are
**spaCy-layer over-detections**, same class as `Basis` and `Driver` in 1.2.0.
This is load-bearing for Task 3: the assertion to write is that they arrive
as `ORG_NAME`/`NRP` and leave suppressed, not that a recognizer stops firing.

### 3.5 The mechanism already exists — do not build a second one

`glossary.txt` loads through `app._load_allowlist()` (`app.py:110-136`), the
same loader as `allowlist.txt`, into the same suppression set. It therefore
already inherits case-sensitive exact match, whole-span matching and the
±40-char user-context backstop. Item 2 adds **eight lines of data and no
code.** Any diff to `app.py` or `recognizers.py` in Task 3 is a scope
violation, not an improvement.

`test_jargon.py` already carries the street-type safety gate, including a
`Rise` case at line 127 (`"Depot at 14 Sunrise Rise, Papakura, Auckland."`
must still redact `14 Sunrise Rise`). That test was written when `Rise` was
pre-cleared but unshipped; shipping it is exactly the event the test was
built to guard. Extend that list, do not write a parallel one.

### 3.6 Environment

Unchanged and still hostile in the same three ways: system Python 3.14 cannot
install the pins (`uv venv --python 3.12 --seed .venv`), this machine is
arm64 against an x86_64 target (`--platform linux/amd64`, always), and disk is
tight enough that `docker system prune` is forbidden.

---

## 4. Decision Matrix

| # | Decision | Chosen | Why not the alternative |
|---|---|---|---|
| D1 | Where does the version come from? | Docker `ARG`/`ENV`, read with `os.getenv` | A file baked at build time is a second artifact to keep in sync. Reading git at runtime needs git in the image and a repo that is not there. |
| D2 | Default when the arg is absent | `dev` | A real-looking default (`1.2.1`, `unknown`) makes a mis-built image indistinguishable from a correct one — the exact incident this item fixes. `dev` is visibly wrong. |
| D3 | Where in the Dockerfile | Immediately before `EXPOSE`, after every `COPY` | An `ENV` invalidates every layer below it. Placed early, each version bump re-runs pip and the spaCy download — minutes per build, for a string. |
| D4 | Which endpoints carry it | `/info` **and** `/v1/selftest` | `/info` is identity, selftest is the payload the handover names. |
| D5 | Does `/v1/scrub` carry it too? | **No** | A constant on every scrub response is payload bloat on the batch path for no gain, and it changes the shape every existing consumer parses. |
| D6 | Replace the hardcoded `FastAPI(version="1.0.0")`? | **Yes** | It is a stale claim on a shipped artifact. Leaving it is leaving the defect half-fixed with a second, contradictory version visible on `/docs`. |
| D7 | Does the harness print it? | **Yes** — `test_deployed.py` | The incident was a *script* reporting the wrong artifact. A version only the endpoint knows fixes nothing unless the thing that prints numbers prints it too. Root cause, not symptom. |
| D8 | Harness behaviour on an old image | Print `build: unknown (pre-1.2.1)`, continue | Aborting would break the harness against the `1.2.0`/`1.1.0` rollback images, which must stay measurable. |
| D9 | Glossary: eight at once, or drip? | Eight at once | Each already meets the shipping rule. A rebuild and a stop/create cycle per entry is eight chances at the 1-pod race. |
| D10 | Add `Close`, `Court`, `Terrace`, `Drive` while in there? | **No** | Pre-cleared in Appendix A of the 1.2.0 plan but with no observed misfire. The protocol is clearance *plus* evidence. `Rise` ships because the blind batch supplied the missing half. |

### Open at Gate 0 — the user answers these, they are not assumed

| # | Question | Recommendation |
|---|---|---|
| Q1 | `test_deployed.py` prints the `HOLDOUT RESULT` banner for any input file and labels a non-holdout run `HOLDOUT RECALL`. Fix that in the same pass as D7, or leave it? | **Fix it** — one line, same incident class (metadata read as evidence), and it is touched by D7 anyway. But it is a third item, so it needs an explicit yes. |
| Q2 | Also print the input filename next to the build version? | **Yes if Q1 is yes**, otherwise no. Half of "every number carries its artifact" is which samples produced it. |
| Q3 | Backlogged `LABEL_MAP` unknown-label warning is a genuine one-liner at startup and this is a rebuild anyway. In or out? | **Out.** It is a fourth item, the failure it guards is only reachable through `en_core_web_lg`, which is not shipped, and "we were rebuilding anyway" is how scope dies. |

---

## 5. Bundle composition and drop order

If something has to go, drop in this order:

1. **Item 2 (glossary)** drops first. It is pure data, it ships in any later
   release for free, and its absence changes no measurement.
2. **Item 1 (`BUILD_VERSION`)** drops only if it cannot be made to work at
   all, which would be surprising for `os.getenv` plus two dict keys.

If item 1 drops, **item 2 must drop with it.** Shipping a glossary change on
an image that still cannot say which build it is reproduces the incident that
put item 1 first: a new number, from an unidentifiable artifact.

---

## 6. Global Constraints

Copied verbatim from the standing rules; every task inherits them.

- **Rule 3 — no outbound calls from inside the boundary.** No bare
  `AnalyzerEngine()` (it downloads `en_core_web_lg`). Mirror `app.py`'s
  explicit `NlpEngineProvider`, or import `app.get_analyzer()`.
- **Rule 7 — dependency changes need approval.** This bundle adds none, and
  must not.
- **Rule 4 — no real ticket text, no mined corpora, no holdout files in the
  repo.** `holdout_samples.json`, `eval_samples_v2.json`, `holdout_v3.json`
  and both HTML reports stay gitignored.
- **Always build `--platform linux/amd64`** and verify with
  `docker buildx imagetools inspect`. A digest check alone cannot catch an
  arm64 image on an arm64 host.
- **Install from `requirements.txt`, pinned**, when producing any number
  anyone will quote.
- **`BUILD_VERSION` defaults to `dev`.** Never to a version-shaped string.
- **Do not tune against any of the four evaluation sets.** All four are now
  burned; they are gates, not measurements.
- **Do not run `docker system prune`.** Unrelated `frappe_docker` images are
  present and disk is at 90%+.
- **The 100% self-test figure is never presented to management.**

---

## 7. Per-task runbook

Lives in `2026-08-16-pii-scrubber-1.2.1-tasks.md`, as TDD steps with the
actual code. Task boundaries and gates:

| Task | Deliverable | Gate |
|---|---|---|
| 0 | Baseline captured: four test counts, `over_detections`, four regression scores | Gate 0 — approval to start |
| 1 | `BUILD_VERSION` in `app.py` + `Dockerfile`, `/info` and selftest carry it | local tests green |
| 2 | `test_deployed.py` stamps the build it measured | local run against 1.2.0 shows `unknown` |
| 3 | Eight glossary entries + safety assertions in `test_jargon.py` | `test_jargon.py` green, count grew |
| 4 | Four-set regression sweep at exact gate values | ⛔ any deviation stops the bundle |
| 5 | `linux/amd64` image, in-container `/info` reads `1.2.1` | Gate 5 — approval to publish |
| 6 | Image on ghcr, platform and pull-back verified | ⚠️ mutates remote |
| 7 | ServingTemplate at `1.2.1`, deployment RUNNING, selftest identical | ⚠️ user drives BTP |

---

## 8. Acceleration Playbook

- Tasks 1 and 3 touch disjoint files and can be done in either order; do 1
  first anyway, so Task 3's measurements carry a build stamp.
- The regression sweep in Task 4 runs against a **local** service
  (`SCRUB_URL=http://localhost:8080/v1/scrub`), not the deployment. Same
  scorer, no BTP round trip, no token expiry mid-run.
- The build is ~3 minutes emulated, not the 19 of the first 1.0.0 attempt —
  pip pulls prebuilt manylinux wheels, so QEMU emulates almost nothing.
- Do not re-run the four regression sets after Task 1. It changes no
  detection path; Task 4 covers it once, after Task 3.

---

## 9. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Image built without `--build-arg BUILD_VERSION`, ships reading `dev` | **High** — it is one flag on a long command | Medium — a wrong-but-visible version | Task 5 asserts the in-container `/info` string **equals `1.2.1`** before push. Default `dev` makes the failure loud, not silent. |
| R2 | `Rise` suppresses a real address span | Low | **High** — a leak | `test_jargon.py:127` already asserts `14 Sunrise Rise` still redacts; Task 3 adds a bare-`Rise` negative and re-runs all four sets. If the address case breaks, `Rise` goes to Appendix A, never to a workaround. |
| R3 | A two-char entry (`GL`, `FX`, `WM`) suppresses something unforeseen | Low | High | Whole-span exact match means only a span whose entire text is `GL` is vetoed. Asserted structurally in Task 3, plus the four-set sweep. |
| R4 | Glossary lowers `over_detections` and the drop is rubber-stamped | Medium | Medium — an unexplained baseline is a future mystery | Task 4 itemises every changed span sample-by-sample **before** the new baseline is asserted, exactly as 1.2.0 did for 6 → 4. |
| R5 | `ENV` placed early, every build re-runs pip and the spaCy download | Medium | Low — time only | D3 fixes the placement; Task 1 states the line number. |
| R6 | Stop/create race on the 1-pod tier marks the revision permanently failed | Medium | **High** — no service | Delete the old deployment, confirm it is gone via the API, then create with nothing else in existence. Never stop-then-create. |
| R7 | Adding a selftest key breaks a consumer | Very low | Low | Additive key. `test_deployed.py` reads `/v1/scrub` only; `test_fixes.py` calls functions, not endpoints. |
| R8 | Token expires mid-run against the deployment | Medium | Low | The harness already prints `401 = token expired; re-mint and re-run`. Task 4 runs local anyway. |
| R9 | A "clean" check that never ran | Medium | **High** | Standing trap. Every verification step in the task plan prints **what it inspected**, not just a verdict. |

---

## 10. Rollback Runbook

**Code, before publish.** Everything is local until Task 6. `git revert` the
task commit, or `git checkout -- glossary.txt`. Item 2 alone rolls back by
deleting eight lines.

**Image, after publish.** `1.2.0` stays in the registry. The ServingTemplate
uses a **mutable tag, not a digest**, on purpose — a corrected image can flow
through without a template change, which was load-bearing when the arm64
image had to be replaced.

**Deployment, after cutover.**

```bash
# revert the template
git revert <template-commit>          # image back to :1.2.0
git push                              # AI Core git-sync picks it up

# then, and only then, one clean cycle
GET  $AI_API/v2/lm/deployments        # confirm what exists
DELETE .../deployments/<id>           # delete, do not stop-then-create
# wait until it is gone from the list
POST .../deployments                  # create fresh
```

**Known-good target if everything fails:** deployment on
`ghcr.io/terusin71/pii-scrubber:1.2.0`, self-test `100.0 / 45/45 /
over_detections 4`, blind figure 90.0%.

---

## 11. Verification Strategy

Four sets, four exact gate values, one scorer:

```bash
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8080 &     # local service

SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py holdout_samples.json    # 108/111
SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py eval_samples_v2.json    # 65/68
SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py holdout_v3.json         # 45/50
curl -s localhost:8080/v1/selftest | python3 -m json.tool | head -30                       # 45/45
```

**These are gates, not measurements.** Every one of the four sets has been
read during a build session, so none of them can still measure what it
shaped. The only correct reading of any of them is "unchanged". A number that
goes *up* is as much a stop as one that goes down: it means detection moved
on a set nobody was authorised to move it on.

**There is no quotable figure in this release.** 1.2.1 changes no detection
path except by suppression, and every set that could produce a number is
burned. If a number is wanted, it needs an externally-authored blind batch
that this session has not seen — a fifth set, authored outside, run once. That
is a separate piece of work and it is not in this bundle.

---

## 12. Verification honesty — plan for this now

The four leak sets are known in advance. Record them **before** Task 3, so a
changed leak list cannot be rationalised afterwards:

| Set | Gate | Leaks that must remain, and only these |
|---|---|---|
| `holdout_samples.json` | 108/111 | `ZHANG`, `Young`, `Mere Tuhoe` |
| `eval_samples_v2.json` | 65/68 | includes `44 Bellbird Rise` (ADDRESS, accepted) |
| `holdout_v3.json` | 45/50 | `NAKAMURA`, `Park`, `Adeyemi`, `5591230`, `6620945` |
| `/v1/selftest` | 45/45 | none |

`eval_samples_v2.json`'s other two leaks are not named in the handover; Task 0
captures them from the baseline run rather than inventing them here.

If a leak list changes while the count holds, that is **still a stop.** Two
compensating changes summing to zero is the single most dangerous shape a
regression can take, and a count-only check is blind to it.

---

## 13. Close-out Checklist

- [ ] All twelve success criteria met, each with the command that produced it
- [ ] `over_detections` delta itemised sample-by-sample, or confirmed zero
- [ ] Four regression sets at exact gate values **and** unchanged leak lists
- [ ] `glossary.txt` header updated: eight entries added, `Rise` moved out of
      PRE-CLEARED, sample IDs recorded
- [ ] `HANDOVER.md` updated: deployment ID, image digest, 1.2.1 items closed,
      1.2.2 backlog restated
- [ ] Task list appended with a Gate row per gate passed
- [ ] `README-DEPLOY.html` checked for version-specific claims — it was wrong
      in five places once already
- [ ] Rollback tag comment in `workflows/serving_template.yaml` updated to
      point at `1.2.0`
- [ ] No credentials in any commit, log or git remote URL

---

## 14. What NOT to do

- **Do not add a ninth glossary entry.** Not `Close`, not `Court`, not
  `Terrace`, not `Drive`, however cleared they are. Clearance is half the
  protocol; evidence is the other half.
- **Do not touch `app.py` or `recognizers.py` in Task 3.** The glossary is
  data. A code change there means the mechanism was rebuilt instead of reused.
- **Do not lower a threshold, delete a recognizer, relax `REDACT_TYPES`, or
  edit any sample file** to make a number come out right. All four are
  forbidden, and all four are tempting at exactly the moment a gate fails.
- **Do not quote any number from this release as a result.** All four sets
  are burned. §11.
- **Do not re-open `en_core_web_lg`.** Closed, not deferred, with the
  measurement recorded.
- **Do not build a regex person-promoter.** Built, measured, reverted;
  `PERSON-CONTEXT-FINDING.md` says why before it says how.
- **Do not chain Task 5 into Task 6.** Publish and deploy mutate remote state
  on a shared corporate BTP account with finite quota.

---

## 15. Answered at Gate 0 — pending

Q1, Q2 and Q3 from §4 are open. This section is where their answers get
written down and become binding, matching how the 1.2.0 plan recorded its Gate
0 answers.

---

## Appendix A — the eight entries, with evidence

Format matches `glossary.txt`: `TOKEN<tab># reason`, one-word reason from the
fixed vocabulary (`module | env | doc | table | process | role | facility |
dept | shorthand`).

| Token | Reason | Sample | Why it is not PII |
|---|---|---|---|
| `GL` | module | `V3-034` | General Ledger. Two chars — below the 4-char `SAP_USER_ID` floor, so it arrived as a spaCy `ORG` span |
| `FX` | module | `V3-034` | Foreign exchange |
| `WM` | module | `V3-035` | Warehouse Management |
| `MDG` | module | `V3-038` | Master Data Governance |
| `MRP` | module | `V3-039` | Material Requirements Planning |
| `OSS` | module | `V3-040` | SAP support portal shorthand |
| `CFO` | role | `V3-001` | Role acronym. A role is not a person; "posted by CFO" still redacts via the context backstop |
| `Rise` | process | `V3-035` | Ordinary noun mid-sentence, "the Rise in failed deliveries". Also a street type — see below |

**`Rise` is the protocol working as designed.** It was safety-cleared in
Appendix A of the 1.2.0 plan and deliberately left unshipped for want of an
observed misfire. The blind batch supplied one. Clearance and evidence now
pair up, which is exactly the shape that protocol was built to produce: prove
it safe when you first meet it, ship it when an incident asks for it.

Its address behaviour is already guarded by `test_jargon.py:127`
(`14 Sunrise Rise` must still redact). Task 3 adds the negative: bare `Rise`
mid-sentence must not.

**Still rejected, unchanged from 1.2.0** — `Bill`, `BRAUN`, `Munich`,
`Wellington`, `Auckland`, `Target`, `OSNO`, the nationality set, and all
multi-token spans.

**Still pre-cleared but unshipped** — `Close`, `Court`, `Terrace`, `Drive`.
`Rise` leaves this list on 1.2.1; the other four stay until evidence appears.

**Not shipping, and why they are not on the list** — `SH` and `ES_SD_REBATE`
misfired only under `en_core_web_lg`, which is not shipped. Evidence from an
unshipped configuration is not evidence about the shipped one.

---

## Appendix B — Quick reference

```bash
# environment
source .venv/bin/activate          # uv venv --python 3.12 --seed .venv

# baselines
python test_fixes.py               # 16/16
python test_address.py             # count captured in Task 0
python test_customer_number.py     # count captured in Task 0
python test_jargon.py              # count captured in Task 0

# local service + the four gates
uvicorn app:app --host 0.0.0.0 --port 8080 &
curl -s localhost:8080/info | python3 -m json.tool
SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py holdout_samples.json   # 108/111
SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py eval_samples_v2.json   # 65/68
SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py holdout_v3.json        # 45/50

# build, tagged and stamped -- the two must agree
docker buildx build --platform linux/amd64 \
  --build-arg BUILD_VERSION=1.2.1 \
  -t ghcr.io/terusin71/pii-scrubber:1.2.1 --load .
docker run --rm -p 8080:8080 ghcr.io/terusin71/pii-scrubber:1.2.1 &
curl -s localhost:8080/info | grep build_version        # must read 1.2.1, not dev

# AI Core, from the API only -- never the cockpit
GET $AI_API/v2/admin/applications/pii-scrubber-app/status
GET $AI_API/v2/lm/deployments        # AI-Resource-Group: default
```
