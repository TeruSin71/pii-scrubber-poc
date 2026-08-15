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


def sap_customer_number_recognizer() -> PatternRecognizer:
    """SAP customer numbers: 10 digits, conventionally zero-padded (0001045567)."""
    patterns = [
        Pattern(name="sap_customer_padded", regex=r"\b000\d{7}\b", score=0.85),
        Pattern(name="sap_customer_ctx", regex=r"\b\d{10}\b", score=0.35),
    ]
    return PatternRecognizer(
        supported_entity="SAP_CUSTOMER_NO",
        patterns=patterns,
        context=["customer", "sold-to", "ship-to", "bill-to", "kunnr", "payer", "account"],
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
        phone_extension_recognizer(),
        bank_account_recognizer(),
    ]


SAP_ENTITIES = [
    "SAP_CUSTOMER_NO",
    "SAP_VENDOR_NO",
    "SAP_USER_ID",
    "SAP_DOC_REF",
]
