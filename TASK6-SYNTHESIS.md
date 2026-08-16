# GLiNER Bake-off — Task 6 Synthesis and Recommendation

**Task 7 review-gate deliverable, 2026-08-16.** Measured against one frozen
artifact, `pii-scrubber:gliner-cand@sha256:d96edef4…c764912`, `git_sha 67fc888`,
read back on every arm. `GLINER_THRESHOLD` frozen at the image default `0.4`
throughout. Nothing pushed, deployment untouched, blind batch v4 untouched.

---

## 0. The headline, before any number

**GLiNER's recall contribution is real and complementary. Its over-redaction
on the batch path is worse than expected and is the blocker.**

⛔ **I cannot confirm the proposed shape "batch = both (pending readability)".**
The readability evidence came back against it, and the reason is structural
rather than a matter of taste — §4. The rest of the proposed shape I do
confirm.

---

## 1. Three-mode comparison

| | `presidio` | `gliner` | `both` |
|---|---|---|---|
| Selftest | `100.0 / 45-45 / od 4 / 49` | `93.3 / 42-45 / od 1 / 43` | `100.0 / 45-45 / od 4 / 49` |
| `holdout_samples` | 97.3% | 93.7% | **100.0%** |
| `eval_samples_v2` | 95.6% | 92.6% | **100.0%** |
| `holdout_v3` | 90.0% | 92.0% | **100.0%** |
| Over-redaction | 31/297 = **10.4%** | 57/313 = 18.2% | 76/351 = **21.7%** |
| Controls damaged | **2 of 21** | 6 of 21 | **8 of 21** |
| p50 latency | **6 ms** | 688 ms | 702 ms |
| 65-sample batch | **0.5 s** | 48.0 s | 48.9 s |
| 4-way concurrency | 1.07× | 0.51× | 0.51× |
| Peak RSS stressed | 456 MiB | 2.098 GiB | **2.175 GiB / 3 GiB** |
| Compressed image | — | — | **1.51 GB** |

⛔ **The three 100.0% figures are not results.** They are the predicted shape of
a burned set: presidio's residual on these corpora is PERSON-dominant, GLiNER's
leak lists contain zero PERSON, and these corpora are what taught us those
failures. **Nothing in this table is quotable.**

---

## 2. The durable finding — near-disjoint failure classes

| Engine | What it leaks |
|---|---|
| `presidio` | PERSON ×8, one bare ADDRESS, two CUSTOMER_NO |
| `gliner` | IBAN ×3, IP ×3, phone extensions, service accounts (`svc_*`), EMAIL ×2, CUSTOMER_NO ×2 |

**Zero overlap.** GLiNER reads names; the deterministic recognizers read
structure. This is a property of the engines, not of the corpora, and it is the
one part of §1 that survives the burned-set objection. **It is also why
`gliner` alone was retired**: it loses values presidio catches for free.

---

## 3. Confounds, named as required

1. **Threshold asymmetry.** Presidio spans pass per-type floors
   (`PERSON 0.50`); GLiNER spans pass one global `0.4` and never touch
   `TYPE_THRESHOLDS`. **Every claim here is configuration-level, never
   engine-level.** "GLiNER is more accurate" is unsupportable by construction.
2. **Merge-winner attribution — release documentation, per the ruling.**
   In union mode the per-engine split counts **which engine's span won
   `_merge`, not which engine detected the value.** presidio's on-value count
   falls **266 → 88** between its own arm and the union, purely because GLiNER
   spans are usually longer and win the overlap. Both engines still detect;
   one span survives. ⚠️ **Any future dashboard, alert or report that reads the
   `engine` field as "who found it" will be wrong**, and wrong in a direction
   that makes presidio look redundant. A coalesced span also keeps the
   **absorbing** span's engine, so boundaries are attributed to the absorber.
3. **Emulated latency.** Every figure is amd64-on-ARM, an **upper bound**. The
   native single-vCPU number is unmeasured and unmeasurable on this hardware.
4. **Burned corpora.** Engineering comparison and regression only.

---

## 4. ⛔ Why batch = both is NOT supportable on current evidence

The batch path exists to put readable text into a KB. Over-redaction there has
a real cost, and the measurement is not marginal:

| Arm | Control samples damaged (of 21 with zero planted PII) |
|---|---|
| `presidio` | **2** (9.5%) |
| `both` | **8** (38%) |

**Union damages four times as many clean samples.** What it redacts is not
borderline PII — it is SAP vocabulary:

```
[HO-015]  'plant'                 -> <ORG_NAME>     [V2-064] 'plant 4000'            -> <ORG_NAME>
[HO-015]  '4000'                  -> <CUSTOMER_NO>  [V2-064] 'storage location 0001' -> <ADDRESS>
[HO-015]  'customer'              -> <PERSON>       [V3-033] 'plant 4100'            -> <ORG_NAME>
[V3-040]  'VF04 collective run'   -> <ORG_NAME>     [V3-040] 'header level'          -> <ADDRESS>
```

`HO-015` is a control line that says, in words, *"No customer or personal data
in this one"*. Union renders it **"No `<PERSON>` or personal data in this
one"**. That is not a readability blemish; it is the sentence being destroyed.

### The cause is structural, which is why it cannot be waved through

This is the **SAP-jargon over-redaction class** the glossary was built to fight
— and **the glossary structurally cannot reach it**. Suppression matches an
**exact token** against `ALLOWLIST_EXACT`; GLiNER emits **multi-word spans**
(`plant 4000`, `storage location 0001`, `VF04 collective run`), so the lookup
never fires. Adding words to the glossary will not help, because the failure is
in the matching shape, not the vocabulary. **R1 of the plan's risk register
predicted exactly this, and it fired.**

### And the two paths' requirements are inverted

| Path | Tolerates | Does not tolerate | GLiNER's liability there |
|---|---|---|---|
| **batch** | latency — it is async | over-redaction — text must stay readable | **over-redaction: 38% of controls damaged** |
| **live** | over-redaction — caller re-maps via `token_map` | latency — no human in the loop | **latency: 702 ms emulated upper bound** |

**GLiNER's two liabilities each disqualify it from a different path.** That is
the real result of this bake-off, and it is sharper than "union wins".

---

## 5. Recommendation

| Mode | Path | Recommendation |
|---|---|---|
| `gliner` | — | ⛔ **RETIRED** (ruled at Gate 0). Dominated: worse recall than union, and union costs only ~2% more |
| `both` | **live** | ⏸️ **DEFERRED to the pod latency gate**, fallback pre-stated: fail → live stays presidio |
| `both` | **batch** | ⛔ **NOT RECOMMENDED as it stands.** Blocked on over-redaction, cause named and addressable — see below |
| `presidio` | both paths | ✅ **Remains the shipped configuration** until one of the above clears |

**This is not a no-ship for GLiNER.** The recall contribution is real and the
blocker has a specific, testable cause. The unblocking work is **overlap-aware
suppression**: allow the allowlist/glossary to suppress a span that *contains*
or *overlaps* a protected token, instead of only one that equals it. That is a
**detection change** and needs its own plan, its own pre-registration and its
own both-directions evidence — it must not be folded in here.

⚠️ **The reviewer-restore token map becomes more important, not less.** If
batch ever ships as `both`, a human gate that can restore over-redacted jargon
is the mitigation for precisely this class. Promoted to the release plan's open
items, as directed — and it is now load-bearing rather than a nicety.

---

## 6. Pre-registered gates for the release that would follow

Registered now, before any release work, so no number acquires its explanation
afterwards. **Determinism was verified first** — the union arm reproduces
span-for-span including scores and engine, and by whole-corpus output hash — so
exact gates are safe to pin.

| Measurement | Registered value, `SCRUBBER_ENGINE=both` | Any other value |
|---|---|---|
| Selftest | `100.0 / 45-45 / missed 0 / over_detections 4 / spans 49` | ⛔ stop |
| `holdout_samples.json` | **`111/111`** | ⛔ stop |
| `eval_samples_v2.json` | **`68/68`** | ⛔ stop |
| `holdout_v3.json` | **`50/50`** | ⛔ stop |
| Over-redaction, union | **76 spans / 12 on controls / 8 controls damaged** | ⛔ stop, either direction |
| Peak RSS, stressed, 3 GB cap | **≤ 2.2 GiB** | ⛔ stop |
| Compressed image | **≤ 1.6 GB** | ⛔ stop |
| `/v1/info` | `engine: both`, `gliner_loaded: true`, `git_sha` matches the built commit | ⛔ stop |

⚠️ **Pinning recall at 100% makes those three gates one-sided** — they can only
fall. That is intended: after the union closes them, the burned sets can detect
regression and nothing else. **Over-redaction is the gate that can still move
in both directions**, which is why it is pinned as an exact count rather than a
ceiling.

⚠️ **The live-path latency gate cannot be pre-registered from here.** It is
measured on the pod at the release's verification step. Fallback, already
stated: fail → GLiNER batch-only, live stays presidio, and the residual returns
to the management Local-LLM question. Live concurrency policy if ever adopted:
**single-flight only** (0.51× measured).

---

## 7. Blind batch v4 — the only route to a quotable number

Run **ONCE**, against the **deployed** release, at its verification step,
authored externally and never seen by the executor before the run.

⚠️ **Its target depends on §5.** If batch does not ship as `both`, v4 measures
the presidio configuration and the union's contribution stays unquantified
outside burned data. **v4 is never a tuning corpus** — it is the instrument,
and tuning against it destroys it exactly as the other four were destroyed.

Salting priorities unchanged, plus one this bake-off adds: **SAP-vocabulary
control lines** (`plant 4000`, `storage location 0001`, `collective run`,
`header level`) — the class union damages, currently measurable only on burned
controls.
