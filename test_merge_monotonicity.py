"""
_merge coverage monotonicity -- the union must never un-redact a character.

THE DEFECT THIS PINS (found while planning the GLiNER bake-off, ruled a DEFECT
at Gate 0, 2026-08-16):

_merge kept spans greedily and DROPPED any span overlapping an already-kept
one, entirely -- including the part of it that nothing else covered. Adding a
second engine could therefore REMOVE protection:

    presidio P = [10, 20]   length 10
    gliner   G = [ 5, 18]   length 13   -> G outranks P (longer), P is dropped
    characters 18-20, which ONLY P covered, are left in cleartext

Both are redacting types, so the redaction-first rule does not separate them
and length decides. This is a leak mechanism, not a ranking preference.

THE INVARIANT, which is what a future change has to keep:

    For any text and any span set, the characters redacted by _merge are the
    union of the characters of every input span. Adding a span may only ADD
    covered characters, never remove one.

Monotonicity follows directly: coverage(presidio + gliner) is a superset of
coverage(presidio alone), because the second is a sub-union of the first.

WHY A REFERENCE IMPLEMENTATION LIVES IN THIS FILE. _merge_prefix() below is
the pre-fix algorithm, verbatim. It is here so the presidio-only regression
can be proved BYTE-IDENTICAL against real corpus spans rather than asserted
-- and so the RED case is demonstrably red against the real old code, not
against a paraphrase of it someone wrote from memory.

Run: python test_merge_monotonicity.py
"""
import json
import os
import random
import sys

os.environ.setdefault("SCRUBBER_ENGINE", "presidio")

import app as A  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    status = "ok  " if cond else "FAIL"
    print(f"  [{status}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


# --------------------------------------------------------------------------
# The pre-fix algorithm, verbatim from app.py before the 2026-08-16 fix.
# Do not "tidy" this. Its value is that it is the old behaviour exactly.
# --------------------------------------------------------------------------
def _merge_prefix(spans):
    spans.sort(key=lambda s: (
        0 if s["type"] in A.REDACT_TYPES else 1,
        -(s["end"] - s["start"]),
        -s["score"],
    ))
    kept = []
    for s in spans:
        if not any(s["start"] < k["end"] and k["start"] < s["end"] for k in kept):
            kept.append(s)
    kept.sort(key=lambda s: s["start"])
    return kept


def span(start, end, type_="PERSON", score=0.9, engine="presidio", text=None):
    return {"start": start, "end": end, "type": type_, "score": score,
            "engine": engine, "text": text if text is not None
            else "x" * (end - start)}


def covered(spans):
    """Set of character offsets covered by REDACTING spans only.

    Redacting is the only kind that matters for a leak: a non-redacting span
    is not protection, so counting it would let the invariant be satisfied by
    something that never redacts anything.
    """
    out = set()
    for s in spans:
        if s["type"] in A.REDACT_TYPES:
            out.update(range(s["start"], s["end"]))
    return out


def non_overlapping(spans):
    ordered = sorted(spans, key=lambda s: s["start"])
    return all(a["end"] <= b["start"] for a, b in zip(ordered, ordered[1:]))


print("=" * 70)
print("_merge coverage monotonicity")
print("=" * 70)

# --------------------------------------------------------------------------
print("\n1. THE REGISTERED EVICTION CASE -- verbatim from the plan (3.4b)")
# --------------------------------------------------------------------------
P = span(10, 20, "PERSON", 0.90, "presidio")
G = span(5, 18, "ADDRESS", 0.80, "gliner")

presidio_only = A._merge([dict(P)])
union = A._merge([dict(P), dict(G)])

cov_presidio = covered(presidio_only)
cov_union = covered(union)
lost = sorted(cov_presidio - cov_union)

print(f"     presidio-only covers: {min(cov_presidio)}-{max(cov_presidio)}  "
      f"({len(cov_presidio)} chars)")
print(f"     union covers:         {sorted(cov_union)[0]}-{sorted(cov_union)[-1]}  "
      f"({len(cov_union)} chars)")
print(f"     characters LOST by adding a span: {lost}")

check("P=[10,20] + G=[5,18]: union loses no character",
      not lost, f"lost {lost} -- chars only P covered were dropped with P")
check("P=[10,20] + G=[5,18]: union output stays non-overlapping",
      non_overlapping(union))

# the pre-fix implementation must FAIL this, or the test proves nothing
pre_union = _merge_prefix([dict(P), dict(G)])
pre_lost = sorted(covered(A._merge([dict(P)])) - covered(pre_union))
check("the reference (pre-fix) implementation DOES lose 18-20 "
      "-- proves this test can fail",
      pre_lost == [18, 19],
      f"expected [18, 19], got {pre_lost}")

# --------------------------------------------------------------------------
print("\n2. EDGE GEOMETRIES -- tie, nest, chain, non-redacting")
# --------------------------------------------------------------------------
cases = {
    "tie (equal length, equal score)":
        ([span(0, 10, "PERSON", 0.9)], [span(5, 15, "ADDRESS", 0.9, "gliner")]),
    "nested (added span strictly inside)":
        ([span(0, 20, "PERSON", 0.9)], [span(5, 10, "ADDRESS", 0.9, "gliner")]),
    "nesting (added span strictly contains)":
        ([span(5, 10, "PERSON", 0.9)], [span(0, 20, "ADDRESS", 0.9, "gliner")]),
    "chain (added span straddles two)":
        ([span(0, 10, "PERSON", 0.9), span(20, 30, "PERSON", 0.9)],
         [span(5, 25, "ADDRESS", 0.9, "gliner")]),
    "added span is NON-redacting":
        ([span(10, 20, "PERSON", 0.9)], [span(5, 18, "DATE", 0.99, "gliner")]),
    "kept span is NON-redacting, added is redacting":
        ([span(5, 18, "DATE", 0.99)], [span(10, 20, "PERSON", 0.5, "gliner")]),
    "identical spans, different engines":
        ([span(10, 20, "PERSON", 0.9)], [span(10, 20, "PERSON", 0.4, "gliner")]),
    "adjacent, not overlapping":
        ([span(0, 10, "PERSON", 0.9)], [span(10, 20, "ADDRESS", 0.9, "gliner")]),
}

for name, (base, added) in cases.items():
    base_out = A._merge([dict(s) for s in base])
    union_out = A._merge([dict(s) for s in base] + [dict(s) for s in added])
    lost = sorted(covered(base_out) - covered(union_out))
    check(f"{name}: no coverage lost", not lost, f"lost {lost}")
    check(f"{name}: output non-overlapping", non_overlapping(union_out))

# --------------------------------------------------------------------------
print("\n2b. COALESCING -- contiguous same-type only, never a gap, never a type")
# --------------------------------------------------------------------------
# Remedy B. Coalescing changes how coverage is PRESENTED, never what it is,
# so each case asserts the resulting span layout, not just the coverage set.
def layout(spans):
    return [(s["start"], s["end"], s["type"]) for s in spans]


# LEFT: remainder lands immediately after a kept span of the same type.
# [0,10) PERSON wins on length; [5,14) PERSON is reduced to [10,14) and must
# be absorbed, giving one span rather than two adjacent ones.
out = A._merge([span(0, 10, "PERSON", 0.9), span(5, 14, "PERSON", 0.8)])
check("coalesce LEFT: two contiguous PERSON spans become one",
      layout(out) == [(0, 14, "PERSON")], f"got {layout(out)}")
check("coalesce LEFT: text is reassembled in order",
      out[0]["text"] == "x" * 14, f"got {out[0]['text']!r}")

# RIGHT: remainder lands immediately before a kept span of the same type.
out = A._merge([span(10, 20, "PERSON", 0.9), span(4, 12, "PERSON", 0.8)])
check("coalesce RIGHT: remainder before a kept span merges into it",
      layout(out) == [(4, 20, "PERSON")], f"got {layout(out)}")

# BETWEEN: remainder exactly fills the gap between two same-type spans.
out = A._merge([span(0, 10, "PERSON", 0.95), span(14, 24, "PERSON", 0.94),
                span(8, 16, "PERSON", 0.5)])
check("coalesce BETWEEN: a remainder filling a gap joins both neighbours",
      layout(out) == [(0, 24, "PERSON")], f"got {layout(out)}")

# CROSS-TYPE: must NOT coalesce -- a merged span would mislabel part of itself.
out = A._merge([span(0, 10, "PERSON", 0.9), span(5, 14, "ADDRESS", 0.8)])
check("cross-type does NOT coalesce: fragments stay separate",
      layout(out) == [(0, 10, "PERSON"), (10, 14, "ADDRESS")],
      f"got {layout(out)}")

# NO GAP BRIDGING: same type, but not contiguous -- must stay two spans.
out = A._merge([span(0, 10, "PERSON", 0.9), span(20, 30, "PERSON", 0.9)])
check("no gap bridging: same-type spans with a gap stay separate",
      layout(out) == [(0, 10, "PERSON"), (20, 30, "PERSON")],
      f"got {layout(out)}")

# Coalescing must never invent coverage.
before = covered([span(0, 10, "PERSON"), span(20, 30, "PERSON")])
after = covered(A._merge([span(0, 10, "PERSON", 0.9), span(20, 30, "PERSON", 0.9)]))
check("coalescing adds no character that no span claimed",
      after == before, f"{sorted(after - before)} invented")

# --------------------------------------------------------------------------
print("\n3. PROPERTY TEST -- random geometries, not hand-picked examples")
# --------------------------------------------------------------------------
# The bug is a GEOMETRY CLASS. Examples do not cover a class, so the geometries
# are generated. Seeded so a failure is reproducible.
rng = random.Random(20260816)
TYPES = ["PERSON", "ADDRESS", "ORG_NAME", "EMAIL", "DATE", "URL"]
violations = []
overlaps = []
for trial in range(3000):
    n_base = rng.randint(1, 5)
    n_add = rng.randint(1, 5)
    base, added = [], []
    for _ in range(n_base):
        a = rng.randint(0, 60)
        base.append(span(a, a + rng.randint(1, 20), rng.choice(TYPES),
                         round(rng.uniform(0.3, 1.0), 2), "presidio"))
    for _ in range(n_add):
        a = rng.randint(0, 60)
        added.append(span(a, a + rng.randint(1, 20), rng.choice(TYPES),
                          round(rng.uniform(0.3, 1.0), 2), "gliner"))
    base_out = A._merge([dict(s) for s in base])
    union_out = A._merge([dict(s) for s in base] + [dict(s) for s in added])
    if covered(base_out) - covered(union_out):
        violations.append((trial, base, added))
    if not non_overlapping(union_out):
        overlaps.append(trial)

print(f"     3000 random base/added geometries, seed 20260816")
check("no trial loses coverage when spans are added",
      not violations,
      f"{len(violations)} violations, first at trial {violations[0][0] if violations else '-'}")
check("no trial produces overlapping output spans",
      not overlaps, f"{len(overlaps)} trials produced overlaps")

# the property must also be violated by the pre-fix code, or it is vacuous
pre_violations = 0
rng2 = random.Random(20260816)
for trial in range(3000):
    n_base = rng2.randint(1, 5)
    n_add = rng2.randint(1, 5)
    base, added = [], []
    for _ in range(n_base):
        a = rng2.randint(0, 60)
        base.append(span(a, a + rng2.randint(1, 20), rng2.choice(TYPES),
                         round(rng2.uniform(0.3, 1.0), 2), "presidio"))
    for _ in range(n_add):
        a = rng2.randint(0, 60)
        added.append(span(a, a + rng2.randint(1, 20), rng2.choice(TYPES),
                          round(rng2.uniform(0.3, 1.0), 2), "gliner"))
    if covered(_merge_prefix([dict(s) for s in base])) - covered(
            _merge_prefix([dict(s) for s in base] + [dict(s) for s in added])):
        pre_violations += 1
print(f"     pre-fix implementation violates on {pre_violations}/3000 trials")
check("the property is NOT vacuous -- pre-fix code violates it",
      pre_violations > 0,
      "pre-fix code passed too, so this property cannot detect the defect")

# --------------------------------------------------------------------------
print("\n4. PRESIDIO-ONLY REGRESSION -- byte-identical on real corpus spans")
# --------------------------------------------------------------------------
# The fix must not change the presidio path. Proved on REAL spans from every
# corpus, comparing new _merge against the verbatim pre-fix implementation --
# not asserted, and not measured on synthetic geometry.
CORPORA = ["samples.json", "holdout_samples.json", "eval_samples_v2.json",
           "holdout_v3.json"]
texts, missing = [], []
for fn in CORPORA:
    if not os.path.exists(fn):
        missing.append(fn)
        continue
    with open(fn) as fh:
        for s in json.load(fh)["samples"]:
            if s.get("text"):
                texts.append((fn, s["text"]))

print(f"     corpora read: {[c for c in CORPORA if c not in missing]}")
if missing:
    print(f"     ⚠️  ABSENT, NOT SCANNED: {missing}")
check("all four corpora present (an unread corpus is an unproven claim)",
      not missing, f"missing {missing}")

differing = []
for fn, text in texts:
    raw = A.detect_raw_spans(text) if hasattr(A, "detect_raw_spans") else None
    if raw is None:
        # No raw hook: rebuild the presidio span list exactly as detect() does,
        # WITHOUT calling _merge, so both implementations see identical input.
        raw = []
        for r in A.get_analyzer().analyze(text=text, language="en"):
            etype = A._norm(r.entity_type)
            floor = A.TYPE_THRESHOLDS.get(etype, A.DEFAULT_THRESHOLD)
            if float(r.score) < floor:
                continue
            raw.append({"start": r.start, "end": r.end,
                        "text": text[r.start:r.end], "type": etype,
                        "score": round(float(r.score), 3),
                        "engine": "presidio"})
    new_out = A._merge([dict(s) for s in raw])
    old_out = _merge_prefix([dict(s) for s in raw])
    key = lambda L: [(s["start"], s["end"], s["type"], s["text"]) for s in L]
    if key(new_out) != key(old_out):
        # Store the FULL text. An earlier version stored text[:70] and the
        # marker check failed on a correct fix, because the value it looks for
        # sits at offset 93 -- the harness truncated away the evidence it was
        # about to assert on. Truncation happens at print time only.
        differing.append((fn, text, key(old_out), key(new_out)))

print(f"     {len(texts)} corpus samples, presidio spans only")

# RE-PINNED at Gate 0 after remedy B, 2026-08-16. Byte-identity is NOT
# achievable on a sample where the defect actually fires -- any true fix
# changes it. So the registration is EXACTLY ONE delta, named, with its new
# output recorded verbatim below. A second delta is a STOP: it would mean the
# fix reaches presidio spans somewhere nobody has looked at.
EXPECTED_DELTAS = 1
HO012_MARKER = "Fields & Sons Pty"
# The pre-fix layout lost character 110, a period, because [102,111)
# 'Sons Pty.' was dropped whole for overlapping [93,110) 'Fields & Sons Pty'.
HO012_PREFIX_LAYOUT = (93, 110, "ORG_NAME", "Fields & Sons Pty")
HO012_POSTFIX_LAYOUT = (93, 111, "ORG_NAME", "Fields & Sons Pty.")

check(f"exactly {EXPECTED_DELTAS} presidio-only delta (re-pinned post-B)",
      len(differing) == EXPECTED_DELTAS,
      f"{len(differing)} samples differ -- more than one is a STOP per Gate 0")

if len(differing) == EXPECTED_DELTAS:
    fn, t, old, new = differing[0]
    check("the single delta is HO-012 'Fields & Sons Pty'",
          HO012_MARKER in t, f"unexpected sample: {t!r}")
    check("pre-fix layout is the recorded one (period LOST)",
          HO012_PREFIX_LAYOUT in old, f"got {old}")
    check("post-fix layout is the recorded one (period COVERED, ONE span)",
          HO012_POSTFIX_LAYOUT in new, f"got {new}")
    print(f"     recorded delta [{fn}]:")
    print(f"        pre-fix : {HO012_PREFIX_LAYOUT}")
    print(f"        post-fix: {HO012_POSTFIX_LAYOUT}")
    print("        -> scrubbed output '<ORG_NAME>.' becomes '<ORG_NAME>'")
elif differing:
    print("\n  ⛔ STOP -- more presidio-only deltas than the one registered.")
    for fn, t, old, new in differing[:5]:
        print(f"     [{fn}] {t[:70]!r}")
        print(f"        pre-fix : {old}")
        print(f"        post-fix: {new}")

# --------------------------------------------------------------------------
print("\n5. NO NEW CROSS-ENGINE SCORE RELIANCE")
# --------------------------------------------------------------------------
# Constraint from Gate 0: the fix must not introduce any new comparison
# between a presidio confidence and a GLiNER sigmoid. The sort key is the only
# place scores are compared, and it must be untouched.
import inspect  # noqa: E402
src = inspect.getsource(A._merge)
check("sort key still ranks (redacting, -length, -score) and nothing else",
      "-(s[\"end\"] - s[\"start\"])" in src and "-s[\"score\"]" in src)
check("no engine field is consulted in _merge",
      '"engine"' not in src.split("def _merge")[1].split("kept.sort")[0]
      or 's["engine"]' not in src,
      "an engine-aware tie-break would be a new cross-engine reliance")

print("\n" + "=" * 70)
if FAILURES:
    print(f"FAILED ({len(FAILURES)}): " + "; ".join(FAILURES))
    sys.exit(1)
print("ALL CHECKS PASSED")
