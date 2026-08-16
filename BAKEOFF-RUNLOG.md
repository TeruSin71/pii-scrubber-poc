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

## Task 1 — MANDATORY fix + rebuild — 🔜 NOT STARTED

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
