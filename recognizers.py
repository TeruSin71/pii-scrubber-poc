"""
SAP-specific PII recognizers for Presidio.

These cover the categories off-the-shelf PII models systematically miss:
SAP customer/vendor numbers and SAP user IDs. This is the domain-adaptation
layer -- deterministic, auditable, and cheap.
"""

import re

from presidio_analyzer import Pattern, PatternRecognizer

# Presidio's PatternRecognizer defaults to IGNORECASE, which makes
# uppercase-sensitive patterns (SAP user IDs, transport IDs) match ordinary
# lowercase words. Case-sensitive flags are required for those.
CASE_SENSITIVE = re.DOTALL | re.MULTILINE


# Cues that put the FOLLOWING number in a customer-account slot. FROZEN at
# six words, both cases spelled out.
#
# Case variants are enumerated rather than left to a flag because Presidio's
# PatternRecognizer defaults to IGNORECASE, and this project has already paid
# for that once: the SAP user-ID pattern matched ordinary lowercase words and
# emitted 249 spans against 45 real values. Explicit beats inherited.
#
# `ship-to` is deliberately NOT here. In delivery text it cues an address far
# more often than an account number, and ADDRESS already owns that.
_CUST_CUES = [
    "Customer ", "customer ", "Account ", "account ",
    "Sold-to ", "sold-to ", "Payer ", "payer ",
    "Bill-to ", "bill-to ", "Debtor ", "debtor ",
]


def sap_customer_number_recognizer() -> PatternRecognizer:
    """
    SAP customer numbers, padded (0001045567) and unpadded (1045567).

    The unpadded form is NOT a scoring problem. Both original patterns require
    ten digits, and every unpadded value seen in the wild has seven -- nothing
    matched at all, so there was no score to raise. It needs its own pattern.

    One Pattern per cue, each carrying a fixed-width lookbehind. Two reasons
    it takes that shape rather than a single `<cue>\\s+<number>` pattern:

      1. presidio-analyzer 2.2.357 reports match.span() for the WHOLE match
         and has no capture-group support, so the cue would be redacted too --
         "customer 2298871" would become "<CUSTOMER_NO>". That is the exact
         defect that forced the person promoter out of the recognizer layer
         (PERSON-CONTEXT-FINDING.md).
      2. Python's re allows only a FIXED-WIDTH lookbehind, so the cues cannot
         share one alternation. Each gets its own pattern instead.

    Score 0.75 clears the 0.50 CUSTOMER_NO floor on its own. The floor is not
    touched -- it governs every recognizer, so admitting one entity type by
    lowering it would admit every sub-threshold span in the pipeline, and a
    customer-number test would never reveal that.

    Digit range is 6-9, not 6-10: the padded pattern keeps sole ownership of
    ten-digit strings, so no two patterns claim the same text.

    Accepted cost, deliberate: "account 400000" redacts GL account numbers.
    A redacted GL account costs readability; a leaked customer number costs
    compliance. Documented at Gate 0 and not engineered around.
    """
    patterns = [
        Pattern(name="sap_customer_padded", regex=r"\b000\d{7}\b", score=0.85),
        Pattern(name="sap_customer_ctx", regex=r"\b\d{10}\b", score=0.35),
    ]
    patterns += [
        Pattern(name=f"sap_customer_unpadded_{i}",
                regex=rf"(?<={re.escape(cue)})\d{{6,9}}\b",
                score=0.75)
        for i, cue in enumerate(_CUST_CUES)
    ]
    return PatternRecognizer(
        supported_entity="SAP_CUSTOMER_NO",
        patterns=patterns,
        context=["customer", "sold-to", "ship-to", "bill-to", "kunnr", "payer", "account"],
        # Required by the enumerated cue variants above. The two original
        # patterns are digit-only, so this cannot change their behaviour.
        global_regex_flags=CASE_SENSITIVE,
    )


def sap_vendor_number_recognizer() -> PatternRecognizer:
    """SAP vendor numbers: 10 digits, conventionally zero-padded (0000778812)."""
    patterns = [
        Pattern(name="sap_vendor_padded", regex=r"\b0000\d{6}\b", score=0.85),
        Pattern(name="sap_vendor_ctx", regex=r"\b\d{10}\b", score=0.35),
    ]
    return PatternRecognizer(
        supported_entity="SAP_VENDOR_NO",
        patterns=patterns,
        context=["vendor", "supplier", "lifnr", "creditor", "purchasing"],
    )


def sap_user_id_recognizer() -> PatternRecognizer:
    """
    SAP user IDs: uppercase alphanumeric, 4-12 chars (KMUELLER, BJOHNSON),
    or service accounts (svc_inv_bot). Low base score -- context words lift it,
    which keeps false positives off ordinary uppercase words like IDOC or PR00.
    """
    patterns = [
        # Must contain at least one further uppercase letter and no lowercase.
        Pattern(name="sap_uid_upper", regex=r"\b[A-Z]{4,12}\b", score=0.3),
        Pattern(name="sap_uid_alnum", regex=r"\b[A-Z]{2,}[0-9]{1,6}\b", score=0.3),
        Pattern(name="sap_uid_service", regex=r"\bsvc[_-][A-Za-z0-9_-]{2,20}\b", score=0.75),
    ]
    return PatternRecognizer(
        supported_entity="SAP_USER_ID",
        patterns=patterns,
        context=["user", "userid", "user id", "uname", "logged", "posted by",
                 "ran", "service account", "requested by", "planner", "approver",
                 "account", "by"],
        global_regex_flags=CASE_SENSITIVE,
    )


def sap_document_ref_recognizer() -> PatternRecognizer:
    """
    Change requests / transport IDs. Not PII per se, but useful to flag for
    review since specs often pair them with author names.
    """
    patterns = [
        Pattern(name="sap_cr", regex=r"\bCR\s?\d{5,8}\b", score=0.4),
        Pattern(name="sap_transport", regex=r"\b[A-Z]{3}K9\d{5}\b", score=0.6),
    ]
    return PatternRecognizer(
        supported_entity="SAP_DOC_REF",
        patterns=patterns,
        context=["change request", "transport", "cr", "cts"],
        global_regex_flags=CASE_SENSITIVE,
    )


def permissive_email_recognizer() -> PatternRecognizer:
    """
    Recall-first email backstop.

    Presidio's built-in EmailRecognizer validates the TLD against the public
    suffix list, so it under-scores internal or non-public domains
    (user@corp.internal, user@company.local, user@x.example). A scrubber must
    not leak an address just because its TLD is unusual -- so we add a
    permissive shape-based pattern alongside the strict one.
    """
    patterns = [Pattern(
        name="email_permissive",
        regex=r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}\b",
        score=0.65,
    )]
    return PatternRecognizer(supported_entity="EMAIL_ADDRESS", patterns=patterns)


def company_suffix_recognizer() -> PatternRecognizer:
    """
    Organisation names by legal suffix (GmbH, Ltd, Pty, BV, AG ...).
    spaCy's small NER model misses many of these; the suffix is a reliable,
    deterministic signal and customer/vendor names are exactly what appears
    in SAP tickets.
    """
    suffixes = (r"(?:GmbH|AG|Ltd|Limited|Pty|Pte|BV|NV|SA|SAS|SRL|SpA|"
                r"Inc|LLC|LLP|PLC|Oy|AB|AS|ApS|KG|OHG|Co)")
    patterns = [Pattern(
        name="org_legal_suffix",
        regex=rf"\b(?:[A-Z][\w&'\-]*\s+){{1,4}}{suffixes}\b\.?",
        score=0.7,
    )]
    return PatternRecognizer(
        supported_entity="ORG",
        patterns=patterns,
        global_regex_flags=CASE_SENSITIVE,
    )


# Street-type keywords, split by false-positive risk. ORDER MATTERS within each
# group: the long form must precede its abbreviation ("Street" before "St") or
# alternation matches the short one first and truncates the span.
#
# UNAMBIGUOUS -- these are never a trailing noun in SAP prose, so a bare
# "<number> <Name> <Type>" is safe on its own.
_SAFE_TYPE = (
    r"(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Lane|Ln|Terrace|Tce|"
    r"Crescent|Cres|Highway|Hwy|Parade|Pde|Boulevard|Blvd|Esplanade|Quay|Grove)"
)

# AMBIGUOUS -- also ordinary words in logistics/WM text, where
# "<number> <Capitalised words> <Type>" occurs naturally and is structurally
# identical to an address. Measured false positives with these matching bare:
#   '20 Pallet Rack Row'  '4 Goods Receipt Close'  '2 Bin View'
#   '3 Storage Bin Track' '12 Handling Unit Place'
# The mandatory-name rule cannot help -- the name slot is genuinely filled.
# So these require a trailing comma-locality, which SAP prose does not produce.
# Cost: a bare "12 Sunrise Rise" with no suburb is missed.
_RISKY_TYPE = (
    r"(?:Place|Pl|Court|Ct|Close|Circle|Valley|Track|View|Walk|Mall|Rise|Row|Loop|Way)"
)

# A street-name word: capital, then a LOWERCASE letter, then anything.
# The mandatory lowercase second character is what keeps all-caps SAP tokens
# (VBAK, MARA, NAST) out of the name slot while still admitting "McLeod".
_NAME_WORD = r"[A-Z][a-z][A-Za-z'\-]*"

# Trailing locality: comma-separated capitalised words, then an optional
# 4-digit NZ postcode. Anchoring each group on a comma is what stops the match
# running past a sentence boundary -- "…Lane, Nelson. Please confirm" cannot
# swallow "Please", because a full stop is not a comma.
_LOCALITY = (
    rf"(?:,\s*{_NAME_WORD}(?:\s+{_NAME_WORD}){{0,2}})*"
    r"(?:,?\s{1,2}\d{4}\b)?"
)

# Same, but at least one comma-locality group is mandatory. This is the whole
# discriminator for the ambiguous street types.
_LOCALITY_REQ = (
    rf"(?:,\s*{_NAME_WORD}(?:\s+{_NAME_WORD}){{0,2}})+"
    r"(?:,?\s{1,2}\d{4}\b)?"
)


def street_address_recognizer() -> PatternRecognizer:
    """
    NZ/AU street addresses: [unit] <number> <Name...> <StreetType> [, locality].

    Deterministic and offline -- no geocoding, no postcode lookup, nothing that
    reaches the network at inference time (Rule 3).

    Two rules keep SAP prose out, and both are verified in test_address.py
    against the RAW recognizer rather than post-merge output (a post-merge
    check gave a false pass during development -- _merge can hand an overlap
    to a longer span of another type and hide the false positive):

      1. At least one capitalised name word must sit between the number and
         the street type. "3 Way match" is number + type with nothing between,
         so it cannot match. This is the most likely false positive in MM text.
      2. Street types that are also ordinary logistics words additionally
         require a trailing comma-locality (see _RISKY_TYPE).

    Scope is NZ/AU forms only. German-style "Hauptstrasse 12, 80331 Munich"
    (name before number, 5-digit postcode) is NOT covered and still relies on
    incidental locality detection.
    """
    unit = (r"(?:(?:Unit|Flat|Apartment|Apt|Level|Suite|Shop|Villa)\s+"
            r"[0-9]{1,4}[A-Za-z]?,?\s+)?")
    number = r"[0-9]{1,5}[A-Za-z]?(?:\s?-\s?[0-9]{1,5}[A-Za-z]?)?"

    patterns = [
        Pattern(
            name="street_address",
            regex=rf"\b{unit}{number}\s+(?:{_NAME_WORD}\s+){{1,4}}{_SAFE_TYPE}\b\.?{_LOCALITY}",
            score=0.8,
        ),
        # Ambiguous types: identical shape, but a locality is mandatory.
        Pattern(
            name="street_address_ambiguous_type",
            regex=rf"\b{unit}{number}\s+(?:{_NAME_WORD}\s+){{1,4}}{_RISKY_TYPE}\b{_LOCALITY_REQ}",
            score=0.8,
        ),
        # No street component at all, so it needs its own pattern.
        Pattern(
            name="postal_box",
            regex=rf"\b(?:P\.?O\.?\s?Box|Private\s+Bag)\s+[0-9]{{1,6}}{_LOCALITY}",
            score=0.8,
        ),
    ]
    return PatternRecognizer(
        supported_entity="ADDRESS",
        patterns=patterns,
        global_regex_flags=CASE_SENSITIVE,
    )


def phone_extension_recognizer() -> PatternRecognizer:
    """Internal extensions ('ext 4471', 'x4471') -- missed by phone libraries."""
    patterns = [
        Pattern(name="ext_word", regex=r"\b(?:ext|extn|extension)\.?\s?\d{2,6}\b", score=0.7),
        Pattern(name="ext_x", regex=r"\bx\d{3,6}\b", score=0.55),
        Pattern(name="ddi", regex=r"\bDDI\s?\+?[\d\s\-()]{6,20}\b", score=0.7),
    ]
    return PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=patterns)


def bank_account_recognizer() -> PatternRecognizer:
    """
    Recall-first bank-account backstop.

    Presidio's IbanRecognizer validates the country code and checksum, so it
    rejects account strings from non-IBAN countries (New Zealand, Australia,
    US) and any malformed-but-real reference. A scrubber must still redact an
    account-shaped string next to banking context.
    """
    patterns = [
        # Uppercase-only groups: allowing [A-Za-z] made this swallow ordinary
        # prose after a T-code ("VF04 collective run" -> false IBAN).
        Pattern(name="iban_like",
                regex=r"\b[A-Z]{2}\d{2}(?:[ \-]?[A-Z0-9]{2,6}){2,8}\b", score=0.6),
        Pattern(name="nz_au_bank",
                regex=r"\b\d{2}[ \-]\d{4}[ \-]\d{6,7}[ \-]\d{2,3}\b", score=0.6),
    ]
    return PatternRecognizer(
        supported_entity="IBAN_CODE",
        patterns=patterns,
        context=["iban", "bank", "account", "remittance", "payment", "swift", "bsb"],
        global_regex_flags=CASE_SENSITIVE,
    )


def all_sap_recognizers():
    return [
        sap_customer_number_recognizer(),
        sap_vendor_number_recognizer(),
        sap_user_id_recognizer(),
        sap_document_ref_recognizer(),
        permissive_email_recognizer(),
        company_suffix_recognizer(),
        street_address_recognizer(),
        phone_extension_recognizer(),
        bank_account_recognizer(),
    ]


SAP_ENTITIES = [
    "SAP_CUSTOMER_NO",
    "SAP_VENDOR_NO",
    "SAP_USER_ID",
    "SAP_DOC_REF",
]
