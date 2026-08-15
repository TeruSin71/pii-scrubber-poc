#!/usr/bin/env python3
"""
LABEL_MAP unknown-label warning (bundle 1.2.2, item 2). Trap 8.

The defect: _norm() falls back to `label.upper()` for any entity label
LABEL_MAP does not carry. That fallback lands outside REDACT_TYPES, so the
span is DETECTED and then silently discarded -- no warning, no log line, and
the value reaches the KB in cleartext. A detection that is thrown away is
indistinguishable from a detection that never happened.

This suite asserts the drop is announced, not that it stops happening.
Mapping FAC to a redacting type would be a detection change and needs its own
evidence; naming it is what turns a silent failure into a visible one.

Run: python test_label_map.py
"""
import os
import sys

os.environ.setdefault("SCRUBBER_ENGINE", "presidio")

import app as A  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    status = "ok  " if cond else "FAIL"
    print(f"  [{status}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


engine = A.get_analyzer()
nlp_engine = engine.nlp_engine

print("The unmapped-label check exists and reads the real pipeline")
check("app exposes unmapped_labels()", callable(getattr(A, "unmapped_labels", None)),
      "no unmapped_labels function on app")

if not callable(getattr(A, "unmapped_labels", None)):
    print(f"\nFAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)

found = A.unmapped_labels(nlp_engine)

# ---------------------------------------------------------------------------
# The live case. en_core_web_sm emits FAC; presidio neither maps it to a
# presidio entity nor ignores it, so FAC arrives at _norm unchanged,
# has no LABEL_MAP entry, and is dropped.
#
# This corrects the handover, which recorded the defect as reachable "only
# through en_core_web_lg, which is not shipped". It is reachable on the
# SHIPPED model, today.
# ---------------------------------------------------------------------------
print("The live case -- FAC leaks on the SHIPPED model, not only under lg")
check("FAC is reported as unmapped", "FAC" in found, f"reported: {found}")
check("FAC really has no LABEL_MAP entry",
      "FAC" not in A.LABEL_MAP and "fac" not in A.LABEL_MAP)
check("and therefore maps to a non-redacting type",
      A._norm("FAC") not in A.REDACT_TYPES,
      f"_norm('FAC') -> {A._norm('FAC')!r}")

print("No false alarms -- every mapped label stays quiet")
for lbl in ("PERSON", "LOCATION", "ORGANIZATION", "NRP", "DATE_TIME"):
    check(f"{lbl!r} not reported (it is mapped)", lbl not in found,
          f"reported: {found}")

print("Shape -- sorted, deduplicated, no ignored labels")
check("result is a sorted list", found == sorted(found), f"got {found}")
check("result has no duplicates", len(found) == len(set(found)), f"got {found}")
check("labels presidio ignores are not reported",
      not ({"CARDINAL", "MONEY", "PERCENT", "ORDINAL"} & set(found)),
      f"reported: {found} -- ignored labels never reach _norm")

# ---------------------------------------------------------------------------
# A warning nobody sees is the defect, restated. Assert it is actually logged
# at analyzer build, in a fresh process -- the module-level cache means an
# in-process rebuild would not re-emit it.
# ---------------------------------------------------------------------------
print("The warning is emitted at startup, in a fresh process")

import subprocess  # noqa: E402

proc = subprocess.run(
    [sys.executable, "-c",
     "import os; os.environ.setdefault('SCRUBBER_ENGINE','presidio');"
     "import app; app.get_analyzer()"],
    capture_output=True, text=True, timeout=600,
)
logged = proc.stderr + proc.stdout
check("startup logs a WARNING naming the unmapped label",
      "FAC" in logged and "LABEL_MAP" in logged,
      f"last log lines: {logged.strip().splitlines()[-3:]}")

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
