#!/usr/bin/env python3
"""
LABEL_MAP unknown-label warning (bundle 1.2.2, item 2). Trap 8.

The defect: _norm() falls back to `label.upper()` for any entity label
LABEL_MAP does not carry. That fallback lands outside REDACT_TYPES, so a span
carrying such a label is discarded with no warning and no log line, and the
value reaches the KB in cleartext.

⚠️ Corrected in 1.2.3, and the correction is why the wording above is careful.
This suite's original text said such spans are "DETECTED and then silently
discarded". That holds only for a label that actually reaches _norm(), and the
one label this check has ever reported does not: SpacyRecognizer does not
declare support for FAC, so it is dropped at the recognizer, before LABEL_MAP.
unmapped_labels() reports a SUPERSET of the labels that can leak -- it models
labels_to_ignore and the entity mapping, not supported_entities. See
fac_probe_validation.md and app.unmapped_labels' docstring.

This suite asserts the gap is announced, not that it stops happening.
Mapping FAC to a redacting type would be a detection change needing its own
evidence -- and, measured at Task 3 of 1.2.3, would also be a NO-OP, because
LABEL_MAP is not the layer that drops it.

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
# The live case. en_core_web_sm emits FAC and presidio neither maps it to a
# presidio entity nor ignores it, so it is genuinely unmapped.
#
# This corrects the handover, which recorded the defect as reachable "only
# through en_core_web_lg, which is not shipped". It is present on the SHIPPED
# model, today.
#
# ⚠️ What it does NOT mean, corrected 1.2.3: FAC does not arrive at _norm.
# SpacyRecognizer never emits it, so it is dropped a layer earlier. The
# _norm assertion below is about what WOULD happen to a FAC label reaching
# _norm -- it is a property of the fallback, not evidence that FAC gets there.
# ---------------------------------------------------------------------------
print("The live case -- FAC is unmapped on the SHIPPED model, not only under lg")
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
# 1.2.3 item 1. unmapped_labels() must read the ignore list the ENGINE was
# built with, not presidio's installed default.
#
# get_analyzer() un-ignores ORG. Reading the default happens to give the same
# answer -- but only because ORG is the ONE label in the default ignore list
# whose presidio entity is in LABEL_MAP. Measured: of the 11 ignored labels
# the model can emit, ORG is mapped and the other 10 are not. Un-ignore any
# of those ten and the diagnostic reports clean while the pipeline drops
# spans -- a silent diagnostic, which is the exact defect this file exists to
# catch. Correct today by coincidence, not by construction.
# ---------------------------------------------------------------------------
print("1.2.3 -- the diagnostic reads the ENGINE's ignore list, not the default")

from presidio_analyzer.nlp_engine import NerModelConfiguration  # noqa: E402

_cfg = NerModelConfiguration()
_default_ignore = set(_cfg.labels_to_ignore or [])
_mapping = _cfg.model_to_presidio_entity_mapping or {}
_model_labels = set()
for _nlp in (getattr(nlp_engine, "nlp", None) or {}).values():
    _model_labels |= set(_nlp.pipe_labels.get("ner", []))

# Premises, asserted rather than assumed -- if any is false the behavioural
# check below would fail for the wrong reason.
check("MONEY is ignored by presidio's default", "MONEY" in _default_ignore,
      f"default ignore: {sorted(_default_ignore)}")
check("MONEY is a label the model can emit", "MONEY" in _model_labels)
check("MONEY has no LABEL_MAP entry",
      _mapping.get("MONEY", "MONEY") not in A.LABEL_MAP,
      f"MONEY -> presidio {_mapping.get('MONEY', 'MONEY')!r}")

# The behaviour: un-ignoring MONEY must make it visible to the diagnostic.
_un_money = _default_ignore - {"MONEY"}
check("un-ignoring MONEY makes the diagnostic report it",
      "MONEY" in A.unmapped_labels(nlp_engine, labels_to_ignore=_un_money),
      "the diagnostic cannot see the engine's real ignore list")

# The list get_analyzer ACTUALLY uses must still give the shipped answer.
_keep = _default_ignore - {"ORG", "ORGANIZATION"}
check("the engine's real ignore list still yields the shipped result",
      A.unmapped_labels(nlp_engine, labels_to_ignore=_keep) == found,
      f"real={A.unmapped_labels(nlp_engine, labels_to_ignore=_keep)} default={found}")

# The call site is the point. A function that CAN take the real list, called
# without it, is the bug with extra steps.
_src = open("app.py").read()
check("get_analyzer() passes the engine's ignore list to unmapped_labels()",
      "unmapped_labels(nlp_engine, labels_to_ignore=keep)" in _src,
      "call site still uses the default -- the parameter is decorative")

# `keep` is bound INSIDE the try that adjusts NerModelConfiguration. If that
# try fails, passing `keep` raises NameError, the outer handler turns it into
# _load_error, and the analyzer never loads -- an optional diagnostic taking
# down detection entirely. Before item 1 that path degraded gracefully
# (ner_cfg stayed None, the engine built with presidio defaults). It must
# still degrade, so `keep` is initialised beside `ner_cfg`.
check("`keep` is initialised before the try that binds it",
      "ner_cfg = keep = None" in _src,
      "keep is only bound inside the try -- a NerModelConfiguration failure "
      "would raise NameError and take the whole analyzer down")

# ---------------------------------------------------------------------------
# 1.2.3 -- the class fix, not the instance.
#
# The `keep` guard above closes ONE way the diagnostic could take detection
# down. This closes the category: no exception from unmapped_labels() may
# reach the analyzer's error path, whatever its cause -- bad argument, a
# presidio internal change, a failure inside the log call itself.
#
# Advisory code must be unable to break the pipeline it advises on. A
# diagnostic that can take down the thing it diagnoses has negative value:
# it converts a reporting gap into an outage.
# ---------------------------------------------------------------------------
print("1.2.3 -- the diagnostic cannot break the pipeline it advises on")

_orig_fn = A.unmapped_labels


def _boom(*_a, **_k):
    raise RuntimeError("forced diagnostic failure")


try:
    A.unmapped_labels = _boom
    A._analyzer = None          # force a rebuild through the failing path
    A._load_error = None
    _eng = A.get_analyzer()
    check("analyzer still loads when the diagnostic raises",
          _eng is not None, f"get_analyzer() returned {_eng!r}")
    check("no _load_error recorded",
          A._load_error is None, f"_load_error={A._load_error!r}")
    check("detection still works after a diagnostic failure",
          any(s["type"] == "EMAIL"
              for s in A.detect("Contact k.mueller@corp.internal for the spec.",
                                "presidio")),
          "a failed advisory broke real detection")
finally:
    A.unmapped_labels = _orig_fn
    A._analyzer = None
    A._load_error = None
    A.get_analyzer()            # restore a clean analyzer for anything below

# ---------------------------------------------------------------------------
# A warning nobody sees is the defect, restated. Assert it is actually logged
# at analyzer build, in a fresh process -- the module-level cache means an
# in-process rebuild would not re-emit it.
# ---------------------------------------------------------------------------
print("The warning is emitted on first analyzer build, in a fresh process")

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

# ---------------------------------------------------------------------------
# 1.2.3 Task 5b -- the three corrections are PINNED.
#
# Task 4 corrected three descriptions and nothing asserted any of them. The
# suite checked only that "FAC" and "LABEL_MAP" appeared in the log, which
# survives ANY rewording -- including a full revert to the text that was
# measured wrong. A corrections-only release whose corrections no test can
# fail on is the "verification that cannot fail where it matters" trap,
# committed by the release that exists to eliminate it.
#
# Each correction is asserted in BOTH directions: the corrected claim is
# present AND the superseded claim is absent. Presence alone would pass if
# someone appended the new text and left the old text sitting above it.
#
# Whitespace-normalised, because markdown and docstrings get rewrapped and a
# correction that survives rewrapping is the one worth pinning.
# ---------------------------------------------------------------------------
print("1.2.3 Task 5b -- the three corrected descriptions are pinned")


def _flat(s):
    return " ".join(s.split())


_WRONG = "DETECTED and then silently dropped"

# Correction 1 -- the shipped log line.
check("log line states the supported_entities limitation",
      _flat("does not model recognizer supported_entities") in _flat(logged),
      f"log line: {[l for l in logged.splitlines() if 'LABEL_MAP has no' in l]}")
check("log line states a label may never reach the pipeline",
      _flat("may never reach the pipeline at all") in _flat(logged))
check("log line no longer claims the spans were DETECTED",
      _flat(_WRONG) not in _flat(logged),
      "the superseded 1.2.2 wording is back in the shipped log line")

# Correction 3 -- unmapped_labels' documented semantics.
_doc = A.unmapped_labels.__doc__ or ""
check("docstring calls the result a SUPERSET of the leak list",
      _flat("SUPERSET OF THE LEAK LIST, NOT THE LEAK LIST") in _flat(_doc),
      "docstring no longer states the superset semantics")
check("docstring names supported_entities as the unmodelled filter",
      _flat("does NOT model the third and narrowest, the registered "
            "recognizer's `supported_entities`") in _flat(_doc))
check("docstring states FAC never reaches _norm",
      _flat("FAC never reaches _norm") in _flat(_doc))

# The payload semantics ship with the value, not only in the docstring.
_sem = getattr(A, "UNMAPPED_LABELS_SEMANTICS", "")
check("UNMAPPED_LABELS_SEMANTICS exists and says SUPERSET, not leak list",
      "SUPERSET" in _sem and "NOT a leak list" in _sem,
      f"got {_sem[:80]!r}")
check("UNMAPPED_LABELS_SEMANTICS names supported_entities",
      "supported_entities" in _sem)
check("UNMAPPED_LABELS_SEMANTICS distinguishes null from []",
      "null =" in _sem and "[] =" in _sem)

# Correction 2 -- the handover's trap-8 mechanism. Local-only: docs/ is in
# .dockerignore and the image COPYs an explicit file list, so this file is
# never present in a container. Skip loudly rather than pass quietly.
_hpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "docs", "HANDOVER.md")
if not os.path.exists(_hpath):
    print(f"  [SKIP] handover trap-8 assertions -- {_hpath} not present "
          f"(expected in-container; a FAILURE if you see this locally)")
else:
    _h = _flat(open(_hpath, encoding="utf-8").read())
    check("handover trap-8 carries Correction 2",
          "Correction 2, measured 2026-08-16 at Task 3 of 1.2.3" in _h,
          "the _norm() correction is missing from docs/HANDOVER.md")
    check("handover states FAC does not reach _norm()",
          "It does not reach `_norm()`." in _h)
    check("handover names the recognizer as the layer that drops it",
          "before `LABEL_MAP` is consulted at all" in _h)
    check("handover states the diagnostic over-reports by construction",
          "over-reports, by construction" in _h)
    # Both-directions, without depending on punctuation: the superseded
    # mechanism may survive ONLY as a labelled record of what was wrong. If
    # the old phrasing is present anywhere, its refutation must be too.
    _old_here = "arrives at `_norm()` raw" in _h
    check("superseded '_norm() raw' mechanism never stands unrefuted",
          (not _old_here) or "It does not reach `_norm()`." in _h,
          "the pre-1.2.3 mechanism appears with no correction beside it")

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
