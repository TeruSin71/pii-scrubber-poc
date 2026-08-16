#!/usr/bin/env python3
"""
GLiNER tokenizer pin -- the fix_mistral_regex arbitration. BLOCKING gate.

NOT one of the six local suites. Those run against the project venv; this one
must run where the PINNED versions actually are, which is the built image:

    docker run --rm -e HF_HUB_OFFLINE=1 \
      -v "$PWD/test_gliner_tokenizer.py:/app/t.py" \
      --entrypoint python <image> /app/t.py

⚠️ HF_HUB_OFFLINE=1 IS PART OF THE TEST, NOT CONVENIENCE. Production has no
outbound network (Rule 3, and the UrlRecognizer boundary guard exists for the
same reason), so offline is the shipped condition. It is also the condition
under which this finding is TRUE -- measured:

                       flag OFF            flag ON
    HF_HUB_OFFLINE=1    0 unk, ok          7 unk, round-trip BROKEN
    HF_HUB_OFFLINE=0    0 unk, ok          0 unk, ok

Offline forces a sentencepiece -> fast CONVERSION, and the regex governs that
conversion. Online, transformers fetches a prebuilt tokenizer.json and the
flag never bites. So a tokenizer test run with network access does not test
what ships -- it silently exercises a different artifact. This suite hard-fails
if it is not running offline rather than passing against the wrong one.

WHY THIS EXISTS
---------------
Loading GLiNER emits, from transformers 4.57:

    The tokenizer you are loading from 'microsoft/mdeberta-v3-base' with an
    incorrect regex pattern... This will lead to incorrect tokenization.
    You should set the `fix_mistral_regex=True` flag...

Taken at face value that would mean every GLiNER measurement is taken on a
mis-tokenized model -- which would invalidate a bake-off before it started.
It was resolved empirically, not by reading the warning: token IDs were
diffed with the flag on and off across six representative texts, and the
disagreement was arbitrated by round-trip decode.

    flag OFF (default):   0 UNK / 22 tokens, round-trip byte-perfect
    flag ON:             11 UNK / 30 tokens, all word boundaries destroyed
                         'Escalated by NAKAMURA...' -> 'EscalatedbyNAKAMURA...'

THE WARNING IS WRONG FOR THIS MODEL. It advertises a Mistral-specific fix via
an over-broad heuristic; applying it to mdeberta-v3 (sentencepiece) shreds the
tokenization. The default is correct and the warning must be IGNORED, not
obeyed.

Nothing in the code sets the flag, so "pinning the winning value" cannot be a
config line -- the winning value IS the default. It is pinned instead by this
assertion plus the transformers pin in requirements.txt. If a future version
flips the default, or someone "fixes" the warning by setting the flag, the
round-trip breaks and this fails.
"""
import sys
import warnings

warnings.filterwarnings("ignore")

FAILURES = []


def check(name, cond, detail=""):
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


import os  # noqa: E402

import transformers  # noqa: E402
import huggingface_hub  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402

MODEL = "microsoft/mdeberta-v3-base"
_OFFLINE = os.environ.get("HF_HUB_OFFLINE") == "1"

# Print what was inspected, never just a verdict.
print(f"transformers {transformers.__version__} | huggingface_hub {huggingface_hub.__version__}")
print(f"model {MODEL} | HF_HUB_OFFLINE={os.environ.get('HF_HUB_OFFLINE', '<unset>')}")
print()

# The environment IS the test. Online, transformers pulls a prebuilt
# tokenizer.json and the flag never bites -- so an online run would pass while
# exercising an artifact production never uses.
print("Running against the SHIPPED condition, not a convenient one")
check("HF_HUB_OFFLINE=1 -- production has no outbound network", _OFFLINE,
      "run with -e HF_HUB_OFFLINE=1; online this suite tests a different "
      "tokenizer artifact than the one that ships")

print("The pinned pair is the pair this was arbitrated on")
check("transformers is the pinned 4.57.6", transformers.__version__ == "4.57.6",
      f"got {transformers.__version__} -- re-run the arbitration before trusting any GLiNER number")
check("huggingface_hub is the pinned 0.36.2", huggingface_hub.__version__ == "0.36.2",
      f"got {huggingface_hub.__version__} -- above 1.0 GLiNER cannot load at all (finding 11)")

tok = AutoTokenizer.from_pretrained(MODEL)

TEXTS = [
    "Escalated by NAKAMURA. The warehouse on Willis Street has no dock access.",
    "Contact k.mueller@corp.internal or customer 5591230.",
    "Mere Tuhoe on +64 21 555 0134, Otahuhu, Auckland 1062.",
    "VL02N refuses goods issue; check MMBE then MB52 for blocked stock.",
    "Jose Muller-Schmidt, Zurich -- diacritics and hyphens survive.",
]

print("Default tokenization is intact -- this is what 'the flag stays off' means")
for t in TEXTS:
    ids = tok(t)["input_ids"]
    unk = sum(1 for i in ids if i == tok.unk_token_id)
    check(f"no [UNK] in {t[:38]!r}", unk == 0, f"{unk}/{len(ids)} unknown tokens")
    check(f"round-trips exactly: {t[:38]!r}",
          tok.decode(ids, skip_special_tokens=True).strip() == t.strip(),
          f"got {tok.decode(ids, skip_special_tokens=True)!r}")

# The arbitration itself, re-run rather than trusted. If a future transformers
# makes the flag harmless this still passes; if it ever becomes CORRECT for
# mdeberta, this fails and the finding must be revisited.
print("The flag remains wrong for this model -- the arbitration, re-run")
try:
    bad = AutoTokenizer.from_pretrained(MODEL, fix_mistral_regex=True)
    t = TEXTS[0]
    bad_ids = bad(t)["input_ids"]
    bad_unk = sum(1 for i in bad_ids if i == bad.unk_token_id)
    bad_rt = bad.decode(bad_ids, skip_special_tokens=True)
    check("fix_mistral_regex=True still corrupts mdeberta offline (so leave it OFF)",
          bad_unk > 0 and bad_rt.strip() != t.strip(),
          f"the flag now looks HARMLESS ({bad_unk} unk). Either transformers "
          "changed, or this run is not really offline and is exercising a "
          "prebuilt tokenizer.json. Re-arbitrate; do not assume the recorded "
          "finding still holds")
except TypeError:
    print("  [ok  ] transformers no longer accepts fix_mistral_regex -- flag is gone, moot")

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
