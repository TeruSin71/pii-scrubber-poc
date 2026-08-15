#!/usr/bin/env python3
"""
Regression tests for the three defects found in the 2026-08-15 plan review.

Run:  python test_fixes.py        (exit 0 = all pass)

Not part of /v1/selftest on purpose -- samples.json is a frozen ground-truth
invariant (13 samples / 45 values) and must not change. These tests cover the
defect classes that invariant cannot see.
"""

import os
import re
import sys
import tempfile

os.environ.setdefault("SCRUBBER_ENGINE", "presidio")

FAILURES = []


def check(name, cond, detail=""):
    status = "ok  " if cond else "FAIL"
    print(f"  [{status}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


# --------------------------------------------------------------------------
# Defect 1: Dockerfile must ship allowlist.txt
# --------------------------------------------------------------------------
print("Defect 1 -- allowlist ships in the image")
with open(os.path.join(os.path.dirname(__file__), "Dockerfile")) as fh:
    docker = fh.read()
copy_lines = [l for l in docker.splitlines()
              if l.strip().startswith("COPY") and "app.py" in l]
check("COPY line includes allowlist.txt",
      bool(copy_lines) and "allowlist.txt" in copy_lines[0],
      f"line: {copy_lines[0] if copy_lines else 'NOT FOUND'}")

# --------------------------------------------------------------------------
# Defect 2: loader strips inline comments (miner format is consumable)
# --------------------------------------------------------------------------
print("Defect 2 -- inline comments in allowlist are stripped")
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("# full-line comment\n")
    fh.write("VBAK   # count=3  detected_as=USER_ID:3\n")
    fh.write("KUNNR\n")
    fh.write("   \n")
    tmp = fh.name
os.environ["ALLOWLIST_PATH"] = tmp

import app as A  # noqa: E402  (import AFTER setting ALLOWLIST_PATH)

check("miner-format line loads as bare token", "VBAK" in A.ALLOWLIST_EXACT)
check("no 46-char comment-token artifact",
      not any("#" in t or "count=" in t for t in A.ALLOWLIST_EXACT))
check("plain token still loads", "KUNNR" in A.ALLOWLIST_EXACT)
os.unlink(tmp)

# --------------------------------------------------------------------------
# Defect 3: all-caps user-ID collision backstop
# --------------------------------------------------------------------------
print("Defect 3 -- context backstop on pure-alpha suppression")

# Simulate the collision: KLEIN/BRAUN allowlisted (as DD02L-style tokens).
A.ALLOWLIST_EXACT.update({"KLEIN", "BRAUN", "MARA"})

# 3a. Technical mention, no user context -> suppressed (allowlist works).
t1 = "Check table KLEIN for the join condition against MARA."
out1 = A.scrub(t1, "batch")["scrubbed_text"]
check("technical mention stays cleartext", "KLEIN" in out1 and "MARA" in out1)

# 3b. User context -> suppression refused; the collision cannot hide a person.
t2 = "Incident posted by KLEIN, please review. Reported by user BRAUN today."
spans2 = A.detect(t2, "presidio")
texts2 = [s["text"] for s in spans2]
check("posted-by KLEIN survives as a span", any("KLEIN" in x for x in texts2),
      f"spans: {texts2}")
check("user BRAUN survives as a span", any("BRAUN" in x for x in texts2),
      f"spans: {texts2}")

# 3c. Unambiguous technical shapes stay deterministic even in user context
#     (the Gate-1 probe from the VS Code plan relies on this).
t3 = "Author Daniel O'Connor changed ZSD_REBATE_CALC and /SOVOSD/RFYTXDISPLAY."
out3 = A.scrub(t3, "batch")["scrubbed_text"]
check("ZSD_REBATE_CALC cleartext despite 'Author'", "ZSD_REBATE_CALC" in out3)
check("/SOVOSD/RFYTXDISPLAY cleartext", "/SOVOSD/RFYTXDISPLAY" in out3)
check("Daniel O'Connor still redacted", "Daniel O'Connor" not in out3)

# 3d. Surname guard unchanged: title-case Z/Y names never suppressed.
check("Zhang not treated as custom object", not A.is_custom_sap_object("Zhang"))
check("ZHANG not treated as custom object", not A.is_custom_sap_object("ZHANG"))

# --------------------------------------------------------------------------
# Invariant: ground-truth recall unchanged at 100%
# --------------------------------------------------------------------------
print("Invariant -- selftest recall")
r = A.selftest()
o = r["overall"]
check("recall_pct == 100.0", o["recall_pct"] == 100.0, str(o))
check("45/45 redacted", o["redacted"] == 45 and o["missed"] == 0)
print(f"  (over_detections measured: {o['over_detections']})")

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
