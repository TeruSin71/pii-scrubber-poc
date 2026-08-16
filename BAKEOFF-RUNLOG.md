# GLiNER Bake-off — Run Log

Execution record for
`docs/superpowers/plans/2026-08-16-pii-scrubber-gliner-bakeoff.md` (revision 1).
Every entry states what was inspected, not just a verdict.

---

## Task 0 — pre-fix baseline + provenance — ✅ COMPLETE 2026-08-16

**Image under test:** `pii-scrubber:gliner-cand`,
digest `sha256:2fa85d674b3ab76bc7f424ddbb00e376e272c29b5f02887b0be04ba583fbdebd`,
`build_version` = `gliner-cand`, `SCRUBBER_ENGINE=presidio`.
⚠️ Emulated: `linux/amd64` image on an `arm64` host. Detection is deterministic
so this does not affect the numbers below; it affects **latency only**, which
Task 0 does not measure.

### 0.1 Provenance — ✅ ALL SIX MATCH, byte for byte

In-image `sha256sum` vs `git cat-file blob b5fbaf6:<file> | shasum -a 256`:

| File | sha256 | Match |
|---|---|---|
| `app.py` | `d17b9709…4430aec` | ✅ |
| `recognizers.py` | `50baa91e…2ccdbdc` | ✅ |
| `samples.json` | `0a634b57…b04811` | ✅ |
| `allowlist.txt` | `5a01a6eb…65f001e` | ✅ |
| `glossary.txt` | `5054e1dc…5ad7772` | ✅ |
| `requirements.txt` | `39f94720…4ce9d8b` | ✅ |

**§3.2's circumstantial argument is now a measured one.** The image was built
from exactly the tracked content at `b5fbaf6`.

⚠️ **What this does NOT prove**, stated so nobody over-reads it: it proves the
**build inputs** in the image match `b5fbaf6`, not that the layers above them
were produced from those inputs. That gap is what the git-sha stamp in Task 1
closes; until then the hashes are the strongest available evidence and are not
a substitute for a stamp.

**Installed pins verified inside the image**, matching `requirements.txt`:

```
gliner 0.2.16 · torch 2.5.1+cpu · huggingface_hub 0.36.2 · transformers 4.57.6
presidio_analyzer 2.2.357 · presidio_anonymizer 2.2.357 · spacy 3.8.3
onnxruntime 1.28.0 · optimum ABSENT  <- Rule 7 held, ONNX arm genuinely struck
```

### 0.2 Pre-fix `presidio` baseline — ✅ ALL FOUR EXACT

Read back from `/v1/info` first: `engine: presidio`, `gliner_loaded: false`,
`presidio_loaded: false` (lazy load, as designed).

| Measurement | Registered | Measured | |
|---|---|---|---|
| Selftest | `100.0 / 45/45 / missed 0 / over_det 4 / spans 49` | **identical** | ✅ |
| `holdout_samples.json` | `108/111` (97.3%) | **97.3%** | ✅ |
| `eval_samples_v2.json` | `65/68` (95.6%) | **95.6%** | ✅ |
| `holdout_v3.json` | `45/50` (90.0%) | **90.0%** | ✅ |

**Leak lists compared line by line, not by count — all three identical:**

| Corpus | Leaks |
|---|---|
| holdout | `ZHANG` · `Young` · `Mere Tuhoe` |
| v2 | `44 Bellbird Rise` · `Okonkwo` · `FONTAINE` |
| v3 | `NAKAMURA` · `Park` · `Adeyemi` · `5591230` · `6620945` |

Over-redaction on controls: holdout 1 (`HO-021`, `<PERSON>`), v2 clean,
v3 1 (`V3-034`, GL account typed `<CUSTOMER_NO>` — the accepted cost already on
record).

**This is the reference Task 2 gets diffed against.** If the post-fix control
arm matches these numbers but not these leak lists, that is the latent-defect
stop in §5.1.

---

## Disk operations — ✅ COMPLETE 2026-08-16, authorized

### D.1 `docker builder prune` — sanctioned, inventory diff clean

```
reclaimed: 3.26 MB
images before: 15    images after: 15    diff: EMPTY (zero images removed)
```

⚠️ **The executor's ~4.5 GB estimate was wrong and the tool had already said
so.** `docker system df` reported `Build Cache SIZE 4.507GB` but
`RECLAIMABLE 3.26MB`; the SIZE column was read and the RECLAIMABLE column was
not. The cache is 4.5 GB and nearly all of it is still referenced. **A figure
in the wrong column of the right table** — same family as the size figures in
D.2.

### D.2 `docker rmi pii-scrubber:gliner-spike` — AUTHORIZED, exact tag

**Authorization, verbatim, 2026-08-16, reviewer session relayed by Teru:**

> pii-scrubber:gliner-spike: DELETION AUTHORIZED — never pushed, never
> deployed, superseded; ban's purpose (rollback images) not implicated.
> Exact-tag rmi only; --digests diff proving exactly one removal;
> deletion + this authorization recorded in the run log.

```
Untagged: pii-scrubber:gliner-spike
Deleted:  sha256:03cb27067b192a9f3f9e9c4f459fc2c4d31b8ea48609d616e0ebed3d9f47655b

--digests inventory diff:  removals: 1   additions: 0
image count: 15 -> 14
```

**Exactly one removal. No rollback image touched** — `1.0.0`, `1.1.0`, `1.2.0`,
`1.2.1`, `1.2.2`, `1.2.3` all still present with unchanged digests.

⚠️ **Two measurement traps hit in one operation, both already named in
`HANDOVER.md` and both hit anyway:**

1. **`docker images` reported gliner-spike as 6.76 GB; the image store fell by
   6.13 GB** — close, but the tag's headline size counts shared layers, so it
   was never a promise of unique bytes. The handover's rule stands: for size
   claims, only `docker save | gzip | wc -c` is trusted.
2. **`df` immediately after the delete still read 6.3 GiB free** — unchanged,
   which looked like the deletion had freed nothing. It had; APFS reclaims
   asynchronously. Re-read moments later: **12 GiB free.** ⚠️ **Reading a
   filesystem gauge immediately after a large delete measures the gauge, not
   the filesystem** — and the wrong reading pointed at a wrong conclusion
   ("deleting 6.76 GB freed 0 bytes") that was briefly stated before the
   re-read corrected it.

### D.3 Free space confirmed

```
before:  6.3 GiB      after: 12 GiB
docker images total: 23.45 GB -> 17.32 GB
```

**Task 1's rebuild has headroom.** Expected incremental cost is small, not a
second ~4.6 GB image, **provided** the Dockerfile edits are placed so the
expensive layers stay cached — see the note in Task 1 below.

---

## Task 1 — MANDATORY fix + rebuild — ✅ COMPLETE 2026-08-16

### 1.1 `_merge` monotonicity — RED, remedy B, GREEN

**RED against unmodified `_merge`** — 3 failures, all coverage-loss:

```
registered case P=[10,20] + G=[5,18]   lost [18, 19]
chain (added span straddles two)       lost [0..4, 25..29]
property test, 3000 geometries         548 VIOLATIONS
```

⚠️ **The defect was a CLASS, not the one example.** 548 of 3000 random
geometries lost characters, and it was **live in presidio-only mode** — two
overlapping presidio spans are enough, no second engine required.

**Remedy B** (approved at Gate 0): coalesce a remainder into a **contiguous,
same-type** kept span. No gap bridging — coalescing can never redact a
character no span claimed. Cross-type remainders stay separate fragments.

**GREEN, all checks:** registered case · 8 edge geometries · 4 new coalesce
geometries (LEFT / RIGHT / BETWEEN / cross-type-stays-separate) · no-gap-
bridging · coalescing-invents-nothing · 3000 property trials · non-vacuity
(pre-fix still violates 548/3000) · no new cross-engine score reliance.

**Byte-identity, re-pinned in the same commit: 157 of 158 identical.**

```
HO-012   pre-fix : (93, 110, 'ORG_NAME', 'Fields & Sons Pty')   <- period LOST
         post-fix: (93, 111, 'ORG_NAME', 'Fields & Sons Pty.')  <- ONE span
         output '<ORG_NAME>.'  ->  '<ORG_NAME>'
```

The character shipped code was losing is a **period**. Recorded as assertions,
not prose, so a second delta anywhere is a STOP and a silent change to this one
cannot pass. **Remedy B removed the artifact** the first fix produced
(`<ORG_NAME><ORG_NAME>`, two tokens for one value).

⚠️ **A harness bug was found and fixed rather than worked around:** the
regression capture stored `text[:70]`, truncating away the very value the
marker assertion then looked for at offset 93 — a correct fix reported as a
failure because the harness discarded the evidence before asserting on it.

### 1.2 Artifact conditions — all four in ONE build

| | Change | Placement |
|---|---|---|
| sha | `GIT_SHA` build arg, surfaced on `/v1/info` | end, beside `BUILD_VERSION` |
| offline | `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` | ⚠️ **after** the prefetch, never by editing the early block |
| threads | `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1` | image **and** `ServingTemplate` |

Build: **3 min 02 s**, `linux/amd64`. Weight prefetch re-ran and reported
`GLiNER weights baked in OK` — the step that can now fail the build did not.

```
re-frozen  pii-scrubber:gliner-cand@sha256:d96edef4fc012217683d219f5f212fe4b420ccc2de5fd440d841ffb32c764912
pre-fix    pii-scrubber:gliner-cand-prefix-2026-08-16@sha256:2fa85d674b3ab76bc7f424ddbb00e376e272c29b5f02887b0be04ba583fbdebd
```

`/v1/info`: `build_version: gliner-cand-b`, **`git_sha: 67fc888`** — matches
`git rev-parse --short HEAD`. Provenance is now a stamped read.

Container env with **no `-e` flags passed**: `HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`.

### 1.3 Tokenizer gate re-proved on the new image — BOTH directions

| Direction | Invocation | Result |
|---|---|---|
| Offline | **default, no `-e` flag** | ✅ ALL TESTS PASS — 5 texts, 0 UNK, byte-perfect round trips, arbitration re-run |
| Online | `-e HF_HUB_OFFLINE=0` | ✅ **FAILS LOUDLY**, 2 checks, naming the cause |

⚠️ **The concern that baking offline in might make the guard untriggerable is
resolved by measurement:** `-e HF_HUB_OFFLINE=0` still overrides the image
default and the suite still fails, with the right diagnosis — *"this run is not
really offline and is exercising a prebuilt tokenizer.json"*. A guard that
cannot fail is not a guard, and this one still can.

---

## Task 2 — control arm on the re-frozen image — ✅ PASS 2026-08-16

`SCRUBBER_ENGINE=presidio`, `/v1/info` read back first
(`engine: presidio`, `gliner_loaded: false`, `git_sha: 67fc888`).

| Measurement | Registered §5.1 | Measured |
|---|---|---|
| Selftest | `100.0 / 45/45 / 0 / 4 / 49` | **identical** ✅ |
| `holdout_samples.json` | `108/111` | **97.3%** ✅ |
| `eval_samples_v2.json` | `65/68` | **95.6%** ✅ |
| `holdout_v3.json` | `45/50` | **90.0%** ✅ |

**Leak lists identical to Task 0's pre-fix capture, line by line, all three.**

**No latent-defect stop at corpus level.** The HO-012 delta is a period, which
is not a scored value, so it changes no leak list and no gate — the unit-level
regression is where it is visible, which is where it was registered.

---

## Task 1 — §9 precondition record

**§9 precondition satisfied before anything else:**

```
pii-scrubber:gliner-cand-prefix-2026-08-16
  @sha256:2fa85d674b3ab76bc7f424ddbb00e376e272c29b5f02887b0be04ba583fbdebd
```

Same digest as `gliner-cand` — two tags, one image, confirmed by
`docker images --digests`. The pre-fix candidate is now recoverable by name and
can reproduce Task 0's baseline after the rebuild replaces the `gliner-cand`
tag.

⚠️ **Layer-cache placement is load-bearing for this build, on time and disk.**
`Dockerfile:7-10` sets `TRANSFORMERS_OFFLINE=0` **early**, and editing that
line invalidates every layer below it — pip install, the spaCy download and the
1.1 GB GLiNER weight prefetch — turning a cheap rebuild into a full emulated
one that also writes a second copy of the expensive layers.

**So the offline vars must be ADDED in a late `ENV`, not edited in place.** The
early `TRANSFORMERS_OFFLINE=0` is *required at build time* for the weight
prefetch to download at all; the runtime value is set afterwards, where the
last `ENV` wins. This is the same reasoning that already placed `BUILD_VERSION`
after every `COPY`, and it is why the plan says "place them after the prefetch
layer" (§7, Task 1, item 3).

---

## Tasks 3–5 — the three arms — ✅ COMPLETE 2026-08-16

**One image, three runs, `pii-scrubber:gliner-cand@sha256:d96edef4…c764912`,
`git_sha 67fc888` read back on every arm.** Threshold frozen at the image
default `GLINER_THRESHOLD=0.4` throughout (Q5).

### Detection

| | `presidio` | `gliner` | `both` |
|---|---|---|---|
| Selftest | `100.0 / 45-45 / 0 / od 4 / 49` | `93.3 / 42-45 / 3 / od 1 / 43` | `100.0 / 45-45 / 0 / od 4 / 49` |
| `holdout_samples` | 97.3% | 93.7% | **100.0%** |
| `eval_samples_v2` | 95.6% | 92.6% | **100.0%** |
| `holdout_v3` | 90.0% | **92.0%** | **100.0%** |

⛔ **THE 100% IS NOT A RESULT. IT IS THE PREDICTED SHAPE OF A BURNED SET.**
Presidio's residual on these three corpora is PERSON-dominant; GLiNER's leak
lists contain **zero PERSON**. A union of two engines whose failures barely
intersect closes sets whose failures were already enumerated. **These sets
taught us about exactly these values.** Nothing here may be quoted, and the
only instrument that could produce a quotable figure is blind batch v4.

### The failure sets are nearly disjoint — the actual finding

| Engine | What it leaks |
|---|---|
| `presidio` | PERSON (`ZHANG` `Young` `Mere Tuhoe` `Okonkwo` `FONTAINE` `NAKAMURA` `Park` `Adeyemi`), one bare ADDRESS, two CUSTOMER_NO |
| `gliner` | IBAN ×3, IP_ADDRESS ×3, phone extensions (`x2244` `x3319`), service accounts (`svc_payprop_prd` `svc_monitor_01`), EMAIL ×2, CUSTOMER_NO ×2 |

**Zero overlap.** GLiNER reads names and misses structured SAP/technical
values; the deterministic recognizers do the opposite. That is a complementarity
result, and it is the only part of the detection table that is not an artefact
of burned corpora.

### Over-redaction, per engine and per path

| Arm | Redacting spans | Over-detections | Rate |
|---|---|---|---|
| `presidio` | 297 | 31 | **10.4%** |
| `gliner` | 313 | 57 | **18.2%** |
| `both` | 351 | 76 (gliner 55 · presidio 21) | **21.7%** |

Dominated by `ORG_NAME` in every arm (presidio 20, gliner 34–35).

⚠️ **Batch vs live span attribution is IDENTICAL in all three arms** — measured,
not assumed. Detection is mode-independent; **the magnitude is the same and only
the COST differs**: on batch an extra redaction damages readable KB text, on
live the caller re-maps inside the boundary and it costs nothing. So
over-redaction is a **batch-path** argument only.

⚠️ **In union mode the per-engine split counts MERGE WINNERS, not detections.**
presidio's on-value count falls 266 → 88 between its own arm and the union,
because GLiNER spans are usually longer and win the overlap. Both engines still
detect the value; only one span survives `_merge`. Reading that 88 as "presidio
found less" would be wrong.

### Pod fitness — `--cpus=1 --memory=3g`, thread cap from the IMAGE

| Gate | `presidio` | `gliner` | `both` |
|---|---|---|---|
| Cold load | 3.1 s | 8.9 s | 9.7 s |
| p50, median sample | **6 ms** | 688 ms | **702 ms** |
| Longest document | 14 ms | 1,043 ms | 1,054 ms (max 1,332) |
| 65-sample batch | **0.5 s** | 48.0 s | **48.9 s** |
| 4-way concurrency | 1.07× | 0.51× | 0.51× (max 6,200 ms) |
| Peak RSS, stressed | 456 MiB (14.8%) | 2.098 GiB (69.9%) | **2.175 GiB (72.5%)** |
| OOM at 3 GB | no | no | **no** |

Compressed image, the only trusted method (`docker save | gzip | wc -c`):
**1,509,635,404 bytes = 1.51 GB.**

⛔ **Every latency figure above is an EMULATED amd64-on-ARM UPPER BOUND.** The
pod figure is unmeasured and unmeasurable here; per the Rule 7 decision the
live gate is answered at a release's verification step, with the fallback
pre-stated. **Do not quote 702 ms as the pod's latency.**

**Union costs ~2% over GLiNER alone** (702 ms vs 688 ms; 48.9 s vs 48.0 s;
2.175 vs 2.098 GiB). Presidio is essentially free once GLiNER is in the
process — so `gliner` alone is **dominated**: worse recall, leaks presidio
catches, and no latency saving. **If GLiNER ships at all, it ships as `both`.**

### Stop conditions — none fired

| | Condition | Result |
|---|---|---|
| S1 | engine / `gliner_loaded` read back per arm | ✅ all three correct, `last_load_error` null |
| S2 | union exposes something presidio redacted | ✅ union leaks **nothing** at all |
| S3 | over-detection of a type the engine has no label for | ✅ every GLiNER over-type is in `GLINER_LABELS` |
| S4 | threshold other than the frozen one | ✅ `0.4` image default, unchanged across arms |
| S5 | RSS > 3 GB or non-zero exit | ✅ max 2.175 GiB, all arms exit clean |
| S6 | corpora line differs between arms | ✅ `samples: 158`, same four files, all arms |
