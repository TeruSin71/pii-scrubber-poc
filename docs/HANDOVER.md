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

## Current state — deployed and running

| Area | State |
|---|---|
| Deployment | ✅ **RUNNING** — `d5e6ea76217ed207` on SAP AI Core |
| Image | ✅ `ghcr.io/terusin71/pii-scrubber:1.1.0`, **linux/amd64**, `sha256:070dea2c…f38290` |
| GitHub | ✅ `https://github.com/TeruSin71/pii-scrubber-poc` — **private**, branch `deploy/aicore-poc` |
| AI Core Git sync | ✅ application `pii-scrubber-app` → repo `pii-scrubber-poc`, **path `workflows`**, revision `deploy/aicore-poc` |
| Scenario | ✅ `pii-scrubber`, version `1.0`, executable `pii-scrubber` |
| Allowlist | ✅ 257,578 tokens from `TSTC` + `DD02L` (service logs `Allowlist loaded: 257583`) |
| Holdout evaluation | ✅ 40 unseen samples, **96.4%** recall |
| Engine | `presidio` only. **`both` is broken — see finding 11.** |

Rollback image, still in the registry: `1.0.0` (`sha256:8e779fde…f026a1b`) —
identical except it lacks the street-address recognizer.

---

## The numbers, and which one to quote

**Quote 96.4%. Never quote 100%.**

| Measurement | Value | What it means |
|---|---|---|
| **Holdout** — 40 unseen samples, 111 planted values | **96.4%** (107/111) | The honest production-shaped estimate. These samples were never used for tuning. |
| Self-test — 13 samples, 45 values | 100.0% (45/45) | A **regression baseline, not a result.** The recognizers were tuned against these 13 samples, so 100% is near-guaranteed. |

The self-test's job is to prove that packaging, rebuilding and deploying did not
degrade detection. It is asserted, not targeted: if `/v1/selftest` returns below
`100.0`, that is a regression to report, never a number to tune toward. Lowering
a threshold, deleting a recognizer, relaxing `REDACT_TYPES`, or editing
`samples.json` to make output match are all forbidden.

`over_detections: 6` on the self-test is stable and expected.

**Do not present 100% to management.** That instruction is in
`README-DEPLOY.html`, `README.md` and the evaluation report, and it exists
because the figure describes how well the rules fit their own training data.

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
| HO-009 | CUSTOMER_NO | `1045567` | keyed without leading zeros | pattern scores 0.35 against a 0.50 floor |

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

### Address coverage limits, accepted deliberately

- **NZ/AU forms only.** German-style `Hauptstrasse 12, 80331 Munich` (name
  before number) is not matched and relies on incidental locality detection.
- **Bare ambiguous-type addresses are missed.** `44 Bellbird Rise` with no
  suburb does not match, because street types that are also ordinary logistics
  words require a trailing comma-locality. That rule is what stops
  `20 Pallet Rack Row` and `12 Handling Unit Place` being eaten.

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

1. `docs/superpowers/plans/2026-08-15-pii-scrubber-task-list.md` — the run
   sheet. Tasks 0–6 all complete; all 18 findings in full.
2. `docs/superpowers/plans/2026-08-15-pii-scrubber-aicore-deployment.md` — the
   detailed runbook, commands and rollbacks.
3. `holdout-evaluation-report.html` — the 96.4% measurement and the backlog
   (gitignored, local only).
4. `VSCODE-PROMPT-address-recognizer.md` — the prompt that produced the address
   work; a good template for the remaining backlog items.
5. `PERSON-CONTEXT-FINDING.md` — why the rule-based person promoter was built
   and then **not shipped**. Read before touching the PERSON class.

**Backlog, roughly in value order:**

| | Item | Note |
|---|---|---|
| ~~P1~~ | ~~street addresses~~ | ✅ **closed 2026-08-15** — 0/3 → 3/3 |
| ~~P2~~ | ~~person-context promoter~~ | ⛔ **closed 2026-08-15 as a negative result** — built, measured, reverted. Reaches ~1/3 of the residual PERSON class. `PERSON-CONTEXT-FINDING.md` |
| P2 | unpadded customer number | `1045567` — `sap_customer_ctx` scores 0.35 against a 0.50 floor. Self-contained; the only remaining leak that rules can close |
| P3 | SAP jargon glossary | the `<ORG_NAME>` over-redaction class |
| P3 | `en_core_web_lg` upgrade | scoped as **frame robustness**, not vocabulary — `sm` tags `Mere Tuhoe` in one sentence frame and misses it in another. Owns HO-018 and HO-031 |
| — | expand the sample set to 50–100 real-shaped samples | **highest value overall** — everything above is measured against 40, where one sample is worth 0.9 points |
| — | GLiNER bake-off | blocked on finding 11 |

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

python test_fixes.py          # 16/16 — the three fixed defect classes + recall invariant
python test_address.py        # street-address recognizer, positives and negatives

# against the deployment (DEPLOYMENT_ID defaults to d5e6ea76217ed207)
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
