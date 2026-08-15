#!/usr/bin/env python3
"""
Tests for unpadded SAP customer numbers (P2, bundle 1.2.0 item 1).

Run:  python test_customer_number.py        (exit 0 = all pass)

The failure this closes is NOT a scoring problem. Both existing patterns
require ten digits -- `\\b000\\d{7}\\b` and `\\b\\d{10}\\b` -- and every
unpadded value seen in the wild has seven, so nothing matched at all and
there was no score to raise.

The fix is a cue-gated lookbehind: one Pattern per cue, each fixed width,
so the cue itself stays OUT of the redacted span. A `<cue> <number>` pattern
would redact the cue too, because presidio 2.2.357 reports match.span() for
the whole match -- the same defect that forced the person promoter out of the
recognizer layer (see PERSON-CONTEXT-FINDING.md).

Cue list is FROZEN at six words, two cases each. `ship-to` is excluded on
purpose: in delivery text it cues an address more often than an account.
"""

import os
import sys

os.environ.setdefault("SCRUBBER_ENGINE", "presidio")

import app as A          # noqa: E402
import recognizers as R  # noqa: E402

FAILURES = []
_REC = R.sap_customer_number_recognizer()


def check(name, cond, detail=""):
    status = "ok  " if cond else "FAIL"
    print(f"  [{status}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def raw_matches(text, min_score=0.5):
    """
    What the recognizer itself matched, BEFORE _merge, at or above min_score.

    Negatives are asserted here, never on merged output: _merge can hand an
    overlap to a longer span of another type and hide a false positive. That
    produced a false pass on '4 Goods Receipt Close' during the address work.

    The score floor matters. `sap_customer_ctx` (\\b\\d{10}\\b, score 0.35)
    legitimately matches ANY ten-digit string -- an order number, a delivery
    number -- and sits below the 0.50 CUSTOMER_NO floor on purpose, waiting
    for a context boost. Asserting "no raw match at all" would be asserting
    against existing intended behaviour and would fail before a line of the
    new code was written. Negatives here target the new cue-gated patterns,
    which score 0.75.
    """
    return [text[m.start:m.end]
            for m in _REC.analyze(text, ["SAP_CUSTOMER_NO"], None)
            if m.score >= min_score]


def redacted(text, value):
    return value not in A.scrub(text, "batch")["scrubbed_text"]


# --------------------------------------------------------------------------
# Positives -- one per frozen cue, both cases, plus the three known values.
# --------------------------------------------------------------------------
print("Positive -- unpadded number after each frozen cue")

POSITIVES = [
    ("customer lower",  "Sales order rejected for customer 2298871 on the credit check.", "2298871"),
    ("Customer upper",  "Customer 1045567 short dumps in VA02 when the partner is redetermined.", "1045567"),
    ("sold-to lower",   "The sold-to 4471902 has no pricing record for this org.", "4471902"),
    ("Sold-to upper",   "Sold-to 3390114 was created without a payment term.", "3390114"),
    ("payer lower",     "Rebate posted to the wrong payer 5582203 last period.", "5582203"),
    ("Payer upper",     "Payer 6610947 is blocked and the run skipped it.", "6610947"),
    ("bill-to lower",   "Invoice went to bill-to 7729183 instead of the head office.", "7729183"),
    ("Bill-to upper",   "Bill-to 8843026 needs the new tax classification.", "8843026"),
    ("debtor lower",    "Ageing report shows debtor 9917455 overdue by 90 days.", "9917455"),
    ("Debtor upper",    "Debtor 2204518 disputes the freight line.", "2204518"),
    ("account lower",   "Credit limit not applied, account 4471902 above tolerance.", "4471902"),
    ("Account upper",   "Account 1188390 was keyed without leading zeros by the desk.", "1188390"),
    ("six digits",      "Order blocked for customer 445019 in the nightly run.", "445019"),
    ("nine digits",     "Conversion loaded customer 123456789 with no sales area.", "123456789"),
]

for name, text, value in POSITIVES:
    check(name, redacted(text, value), f"out: {A.scrub(text, 'batch')['scrubbed_text']}")

# The cue must survive. If it does not, the lookbehind has been replaced by a
# plain match and the sentence stops being readable in batch mode.
print("Span extent -- the cue must stay outside the span")
out = A.scrub("Sales order rejected for customer 2298871 on the credit check.", "batch")["scrubbed_text"]
check("cue word kept out of the redaction", "customer <CUSTOMER_NO>" in out, out)

# The padded form keeps sole ownership of 10-digit strings.
print("Ownership -- the padded pattern still owns 10 digits")
check("padded form still detected", redacted("Credit block on account 0001045567 again.", "0001045567"))
m = raw_matches("Credit block on account 0001045567 again.")
check("10 digits not claimed by an unpadded pattern",
      m and all(len(x) == 10 for x in m), f"matched: {m}")
# The unpadded patterns cap at 9 digits, so they cannot also own this string.
check("no 6-9 digit sub-match inside the padded form",
      not any(6 <= len(x) <= 9 for x in m), f"matched: {m}")

# --------------------------------------------------------------------------
# Negatives -- asserted against the RAW recognizer.
# --------------------------------------------------------------------------
print("Negative -- technical numbers with no customer cue")

NEGATIVES = [
    ("movement type",      "Check movement type 601 configuration for this plant."),
    ("plant number",       "No plant 4000 deliveries were created overnight."),
    ("storage location",   "Storage location 0001 is not assigned to the warehouse."),
    ("order and line",     "See Order 4500001234 Line 10 for the pricing detail."),
    ("material no cue",    "Material 1234567 has no batch classification maintained."),
    ("transfer orders",    "There are 40 open transfer orders on the queue."),
    ("delivery number",    "Delivery 809912345 shows PGI complete but no invoice."),
    ("bare number",        "The run processed 2298871 records before it dumped."),
    ("ship-to excluded",   "Freight quote failed for ship-to 4471902 in the portal."),
]

for name, text in NEGATIVES:
    m = raw_matches(text)
    check(name, not m, f"MATCHED: {m}")

# Case sensitivity is explicit, not inherited from presidio's IGNORECASE
# default. This project already lost 249 spans to that default once.
print("Negative -- unlisted case variants must not match")
for name, text in [
    ("ALL CAPS cue",   "CUSTOMER 2298871 was rejected by the credit check."),
    ("mIxed case cue", "cUsToMeR 2298871 was rejected by the credit check."),
]:
    m = raw_matches(text)
    check(name, not m, f"MATCHED: {m}")

# --------------------------------------------------------------------------
# Accepted cost, asserted so it stays deliberate rather than becoming a
# surprise. A redacted GL account costs readability; a leaked customer number
# costs compliance. Documented at Gate 0, not engineered around.
# --------------------------------------------------------------------------
print("Accepted cost -- GL accounts after 'account' DO redact, on purpose")
check("GL account redacts (known, accepted)",
      redacted("Posting went to account 400000 instead of the accrual account.", "400000"),
      A.scrub("Posting went to account 400000 instead of the accrual account.", "batch")["scrubbed_text"])

# --------------------------------------------------------------------------
# Regression -- the rest of the pipeline is untouched.
# --------------------------------------------------------------------------
print("Regression -- neighbouring detection unchanged")
check("vendor number still detected", redacted("Purchase order blocked for vendor 0000778812.", "0000778812"))
check("address still detected", redacted("Deliver to 48 Rimu Road, Papakura, Auckland.", "Rimu"))
check("3 Way match still not eaten",
      "3 Way match" in A.scrub("Invoice blocked, 3 Way match failed.", "batch")["scrubbed_text"])

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
