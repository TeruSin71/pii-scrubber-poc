"""
PII Scrubber -- POC serving app for SAP AI Core.

Two modes, one engine (matches the architecture):
  * batch  -- scrub source material on its way into the KB corpus
  * live   -- tokenize an incident payload before triage, with a reversible map

Engines (env SCRUBBER_ENGINE): presidio | gliner | both
  Start with 'presidio' to prove the deployment, then flip to 'both' to add
  contextual recall from GLiNER. Keeps the first deploy light on the
  free-tier 'starter' resource plan.

Endpoints:
  GET  /health                      -- instant readiness (does NOT load models)
  GET  /info, /v1/info              -- engine + model config + build_version
                                       (/v1 route: the AI Core gateway proxies
                                       /v1/* only, /info returns RBAC denied)
  POST /v1/scrub                    -- scrub one text
  POST /v1/models/pii-scrubber:predict  -- KServe-style wrapper
  GET  /v1/selftest                 -- run the labelled synthetic SAP samples,
                                       return recall/precision per PII type
"""

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scrubber")

ENGINE = os.getenv("SCRUBBER_ENGINE", "presidio").lower()
GLINER_MODEL = os.getenv("GLINER_MODEL", "urchade/gliner_multi_pii-v1")
SPACY_MODEL = os.getenv("SPACY_MODEL", "en_core_web_sm")
GLINER_THRESHOLD = float(os.getenv("GLINER_THRESHOLD", "0.4"))

# Per-type confidence floors. A single global threshold is too blunt: it
# either lets noisy pattern types (USER_ID) flood the output, or discards
# valid low-scored hits from deterministic types. Deterministic, structurally
# validated types are trusted at low scores; noisy pattern types must earn a
# context boost to survive.
TYPE_THRESHOLDS = {
    "EMAIL": 0.30, "IBAN": 0.30, "IP_ADDRESS": 0.30,
    "CUSTOMER_NO": 0.50, "VENDOR_NO": 0.50,
    "PHONE": 0.30,
    "PERSON": 0.50, "ADDRESS": 0.50, "ORG_NAME": 0.50,
    "USER_ID": 0.55,          # noisy: needs a context word to clear this
    "DOC_REF": 0.55,
}
DEFAULT_THRESHOLD = float(os.getenv("PRESIDIO_THRESHOLD", "0.50"))

# Phone regions matter: the default US-only recognizer misses NZ/AU numbers.
PHONE_REGIONS = os.getenv("PHONE_REGIONS", "NZ,AU,GB,DE,US,PL").split(",")
SAMPLES_PATH = os.getenv("SAMPLES_PATH", str(Path(__file__).parent / "samples.json"))

# Entity labels GLiNER is asked to find. Zero-shot: add SAP-specific ones freely.
GLINER_LABELS = [
    "person", "email address", "phone number", "physical address",
    "organization", "customer number", "vendor number", "user id",
    "ip address", "bank account number",
]

# Map every engine's native labels onto one shared taxonomy.
LABEL_MAP = {
    "PERSON": "PERSON", "person": "PERSON",
    "EMAIL_ADDRESS": "EMAIL", "email address": "EMAIL", "email": "EMAIL",
    "PHONE_NUMBER": "PHONE", "phone number": "PHONE",
    "LOCATION": "ADDRESS", "physical address": "ADDRESS", "address": "ADDRESS",
    "ORG": "ORG_NAME", "ORGANIZATION": "ORG_NAME", "organization": "ORG_NAME",
    "NRP": "ORG_NAME",
    "IP_ADDRESS": "IP_ADDRESS", "ip address": "IP_ADDRESS",
    "IBAN_CODE": "IBAN", "bank account number": "IBAN", "iban": "IBAN",
    "SAP_CUSTOMER_NO": "CUSTOMER_NO", "customer number": "CUSTOMER_NO",
    "SAP_VENDOR_NO": "VENDOR_NO", "vendor number": "VENDOR_NO",
    "SAP_USER_ID": "USER_ID", "user id": "USER_ID",
    "SAP_DOC_REF": "DOC_REF",
    "URL": "URL", "DATE_TIME": "DATE",
}


def unmapped_labels(nlp_engine, labels_to_ignore=None) -> List[str]:
    """Entity labels the NLP layer can emit that LABEL_MAP does not translate.

    Such a label has no redacting type: it falls through _norm's
    `label.upper()` default and lands outside REDACT_TYPES. Trap 8, and the
    reason the gap is announced.

    ⚠️ THIS IS A SUPERSET OF THE LEAK LIST, NOT THE LEAK LIST -- corrected in
    1.2.3 on measurement, and the correction is the point of the entry.
    Three filters sit between the model and _norm. This function models two:
    presidio's `labels_to_ignore` and its entity mapping. It does NOT model
    the third and narrowest, the registered recognizer's `supported_entities`,
    which is applied last. A label can therefore be reported here and never
    reach the pipeline at all.

    FAC is exactly that case on the shipped config: spaCy `sm` emits it,
    presidio neither maps nor ignores it -- so this function reports it, and
    correctly, because it IS unmapped -- but SpacyRecognizer declares support
    only for DATE_TIME/NRP/LOCATION/PERSON/ORGANIZATION, so no
    RecognizerResult is ever produced and FAC never reaches _norm. The label
    is right; the old accompanying claim that such spans are "detected and
    then dropped" was wrong for it. Whether a reported label is dropped AFTER
    detection or never detected at all is NOT determined by this function.
    Both are gaps and neither redacts, which is why the report is still worth
    making. Evidence: fac_probe_validation.md. Modelling supported_entities is
    deferred to the recognizer plan; only the documentation is corrected here.

    Announced on FIRST ANALYZER BUILD, not at process start: model loading is
    lazy so /health stays instant and readiness probes never time out. A pod
    that has only answered health checks has not logged it yet.

    Reads presidio's OWN configuration rather than reimplementing it: each
    spaCy label is either translated to a presidio entity, ignored outright,
    or passed through raw.

    `labels_to_ignore` MUST be the list the engine was actually built with.
    get_analyzer() un-ignores ORG, and reading presidio's installed default
    instead happens to give the same answer -- but only because ORG is the
    ONE label in that default whose presidio entity is in LABEL_MAP.
    Measured on the pinned stack: of the 11 ignored labels this model can
    emit, ORG is mapped and the other ten (CARDINAL, EVENT, LANGUAGE, LAW,
    MONEY, ORDINAL, PERCENT, PRODUCT, QUANTITY, WORK_OF_ART) are not.
    Un-ignore any of those ten and a default-reading diagnostic reports clean
    while the pipeline drops spans -- a silent diagnostic, which is the very
    failure this function exists to prevent. Correct by coincidence is not
    correct. Defaults to the installed list so the function stays callable
    standalone in tests.
    """
    try:
        from presidio_analyzer.nlp_engine import NerModelConfiguration
        cfg = NerModelConfiguration()
        mapping = cfg.model_to_presidio_entity_mapping or {}
        ignored = set(labels_to_ignore if labels_to_ignore is not None
                      else (cfg.labels_to_ignore or []))
        model_labels = set()
        for nlp in (getattr(nlp_engine, "nlp", None) or {}).values():
            model_labels |= set(nlp.pipe_labels.get("ner", []))
        emitted = {mapping.get(lb, lb) for lb in model_labels if lb not in ignored}
        return sorted(e for e in emitted
                      if e not in LABEL_MAP and e.lower() not in LABEL_MAP)
    except Exception as exc:
        log.warning("Could not compute unmapped labels: %s", exc)
        return []

# Types we always redact. DATE/URL/DOC_REF are detected but reported only,
# so the POC can show them without over-scrubbing technical text.
REDACT_TYPES = {
    "PERSON", "EMAIL", "PHONE", "ADDRESS", "ORG_NAME",
    "IP_ADDRESS", "IBAN", "CUSTOMER_NO", "VENDOR_NO", "USER_ID",
}

# --------------------------------------------------------------------------
# Technical allowlist -- never redact these.
#
# SAP transaction codes and status/error codes look like PII to a generic
# detector (VF04 scans as an account number, ME23N as a user ID). Redacting
# them destroys the technical meaning the KB depends on. Populate
# allowlist.txt from SAP table TSTC (one token per line) to fix this.
# --------------------------------------------------------------------------
ALLOWLIST_PATH = os.getenv("ALLOWLIST_PATH", str(Path(__file__).parent / "allowlist.txt"))

# Hand-curated SAP jargon, loaded into the SAME set through the SAME loader.
# It is data, not mechanism -- so it inherits case-sensitive exact match, the
# +/-40-char user-context backstop, and whole-span matching, instead of
# reimplementing any of them. A glossary entry may veto a PATTERN, never
# CONTEXT: "posted by Driver" still redacts. See glossary.txt and
# test_jargon.py.
GLOSSARY_PATH = os.getenv("GLOSSARY_PATH", str(Path(__file__).parent / "glossary.txt"))

# Baked at build time by the Dockerfile (ARG -> ENV) and read once here.
# Default "dev" on purpose: an image built without --build-arg must be
# VISIBLY wrong, not plausibly right. From the stale-deployment incident --
# a script measured a live-but-stale deployment and reported confident
# numbers for an artifact nothing in the response identified. Surfaced by
# /info and /v1/selftest so every number carries the build that produced it.
#
# `or "dev"`, NOT os.getenv(..., "dev"): the two-arg form returns "" when the
# variable is set but empty, and FastAPI asserts a truthy version when it
# builds the OpenAPI schema --
#   AssertionError: A version must be provided for OpenAPI, e.g.: '2.1.0'
# -- so `--build-arg BUILD_VERSION=` would not mislabel the service, it would
# stop it booting. On a 1-pod tier where an admission-rejected revision is
# permanent, that is a far worse failure than a wrong string. Measured, not
# theorised: the empty-value service exited 1 at startup.
BUILD_VERSION = os.getenv("BUILD_VERSION") or "dev"


def _load_allowlist() -> set:
    tokens = {
        # Minimal built-in seed; replace/extend from TSTC.
        "VF04", "VF01", "VF02", "VF03", "VA01", "VA02", "VA03",
        "ME21N", "ME22N", "ME23N", "VK11", "VK12", "VK13",
        "VD51N", "OVKK", "SE16N", "SE38", "SM37", "ST22",
        "PR00", "NAST", "IDOC", "IDoc", "GR/IR", "BPA", "CPI", "FSD",
    }
    for label, path in (("Allowlist", ALLOWLIST_PATH), ("Glossary", GLOSSARY_PATH)):
        before = len(tokens)
        try:
            with open(path) as fh:
                for line in fh:
                    # Strip INLINE comments too, not just full-line ones. The
                    # miner emits "TOKEN   # count=N  detected_as=TYPE"; keeping
                    # only lines that *start* with '#' stored the whole 46-char
                    # string as a token that matches nothing -- a populated-looking
                    # allowlist with zero effect. (Defect found in plan review.)
                    # The glossary reuses this to carry its one-word reason
                    # column: "Basis   # module".
                    t = line.split("#", 1)[0].strip()
                    if t:
                        tokens.add(t)
            log.info("%s loaded: %d tokens (total %d)", label, len(tokens) - before, len(tokens))
        except FileNotFoundError:
            log.info("No %s file at %s -- skipped (total %d)", label.lower(), path, len(tokens))
    return tokens


# --------------------------------------------------------------------------
# Deterministic custom-object rule.
#
# SAP reserves the Z* and Y* namespaces, and registered /NAMESPACE/ prefixes,
# exclusively for customer development. So a token in that shape is provably a
# technical object, not PII -- a rule rather than a list. It needs no extract,
# no maintenance, and it covers Z-objects created after any extract was taken.
#
# The trap is surnames: Zhang, Young, Yamamoto, Zimmermann all start with Z/Y.
# The discriminator is SHAPE, not the prefix:
#   * contains "_" or a digit  -> unambiguously technical (ZSD_REBATE_CALC, ZVA01)
#   * pure uppercase letters   -> ambiguous with an ALL-CAPS surname, so a
#                                 guard list of common Z/Y surnames is excluded
#   * title case (Zhang)       -> never matches; the rule requires all-uppercase
# --------------------------------------------------------------------------
CUSTOM_OBJ_RE = re.compile(r"^[ZY][A-Z0-9_]{2,29}$")
NAMESPACE_RE = re.compile(r"^/[A-Z0-9]{2,10}/[A-Z0-9_]{2,30}$")

# All-caps surnames that would otherwise be swallowed by the pure-alpha branch.
ZY_SURNAME_GUARD = {
    "ZHANG", "ZHAO", "ZHOU", "ZHENG", "ZHU", "ZENG", "ZUNIGA", "ZIMMER",
    "ZIMMERMANN", "ZIEGLER", "ZELLER", "ZAMORA", "ZAHRA", "ZAIDI", "ZAMAN",
    "YANG", "YOUNG", "YAMAMOTO", "YAMADA", "YILMAZ", "YOSHIDA", "YUSUF",
    "YADAV", "YOON", "YATES", "YEUNG", "YIP", "YU", "YEE", "YOUSSEF",
}

ENABLE_CUSTOM_OBJ_RULE = os.getenv("CUSTOM_OBJECT_RULE", "true").lower() == "true"


def is_custom_sap_object(token: str) -> bool:
    """True if the token is provably a customer-namespace SAP technical object."""
    if not ENABLE_CUSTOM_OBJ_RULE:
        return False
    t = token.strip().strip(".,;:'\"()")
    if NAMESPACE_RE.match(t):
        return True
    if not CUSTOM_OBJ_RE.match(t):
        return False
    if "_" in t or any(c.isdigit() for c in t):
        return True          # unambiguously technical
    return t not in ZY_SURNAME_GUARD   # pure alpha: guard against ALL-CAPS names


ALLOWLIST = _load_allowlist()

# CASE-SENSITIVE ON PURPOSE. Several SAP object names collide with real
# surnames -- MARA, LIPS, KNA1, BRAUN, KLEIN. A case-insensitive allowlist
# would stop redacting a person called "Mara" the moment the MARA table name
# was allowlisted. SAP technical tokens are uppercase by convention, so exact
# case is the discriminator that keeps the allowlist from creating a leak.
# Mixed-case entries (e.g. "IDoc") are matched as written.
ALLOWLIST_EXACT = set(ALLOWLIST)

# version= tracks the build, not a literal. It read "1.0.0" on every image
# ever shipped, including the deployed 1.2.0 -- wrong information, not
# missing information, and visible on /docs.
app = FastAPI(title="PII Scrubber (POC)", version=BUILD_VERSION)

_lock = threading.Lock()
_analyzer = None
_gliner = None
_load_error: Optional[str] = None

# Labels the model emits that LABEL_MAP does not translate, computed once at
# analyzer build and surfaced by /info. Stays None until that build: the
# warning it mirrors fires lazily, and reporting [] beforehand would claim
# "nothing unmapped" before anything could have been checked. None means
# "not known yet" -- a false negative here would hide the very drop this
# exists to announce.
_unmapped: Optional[List[str]] = None

# Shipped IN the /v1/info payload, not only in a docstring nobody curls.
# 1.2.3 corrected three descriptions of this field and left the field itself
# bare: a one-element list `["FAC"]` that reads exactly like a leak list to
# anyone hitting the endpoint. It is not one -- it is a SUPERSET, and the
# caveat has to travel with the value or it does not travel at all.
# A field whose meaning lives somewhere the reader is not is an unlabelled
# number, and this project has already paid for one of those.
UNMAPPED_LABELS_SEMANTICS = (
    "SUPERSET of entity labels that LABEL_MAP does not translate -- NOT a "
    "leak list. Models presidio's labels_to_ignore and its entity mapping, "
    "but NOT the recognizer's supported_entities, so a label listed here may "
    "be dropped AFTER detection or may never reach the pipeline at all "
    "(FAC is the latter on this build: SpacyRecognizer does not support it, "
    "so the span is discarded before LABEL_MAP is consulted). "
    "null = analyzer not built yet, nothing checked; [] = checked, nothing "
    "unmapped. Evidence: fac_probe_validation.md."
)


# --------------------------------------------------------------------------
# Lazy model loading -- keeps /health instant so readiness probes never time
# out while a multi-hundred-MB model warms up.
# --------------------------------------------------------------------------

def get_analyzer():
    global _analyzer, _load_error
    if _analyzer is not None:
        return _analyzer
    with _lock:
        if _analyzer is None:
            try:
                from presidio_analyzer import AnalyzerEngine
                from presidio_analyzer.nlp_engine import NlpEngineProvider
                from recognizers import all_sap_recognizers

                # presidio 2.2.357's NerModelConfiguration.labels_to_ignore
                # contains ORG and ORGANIZATION, so spaCy's ORG entity is
                # discarded at the NLP-engine layer -- before any recognizer
                # runs. Effect: an unsuffixed company name ("Pacific Traders")
                # is undetectable, because company_suffix_recognizer needs a
                # legal suffix and this was the only other path. Rebuild the
                # ignore list from the installed default minus ORG so the fix
                # is correct on 2.2.357 and a no-op on versions that already
                # allow it.
                # BOTH initialised here: `keep` is passed to unmapped_labels()
                # below, and if this try fails it would otherwise be unbound.
                # A NameError there is caught by the outer handler and becomes
                # _load_error -- i.e. an optional diagnostic would take the
                # whole analyzer down. This path must keep degrading the way
                # it did before item 1: engine builds on presidio defaults,
                # diagnostic falls back to the installed ignore list.
                ner_cfg = keep = None
                try:
                    from presidio_analyzer.nlp_engine import NerModelConfiguration
                    default_ignore = set(NerModelConfiguration().labels_to_ignore or [])
                    keep = sorted(default_ignore - {"ORG", "ORGANIZATION"})
                    ner_cfg = {"labels_to_ignore": keep}
                    log.info("ORG un-ignored at NLP layer (%d labels still ignored)",
                             len(keep))
                except Exception as exc:
                    log.warning("Could not adjust NerModelConfiguration: %s", exc)

                nlp_conf = {
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
                }
                if ner_cfg:
                    nlp_conf["ner_model_configuration"] = ner_cfg
                provider = NlpEngineProvider(nlp_configuration=nlp_conf)
                nlp_engine = provider.create_engine()
                engine = AnalyzerEngine(nlp_engine=nlp_engine,
                                        supported_languages=["en"])

                # Trap 8: an entity label with no LABEL_MAP entry maps nowhere
                # and never becomes a redacting type. Announce it. This does
                # NOT change detection -- mapping a label to a redacting type
                # is a behaviour change needing its own evidence -- it makes
                # an unannounced gap a visible one, so a future model or spaCy
                # upgrade cannot introduce one without saying so on first
                # analyzer build.
                # What this list is NOT: the set of labels that leak. It does
                # not model the recognizer's supported_entities, so a reported
                # label may never reach the pipeline at all -- FAC does not.
                # Superset, deliberately. See unmapped_labels' docstring.
                # `keep` -- the list THIS engine was built with, not the
                # installed default. See unmapped_labels' docstring: reading
                # the default is correct only by coincidence.
                # ADVISORY, AND STRUCTURALLY UNABLE TO BREAK WHAT IT ADVISES
                # ON. Everything in this block is reporting: it changes no
                # detection, so no failure inside it may reach the analyzer's
                # error path. A diagnostic that can take down the thing it
                # diagnoses has negative value -- it converts a reporting gap
                # into an outage.
                #
                # This is the class fix. The instance was `keep` being unbound
                # when the NerModelConfiguration adjustment failed; wrapping
                # here also covers a bad argument, a presidio internal change,
                # or a failure inside the log call itself. Pinned by
                # test_label_map.py, which forces unmapped_labels to raise and
                # asserts detection still works.
                try:
                    global _unmapped
                    unmapped = unmapped_labels(nlp_engine, labels_to_ignore=keep)
                    _unmapped = unmapped
                    if unmapped:
                        log.warning(
                            "LABEL_MAP has no entry for: %s -- these labels "
                            "have no redacting type, so they are never "
                            "redacted. This check does not model recognizer "
                            "supported_entities: a label listed here may be "
                            "dropped AFTER detection, or may never reach the "
                            "pipeline at all (FAC is the latter) (trap 8)",
                            ", ".join(unmapped))
                    else:
                        log.info("LABEL_MAP covers every label the model emits")
                except Exception as exc:  # noqa: BLE001 -- advisory, never fatal
                    log.warning("unmapped-label diagnostic failed: %s -- "
                                "detection is unaffected", exc)

                # BOUNDARY GUARD: Presidio's UrlRecognizer pulls the public
                # suffix list from publicsuffix.org at runtime -- an outbound
                # call from inside the compliance boundary. We don't redact
                # URLs, so remove it entirely. Verified: without this the
                # container attempts an external fetch on first analyze().
                try:
                    engine.registry.remove_recognizer("UrlRecognizer")
                    log.info("Removed UrlRecognizer (prevents outbound call)")
                except Exception:
                    pass

                # ORGANIZATION is absent from SpacyRecognizer.supported_entities
                # in presidio 2.2.357 (present in 2.2.364), so spaCy detects
                # ('Pacific Traders', 'ORG') and the recognizer silently drops
                # it -- an unsuffixed company name becomes undetectable. The
                # ORGANIZATION->ORG label mapping already exists in
                # CHECK_LABEL_GROUPS; only the entity is missing. Re-register
                # with it added, reading the current list rather than
                # hardcoding one, so this is correct on either version.
                try:
                    from presidio_analyzer.predefined_recognizers import SpacyRecognizer
                    current = list(getattr(engine.registry, "recognizers", []))
                    spacy_rec = next((r for r in current
                                      if type(r).__name__ == "SpacyRecognizer"), None)
                    ents = list(getattr(spacy_rec, "supported_entities", []) or [])
                    if "ORGANIZATION" not in ents:
                        ents.append("ORGANIZATION")
                        engine.registry.remove_recognizer("SpacyRecognizer")
                        engine.registry.add_recognizer(
                            SpacyRecognizer(supported_entities=ents))
                        log.info("SpacyRecognizer re-registered with ORGANIZATION")
                    else:
                        log.info("SpacyRecognizer already supports ORGANIZATION")
                except Exception as exc:
                    log.warning("Could not extend SpacyRecognizer entities: %s", exc)

                # Default PhoneRecognizer is US-centric; re-register with the
                # regions our tickets actually contain.
                try:
                    from presidio_analyzer.predefined_recognizers import PhoneRecognizer
                    engine.registry.remove_recognizer("PhoneRecognizer")
                    engine.registry.add_recognizer(
                        PhoneRecognizer(supported_regions=PHONE_REGIONS))
                    log.info("PhoneRecognizer regions: %s", PHONE_REGIONS)
                except Exception as exc:
                    log.warning("Could not re-register PhoneRecognizer: %s", exc)

                for rec in all_sap_recognizers():
                    engine.registry.add_recognizer(rec)
                _analyzer = engine
                log.info("Presidio analyzer ready (spacy=%s)", SPACY_MODEL)
            except Exception as exc:  # pragma: no cover
                _load_error = f"presidio: {exc}"
                log.exception("Presidio failed to load")
                raise
    return _analyzer


def get_gliner():
    global _gliner, _load_error
    if _gliner is not None:
        return _gliner
    with _lock:
        if _gliner is None:
            try:
                from gliner import GLiNER
                _gliner = GLiNER.from_pretrained(GLINER_MODEL)
                log.info("GLiNER ready (%s)", GLINER_MODEL)
            except Exception as exc:  # pragma: no cover
                _load_error = f"gliner: {exc}"
                log.exception("GLiNER failed to load")
                raise
    return _gliner


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------

def _norm(label: str) -> str:
    return LABEL_MAP.get(label, LABEL_MAP.get(label.lower(), label.upper()))


# Words that signal "this token is an actor, not an object". Checked in a
# +/-40-char window around a span before allowlist/custom-rule suppression is
# allowed. Kept intentionally narrow: a false hit merely over-redacts one
# technical token (safe), while a miss on a real user ID would be a leak.
_USER_CONTEXT_RE = re.compile(
    r"\b(user(?:\s?id)?|uname|posted\s+by|reported\s+by|requested\s+by|"
    r"created\s+by|changed\s+by|logged\s+(?:in|on)|ran\s+by|run\s+by|"
    r"approver|planner|account\s+of|on\s+behalf\s+of|author)\b",
    re.IGNORECASE,
)
_USER_CONTEXT_WINDOW = 40


def _in_user_context(text: str, start: int, end: int) -> bool:
    lo = max(0, start - _USER_CONTEXT_WINDOW)
    hi = min(len(text), end + _USER_CONTEXT_WINDOW)
    return bool(_USER_CONTEXT_RE.search(text[lo:hi]))


def detect(text: str, engine: str) -> List[Dict[str, Any]]:
    spans: List[Dict[str, Any]] = []

    if engine in ("presidio", "both"):
        for r in get_analyzer().analyze(text=text, language="en"):
            etype = _norm(r.entity_type)
            floor = TYPE_THRESHOLDS.get(etype, DEFAULT_THRESHOLD)
            if float(r.score) < floor:
                continue
            spans.append({
                "start": r.start, "end": r.end, "text": text[r.start:r.end],
                "type": etype, "score": round(float(r.score), 3),
                "engine": "presidio",
            })

    if engine in ("gliner", "both"):
        for e in get_gliner().predict_entities(text, GLINER_LABELS,
                                               threshold=GLINER_THRESHOLD):
            spans.append({
                "start": e["start"], "end": e["end"], "text": e["text"],
                "type": _norm(e["label"]), "score": round(float(e.get("score", 0)), 3),
                "engine": "gliner",
            })

    # Drop spans that are a known technical token (exact case) or that match
    # the deterministic customer-namespace rule -- UNLESS the span sits in
    # user context (see _in_user_context). This is the automated backstop for
    # the all-caps collision: case sensitivity protects "Mara" the person from
    # MARA the table, but an SAP *user ID* is all-caps by convention, so a
    # real user ID of KLEIN or BRAUN is byte-identical to the allowlistable
    # token. An allowlist may veto a pattern; it must not veto context.
    # "Check table KLEIN" -> suppressed; "posted by KLEIN" -> still redacted.
    # Shape decides how much the context backstop applies:
    #   * underscore/digit/namespace tokens (ZSD_REBATE_CALC, VA01, /IWFND/..)
    #     are unambiguously technical -- suppression is unconditional. A
    #     surname-style user ID cannot take this shape.
    #   * pure-alpha tokens (KLEIN, MARA, VBAK) are the collision class --
    #     suppression is refused when user context is present.
    kept = []
    for s in spans:
        token = s["text"].strip().strip(".,;:'\"()")
        suppressible = (token in ALLOWLIST_EXACT) or is_custom_sap_object(token)
        if suppressible:
            unambiguous = ("_" in token or any(c.isdigit() for c in token)
                           or bool(NAMESPACE_RE.match(token)))
            if unambiguous or not _in_user_context(text, s["start"], s["end"]):
                continue
        kept.append(s)
    spans = kept

    return _merge(spans)


def _merge(spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Resolve overlapping spans.

    CRITICAL ordering rule: a span whose type is redacted always outranks one
    that is not, regardless of score. Without this, a higher-scoring
    non-redacting label swallows a redacting one and the value leaks --
    observed for real: spaCy tags '172.16.4.8' as DATE_TIME (0.85), beating
    IP_ADDRESS (0.60), and DATE is not redacted. Protection wins over
    confidence. Then prefer longer spans, then higher scores.
    """
    spans.sort(key=lambda s: (
        0 if s["type"] in REDACT_TYPES else 1,
        -(s["end"] - s["start"]),
        -s["score"],
    ))
    kept: List[Dict[str, Any]] = []
    for s in spans:
        if not any(s["start"] < k["end"] and k["start"] < s["end"] for k in kept):
            kept.append(s)
    kept.sort(key=lambda s: s["start"])
    return kept


def scrub(text: str, mode: str = "batch") -> Dict[str, Any]:
    """
    batch -> replace with <TYPE>
    live  -> replace with <TYPE_n> and return the reverse map so the caller can
             re-map INSIDE the boundary after the LLM answers.
    """
    spans = detect(text, ENGINE)
    targets = [s for s in spans if s["type"] in REDACT_TYPES]

    out, cursor, mapping, counters = [], 0, {}, {}
    for s in targets:
        out.append(text[cursor:s["start"]])
        if mode == "live":
            counters[s["type"]] = counters.get(s["type"], 0) + 1
            token = f"<{s['type']}_{counters[s['type']]}>"
            mapping[token] = s["text"]
        else:
            token = f"<{s['type']}>"
        out.append(token)
        cursor = s["end"]
    out.append(text[cursor:])

    return {
        "scrubbed_text": "".join(out),
        "entities": spans,
        "redacted_count": len(targets),
        "token_map": mapping if mode == "live" else {},
        "engine": ENGINE,
        "mode": mode,
    }


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

class ScrubRequest(BaseModel):
    text: str
    mode: str = Field(default="batch", description="batch | live")


@app.get("/health")
@app.get("/v1/health")
@app.get("/")
def health():
    return {"status": "ok", "engine": ENGINE}


@app.get("/info")
@app.get("/v1/info")
def info():
    # Two paths, ONE handler -- same stacking idiom as health() above.
    # /info is not proxied by the AI Core inference gateway; only /v1/* is,
    # and GET $AI_API/v2/inference/deployments/<id>/info returns
    # "RBAC: access denied" (confirmed on d08c99a19640540f). Without the /v1
    # route, reading a build off a deployment means running a 13-sample
    # selftest, so nobody checks casually -- and an identity check people
    # avoid is one that does not happen.
    return {
        "build_version": BUILD_VERSION,
        "engine": ENGINE,
        "gliner_model": GLINER_MODEL if ENGINE in ("gliner", "both") else None,
        "spacy_model": SPACY_MODEL,
        # null until the analyzer is built (lazy). null = "not known yet",
        # [] = "checked, nothing unmapped". Do not collapse them.
        "unmapped_labels": _unmapped,
        # The value's meaning travels WITH the value. See the constant.
        "unmapped_labels_semantics": UNMAPPED_LABELS_SEMANTICS,
        "presidio_loaded": _analyzer is not None,
        "gliner_loaded": _gliner is not None,
        "last_load_error": _load_error,
        "redact_types": sorted(REDACT_TYPES),
    }


@app.post("/v1/scrub")
def v1_scrub(req: ScrubRequest):
    return scrub(req.text, req.mode)


@app.post("/v1/models/pii-scrubber:predict")
def kserve_predict(payload: Dict[str, Any]):
    """KServe-style: {"instances":[{"text":"...","mode":"batch"}]}"""
    instances = payload.get("instances") or [payload]
    return {"predictions": [
        scrub(i.get("text", ""), i.get("mode", "batch")) for i in instances
    ]}


# --------------------------------------------------------------------------
# Self-test: the bake-off, running inside the deployed service
# --------------------------------------------------------------------------

def _covered(value: str, spans: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Was this ground-truth value actually covered by a span that gets redacted?

    Deliberately strict: only spans whose type is in REDACT_TYPES count, because
    a span that is detected but never redacted does not protect the data. A
    loose 'any overlap counts' check overstates recall, which for a compliance
    measurement is the most dangerous kind of error.
    """
    v = re.sub(r"\s+", " ", value).strip().lower()
    best = None
    for s in spans:
        if s["type"] not in REDACT_TYPES:
            continue
        d = re.sub(r"\s+", " ", s["text"]).strip().lower()
        if v == d or v in d or d in v:
            # Prefer a span whose type also matches -- but any redacting span
            # still protects the value.
            if best is None or s.get("_type_match"):
                best = s
    return best


@app.get("/v1/selftest")
def selftest():
    with open(SAMPLES_PATH) as fh:
        data = json.load(fh)
    samples = data["samples"]

    per_type: Dict[str, Dict[str, Any]] = {}
    misses: List[Dict[str, str]] = []
    mistyped: List[Dict[str, str]] = []
    total_expected = total_found = total_redacting_spans = 0
    matched_span_ids = set()

    for smp in samples:
        spans = detect(smp["text"], ENGINE)
        redacting = [s for s in spans if s["type"] in REDACT_TYPES]
        total_redacting_spans += len(redacting)

        for gt in smp["pii"]:
            t = gt["type"]
            per_type.setdefault(t, {"expected": 0, "redacted": 0, "correct_type": 0})
            per_type[t]["expected"] += 1
            total_expected += 1

            hit = _covered(gt["value"], spans)
            if hit:
                per_type[t]["redacted"] += 1
                total_found += 1
                matched_span_ids.add((smp["id"], hit["start"], hit["end"]))
                if hit["type"] == t:
                    per_type[t]["correct_type"] += 1
                else:
                    mistyped.append({
                        "sample_id": smp["id"], "value": gt["value"],
                        "expected_type": t, "detected_as": hit["type"],
                    })
            else:
                misses.append({
                    "sample_id": smp["id"], "source_type": smp["source_type"],
                    "missed_value": gt["value"], "pii_type": t,
                })

        for s in redacting:
            if (smp["id"], s["start"], s["end"]) not in matched_span_ids:
                s.setdefault("_fp_candidate", True)

    for t, c in per_type.items():
        c["recall_pct"] = round(100.0 * c["redacted"] / c["expected"], 1) if c["expected"] else None

    over_detected = max(0, total_redacting_spans - total_found)

    return {
        "build_version": BUILD_VERSION,
        "engine": ENGINE,
        "samples_run": len(samples),
        "overall": {
            "expected_pii": total_expected,
            "redacted": total_found,
            "missed": total_expected - total_found,
            "recall_pct": round(100.0 * total_found / total_expected, 1) if total_expected else None,
            "redacting_spans_emitted": total_redacting_spans,
            "over_detections": over_detected,
            "over_detection_note": "Extra redactions are safe-but-noisy: acceptable on the "
                                   "live path (over-redacting costs nothing), worth tuning "
                                   "for the build path where entries must stay readable.",
        },
        "measurement": "Recall counts a value as caught ONLY if a span that is actually "
                       "redacted covers it. Detected-but-not-redacted does not count.",
        "per_type": dict(sorted(per_type.items())),
        "misses": misses,
        "type_mismatches": mistyped,
        "interpretation": "Misses are exactly what the BPA human gate must catch. "
                          "Watch SAP-specific types (CUSTOMER_NO / VENDOR_NO / USER_ID) -- "
                          "those are where off-the-shelf models fail.",
    }
