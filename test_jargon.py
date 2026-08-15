#!/usr/bin/env python3
"""
Tests for the SAP jargon glossary (P3, bundle 1.2.0 item 2).

Run:  python test_jargon.py        (exit 0 = all pass)

The glossary is DATA, not mechanism. `glossary.txt` loads through the same
loader as `allowlist.txt` into the same suppression set, so it inherits three
properties rather than reimplementing them. All three are asserted below,
because inheriting a property silently is how it gets broken later:

  1. case-sensitive exact match  -- "Basis" the module stays distinct from
     "basis" the ordinary word
  2. the +/-40-char user-context backstop -- a glossary entry may veto a
     PATTERN, never CONTEXT. "posted by Driver" still redacts.
  3. whole-span exact matching   -- "Driver" suppresses the single-token span
     only; a genuine "Driver Logistics Ltd" ORG span is multi-token and can
     never match the entry.

Every entry earns its place by fixing an OBSERVED over-detection. Entries
that merely look plausible are not shipped -- a glossary can grow for free in
a later release, but a leak it causes cannot be un-leaked.
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


def spans(text):
    return [(s["text"], s["type"]) for s in A.detect(text, "presidio")]


def clean(text, token):
    """No span is exactly this token any more."""
    return not any(t == token for t, _ in spans(text))


def redacted(text, value):
    return value not in A.scrub(text, "batch")["scrubbed_text"]


# --------------------------------------------------------------------------
# 1. Observed misfires must stop.
# --------------------------------------------------------------------------
print("Must stop redacting -- every one an observed over-detection")

STOPS = [
    ("Basis as ORG_NAME", "VF04 collective run fails when NAST has no entry, check MARA and VBAK before raising it with Basis.", "Basis"),
    ("Basis as ADDRESS",  "Escalated to Level 3 support and routed to Basis for the ST22 dump, no customer specifics required.", "Basis"),
    ("Driver as ORG_NAME", "Driver could not find the depot so the delivery came back.", "Driver"),
    ("Way as ORG_NAME",   "Invoice blocked, 3 Way match failed against the goods receipt.", "Way"),
    ("Config as PERSON",  "This is Config, no customer specifics required.", "Config"),
    ("PO as ADDRESS",     "Tax code V1 not defaulting on PO for vendor 0000889900.", "PO"),
    ("IBAN as ORG_NAME",  "Remittance rejected, IBAN on file does not match the branch record.", "IBAN"),
    ("RFC as ORG_NAME",   "Basis checking the RFC destination for the interface.", "RFC"),
    ("DC as ADDRESS",     "The delivery came back to the DC late on Friday.", "DC"),
]

for name, text, token in STOPS:
    check(name, clean(text, token), f"spans: {spans(text)}")

# Basis misfires as TWO different types. If suppression were type-scoped
# anywhere, this is the pair that would show it.
print("Type-independence -- suppression is not scoped to one entity type")
check("Basis suppressed as both ORG_NAME and ADDRESS",
      clean(STOPS[0][1], "Basis") and clean(STOPS[1][1], "Basis"))

# --------------------------------------------------------------------------
# 2. The glossary sits UNDER the context backstop. This is the leak guard and
#    it is the most important group in this file.
# --------------------------------------------------------------------------
print("Leak guard -- a glossary entry may veto a pattern, never context")

check("'posted by Driver' still redacts",
      redacted("Ticket posted by Driver on Tuesday for the Napier run.", "Driver"),
      A.scrub("Ticket posted by Driver on Tuesday for the Napier run.", "batch")["scrubbed_text"])
check("'reported by Config' still redacts",
      redacted("Issue reported by Config during the cutover weekend.", "Config"))
check("'changed by Payer' still redacts",
      redacted("Master record changed by Payer last Thursday.", "Payer"))

print("Leak guard -- whole-span matching, multi-token spans unaffected")
check("'Driver Logistics Ltd' still redacts",
      redacted("Carrier is Driver Logistics Ltd and the rate card is stale.", "Driver Logistics Ltd"),
      A.scrub("Carrier is Driver Logistics Ltd and the rate card is stale.", "batch")["scrubbed_text"])
check("'Treasury Holdings Pty' still redacts",
      redacted("Counterparty is Treasury Holdings Pty on the intercompany doc.", "Treasury Holdings Pty"))

print("Leak guard -- case-sensitive exact match, asserted structurally")
check("'Basis' is a glossary entry", "Basis" in A.ALLOWLIST_EXACT)
check("'basis' is NOT", "basis" not in A.ALLOWLIST_EXACT)
check("'DRIVER' is NOT", "DRIVER" not in A.ALLOWLIST_EXACT)

print("Leak guard -- rejected entries stay out")
for tok, why in [("Bill", "real given name"), ("Munich", "real city"),
                 ("Auckland", "real city"), ("Target", "real company"),
                 ("BRAUN", "surname/table collision"), ("OSNO", "unknown provenance")]:
    check(f"{tok!r} rejected ({why})", tok not in A.ALLOWLIST_EXACT)

# BRAUN specifically: test_fixes.py asserts it survives as a user-ID span.
# Adding it to the glossary would have broken that, silently.
check("BRAUN still detected as a span",
      any("BRAUN" in t for t, _ in spans("Authorisation issue for user BRAUN in the plant role.")))

# --------------------------------------------------------------------------
# 3. Street-type protocol. These words are BOTH jargon and address
#    components, so each is proved against a real address before it ships.
#    A break here sends the entry to Appendix A, never to a workaround.
# --------------------------------------------------------------------------
print("Street-type safety -- real addresses containing each type still redact")

STREET = [
    ("Way",     "Site at 8 Harbour Way, Whangarei 0110.",          "8 Harbour Way"),
    ("Rise",    "Depot at 14 Sunrise Rise, Papakura, Auckland.",   "14 Sunrise Rise"),
    ("Close",   "Vendor at 14 Sunrise Close, Papakura.",           "14 Sunrise Close"),
    ("Court",   "Ship to 19 Kereru Court, Rotorua.",               "19 Kereru Court"),
    ("Terrace", "Ship to 77 Silver Fern Terrace, Porirua.",        "77 Silver Fern Terrace"),
    ("Drive",   "Unit 5, 21 Pohutukawa Drive, Tauranga is the DC.", "21 Pohutukawa Drive"),
]

for word, text, addr in STREET:
    check(f"address with {word!r} still redacts", redacted(text, addr),
          f"out: {A.scrub(text, 'batch')['scrubbed_text']}")

# --------------------------------------------------------------------------
# 4. Regression -- the glossary must not disturb real detection.
# --------------------------------------------------------------------------
print("Regression -- real PII still detected")
check("person still detected", redacted("Spec written by Aroha Ngatai in March.", "Aroha Ngatai"))
check("email still detected", redacted("Contact k.mueller@corp.internal for the spec.", "k.mueller"))
check("customer number still detected", redacted("Order for customer 2298871 rejected.", "2298871"))
check("vendor number still detected", redacted("Blocked for vendor 0000778812.", "0000778812"))
check("address still detected", redacted("Deliver to 48 Rimu Road, Papakura, Auckland.", "Rimu"))
check("suffixed org still detected", redacted("Counterparty is Rheinland Logistik GmbH.", "Rheinland Logistik GmbH"))

# --------------------------------------------------------------------------
# 5. Packaging. A glossary that is not in the image is a glossary that does
#    nothing, and the service would start clean with no error -- the loader
#    logs a skip and carries on. Asserted here rather than in test_fixes.py
#    so that suite's count stays frozen at 16.
# --------------------------------------------------------------------------
print("Packaging -- the glossary must reach the image")
copy_lines = [l for l in open("Dockerfile") if l.strip().startswith("COPY") and "app.py" in l]
check("Dockerfile COPY includes glossary.txt",
      copy_lines and "glossary.txt" in copy_lines[0],
      f"line: {copy_lines[0].strip() if copy_lines else 'NOT FOUND'}")
check("glossary entries actually reached the live set",
      sum(1 for e in ("Basis", "Config", "Driver", "Way", "PO") if e in A.ALLOWLIST_EXACT) == 5)

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
