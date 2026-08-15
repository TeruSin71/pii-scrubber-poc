# PII Scrubber — Handover

**As of 2026-08-15.** Written for someone picking this up with zero prior context.

---

## What this is

A **PII scrubber for an SAP incident knowledge base**. It redacts personal data
out of ticket text, functional specs and expert notes before that material
enters a KB corpus or reaches a triage LLM. It runs entirely inside the
compliance boundary — no third-party model ever sees raw data.

The folder is called `NER POC`, which undersells it. This is not a general
named-entity-recognition experiment; it is compliance tooling with a hard
no-leak requirement, being deployed to **SAP AI Core (bring-your-own-model)** on
BTP Free Tier. No Cloud Foundry, no Generative AI Hub.

Two paths through the service:

- **batch** — scrub source material on its way into the KB corpus. Replaces
  values with `<TYPE>`. Output must stay readable, so over-redaction has a cost.
- **live** — tokenize an incident payload before triage. Replaces with
  `<TYPE_n>` and returns a `token_map` so the caller re-maps *inside the
  boundary* after the answer comes back. Over-redaction costs nothing here.

---

## Current state

**Nothing has been deployed. Nothing has been built. No remote exists yet.**

| Area | State |
|---|---|
| Source code | Complete and reviewed. Not yet run on this machine. |
| Local verification | Not started — this is Task 1 |
| Allowlist sources | **In hand** — `TSTC` + `DD02L` exports received 2026-08-15 |
| `allowlist.txt` | Still the 28-token seed. Task 2 populates it. |
| Docker image | Not built |
| GitHub remote | Does not exist |
| Container registry | Nothing pushed |
| AI Core deployment | Nothing created |
| Git repository | **Not yet initialised** — Task 0 does this |

The immediate next action is **Task 0** in
`docs/superpowers/plans/2026-08-15-pii-scrubber-task-list.md`.

---

## The one number that matters

`GET /v1/selftest` runs the service against 13 labelled synthetic samples
containing 45 planted PII values and reports recall.

**`recall_pct: 100.0` is an assertion, not a target.** If it comes back lower,
that is a regression to report — never a number to tune toward. Lowering a
threshold, deleting a recognizer, relaxing `REDACT_TYPES`, or editing
`samples.json` to make the output match are all explicitly forbidden. Recall is
the product; over-detection is safe, under-detection is a leak.

**The 100% is also not a production figure.** It is 13 synthetic samples that
the recognizers were tuned against, so some over-fitting is certain. The
project's own docs say plainly: *do not present 100% to management as the
expected production figure.* The number worth quoting comes after expanding to
50–100 real-shaped samples — work that has not been done and is out of scope.

What the deployment tasks verify is a **regression baseline**: that packaging
and deploying did not degrade detection.

---

## Settled — do not relitigate

Decided in a session before 2026-08-15, after benchmark research:

- **Engine:** Presidio + 8 custom SAP recognizers. GLiNER stays optional behind
  `SCRUBBER_ENGINE=both`.
- **Licensing:** Apache 2.0 / MIT only. Piiranha was screened out deliberately
  (CC-BY-NC-ND, non-commercial).
- **Deployment path:** SAP AI Core BYOM via a KServe `ServingTemplate`.
- **First deploy runs `engine=presidio`** — GLiNER may not fit free-tier
  `starter` memory. Switching to `both` is a configuration change, not a rebuild.
- **`USR02` is refused as an allowlist source.** A gazetteer of real user IDs
  would improve recall, but the list would itself become a PII asset requiring
  the same access control, retention and deletion policy as the data it
  protects. That is a governance decision, not an engineering shortcut.

---

## Three defects already found and fixed — leave them alone

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

---

## What changed on 2026-08-15

`app.py` gained two detection changes, verified by diff:

- A deterministic **custom-object rule** (`is_custom_sap_object`). SAP reserves
  `Z*`, `Y*` and registered `/NAMESPACE/` prefixes for customer development, so
  a token in that shape is provably technical, not PII. Implemented as a rule
  rather than a list: no extract, no maintenance, and it covers Z-objects that
  do not exist yet. Guarded against the surname trap — `Zhang`, `Young`,
  `Yamamoto` must still be redacted.
- The allowlist match moved from **case-insensitive to case-sensitive**. Several
  SAP object names are also surnames (`MARA`, `LIPS`, `BRAUN`, `KLEIN`);
  uppercase `MARA` is allowlisted while the person `Mara` is still redacted.

`ALLOWLIST-EXTRACTION.md` was added — a tiered spec for which SAP tables to
export (Tier 1 `TSTC`/`DD02L`, Tier 2 `TFDIR`/`T100`/`TADIR`, Tier 3 domain
codes) with assembly rules. `DD03L` was in Tier 1 originally and was dropped as
impractical — roughly 200k distinct field names — in favour of the corpus
miner, `mine_allowlist.py`.

**On `over_detections: 6`:** the figure was originally measured against the
previous `app.py`, and the custom-object rule exists specifically to reduce it.
`FIXES-2026-08-15.md` reports it re-verified at 6 on the current code. That
report has not been reproduced on this machine — see "Verification status"
below. Task 1 settles it.

---

## Decisions waiting on a human

| # | Decision | Blocks |
|---|---|---|
| 1 | ~~Does `allowlist.txt` ship in the image?~~ **Resolved at source** (`FIXES-2026-08-15.md`) — the Dockerfile `COPY` line now includes it. Task 2 Step 6 is a verification, not a decision. | — |
| 2 | GitHub repo URL, or authorisation to create one | Task 4 |
| 3 | Registry: Docker Hub (separate credentials) or `ghcr.io` (reuses the GitHub token, but it needs **Packages: write**) | Task 4 |
| 4 | **Which repo and branch does AI Core's Git sync already watch?** Check *AI Launchpad → Administration → Git Repositories*. If it is not the repo created in Task 4, the ServingTemplate commit lands in the wrong place. | Tasks 4, 6 |
| 5 | ~~Is the TSTC/DDIC export available?~~ **Delivered 2026-08-15** and parsed — see "The allowlist source exports" below. What remains is only the *optional* miner step: is there a corpus to mine, and who performs the mandatory review pass? Tier 1 alone is enough to complete Task 2. | Task 2 |

The allowlist task still runs *before* the Docker build — the content of
`allowlist.txt` must be final before it is baked into the image, even now that
shipping it is no longer in question.

---

## The allowlist source exports

Both Tier 1 sources arrived on 2026-08-15 and are parked **outside the repo**:

```
/Users/terulinsinulingga/Downloads/sap-exports/
    TSTC.txt        12.6 MB   147,048 distinct transaction codes
    DD02L.txt       61.9 MB   111,388 distinct active transparent tables
    CHECKSUMS.txt   SHA-256 — verify before use
    README.md       format, extraction commands, PII warning
```

Union after filtering: **257,584 tokens**, against the 28-token seed
`allowlist.txt` ships today.

**Read that folder's `README.md` before extracting anything.** Three traps are
documented there, and all three are silent failures:

- The files are SAPGUI list exports, not CSV — tab-delimited with a **leading
  empty field**, so the token column is field **2**.
- They are **Latin-1**. `awk` aborts on a multibyte conversion failure partway
  through unless `LC_ALL=C` is set — and a partial parse looks like a smaller
  allowlist, not like an error.
- `DD02L` needs the `Ac='A'` + `Tab.cat.='TRANSP'` filter. Unfiltered it yields
  578,227 names, mostly internal structures and views.

**Why they are outside the repo.** `DD02L.txt` has an **Author** column
carrying **87 distinct real SAP user IDs**. That makes the raw file a PII
asset of exactly the kind this project refused when it declined `USR02`. The
repo becomes a git repository in Task 0 and is pushed to GitHub in Task 4; a
`.gitignore` entry is one mistake away from failing, so the file stays out of
the working tree altogether. Extract **field 2 and nothing else** — a naive
sweep for all-caps tokens would load 87 real user IDs into `allowlist.txt`,
and an allowlisted token is never redacted.

---

## Open risks — status after the 2026-08-15 fix drop

Three findings from the plan review were fixed at source in the same-day drop
(`FIXES-2026-08-15.md`, regression-tested by `test_fixes.py`). Current status:

**The all-caps USER_ID collision — downgraded, not closed.** Case sensitivity
protects `Mara` the person from `MARA` the table, but an SAP *user ID* is
all-caps by convention, so a real user ID of `KLEIN` or `BRAUN` is
byte-identical to the allowlistable token. The fix: `detect()` now refuses to
suppress a pure-alpha token when user-context words ("posted by", "user",
"author"…) appear within ±40 characters — "Check table KLEIN" stays cleartext,
"posted by KLEIN" is still redacted. Unambiguous shapes (underscore, digit,
`/NAMESPACE/`) suppress unconditionally, a shape a surname-style user ID
cannot take.

**The residual case:** a collision token with *no* context word inside the
window — a bare signature line, say — is still suppressed. So the mandatory
human review of mined candidates remains the controlling mitigation, now as
defence-in-depth rather than the only line. `mine_allowlist.py` makes that
review non-negotiable: it proposes exactly the tokens the scrubber would have
redacted, and its own test run surfaced `BJOHNSON`, `KMUELLER` and `MTANAKA` —
three real user IDs.

**Measured against the real exports (2026-08-15, read-only).** The 87 author
user IDs in `DD02L` were compared against all 257,584 Tier 1 tokens: **zero
collisions**. Neither Tier 1 source introduces a self-inflicted collision, and
`KLEIN` and `BRAUN` — the plan's worked examples — are absent from both. The
exposure is therefore narrower than assumed: it enters through the *optional*
corpus miner, not through `TSTC`/`DD02L`.

What the zero does **not** license is relaxing the review pass. 22,178 of the
extracted tokens are pure-alpha all-caps of 4–8 characters — the surname-shaped
range, `MARA` and `LIPS` among them. Each is a token the scrubber will refuse
to redact, and each rests on the `_in_user_context()` backstop when a real
person's user ID happens to share its spelling. The cross-check clears these
87 known IDs; it says nothing about a user ID that appears only in the incident
corpus.

**The candidates-file merge trap — fixed.** `_load_allowlist()` now strips
inline comments, so the miner's `TOKEN   # count=N` lines load as bare tokens.
The `sed 's/#.*//'` strip in the plan is now optional hygiene, not a
correctness requirement.

**Documentation staleness — fixed.** README config table documents
`CUSTOM_OBJECT_RULE` and the backstop; README-DEPLOY lists the rule among four
over-detection reduction paths and marks the 6 as re-verified on current code.

**`ES_SD_REBATE` is uncovered — unchanged.** The enhancement spot in sample
FSD-0001 has no `Z`/`Y` prefix, so the custom-object rule does not match it.
If it appears among the remaining over-detections, `TADIR` (Tier 2, currently
optional) is the fix.

**Verification status of the fixes:** statically verified on this machine
(compile, loader parse, context-regex behaviour, Dockerfile `COPY` line).
The full 15/15 runtime pass reported in `FIXES-2026-08-15.md` is confirmed at
Task 1 Step 3b, which now runs `python test_fixes.py` alongside the self-test.

---

## How to resume

1. Read `docs/superpowers/plans/2026-08-15-pii-scrubber-task-list.md` — the run
   sheet, with checkboxes, gates and a blocked-on-user table.
2. Consult
   `docs/superpowers/plans/2026-08-15-pii-scrubber-aicore-deployment.md` for the
   exact commands, expected output and rollback of whichever task is next.
3. `VSCODE-PROMPT-pii-scrubber-deploy.md` carries the 9 Hard Rules.
   `README-DEPLOY.html` is the authorization boundary — anything not in it needs
   a stop and an ask.

**Tasks 0 through 3 need nothing from anyone.** Only publishing and deployment
wait on the decisions above.

Every task ends at an approval gate with a stated deliverable and word limit.
Do not chain phases unattended — this runs against a shared corporate BTP
account with finite free-tier quota.

---

## Environment notes for this machine

- **System Python is 3.14.3**, which cannot install the pinned `torch==2.5.1` /
  `spacy==3.8.3` — no cp314 wheels. The pins do not change; the interpreter
  does. Use `uv venv --python 3.12 --seed .venv`. The `--seed` flag is
  mandatory: without it the venv has no pip, `pip install` escapes to the system
  Python, and `python -m spacy download` fails for the same reason.
- **Docker** is running (server 29.2.1, 10 CPUs, 8.2 GB allocated).
- **Disk is tight** — roughly 20 GB free on a 90%-full volume, against an image
  of several GB. Do **not** run `docker system prune` to make room; an unrelated
  `frappe_docker` container and its images are present on this machine.

---

## Credentials

None are stored in this repository, and none should ever be. Registry tokens,
GitHub tokens and BTP client secrets are supplied at the moment of use via
environment variables and never committed, echoed into logs, or embedded in a
git remote URL. The AI Core `docker-registry-secret` is created in the AI
Launchpad cockpit by a human, not by tooling.

If the image lands in a private `ghcr.io` namespace, that secret must target
`https://ghcr.io` — not `https://index.docker.io`, which is what the runbook's
example shows.
