# Execution prompt — close the ADDRESS gap (P1)

Paste everything below the line into Claude Code in VS Code, in the
`NER POC` project folder.

---

## Skills

Use **superpowers** for plan/gate discipline, **ponytail** for
anti-over-engineering, and **caveman** for blunt, minimal implementation.
This is a small, deterministic, single-purpose addition. If you find
yourself designing a general-purpose international address parser, stop —
you have left the scope.

## Context

`pii-scrubber-poc` is deployed and running on SAP AI Core
(deployment `d321900053823717`). A holdout evaluation of 40 unseen synthetic
SAP tickets measured **93.7% recall (104 of 111 planted values)**. Full
method and findings: `holdout-evaluation-report.html` in this folder.

One failure class is a pure coverage hole rather than a tuning miss:

| Type | Planted | Caught | Recall |
|---|---|---|---|
| ADDRESS | 3 | 0 | **0%** |

There is no street-address recognizer in the service at all. Locality names
(`Wellington`) are caught incidentally by the NLP layer and mapped to
`ADDRESS`, which is worse than catching nothing — the output reads
`the <ADDRESS> office at 22 Willis Street`, so the redaction tag is present
while the identifying detail is not. A reviewer skimming for tags is misled.

**Your job: build the street-address recognizer. Nothing else.**

## Hard rules — violating any of these is a stop condition

1. **Never weaken existing detection to make anything pass.** If a change
   raises ADDRESS recall by lowering any other type, revert and report.
2. **`samples.json` is frozen.** Byte-identical at the end. It must still
   score `recall_pct 100.0`, `45/45`, `missed 0`.
3. **`test_fixes.py` must still pass 16/16.** (Historical note: `FIX-GATE1-ORG.md`
   records "17 checks". That was a miscount — the suite has emitted 16 since the
   ORG fix, with no checks inside conditionals. 16 is the invariant.)
4. **No outbound network calls at inference time.** No geocoding, no
   address-validation API, no postcode lookup service, no new library that
   phones home on import. This is a compliance boundary, not a preference.
5. **`holdout_samples.json` is a HOLDOUT. Do not open it, read it, grep it,
   or run against it until Gate 3.** Everything you build must be derived
   from the *class* description in this prompt, not from the specific
   strings that leaked. If you tune to those three strings the measurement
   is destroyed and the number becomes worthless.
6. **Synthetic data only.** No real customer data in any file, test, log or
   image.
7. Do not commit secrets. Do not handle BTP credentials — ask the human to
   run anything requiring them.

## Scope

**In scope:** a deterministic street-address recognizer for NZ and AU
address forms, registered into the Presidio analyzer, plus tests.

**Explicitly out of scope** — do not touch these, they are separate work
items with their own risk profiles:

- The person-context promoter (the `ZHANG` class). Separate prompt.
- The unpadded customer-number pattern (the `1045567` class). Separate prompt.
- The `en_core_web_sm` → `lg` model upgrade.
- The SAP jargon glossary for over-redaction.
- Anything touching `CUSTOM_OBJECT_RULE`, `ZY_SURNAME_GUARD`, the allowlist
  loader, or the merge ordering.

## The class specification

Build from this description. Do not go looking for the leaked examples.

An address match is a **street number**, followed by a **street name**,
followed by a **street-type keyword**, with optional unit prefix and optional
trailing locality.

**Street number** — digits, optionally with a letter suffix (`12A`) or a
range (`12-14`).

**Unit prefix (optional, precedes the number)** — `Unit`, `Flat`, `Apartment`,
`Apt`, `Level`, `Suite`, `Shop`, `Villa`, followed by a number or letter.
Also standalone `PO Box <n>` and `Private Bag <n>` forms, which have no
street component.

**Street name** — one to four capitalised words between the number and the
street type. **At least one is mandatory** (see the negative tests — this is
the rule that keeps SAP jargon out).

**Street-type keyword** — `Street`, `St`, `Road`, `Rd`, `Avenue`, `Ave`,
`Drive`, `Dr`, `Lane`, `Ln`, `Place`, `Pl`, `Terrace`, `Tce`, `Crescent`,
`Cres`, `Way`, `Highway`, `Hwy`, `Parade`, `Pde`, `Quay`, `Close`, `Court`,
`Ct`, `Grove`, `Boulevard`, `Blvd`, `Esplanade`, `Mall`, `Rise`, `Row`,
`Track`, `Valley`, `View`, `Walk`, `Circle`, `Loop`.

**Trailing locality (optional)** — after the street type, up to three
additional capitalised words and/or a four-digit NZ postcode, comma-separated.
The match should extend to cover the suburb, city and postcode when present,
because a partially-redacted address is still an identifying address.

**Case sensitivity.** Street names and types are capitalised in real text.
Match case-sensitively on the name and type tokens. Presidio patterns default
to `IGNORECASE` — this project already had a defect from that; use the
`CASE_SENSITIVE` flag constant already defined in `recognizers.py`.

## Required negative tests — SAP text that must NOT match

This is the part that matters. SAP prose is full of number-plus-word
sequences and the recognizer must not eat them.

| Text | Why it must not match |
|---|---|
| `3 Way match` / `three way match` | **Invoice verification term.** Number directly followed by a street type with no name token between. This is the single most likely false positive in MM text. |
| `2 Way match` | Same. |
| `Level 3 support ticket` | Unit prefix followed by a number, but no street name or type follows. |
| `movement type 601 configuration` | No street type. |
| `plant 4000 deliveries` | No street type. |
| `Close the order` | Street type with no preceding number-plus-name. |
| `Court of Auckland` | No leading number. |
| `40 open transfer orders` | No street type. |
| `Order 4500001234 Line 10` | No street type. |
| `Storage location 0001` | No street type. |

The mandatory-name-token rule kills the `3 Way match` family. Verify that
explicitly rather than assuming it.

## Positive test shapes — write your own values

Do **not** reuse the three strings from the holdout. Write fresh ones of
these shapes:

- Bare street line: `<number> <Name> <Type>`
- With suburb and city: `<number> <Name> <Type>, <Suburb>, <City>`
- With postcode: `... <City> <4-digit>`
- With unit prefix: `Unit <n>, <number> <Name> <Type>, ...`
- Multi-word street name: `<number> <Name> <Name> <Type>`
- Abbreviated type: `<number> <Name> Rd`
- `PO Box <n>, <City>`
- Embedded mid-sentence, and at end of sentence followed by a full stop.

## Tasks and gates

Stop at every gate. Report and wait.

### Gate 0 — plan, no code

Restate the scope in your own words. List the files you intend to change.
Confirm you have not opened `holdout_samples.json`. Flag anything in this
prompt you think is wrong or under-specified — including if you think the
class spec will produce false positives I have not listed. **Wait for
approval.**

### Gate 1 — recognizer plus unit tests

Implement in `recognizers.py`, following the existing recognizer style. Add
`ADDRESS` to the redacting types in `app.py` if it is not already there —
check first, since locality detection already emits the tag.

Add a test file `test_address.py` covering every positive shape and every
negative in the table above.

Report:

- `python test_address.py` — all pass
- `python test_fixes.py` — **16/16**
- `/v1/selftest` locally — **`recall_pct 100.0`, `45/45`, `missed 0`**
- `over_detections` — report the number. It was 6. If it moved, say by how
  much and which strings are new. An increase is acceptable if every new
  over-detection is a genuine address-shaped string; it is not acceptable if
  SAP jargon is being eaten.

**Wait for approval.**

### Gate 2 — independent verification batch

Write `address_verify_samples.json` — 20 new SAP-flavoured tickets in the
same schema as `samples.json`. Twelve containing addresses of varied shape,
eight containing the negative-test jargon and no address at all.

You are writing these blind to the holdout, which is the point: it is an
honest check that the *class* is covered rather than three specific strings.

Report recall on this batch and any false positives on the eight negatives.
**Wait for approval.**

### Gate 3 — holdout re-run (first time you may touch it)

Now run `python3 test_deployed.py holdout_samples.json` against the **local**
service, not the deployment. Ask the human if you need the endpoint switched.

Expected: ADDRESS moves 0/3 → 3/3, total 104 → **107 of 111 = 96.4%**, and
**nothing else moves**.

Report the full per-type table. If any other type dropped, that is a stop
condition — report and do not proceed.

If ADDRESS is not 3/3, do **not** patch the recognizer to make those three
strings pass. Report which shape was missed, and we will extend the class
spec and re-verify on a fresh batch. That distinction is the whole discipline.

**Wait for approval.**

### Gate 4 — rebuild and redeploy

Only after Gate 3 is approved.

- Rebuild `--platform linux/amd64`, tag `1.1.0`, push to
  `ghcr.io/terusin71/pii-scrubber:1.1.0`
- Update `workflows/serving_template.yaml` to the new tag
- Commit and push; the human will sync AI Core and create the configuration
  and deployment — **the free tier allows 1 pod**, so the existing deployment
  must be stopped and deleted first. Tell the human when you need this.
- After the new deployment reports RUNNING, the human runs the deployed
  selftest and the holdout script against it. Report both.

### Gate 5 — documentation

Update `README.md` (endpoints/config unchanged, but the recognizer list and
the verified-result caveat need it) and note in
`holdout-evaluation-report.html` that P1-address is closed, with the new
figure. Do not restate 93.7% as current once 96.4% is verified — supersede it
and keep the old number labelled as the pre-fix baseline.

## Definition of done

- ADDRESS 3/3 on the holdout, total 96.4%, no other type regressed
- `samples.json` byte-identical, still 45/45
- `test_fixes.py` 16/16, `test_address.py` all pass
- No new over-detections on SAP jargon; `3 Way match` provably safe
- No outbound calls added
- New image deployed and verified through the live endpoint
- Docs superseded, not just appended to

## If you disagree

If at any gate you think the instruction is wrong — the class spec is too
broad, a negative test is unrealistic, the expected number is miscalculated —
say so and stop. A correct objection at Gate 0 is worth more than a clean run
to Gate 4 on a bad spec. The last agent on this project caught a defect in my
documented baseline by refusing to proceed, and that was the right call.
