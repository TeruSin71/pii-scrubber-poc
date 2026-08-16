#!/usr/bin/env python3
"""
Tests for OVERLAP-AWARE SUPPRESSION -- ALL-TOKENS semantics.

Run:  python test_overlap_suppression.py        (exit 0 = all pass)

Plan: GATE0-overlap-suppression-plan.md, Gate 0 answered 2026-08-16.
Corpus: jargon_suppression_samples.json -- authored at Task 0 BEFORE this rule
existed, openly readable, committed. The burned sets are regression gates only
and do not appear here; a rule developed against the controls its failures were
observed on is a rule measured against itself.

WHAT CHANGED. Suppression used to compare the WHOLE span text against
ALLOWLIST_EXACT. GLiNER emits multi-word spans, so the lookup never fired for
them. It now suppresses a span when EVERY token in it is independently
suppressible AND every token clears the +/-40-char user-context backstop at
ITS OWN offsets.

WHAT WAS REJECTED, AND WHY IT IS TESTED HERE. The obvious reading -- suppress
a span that CONTAINS a protected token -- was disqualified by measurement, not
taste: protected tokens live inside real values.

    'PO Box 91020, Auckland'   PO   is a glossary entry
    '44 Bellbird Rise'         Rise is a glossary entry

Section 3 carries that rejected semantics verbatim and PROVES it would expose
the values, so the both-directions assertions cannot pass vacuously. A check
that has never been shown to fail is a check that has not been shown to work.

Section 7 carries the PRE-CHANGE rule verbatim, for the same reason: the
property test must be shown to fail against it, and single-token behaviour is
proved identical rather than asserted.
"""

import json
import os
import random
import sys

os.environ.setdefault("SCRUBBER_ENGINE", "presidio")

import app as A  # noqa: E402

FAILURES = []
CORPUS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "jargon_suppression_samples.json")))
BY_ID = {s["id"]: s for s in CORPUS["samples"]}


def check(name, cond, detail=""):
    status = "ok  " if cond else "FAIL"
    print(f"  [{status}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def scrub_of(sid):
    return A.scrub(BY_ID[sid]["text"], "batch")


# --- the two rules NOT in force, carried verbatim so they can be disproved ---

def prefix_rule(text, span_text, start, end):
    """The rule as it stood until 2026-08-16. Verbatim."""
    token = span_text.strip().strip(".,;:'\"()")
    suppressible = (token in A.ALLOWLIST_EXACT) or A.is_custom_sap_object(token)
    if suppressible:
        unambiguous = ("_" in token or any(c.isdigit() for c in token)
                       or bool(A.NAMESPACE_RE.match(token)))
        if unambiguous or not A._in_user_context(text, start, end):
            return True
    return False


def whole_span_rule(text, start, end):
    """The REJECTED semantics: suppress if ANY token is protected."""
    toks = A._span_tokens(text, start, end)
    return bool(toks) and any(
        A._token_protected(t) and A._token_clears_backstop(text, t, s, e)
        for t, s, e in toks)


# ---------------------------------------------------------------------------
print("1. reach -- multi-token spans where EVERY token is already protected")
print("   (these over-redacted before the change; see the plan's Task 1 RED)")
for sid in ("JS-A01", "JS-A02", "JS-A05", "JS-A07"):
    smp = BY_ID[sid]
    out = scrub_of(sid)["scrubbed_text"]
    check(f"{sid} no longer over-redacts", out == smp["text"],
          f"got {out!r}")

print("   single-token protected spans keep behaving exactly as before")
for sid in ("JS-A06", "JS-D06"):
    smp = BY_ID[sid]
    out = scrub_of(sid)["scrubbed_text"]
    check(f"{sid} unchanged", out == smp["text"], f"got {out!r}")

# ---------------------------------------------------------------------------
print()
print("2. both directions -- a protected token INSIDE a real value")
print("   R1 of the risk register. These are the reason WHOLE was rejected.")
for sid in ("JS-B01", "JS-B02", "JS-B03", "JS-B04", "JS-B05", "JS-B06"):
    smp = BY_ID[sid]
    r = scrub_of(sid)
    for p in smp["pii"]:
        check(f"{sid} {p['type']} {p['value']!r} still redacted",
              A._covered(p["value"], r["entities"]) is not None,
              f"out={r['scrubbed_text']!r}")

# ---------------------------------------------------------------------------
print()
print("3. NON-VACUITY -- the rejected WHOLE semantics really would leak these")
print("   If this section ever goes quiet, section 2 has stopped proving")
print("   anything and the plan's central risk is untested.")
proved = 0
for sid in ("JS-B01", "JS-B02", "JS-B03"):
    smp = BY_ID[sid]
    r = scrub_of(sid)
    for s in r["entities"]:
        if s["type"] not in A.REDACT_TYPES:
            continue
        covers = any(p["value"] in smp["text"]
                     and s["start"] < smp["text"].index(p["value"]) + len(p["value"])
                     and smp["text"].index(p["value"]) < s["end"]
                     for p in smp["pii"])
        if not covers:
            continue
        would_drop = whole_span_rule(smp["text"], s["start"], s["end"])
        kept_now = not A._suppress_span(smp["text"], s["start"], s["end"])
        check(f"{sid} span {s['text']!r}: WHOLE drops it", would_drop)
        check(f"{sid} span {s['text']!r}: ALL-TOKENS keeps it", kept_now)
        proved += 1
check("at least three value-bearing spans exercised", proved >= 3,
      f"only {proved}")

# ---------------------------------------------------------------------------
print()
print("4. the backstop still wins -- a glossary entry vetoes a PATTERN,")
print("   never CONTEXT, and it is evaluated at each token's own offsets")
for sid, val in (("JS-C01", "Driver"), ("JS-C04", "Basis")):
    r = scrub_of(sid)
    check(f"{sid} {val!r} redacted behind a frozen cue",
          A._covered(val, r["entities"]) is not None,
          f"out={r['scrubbed_text']!r}")

print("   PRE-EXISTING cue-list boundaries, pinned as KNOWN -- not caused by")
print("   this change and deliberately NOT fixed here (promotion-side work)")
check("JS-C02 'Payer' leaks: 'approved by' is not a frozen cue "
      "('approver' is)",
      A._covered("Payer", scrub_of("JS-C02")["entities"]) is None)
check("JS-C03 'Way' leaks: 'countersigned by' is not a frozen cue",
      A._covered("Way", scrub_of("JS-C03")["entities"]) is None)

# ---------------------------------------------------------------------------
print()
print("5. controls -- nothing fires where nothing is protected")
for sid in ("JS-D02", "JS-D04", "JS-D05"):
    smp = BY_ID[sid]
    out = scrub_of(sid)["scrubbed_text"]
    check(f"{sid} clean", out == smp["text"], f"got {out!r}")

print("   PRE-EXISTING over-detections, pinned as KNOWN. The four")
print("   pre-cleared-but-unshipped street types are NOT in the glossary, so")
print("   no matching rule can reach them -- that is Q1's vocabulary question,")
print("   not this change's.")
d03 = scrub_of("JS-D03")["scrubbed_text"]
check("JS-D03 still over-redacts street-type nouns",
      d03 != BY_ID["JS-D03"]["text"])
for tok in ("Close", "Court", "Terrace", "Drive"):
    check(f"{tok!r} still unshipped", tok not in A.ALLOWLIST_EXACT)

# ---------------------------------------------------------------------------
print()
print("6. property -- suppression removes no character outside a protected")
print("   token, over generated geometries")
random.seed(20260816)
PROT = ["VF04", "FSD", "QMEL", "Basis", "DEV", "ZSD_REBATE_CALC", "PGI", "DC"]
FREE = ["plant", "customer", "Auckland", "Waititi", "collective", "the", "4000"]
CUES = ["", "", "", "posted by ", "reported by ", "user "]
trials = viol_now = viol_prefix = fired = 0
for _ in range(3000):
    n = random.randint(1, 4)
    toks = [random.choice(PROT if random.random() < 0.6 else FREE)
            for _ in range(n)]
    span_text = " ".join(toks)
    prefix = random.choice(CUES)
    text = f"{prefix}{span_text} in the ticket."
    start, end = len(prefix), len(prefix) + len(span_text)
    trials += 1

    if A._suppress_span(text, start, end):
        fired += 1
        parsed = A._span_tokens(text, start, end)
        # every character the span would have redacted lies inside a token
        # that is itself protected AND cleared the backstop
        if not all(A._token_protected(t) for t, _, _ in parsed):
            viol_now += 1
        if not all(A._token_clears_backstop(text, t, s, e)
                   for t, s, e in parsed):
            viol_now += 1
    # the pre-change rule on the SAME geometry, for non-vacuity below
    if prefix_rule(text, text[start:end], start, end) != \
            A._suppress_span(text, start, end):
        viol_prefix += 1

check(f"{trials} geometries, {fired} suppressions, zero violations",
      viol_now == 0, f"{viol_now} violations")
check("the property is NON-VACUOUS: the pre-change rule disagrees on "
      f"{viol_prefix} of {trials}", viol_prefix > 0)

# ---------------------------------------------------------------------------
print()
print("7. single-token spans are PROVED identical to the pre-change rule,")
print("   not asserted -- this is what holds the registered gate values")
same = diff = 0
for smp in CORPUS["samples"]:
    text = smp["text"]
    for s in A.detect(text, "presidio"):
        toks = A._span_tokens(text, s["start"], s["end"])
        if len(toks) != 1:
            continue
        a = A._suppress_span(text, s["start"], s["end"])
        b = prefix_rule(text, s["text"], s["start"], s["end"])
        if a == b:
            same += 1
        else:
            diff += 1
            print(f"      DIVERGENCE {s['text']!r} new={a} old={b}")
check(f"{same} single-token spans agree, {diff} diverge", diff == 0)

# ---------------------------------------------------------------------------
print()
print("8. structural guards")
import inspect  # noqa: E402
sig = list(inspect.signature(A._suppress_span).parameters)
check("_suppress_span is a PURE per-span filter -- (text, start, end) only, "
      "no span list; this is what preserves union-coverage monotonicity",
      sig == ["text", "start", "end"], f"got {sig}")

# Gate 0 Q6: an assertion, not a feature. If a multi-word entry is ever added
# it must break this test loudly rather than silently never match.
mw = sorted(t for t in A.ALLOWLIST_EXACT if any(c.isspace() for c in t))
check("no whitespace-bearing entry in the suppression set -- tokenisation is "
      "whitespace-delimited, so such an entry could never match (Gate 0 Q6)",
      not mw, f"found {mw[:5]}")

# Ordering matters: suppression must filter BEFORE _merge, or a suppressed
# span could already have absorbed a remainder from another span and the
# characters it carried would vanish with it. Asserted against the source,
# because "it is written that way" is not a check.
src = inspect.getsource(A.detect)
check("suppression runs BEFORE _merge in detect()",
      "_suppress_span" in src and "_merge(spans)" in src
      and src.index("_suppress_span") < src.index("_merge(spans)"),
      "ordering not provable from the source")

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
