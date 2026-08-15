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

# --------------------------------------------------------------------------
# 6. Bundle 1.2.1 -- eight entries, each traced to a blind-batch sample in
#    holdout_v3.json (V3-001, V3-034, V3-035, V3-038, V3-039, V3-040).
#
#    The sentences below are PARAPHRASES, never the sample text: holdout_v3
#    is gitignored on purpose and copying it here would put it in the repo
#    through the back door.
#
#    Every frame was checked to misfire BEFORE the entries were added. Three
#    of the first drafts did not -- "The GL posting failed during the period
#    close run", an MRP frame and a Rise frame all came back clean, and would
#    have shipped as three checks that passed before the feature existed.
#    The misfire is frame-sensitive, not token-sensitive; a paraphrase is not
#    automatically a test.
#
#    Six of the eight are 2-3 chars, below the 4-char SAP_USER_ID floor
#    (recognizers.py:108), so none was ever a recognizer hit -- they arrive
#    from the spaCy layer, and they arrive inconsistently typed: WM and MRP
#    as ADDRESS, the rest as ORG_NAME. Suppression is type-independent, which
#    is why these assert on the span text rather than its type.
# --------------------------------------------------------------------------
print("1.2.1 entries -- observed misfires must stop")

STOPS_121 = [
    ("GL   (V3-034, fires ORG_NAME)", "Postings to the GL account doubled overnight.", "GL"),
    ("FX   (V3-034, fires ORG_NAME)", "Revaluation picked up the wrong FX rate for the period.", "FX"),
    ("WM   (V3-035, fires ADDRESS)",  "Bin determination in WM did not resolve for the depot.", "WM"),
    ("MDG  (V3-038, fires ORG_NAME)", "The record was blocked in MDG pending data steward review.", "MDG"),
    ("MRP  (V3-039, fires ORG_NAME)", "The MRP run completes but no planned order appears.", "MRP"),
    ("OSS  (V3-040, fires ORG_NAME)", "Raised an OSS note with support for the dump.", "OSS"),
    ("CFO  (V3-001, fires ORG_NAME)", "Escalated to the CFO office for the write-off approval.", "CFO"),
    ("Rise (V3-035, fires ORG_NAME)", "Management flagged the Rise in open credit memos.", "Rise"),
]

for name, text, token in STOPS_121:
    check(name, clean(text, token), f"spans: {spans(text)}")

# The leak guard, applied to the new entries. An entry may veto a PATTERN,
# never CONTEXT -- this is the group that would show it if that ever broke.
print("1.2.1 leak guard -- context still overrides every new entry")
check("'posted by CFO' still redacts",
      redacted("Adjustment posted by CFO during the close.", "CFO"),
      A.scrub("Adjustment posted by CFO during the close.", "batch")["scrubbed_text"])
check("'requested by MDG' still redacts",
      redacted("Change requested by MDG last Thursday.", "MDG"),
      A.scrub("Change requested by MDG last Thursday.", "batch")["scrubbed_text"])

# Rise is BOTH jargon and a street type. Section 3 already asserts the
# address direction; this is the other half. If either breaks, Rise goes to
# Appendix A, never to a workaround.
print("1.2.1 Rise -- suppressed as a noun, intact as a street type")
check("bare 'Rise' does not redact", clean(STOPS_121[7][1], "Rise"),
      f"spans: {spans(STOPS_121[7][1])}")
check("'14 Sunrise Rise' still redacts",
      redacted("Depot at 14 Sunrise Rise, Papakura, Auckland.", "14 Sunrise Rise"),
      A.scrub("Depot at 14 Sunrise Rise, Papakura, Auckland.", "batch")["scrubbed_text"])

# Case sensitivity, per entry. 'gl' and 'rise' are ordinary words and must
# never be suppressed; 'RISE' could be a custom object.
print("1.2.1 leak guard -- case-sensitive exact match holds per entry")
for tok in ("GL", "FX", "WM", "MDG", "MRP", "OSS", "CFO", "Rise"):
    check(f"{tok!r} is an entry", tok in A.ALLOWLIST_EXACT)
for tok in ("gl", "fx", "wm", "mdg", "mrp", "oss", "cfo", "rise", "RISE"):
    check(f"{tok!r} is NOT an entry", tok not in A.ALLOWLIST_EXACT)

# Still out. A future session that ships one of these must delete the
# assertion deliberately, not discover it went green by accident.
print("1.2.1 -- pre-cleared but unshipped street types stay out")
for tok in ("Close", "Court", "Terrace", "Drive"):
    check(f"{tok!r} still unshipped (cleared, no observed misfire)",
          tok not in A.ALLOWLIST_EXACT)
print("1.2.1 -- lg-only evidence is not evidence about the shipped config")
for tok in ("SH", "ES_SD_REBATE"):
    check(f"{tok!r} rejected (misfired only under en_core_web_lg)",
          tok not in A.ALLOWLIST_EXACT)

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
