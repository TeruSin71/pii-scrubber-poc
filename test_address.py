#!/usr/bin/env python3
"""
Tests for the street-address recognizer (P1 ADDRESS coverage gap).

Run:  python test_address.py        (exit 0 = all pass)

Every value here is written fresh for these tests. Nothing is copied from
holdout_samples.json, which was not opened while building the recognizer --
the point of the holdout is destroyed if the pattern is tuned to its strings.
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


import recognizers as R  # noqa: E402

_REC = R.street_address_recognizer()


def address_spans(text):
    """Post-merge ADDRESS spans -- what the service actually emits."""
    return [s for s in A.detect(text, "presidio") if s["type"] == "ADDRESS"]


def raw_matches(text):
    """
    What the recognizer itself matched, BEFORE _merge.

    Negatives must be checked here, not on address_spans(). _merge can hand an
    overlap to a longer span of another type, so a false positive can vanish
    from the post-merge view while the recognizer is still matching it -- that
    produced a false pass on '4 Goods Receipt Close' during development.
    """
    return [text[m.start:m.end] for m in _REC.analyze(text, ["ADDRESS"], None)]


def covers(text, expected_substring):
    """An ADDRESS span exists that contains the identifying detail."""
    return any(expected_substring in s["text"] for s in address_spans(text))


# --------------------------------------------------------------------------
# Positives -- one per shape in the class spec
# --------------------------------------------------------------------------
print("Positive shapes")

POSITIVES = [
    ("bare street line",        "Send it to 12 Kauri Street for collection.",        "12 Kauri Street"),
    ("suburb and city",         "Deliver to 48 Rimu Road, Papakura, Auckland.",      "48 Rimu Road"),
    ("with postcode",           "Site address 9 Totara Avenue, Hamilton 3204.",      "9 Totara Avenue"),
    ("unit prefix",             "Unit 5, 21 Pohutukawa Drive, Tauranga is the DC.",  "21 Pohutukawa Drive"),
    ("multi-word street name",  "Ship to 77 Silver Fern Terrace, Porirua.",          "77 Silver Fern Terrace"),
    ("abbreviated type",        "Vendor is at 14 Manuka Rd, Levin.",                 "14 Manuka Rd"),
    ("number with letter",      "Depot at 12A Rata Place, Napier.",                  "12A Rata Place"),
    ("number range",            "Warehouse 12-14 Kowhai Lane, Nelson.",              "12-14 Kowhai Lane"),
    ("PO Box",                  "Remit to PO Box 1421, Dunedin.",                    "PO Box 1421"),
    ("Private Bag",             "Postal is Private Bag 92019, Auckland.",            "Private Bag 92019"),
    ("mid-sentence",            "The 33 Karaka Grove site raised the ticket.",       "33 Karaka Grove"),
    ("end of sentence",         "Confirm the drop at 6 Nikau Crescent.",             "6 Nikau Crescent"),
]

for name, text, expected in POSITIVES:
    check(name, covers(text, expected), f"spans: {[s['text'] for s in address_spans(text)]}")

# Postcode and locality must be inside the span -- a partially redacted
# address is still an identifying address.
print("Span extent")
t = "Site address 9 Totara Avenue, Hamilton 3204."
sp = address_spans(t)
check("locality+postcode absorbed into the span",
      any("Hamilton 3204" in s["text"] for s in sp),
      f"spans: {[s['text'] for s in sp]}")

# The comma anchoring must stop the match at a full stop.
t = "Meet at 33 Karaka Lane, Nelson. Please confirm with Finance."
sp = address_spans(t)
check("match does not cross a sentence boundary",
      sp and all("Please" not in s["text"] for s in sp),
      f"spans: {[s['text'] for s in sp]}")

# End to end: the value must actually be redacted, not merely detected.
out = A.scrub("Deliver to 48 Rimu Road, Papakura, Auckland.", "batch")["scrubbed_text"]
check("redacted end to end", "Rimu" not in out and "<ADDRESS>" in out, out)

# --------------------------------------------------------------------------
# Negatives -- SAP prose that must NOT match. This is the part that matters.
# --------------------------------------------------------------------------
print("Negative -- SAP jargon must not be eaten")

NEGATIVES = [
    ("3 Way match",                     "Invoice blocked, 3 Way match failed."),
    ("2 Way match",                     "Config uses 2 Way match for this doc type."),
    ("three way match (words)",         "The three way match tolerance is too tight."),
    ("Level 3 support ticket",          "Escalated to Level 3 support ticket queue."),
    ("movement type 601",               "Check movement type 601 configuration."),
    ("plant 4000 deliveries",           "No plant 4000 deliveries were created."),
    ("Close the order",                 "Close the order once GR is posted."),
    ("Court of Auckland",               "Filed at the Court of Auckland registry."),
    ("40 open transfer orders",         "There are 40 open transfer orders."),
    ("Order 4500001234 Line 10",        "See Order 4500001234 Line 10 for detail."),
    ("Storage location 0001",           "Storage location 0001 is not assigned."),
]

for name, text in NEGATIVES:
    m = raw_matches(text)
    check(name, not m, f"MATCHED: {m}")

# The two existing over-detections tag a bare "PO" as ADDRESS via the NLP
# layer. Adding a PO Box form must not make the recognizer match bare "PO".
print("Negative -- bare PO must not match the postal_box pattern")
check("bare 'PO' not matched by street_address_recognizer",
      not raw_matches("Tax code V1 not defaulting on PO for vendor 0000889900."))

# --------------------------------------------------------------------------
# Ambiguous street types (Option C). These are also ordinary logistics words,
# so they match ONLY with a trailing comma-locality. Both directions matter:
# bare must not match, with-locality must still match.
# --------------------------------------------------------------------------
print("Negative -- ambiguous street types must NOT match bare")

for name, text in [
    ("Row",   "Scan 20 Pallet Rack Row before picking."),
    ("Close", "Run 4 Goods Receipt Close at period end."),
    ("View",  "Open 2 Bin View in the warehouse monitor."),
    ("Track", "Move 3 Storage Bin Track to the next wave."),
    ("Place", "Check 12 Handling Unit Place assignments."),
    ("Way",   "Configure 2 Invoice Way rules for this plant."),
    ("Court", "Book 3 Loading Court slots for the wave."),
]:
    m = raw_matches(text)
    check(f"bare ambiguous type: {name}", not m, f"MATCHED: {m}")

print("Positive -- ambiguous street types DO match with a locality")

for name, text, expected in [
    ("Close", "Vendor at 14 Sunrise Close, Papakura.",         "14 Sunrise Close"),
    ("Place", "Depot at 12A Rata Place, Napier.",              "12A Rata Place"),
    ("Way",   "Site at 8 Harbour Way, Whangarei 0110.",        "8 Harbour Way"),
    ("View",  "Office at 5 Harbour View, Devonport, Auckland.", "5 Harbour View"),
    ("Court", "Ship to 19 Kereru Court, Rotorua.",             "19 Kereru Court"),
]:
    check(f"ambiguous type with locality: {name}", covers(text, expected),
          f"spans: {[s['text'] for s in address_spans(text)]}")

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
