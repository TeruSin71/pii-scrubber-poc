# PII Scrubber — Overlap-Aware Suppression Plan

**GATE 0 — NOT ANSWERED. Nothing in this plan has been executed.** No code
changed, no build run, no gate re-measured, deployment untouched, blind batch
v4 unread. Authored 2026-08-16 against `b9c4185`, measured against the frozen
candidate `pii-scrubber:gliner-cand@sha256:d96edef4…c764912` / `git_sha 67fc888`
— the same artifact the bake-off measured.

**Predecessor.** The GLiNER bake-off closed NO-SHIP AS-IS at `2ff5802`. Its §13
verdict routed all further GLiNER work through one named blocker:
*"overlap-aware suppression — detection change, own plan, own Gate 0, own
pre-registration; readability measurement re-runs against the fixed
candidate."* This is that plan.

---

## ⚠️ READ THIS BEFORE §1 — Phase 1 measured the premise and it does not hold

The bake-off's diagnosis was that the glossary **structurally cannot reach**
the union's over-redaction because suppression matches an exact token while
GLiNER emits multi-word spans. **That half is correct and reproduced here.**
The inference drawn from it — recorded in `TASK6-SYNTHESIS.md` §4 and in
`docs/HANDOVER.md`'s START HERE block as *"Adding glossary entries cannot
help — the failure is the matching shape, not the vocabulary"* — leads a
reader to expect that fixing the matching shape unblocks the batch path.

**Measured, in the pinned container, against the recorded bake-off span dumps:**

| | |
|---|---|
| Control samples with zero planted PII | **21** |
| Damaged by the union today | **8** (38%) — the bake-off's blocker |
| Damaged spans that containment matching can reach | **1 sample fully** (`HO-029`), **1 partially** (`V3-040`) |
| Control damage after overlap-aware suppression, **any semantics** | **7 of 21 (33%)** |
| presidio-alone, for comparison | **2 of 21 (9.5%)** |

**Overlap-aware suppression moves the blocking metric from 38% to 33%.** It
does not unblock batch. The reason is not the matching shape: it is that the
damage is dominated by generic English role, facility and process nouns —
`customer`, `plant`, `warehouse team`, `service desk`, `buyer`, `vendor
master`, `storage location` — **none of which is in the glossary**, so no
matching rule can find them there. Matching shape and vocabulary are **jointly
necessary and separately insufficient**, and only the first is in scope here.

This plan is written in full for the work as scoped, because the scope is the
reviewer's to set and not the executor's to narrow. **Q1 puts the consequence
to Gate 0.** Everything downstream of §5 assumes the work proceeds.

---

## 1. Executive Summary

**Goal.** Teach the suppression layer to recognise a protected token *inside*
a detected span, not only a span equal to one — as a pre-registered detection
change with both-directions evidence, ending at a review gate with nothing
shipped.

**Why it is the named next step.** The union's over-redaction blocks the batch
path. Suppression is the only layer that can decline a span after both engines
have produced it, and it is engine-agnostic, so one change covers presidio and
GLiNER alike. It is also **detection-weakening — the most dangerous direction
this project has**, which is why it gets its own plan rather than a patch.

**⛔ This plan produces NO quotable figure, by construction.** All four
evaluation sets are burned. Every number below is regression, engineering
comparison, or a pre-registered gate. Blind batch v4 stays HELD and is not
read, run or salted here.

**Success criteria — all measurable, all blocking:**

| # | Criterion | Source |
|---|---|---|
| 1 | A **RED-first** failing case exists before the fix, on a control the change is measured to reach (`HO-029`, §11) | test output pre-fix |
| 2 | The **both-directions** case is RED for the rejected semantics and GREEN for the chosen one: `PO Box 91020, Auckland` stays redacted (§3.5) | test output |
| 3 | Recall gates **unmoved**: `108/111`, `65/68`, `45/50`, selftest `100.0 / 45/45 / missed 0`, leak lists line-by-line | four gates, presidio arm |
| 4 | Over-redaction moves **only** to the pre-registered per-set values of §6.1, in the pre-registered direction | span dump per arm |
| 5 | Coverage monotonicity still holds — `_merge`'s property test green, and suppression proved a **per-span pure filter** (§3.6) | `test_merge_monotonicity.py` + new property test |
| 6 | A **fresh, openly-readable** control corpus exists and the rule was developed against it, not against the burned sets (§Appendix B) | committed file |
| 7 | The 21-control readability re-measure re-run against the re-frozen candidate | `READABILITY-SAMPLES.md` v2 |
| 8 | Nothing pushed before the review gate; deployment untouched; v4 unread | `git log`, `docker images` |

**Time estimate.**

| Task | Budget | Risk |
|---|---|---|
| 0 — fresh control corpus, authored and committed | 60 min | no code |
| 1 — RED: failing cases for the chosen semantics, both directions | 45 min | no behaviour change |
| 2 — the change, GREEN, six suites, monotonicity re-proved | 75 min | ⚠️ detection change |
| 3 — four gates on the presidio arm (control) | 30 min | local |
| 4 — union arm: span dump, over-redaction, control damage, readability re-measure | 75 min | local, slow |
| 5 — ONE rebuild, sha-stamped, re-freeze | 45 min | ⚠️ build |
| 6 — ⛔ REVIEW GATE | — | nothing ships |

≈ 5.5 hours. Task 4 is slow because GLiNER is slow (48 s per 65-sample pass).

**Risk posture.** Low on the artifact — no deployment touch, no registry push,
one rebuild at the end. **High on inference and on detection:** this is the
first change in the project's history whose *purpose* is to redact less, and
the failure mode it can produce is a leak, not a defect anyone will notice in
a log.

---

## 2. Philosophy and Principles

1. **Suppression is detection-weakening. Its central risk is that it swallows
   a true value, and that risk is measured in both directions before the
   change lands, never after.** Promotion and suppression each need their own
   evidence; this plan owes the suppression half in full.
2. **Evidence before action.** Every fact in §3 carries the command or the
   file that produced it. Inherited facts are marked **[inherited]**.
3. **Measured through the real call path, never through a library.** Every
   probe in §3 ran inside the pinned image against `app.detect()` /
   `app.scrub()`, because a mechanism measured one layer off is this project's
   most expensive recorded error class.
4. **The rule is developed against fresh, openly-readable material.** The
   readability failures were observed on burned-set controls; designing
   against those exact examples and re-measuring on the same sets is circular.
   Burned sets are **regression gates only** in this plan — they never inform
   the rule. §Appendix B.
5. **⛔ Blind batch v4 is not a tuning corpus and is not read here.** It stays
   HELD for the union release's verification.
6. **Exact gates survive a detection change.** Recall gates and leak lists are
   pre-registered as **unmoved**. Over-redaction counts **are** expected to
   move, so the plan registers the **direction and the per-set value in
   advance**; unregistered movement in either direction is a stop.
7. **Derived is not measured.** §6.1's over-redaction expectations are
   *derived* from recorded span dumps by re-applying the candidate rule
   offline. They are registered as predictions and the run measures them. Each
   is labelled.
8. **Suppression must stay a per-span pure function of `(span, text)`.** That
   is what makes the union-coverage monotonicity invariant survive this change
   by construction rather than by re-argument. §3.6.
9. **Plan is the authorization.** Scope not covered by this document is a Gate
   0 question, never an assumption made mid-run.

---

## 3. Current State — verified ground truth

All measured 2026-08-16 inside
`pii-scrubber:gliner-cand@sha256:d96edef4…c764912` unless marked
**[inherited]**. Probe scripts and their output are listed in Appendix A.

### 3.1 The suppression loop, as the code holds it

`app.py:569-579`, inside `detect()`, **after** both engines have produced
spans and **before** `_merge`:

```python
kept = []
for s in spans:
    token = s["text"].strip().strip(".,;:'\"()")
    suppressible = (token in ALLOWLIST_EXACT) or is_custom_sap_object(token)
    if suppressible:
        unambiguous = ("_" in token or any(c.isdigit() for c in token)
                       or bool(NAMESPACE_RE.match(token)))
        if unambiguous or not _in_user_context(text, s["start"], s["end"]):
            continue
    kept.append(s)
spans = kept
return _merge(spans)
```

⚠️ **The bake-off plan's §3.4 cites this loop at `app.py:553-563`. That
reference is stale** — the `_merge` monotonicity fix moved it. The loop is at
**569-579** at `b9c4185`. Recorded because a line reference that silently
drifts is how a reader concludes the code changed when it did not.

Three properties follow directly, and all three are load-bearing:

| | Property | Consequence |
|---|---|---|
| a | The test is on the **whole span text**, stripped only of surrounding punctuation | A multi-word span never matches a single-word entry. This is the bake-off's structural finding, reproduced |
| b | Suppression is **per-span** and reads only `(span, text)` | Monotonicity is preserved by construction (§3.6) |
| c | It runs **before** `_merge` | The change cannot interact with coalescing unless it alters span boundaries — which only the TRIM semantics does |

### 3.2 The suppression set, as the artifact holds it

```
Allowlist loaded: 257556 tokens (total 257583)
Glossary loaded: 36 tokens (total 257619)
ALLOWLIST_EXACT size: 257619       multi-word entries: 0
_USER_CONTEXT_WINDOW: 40
```

One set, one loader, three sources: a 27-token built-in seed, `allowlist.txt`
(TSTC + DD02L), `glossary.txt` (37 entries / 36 newly-added tokens). Matching
is **case-sensitive on purpose** — it is the only thing separating `MARA` the
table from `Mara` the person. A parallel deterministic rule
(`is_custom_sap_object`) covers the `Z*`/`Y*` and `/NAMESPACE/` shapes.

⚠️ **There are zero multi-word entries today**, and `glossary.txt` records
that multi-token entries were **rejected** as brittle. So the seed question
"multi-word glossary terms vs multi-word GLiNER spans" has an empty left-hand
side at present — but nothing in the loader prevents one being added, and a
containment rule that tokenises on whitespace would silently never match it.
Q6.

### 3.3 ⚠️ What containment can actually reach — the headline measurement

Re-applying a containment test (`any token of the span is in ALLOWLIST_EXACT
or matches is_custom_sap_object`) to the recorded bake-off span dumps, using
the artifact's own set:

| Arm | Redacting spans | Over-detections | Already whole-span matchable (backstop refused) | **Newly reachable by containment** |
|---|---|---|---|---|
| `presidio` | 297 | 31 | 4 | **4** |
| `gliner` | 313 | 57 | 0 | **5** |
| `both` | 351 | 76 | 4 | **7** |

The seven the union gains:

```
TKT-0003  presidio ORG_NAME  'Invoice IDoc'           -> ['IDoc']
HO-028    presidio ORG_NAME  'FSD ZMM_VENDOR_PORTAL'  -> ['FSD','ZMM_VENDOR_PORTAL']   ALL tokens protected
HO-029    gliner   ORG_NAME  'FSD ZCO_ALLOC_CYCLE'    -> ['FSD','ZCO_ALLOC_CYCLE']     ALL tokens protected
V2-023    gliner   ADDRESS   'Hamilton DC'            -> ['DC']
V3-001    gliner   ORG_NAME  'CFO office'             -> ['CFO']
V3-026    gliner   ORG_NAME  'Sydney DC'              -> ['DC']
V3-040    gliner   ORG_NAME  'VF04 collective run'    -> ['VF04']
```

**And on the metric that blocked the batch path** — the 21 zero-PII controls:

```
TKT-0009  DAMAGED  'customer'[MISS]
HO-015    DAMAGED  'plant'[MISS] '4000'[MISS] 'customer'[MISS]
HO-021    DAMAGED  'config knowledge'[MISS]
HO-029    DAMAGED  'FSD ZCO_ALLOC_CYCLE'[REACH]
V2-064    DAMAGED  'storage location 0001'[MISS] 'plant 4000'[MISS]
V3-033    DAMAGED  'plant 4100'[MISS]
V3-034    DAMAGED  '400000'[MISS]
V3-040    DAMAGED  'VF04 collective run'[REACH] 'header level'[MISS]

controls 21 · damaged 8 · every damaging span reachable: 1 (HO-029)
                        · partially reachable: 1 (V3-040) · none: 6
```

**8 → 7 damaged, under every candidate semantics.** `V3-040` stays damaged
because `header level` is not reachable by any rule discussed here.

⚠️ **The 65 unreachable over-detections are not exotic.** They are generic
role, facility and process nouns that GLiNER types as PERSON or ORG_NAME:
`customer` ×6, `plant` ×6, `warehouse …` ×6, `service desk` ×3, `buyer` ×3,
`vendor master` ×2, plus nationality adjectives the glossary **deliberately
rejected** (`Australian`, `Dutch`, `Brazilian`, `German`) and real place names
it **deliberately rejected** (`Wellington`, `Auckland`, `Melbourne`). Reaching
this class is a vocabulary question and it is **out of scope here**. Q1.

### 3.4 The four spans that already match and are still not suppressed

Four of the eleven reachable over-detections are **whole-span matches
today** — the existing rule should have fired and did not. Measured through
`app.detect()`, not inferred:

| Sample | Token | In allowlist | Unambiguous | `_in_user_context` | Surviving span |
|---|---|---|---|---|---|
| `TKT-0002` | `PO` | ✅ | ✗ | **True** | `(54,56) ADDRESS 'PO'` |
| `HO-002` | `Incident` | ✅ | ✗ | **True** | `(28,36) ORG_NAME 'Incident'` |
| `HO-012` | `Restart` | ✅ | ✗ | **True** | `(112,119) PERSON 'Restart'` |
| `HO-035` | `QMEL` | ✅ | ✗ | **True** | `(116,120) ORG_NAME 'QMEL'` |

All four are **the ±40-character user-context backstop doing its job**
(`"posted by KLEIN"`, `"approved by planner"`, `"Assign follow-up to user"`).
**They are not a containment failure and containment will not change them.**
Anyone reading "11 reachable" as "11 fixable" is over-reading by four, which
is why the two columns are reported separately in §3.3. Q5 decides where the
backstop is evaluated once a span is bigger than the token.

### 3.5 ⛔ Both-directions exposure — measured, on values that ship redacted

Scanning all 274 planted values across the four corpora for values that
**contain** a protected token, then putting each through `scrub()` in union
mode:

| Sample | Planted value | Protected token | User context | Currently redacted | Whole-span containment would expose it |
|---|---|---|---|---|---|
| `V3-024` | `PO Box 91020, Auckland` | `PO` | False | ✅ yes | ⛔ **YES** |
| `V2-010` | `PO Box 4471, Palmerston North 4440` | `PO` | False | ✅ yes | ⛔ **YES** |
| `V2-008` | `44 Bellbird Rise` | `Rise` | False | ✅ yes (union) | ⛔ **YES** |

```
V3-024 in : All invoices go to PO Box 91020, Auckland from September, …
       out: All invoices go to <ADDRESS> from September, …
       span [19,41) ADDRESS 'PO Box 91020, Auckland'  protected=['PO']
       >>> whole-span containment suppression would DROP this span: True
```

**This is the plan's central risk, and it is not hypothetical.** The naive
reading of "suppress a span that contains a protected token" un-redacts three
real postal addresses, two of them on the **presidio** path where the change
would be a live leak in shipped configuration. `V3-024` alone takes
`holdout_v3` from `45/50` to `44/50` on the control arm — a registered gate
falling, in the direction that matters.

⚠️ **`Rise` is the class the glossary already warned about.** It entered the
glossary in 1.2.1 as a process noun and it is also a street type. A rule that
lets a glossary word veto a span it merely *sits inside* hands every such
collision the power to un-redact.

### 3.6 Where suppression sits, and the invariant it must not break

Suppression runs **before** `_merge` and is a per-span filter. The union
monotonicity invariant fixed at the bake-off's Task 1 —

> coverage(`both`) ⊇ coverage(`presidio`)

— survives **only** while suppression stays a pure function of `(span, text)`.
It is preserved by construction today: the presidio span set is identical in
both modes, so a filter applied independently to each span removes the same
presidio spans in both. **A suppression rule that consulted the whole span
list — "suppress this span because another span covers it" — would break that
by construction**, and no amount of testing afterwards would restore the
argument. Recorded as a design constraint, not a preference. R6.

**TRIM semantics is the only candidate that alters boundaries**, and a trimmed
remainder re-enters `_uncovered` / `_absorb`. Coalescing joins **contiguous
same-type** spans only, and trimming leaves a gap exactly where the protected
token was, so a trimmed span cannot be re-joined across it. That is an
argument, not a measurement — it is registered as a property test in §11, not
accepted here.

### 3.7 Cost, determinism, case

- **Cost:** set membership against 257,619 tokens, `k` lookups per span where
  `k` = words in the span. Longest span observed in the bake-off dumps is 5
  words (`Australian ship-to failing address validation`). Against a
  GLiNER-dominated path at ~700 ms per request this is unmeasurable. **No
  index, no trie, no caching is warranted** — and building one would add a
  second copy of the suppression set to keep in sync.
- **Determinism:** set membership and regex; deterministic. The bake-off's
  determinism check (span-for-span, plus whole-corpus output hash) is the
  precondition for pinning exact gates and must be re-run after the change.
- **Case:** `ALLOWLIST_EXACT` is case-sensitive by design. Note that both
  `Customer` and `customer` appear in the over-detection list — a
  case-insensitive containment rule would be strictly more dangerous than the
  current exact-case one, because it multiplies the surnames a table name can
  veto. Q4.

### 3.8 Two documentation defects found while measuring

Neither is fixed here — **this session ships a plan, nothing else** — and both
are Gate 0 items because the correction rule requires a repo-wide grep
transcript attached to the commit that claims it.

1. **`GATE0-gliner-bakeoff-plan.md` at the repo root is a stale staging copy.**
   It is byte-identical to
   `docs/superpowers/plans/2026-08-16-pii-scrubber-gliner-bakeoff.md` **except
   that it is missing §13 entirely** — the verdict. A reader sent to "§13 of
   the bake-off plan" and handed the root copy finds no §13. Third recorded
   instance of the correction-applied-in-some-places class. Q8.
2. **The vocabulary claim in the durable record over-reaches.**
   `TASK6-SYNTHESIS.md` §4 and `docs/HANDOVER.md` START HERE both read
   *"Adding glossary entries cannot help — the failure is the matching shape,
   not the vocabulary."* §3.3 measures the matching shape at **1 of 8 damaged
   controls**. The sentence is true as written and false as read. Q1.

---

## 4. Decision Matrix

| # | Decision | Chosen | Why not the alternative |
|---|---|---|---|
| D1 | Where does the change live? | The suppression loop in `detect()`, `app.py:569-579` | It is the only engine-agnostic layer after detection; a recognizer-level fix would cover presidio only |
| D2 | Does the glossary/allowlist **file format** change? | **No** | Data stays data. Multi-word entries were rejected on their own evidence and re-opening that is a different change |
| D3 | Is a new list introduced? | **No** | One set, one loader. A second list is a second thing to keep in sync and an unauditable one |
| D4 | Is the ±40-char backstop weakened? | **No** | §3.4 measures it doing its job on four spans. Weakening it is promotion-side work with its own evidence burden |
| D5 | Is the custom-object rule in scope? | **Yes, unchanged** — it is applied per token exactly as today | It is already a token-shape test, so containment extends it for free |
| D6 | Does presidio-mode behaviour change? | **Yes, and it is pre-registered** — §6.1 | Pretending a shared code path is union-only is how a control arm moves unexplained |
| D7 | Is the fresh corpus committed or gitignored? | **Committed** | It is a development verification set; visibility is its purpose. The `address_verify_samples.json` precedent |
| D8 | Rebuild? | **One**, at Task 5, sha-stamped, then re-frozen | Same discipline as the bake-off's Task 1. Measurement before the rebuild runs in the venv against the same source |

---

## 5. Gate 0 — questions for the reviewer, with a recommendation each

**Q1 — the scope question, and the one that matters.** §3.3 measures
overlap-aware suppression at **8 → 7 damaged controls (38% → 33%)** against
presidio's 2 (9.5%). It does not unblock batch. Does this work proceed as
scoped, proceed **paired with a glossary-vocabulary item**, or stop pending a
re-decision?
→ **Recommendation: proceed as scoped, and treat it as necessary-not-
sufficient rather than as the unblocker.** The rule is small, its risk is
containable, and the vocabulary question cannot be answered honestly until
matching stops hiding it. But the durable record must be corrected in the same
breath (Q8), or the next session inherits the expectation that batch is now
unblocked.

**Q2 — semantics.** Three candidates, measured:

| Semantics | Rule | Union over-detections | Controls damaged | Planted values exposed |
|---|---|---|---|---|
| **ALL-TOKENS** | suppress iff **every** token in the span is protected | 76 → 74 *(derived)* | 8 → 7 | **0** |
| **TRIM** | remove the protected tokens' characters, keep the remainder redacted | 76 → 74, 5 spans shrink *(derived)* | 8 → 7 | **0** |
| **WHOLE** | suppress if **any** token is protected | 76 → 69 *(derived)* | 8 → 7 | ⛔ **3** (§3.5) |

→ **Recommendation: ALL-TOKENS.** ⛔ WHOLE is disqualified by measurement, not
by taste. TRIM and ALL-TOKENS repair the identical set of controls; TRIM buys
five shorter spans for a boundary rewrite that re-enters `_merge`, re-opens the
monotonicity argument and can render `"<ADDRESS> Rise"`. **ALL-TOKENS is a
two-line change that cannot expose a character the current code protects,
because it only drops spans whose every token is already suppressible
alone.** If the reviewer wants the five shrunk spans, TRIM is the fallback and
§11 covers it.

**Q3 — does the rule apply to both engines?**
→ **Recommendation: yes, unchanged.** Suppression is engine-agnostic today and
splitting it would create a per-engine detection policy nothing else in the
codebase has. The presidio-side effect is pre-registered in §6.1.

**Q4 — case sensitivity.**
→ **Recommendation: keep exact-case, unchanged.** §3.7. A case-insensitive
containment rule multiplies the surnames a table name can veto, which is the
leak the case-sensitivity decision was made to prevent.

**Q5 — where is the ±40-char backstop evaluated once a span is larger than the
token?** At the span's offsets, or at the protected token's own offsets?
→ **Recommendation: the protected token's own offsets.** The backstop exists
because an SAP user ID is all-caps and byte-identical to an allowlistable
token; the question it answers is "is *this token* being used as an actor",
which is a property of the token's position. Under ALL-TOKENS a span is
suppressed only if **every** token clears the backstop at its own offsets.

**Q6 — multi-word entries.** None exist (§3.2) and the glossary rejected them.
Should the rule be defined so a future multi-word entry cannot silently never
match?
→ **Recommendation: yes, but as an assertion, not a feature.** A test that
fails if `ALLOWLIST_EXACT` ever gains a whitespace-bearing entry, naming this
plan. Cheaper than implementing phrase matching for a case that does not exist,
and it cannot rot silently.

**Q7 — does the fresh control corpus need reviewer authorship?**
→ **Recommendation: no.** It is a development verification set, openly
readable and committed; it produces no quotable figure. Only **v4** needs
external authorship, and v4 stays HELD.

**Q8 — the two documentation defects (§3.8).** Correcting them needs a
repo-wide grep transcript per the standing rule.
→ **Recommendation: authorize both as one docs-only commit at Task 0**, before
the code work, with the transcript attached. The stale root plan copy should
be deleted rather than re-synced — two copies drifted once already.

**Q9 — what if the readability re-measure at Task 4 confirms 7 of 21?**
→ **Recommendation: pre-state it now as a PASS for this plan and a
CONTINUED-BLOCK for the batch path.** A change can be correct, land, and not
unblock what it was hoped to unblock. Deciding that in advance is what stops
Task 4 from being re-read into a better result.

---

## 6. Pre-registration — written before anything runs

### 6.1 Registered values

⚠️ **Marked `[derived]` where the value comes from re-applying the candidate
rule to the recorded bake-off span dumps rather than from a run.** A derived
value is a **prediction under pre-registration**: the run measures it, and a
deviation is a stop exactly as a moved gate is.

**Control arm — `SCRUBBER_ENGINE=presidio`. Recall does not move. At all.**

| Measurement | Registered | Any other value |
|---|---|---|
| Selftest | `100.0 / 45/45 / missed 0` | ⛔ stop |
| Selftest `over_detections` | **`4`, unchanged** `[derived]` — no `samples.json` span has all tokens protected | ⛔ stop, either direction |
| Selftest `redacting_spans_emitted` | **`49`, unchanged** `[derived]` | ⛔ stop |
| `holdout_samples.json` | `108/111`, leaks `ZHANG` `Young` `Mere Tuhoe` | ⛔ stop, rise or fall |
| `eval_samples_v2.json` | `65/68`, leaks `44 Bellbird Rise` `Okonkwo` `FONTAINE` | ⛔ stop, rise or fall |
| `holdout_v3.json` | `45/50`, leaks `NAKAMURA` `Park` `Adeyemi` `5591230` `6620945` | ⛔ stop, rise or fall |
| presidio-arm over-detections | **31 → `30`** `[derived]` — `HO-028 'FSD ZMM_VENDOR_PORTAL'` alone | ⛔ stop, any other count |

**Union arm — `SCRUBBER_ENGINE=both`.**

| Measurement | Registered | Any other value |
|---|---|---|
| `holdout_samples.json` | `111/111` | ⛔ stop |
| `eval_samples_v2.json` | `68/68` | ⛔ stop |
| `holdout_v3.json` | `50/50` | ⛔ stop |
| Union over-detections | **76 → `74`** `[derived]` — `HO-028` and `HO-029` | ⛔ stop, any other count |
| **Controls damaged** | **8 → `7` of 21** `[derived]` — `HO-029` repaired, `V3-040` still damaged by `header level` | ⛔ stop, any other count |
| `gliner`-arm over-detections, if the arm is run | 57 → `56` `[derived]` | ⛔ stop |

**The direction is registered as well as the value: over-redaction may only
fall, and only by the named spans.** A larger fall is a stop — it means the
rule reached something this plan did not predict, and an unpredicted
suppression is exactly the shape a leak takes.

### 6.2 Stop conditions

| # | Condition | Why it is a stop |
|---|---|---|
| S1 | Any recall gate moves, in either direction | The change is not supposed to alter recall at all |
| S2 | A leak list changes while its count does not | Two different sets of three leaks both read `108/111` |
| S3 | **Any planted value in any corpus becomes exposed** | The central risk of the whole plan. `V3-024`, `V2-010`, `V2-008` are the pinned cases |
| S4 | Over-redaction falls by more than the registered spans | An unpredicted suppression fired; find out what before continuing |
| S5 | `test_merge_monotonicity.py` fails, or the new suppression property test shows suppression reading anything but `(span, text)` | §3.6's invariant is broken by construction, not by accident |
| S6 | The RED case passes before the fix | A check that has never failed has not been shown to work |
| S7 | Determinism check differs from the bake-off's | Exact gates on a non-deterministic arm manufacture stops |
| S8 | The rule was tuned against a burned set at any point | §2.4. The fresh corpus exists so this cannot happen quietly |

### 6.3 What a PASS looks like, registered in advance

- **Rule ships:** every §6.1 value exact, S1–S8 silent, both-directions cases
  green, monotonicity re-proved, fresh corpus committed and the rule traceable
  to it.
- **Batch path unblocked:** ⛔ **not expected, and pre-stated as such.** 7 of
  21 controls damaged against presidio's 2. Q9.
- **No-ship of the rule** requires nothing; it is the default if the above are
  not met.

### 6.4 What downstream already expects from this plan

| Downstream item | What it inherits |
|---|---|
| The union release (queue item 5) | A re-frozen candidate with a sha, the §6.1 union gates as its own starting registration, and — per §6.3 — an **unchanged** batch blocker unless Q1 is re-scoped |
| Pod-latency gate | Untouched. Suppression adds `k` set lookups per span; §3.7. The gate stays a pod-time measurement with the presidio fallback pre-stated |
| Blind batch v4 | **HELD.** Still runs once, at the union release's verification. This plan does not read, run or salt it, and produces no quotable figure it could contaminate |
| `READABILITY-SAMPLES.md` | Re-generated at Task 4 against the fixed candidate, replacing the current file rather than sitting beside it |

---

## 7. Global constraints

- **Rule 3:** no outbound calls. Offline is an image property as of the
  bake-off's Task 1; probes still pass it explicitly.
- **Rule 7:** no dependency changes. Nothing in this plan needs one.
- **Rule 4:** no real ticket text.
- **⛔ Do not tune against the four burned sets, and do not touch v4.**
- **One rebuild**, at Task 5, after all measurement in the venv is green.
- **Nothing is pushed before the review gate.** No registry push grant exists;
  grants are per-release, exact-tag, at the publish step.
- **Deployment `daedcfe9342d21a7` (1.2.3, presidio) is not touched.**
- Every check prints what it inspected — corpora read, engine reported,
  semantics in force — not just a verdict.

---

## 8. Per-task runbook

### Task 0 — fresh control corpus + the two documentation corrections (60 min)

1. Author `jargon_suppression_samples.json` to the Appendix B spec. **Committed,
   openly readable**, `_provenance` block, `note` fields never transmitted
   (metadata-as-payload is a named trap class).
2. If Q8 is authorized: one docs-only commit correcting §3.8's two defects,
   **with the repo-wide grep transcript attached to the commit message**.

No approval gate. Report ≤200 words.

### Task 1 — RED first (45 min)

Three failing cases against **unmodified** `app.py`:

1. **The reach case:** `HO-029`'s `FSD ZCO_ALLOC_CYCLE` is redacted today and
   must not be after the change. ⚠️ **Not `HO-015`** — §3.3 measures `HO-015`
   as unreachable by any semantics in this plan, so a test written on it would
   be red before and red after, which is worse than no test.
2. **The both-directions case:** `V3-024`'s `PO Box 91020, Auckland` stays
   redacted. **This case must be RED against a WHOLE implementation and GREEN
   against ALL-TOKENS** — it is the test that encodes Q2's ruling, so it must
   be able to fail for the right reason.
3. **The property case:** over generated span/token geometries, suppression
   never removes a character that no protected token covers.

**S6:** each must fail before the change. Report the failure text.

### Task 2 — the change, GREEN (75 min)

The chosen semantics in the suppression loop. Then:

- the three RED cases green;
- **six suites** re-run — `test_fixes` 16, `test_address` 39,
  `test_customer_number` 33, `test_jargon` 74, `test_build_version` 29,
  `test_label_map` 37. Any movement is reported before anything proceeds;
- `test_merge_monotonicity.py` green, unchanged;
- a new assertion per Q6 if authorized.

`test_jargon.py` is the suite most likely to move — it owns suppression under
the context backstop — and any movement there is a **finding**, not an
expected consequence.

Report ≤300 words.

### Task 3 — control arm, four gates (30 min)

`SCRUBBER_ENGINE=presidio`. **Every §6.1 control value exact, leak lists
line-by-line.** A moved recall gate is S1 and the run stops there.

Report ≤250 words.

### Task 4 — union arm, span dump, control damage, readability (75 min)

`SCRUBBER_ENGINE=both`. `bakeoff_spans.py` per path, the union gates, the
control-damage count, and **`READABILITY-SAMPLES.md` regenerated** on the same
21 controls so the reviewer judges text rather than a count.

Diff the over-detection list against the recorded bake-off dump **row by row**,
not by count: the registered claim is that exactly `HO-028` and `HO-029`
disappear and nothing else changes.

Report ≤400 words plus the dump.

### Task 5 — ONE rebuild, sha-stamped, re-freeze (45 min)

Same discipline as the bake-off's Task 1: offline vars stay **after** the
prefetch layer, thread caps at both layers, `GIT_SHA` read back from
`/v1/info`, tokenizer gate re-proved **both directions** in the new image, new
digest recorded, previous candidate re-tagged before the tag is replaced.

⚠️ **Gates are re-run in the new image**, not inherited from the venv run —
tested artifact = deployed artifact under default invocation.

### Task 6 — ⛔ REVIEW GATE

Nothing pushed, deployment untouched, v4 unread. Deliverable: §6.1 measured
beside registered, S1–S8 each stated fired or not, the readability re-measure,
and an explicit answer to Q9 — whether the batch path is unblocked, in the
words the measurement supports.

---

## 9. Risk register

| # | Risk | L | I | Mitigation | Detection | Rollback |
|---|---|---|---|---|---|---|
| **R1** | **Suppression swallows a true value.** A protected token sits inside a real PII span (`PO Box …`, `44 Bellbird Rise`) | **High** | **Critical** — a leak in shipped configuration | Q2 disqualifies WHOLE on measurement; ALL-TOKENS cannot remove a character the current rule protects | S3; the three pinned cases; recall gates line-by-line | Revert the loop; it is one commit and one function |
| R2 | **The rule is developed against the burned controls it was found on** | **High** | High — the sets stop measuring | Appendix B's fresh corpus is authored **first**, at Task 0, before the rule exists | S8; the rule's tests must cite the fresh corpus, not a burned ID | Re-author against the fresh corpus |
| R3 | **The change is read as unblocking batch** when it moves 38% → 33% | **High** | High — a release opens on a false premise | §3.3 measured before the plan was written; Q1 and Q9 both force the statement in advance | Task 4's control-damage count against the registered 7 | None needed; it is a communication failure, and pre-registration is the guard |
| R4 | **A glossary word that is also a person name vetoes a real PERSON span** — the `Rise` class, one layer up | Medium | **Critical** | The ±40-char backstop is retained (D4) and evaluated at the token's own offsets (Q5) | Fresh-corpus controls (c); `test_jargon.py` | Revert |
| R5 | **The presidio path moves and the movement is waved through** as "we changed shared code" | Medium | High — a latent defect read as noise | The presidio delta is pre-registered to the exact span (`HO-028`) in §6.1 | Task 3 vs registered; any other count is S4 | Stop and dispatch the finding on its own terms |
| R6 | **Monotonicity broken by construction** — a rule that consults other spans | Low | **High** — union un-redacts | §3.6 states it as a design constraint; §2.8 as a principle | S5; the property test asserts the filter's inputs | Revert to a per-span filter |
| R7 | **TRIM's boundary rewrite interacts with `_absorb`** if TRIM is chosen at Q2 | Medium | Medium — split or mislabelled tokens | ALL-TOKENS is recommended precisely to avoid this; if TRIM wins, §11 adds the coalescing property test | `test_merge_monotonicity.py`; readability re-measure | Fall back to ALL-TOKENS |
| R8 | **A future multi-word entry silently never matches** | Low | Medium — a glossary entry with no effect, which reads as a fix | Q6's assertion fails the suite the moment such an entry appears | The assertion | — |
| R9 | **Scope creeps from suppression into vocabulary** — someone adds `plant`, `customer` mid-run | Medium | **High** — an unreviewed detection change, and the most dangerous words in the corpus | §12; Q1 routes vocabulary to its own decision | Any diff to `glossary.txt` during Tasks 1–5 | Revert the glossary; it is data |
| R10 | **Rebuild at Task 5 invalidates the venv measurements** by drifting from source | Low | High | Gates re-run in the image, not inherited (Task 5) | `git_sha` on `/v1/info` vs `git rev-parse` | Re-tag the previous candidate; it is preserved first |
| R11 | Disk exhaustion during the rebuild | Medium | Medium | `docker builder prune` only, with a before/after `docker images` diff proving zero removals | ~12 GB free against a 4.64 GB candidate | — |

---

## 10. Rollback

| Scope | Action |
|---|---|
| Mid-task, uncommitted | `git checkout -- app.py`. The change is one function in one file |
| Committed, unpushed | `git revert <sha>`. Nothing is pushed before Task 6 |
| Rebuild (Task 5) | The previous candidate is re-tagged under a dated tag **before** the `gliner-cand` tag is replaced — the bake-off's §9 precondition, which is the only reason its pre-fix baseline stayed reproducible |
| Deployment | **Not applicable.** `daedcfe9342d21a7` runs `1.2.3`, presidio, untouched throughout |
| Corpus | ⚠️ **The one irreversible act available here is burning a corpus.** v4 is not read, run or salted. The fresh corpus is openly readable by design and cannot be burned |

Known-good throughout: deployment `daedcfe9342d21a7` on `1.2.3`, selftest
`1.2.3 / 100.0 / 45/45 / missed 0 / over_detections 4`.

---

## 11. Verification strategy

| Level | Check | Exit criterion |
|---|---|---|
| RED | The three Task 1 cases against unmodified `app.py` | All three fail, with the failure text recorded (S6) |
| Unit | The three cases after the change | Green, and the both-directions case demonstrably red against WHOLE |
| Property | Generated span/token geometries: suppression removes no character no protected token covers; the filter reads only `(span, text)` | Green over ≥3000 trials, and **non-vacuous** — the pre-change rule must violate it |
| Property (TRIM only) | A trimmed remainder is never coalesced across the removed token | Green; skipped if ALL-TOKENS is chosen |
| Suite | Six suites, counts as registered | No movement; any movement reported first |
| Invariant | `test_merge_monotonicity.py` | Green, unchanged, still non-vacuous |
| Control | Four gates, presidio arm | Exactly §6.1, leak lists line-by-line |
| Union | Four gates + span dump + control damage, union arm | Exactly §6.1; over-detection diff row-by-row |
| Readability | 21 controls re-rendered | Reviewer judges text, not a count |
| Determinism | Re-run the union arm, compare span-for-span and by whole-corpus hash | Identical (S7) |
| Identity | `/v1/info` per run | `engine`, `gliner_loaded`, `git_sha` as expected |
| Hygiene | `git log`, `docker images` | Nothing pushed; exactly one new image |

**Non-vacuity is required, not optional.** Every property test in this plan
must be shown to fail against the pre-change code, because this project has
recorded three separate checks that passed against unmodified code.

---

## 12. What NOT to do

- ⛔ **Do not implement WHOLE-span containment.** §3.5 measures it exposing
  three real addresses. If Gate 0 overrules Q2, the three pinned cases must be
  re-registered as expected leaks first, in writing, before any code moves.
- ⛔ **Do not add words to `glossary.txt` in this plan.** The most tempting
  additions — `customer`, `plant`, `Warehouse`, `Buyer` — are ordinary English
  nouns, and the words that would repair the most controls are the words most
  likely to veto a real name. Vocabulary is Q1's, not this plan's.
- **Do not weaken the ±40-char user-context backstop.** It is measured doing
  its job on four spans (§3.4).
- **Do not derive the rule from a burned-set example.** They are illustrations
  of the failure class and regression gates; the rule is developed on the
  fresh corpus.
- **Do not touch v4** — not read, not run, not salted.
- **Do not build before Task 5**, and do not build twice.
- **Do not quote any figure this plan produces.** Every set is burned.
- **Do not read `engine` on a span as "who detected the value".** It records
  which span won `_merge`.
- **Do not touch the deployment or request a registry push grant.** A blocked
  action is a decision point, not an obstacle to route around.
- **Do not report the control-damage number without presidio's 2 of 21 beside
  it.** 7 of 21 read alone is an improvement; read beside 2 it is the blocker
  still standing.

---

## Appendix A — evidence trail

Every §3 number came from these, run read-only inside
`pii-scrubber:gliner-cand@sha256:d96edef4…c764912`. Scripts are in the session
scratchpad and are reproducible verbatim.

```bash
# The suppression set and containment reach, using the ARTIFACT's own set
docker run --rm -v "$(pwd)":/probe:ro -v <probe>.py:/tmp/p.py:ro \
  --entrypoint python pii-scrubber:gliner-cand /tmp/p.py

# probe 1  ALLOWLIST_EXACT size / multi-word entries / reach over the 76
#          union over-detections / planted values containing a protected token
# probe 2  zero-PII controls, damage, per-span reachability;
#          app.detect() on the four whole-span matches -> _in_user_context
# probe 3  app.scrub() engine=both: HO-015 reproduced, working suppression
#          reproduced, V3-024 / V2-010 / V2-008 both-directions cases
# probe 4  per-arm reach against bakeoff-spans-{presidio,gliner,both}.json
```

Inputs: `bakeoff-spans-{presidio,gliner,both}.json` (bake-off Tasks 3–5),
`samples.json`, `holdout_samples.json`, `eval_samples_v2.json`,
`holdout_v3.json`, `READABILITY-SAMPLES.md`, `glossary.txt`, `allowlist.txt`.

⚠️ **`eval_samples_v2.json` and the two holdouts are gitignored and local to
this Mac.** All four were present for every probe above — the corpora line is
printed by each script. A probe run without them measures a different corpus
under the same label.

---

## Appendix B — `jargon_suppression_samples.json`, the fresh control corpus

Authored at Task 0, **committed**, openly readable, never quoted. Its job is
to let the rule be developed and its safety proved without touching a burned
set. Four classes, and the last two are the ones that make it honest:

| Class | Content | Asserts |
|---|---|---|
| (a) **Reach** | SAP jargon inside multi-word spans, built from vocabulary **already in the glossary** — `FSD Z*_*`, `VF04 collective run`, `… DC`, `CFO office`, `Basis`, `PGI`, `IDoc` | The rule fires where it should |
| (b) **Both-directions, value class** | Real PII values that **contain** a protected token: `PO Box …`, street names ending in glossary street-types, a person whose surname collides with a table name | ⛔ The value survives. This is R1's test |
| (c) **Both-directions, person class** | Glossary words used as person names — `Driver`, `Payer`, `Rise`, `Way` — in subject position and behind user-context cues | The backstop still wins; a glossary entry vetoes a **pattern**, never **context** |
| (d) **Controls** | Zero-PII SAP prose using street-type words as ordinary nouns, and jargon with no protected token at all | The rule does not fire where nothing is protected |

Rules for the file, all from named trap classes:

- Every value appears **verbatim** in its `text`; no annotation text in any
  `text` field. Commentary goes in a `note` field the harness never transmits.
- Validated programmatically before use, not by reading it.
- It is a **development verification set**: it never produces a quotable
  figure, and it is not a gate. The burned sets stay the gates.
- It is **not** blind batch v4 and does not substitute for it.
