#!/usr/bin/env python3
"""
SPEC, NOT A LIVE TEST. This file does not run green -- it will raise
AttributeError on app._person_context_spans, because the promoter it
describes was built, measured, and deliberately NOT shipped.

Read PERSON-CONTEXT-FINDING.md first. The short version: the mechanism works,
but it reaches about one third of the residual PERSON class, and the rest
needs the NLP layer rather than more rules. This file is kept as the
executable spec for whoever picks that up -- the 24 checks below are the
behaviour a promoter would have to satisfy, including the negatives that
constrain it.

Do NOT wire this into a test runner until an implementation exists.

Original header follows.
---------------------------------------------------------------------------
Tests for the person-context promoter (P2 PERSON leak classes).

Run:  python test_person_context.py        (exit 0 = all pass, once implemented)

Every value here is written fresh for these tests. holdout_samples.json was
not opened while building the promoter -- the point of the holdout is
destroyed if the rule is tuned to its strings.

The promoter covers name-shaped tokens sitting in an explicit agent slot
("posted by ZHANG"). Cue-free actor position ("Young confirmed the date") is
NOT covered and cannot be, without the P3 jargon glossary -- see the
negatives at the bottom, which are what makes that so.
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


def raw_promoted(text):
    """
    What the promoter itself matched, BEFORE _merge and before spaCy.

    Negatives are checked here, not on scrub() output. A promoter false
    positive can be hidden post-merge by a longer span of another type -- that
    is exactly how '4 Goods Receipt Close' produced a false pass during the
    address work.
    """
    return [s["text"] for s in A._person_context_spans(text)]


def redacted(text, value):
    """The value is actually gone from the batch output, not merely detected."""
    return value not in A.scrub(text, "batch")["scrubbed_text"]


# --------------------------------------------------------------------------
# Positives -- the three leak classes, each in an explicit agent slot.
# --------------------------------------------------------------------------
print("Positive -- cued agent slot, one per leak class")

POSITIVES = [
    # class A: ALL-CAPS surname. spaCy's small model tags these as nothing at
    # all -- this is the class that produced zero spans before the promoter.
    ("all-caps surname",      "Ticket was posted by ZHANG on 12.03 for plant 1000.", "ZHANG"),
    ("all-caps, changed by",  "Line item changed by NGATA after the GR.",            "NGATA"),
    ("all-caps, on behalf",   "Raised on behalf of MCLEOD for the Napier DC.",       "MCLEOD"),
    # class B: single title-case surname.
    ("bare surname",          "The block was approved by Young last Tuesday.",       "Young"),
    ("bare surname, run by",  "Batch job run by Kaur failed with dump ST22.",        "Kaur"),
    # class C: full name.
    ("full name",             "Ticket reported by Mere Tuhoe against the DC.",       "Mere Tuhoe"),
    ("full name, created by", "Spec created by Hemi Walker in March.",               "Hemi Walker"),
    # shapes that must survive the name pattern
    ("hyphenated surname",    "Invoice entered by Anne-Marie Dubois on 03.04.",      "Anne-Marie"),
    ("apostrophe surname",    "Credit note requested by O'Brien for the rebate.",    "O'Brien"),
]

for name, text, value in POSITIVES:
    check(name, redacted(text, value), f"out: {A.scrub(text, 'batch')['scrubbed_text']}")

# The cue itself must NOT be swallowed. presidio 2.2.357 reports the whole
# match span, which is precisely why this is a post-pass and not a tenth
# PatternRecognizer -- if that regressed, "posted by ZHANG" becomes "<PERSON>"
# and the sentence stops being readable in batch mode.
print("Span extent -- the cue must survive, only the name goes")
out = A.scrub("Ticket was posted by ZHANG on 12.03 for plant 1000.", "batch")["scrubbed_text"]
check("cue words kept outside the span", "posted by <PERSON>" in out, out)

# Allowlist must not veto an explicit agent cue. This mirrors the existing
# _in_user_context rule: KLEIN is a real SAP table AND a real surname, and in
# an agent slot the person reading wins.
print("Allowlist must not veto an explicit cue")
check("allowlisted token in agent slot still redacted",
      redacted("Delivery note posted by KLEIN on Friday.", "KLEIN"),
      A.scrub("Delivery note posted by KLEIN on Friday.", "batch")["scrubbed_text"])

# --------------------------------------------------------------------------
# Negatives -- SAP prose that must NOT be promoted. This is the part that
# matters: the promoter runs after allowlist suppression, so nothing
# downstream will catch a false positive it creates.
# --------------------------------------------------------------------------
print("Negative -- no cue, no promotion")

NEGATIVES_NO_CUE = [
    ("sentence-initial SAP noun", "Invoice confirmed the delivery date with the carrier."),
    ("noun phrase subject",       "Delivery Note raised an error during the PGI run."),
    ("plain technical prose",     "Storage location 0001 is not assigned to the plant."),
    ("transaction code",          "VF04 was executed for the collective billing run."),
    ("two-word SAP jargon",       "Handling Unit Place assignments are missing."),
]

for name, text in NEGATIVES_NO_CUE:
    m = raw_promoted(text)
    check(name, not m, f"PROMOTED: {m}")

# The 'to' family of cues is deliberately excluded. In ticket text it takes a
# team or a queue, not a person, so including it would promote 'Level',
# 'Finance' and 'Basis' -- a new over-redaction class on top of the P3 one.
print("Negative -- 'to' cues are excluded on purpose (team/queue, not person)")

NEGATIVES_TO_CUE = [
    ("escalated to Level 3", "Escalated to Level 3 support ticket queue."),
    ("assigned to a team",   "Assigned to Finance for credit review."),
    ("routed to Basis",      "Routed to Basis for the ST22 dump."),
]

for name, text in NEGATIVES_TO_CUE:
    m = raw_promoted(text)
    check(name, not m, f"PROMOTED: {m}")

# The cue must be followed by something name-shaped. A lowercase word, a
# number or a T-code in the slot means the sentence is not naming a person.
print("Negative -- cue present but the slot is not name-shaped")

NEGATIVES_SLOT = [
    ("lowercase word in slot", "The IDoc was posted by the overnight batch job."),
    ("digit in slot",          "Document created by 0000778812 during conversion."),
]

for name, text in NEGATIVES_SLOT:
    m = raw_promoted(text)
    check(name, not m, f"PROMOTED: {m}")

# --------------------------------------------------------------------------
# Regression -- the promoter must not disturb what already worked.
# --------------------------------------------------------------------------
print("Regression -- existing detection unchanged")

check("address still detected",
      redacted("Deliver to 48 Rimu Road, Papakura, Auckland.", "Rimu"))
check("email still detected",
      redacted("Contact k.mueller@corp.internal for the spec.", "k.mueller"))
check("3 Way match still not an address",
      "3 Way match" in A.scrub("Invoice blocked, 3 Way match failed.", "batch")["scrubbed_text"])

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
