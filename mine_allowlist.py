#!/usr/bin/env python3
"""
Mine allowlist candidates from your own corpus.

Why this exists: DD03L holds every field of every table in SAP (~200k+
distinct names) and is impractical to export. But your tickets and specs only
ever mention a few hundred distinct technical tokens. Mining those is smaller,
self-calibrating, and covers exactly the vocabulary you actually use.

What it does: runs the scrubber over a folder of text, collects every span it
WOULD redact that looks like a technical identifier (all-uppercase, no
spaces), and ranks them by frequency for one human review pass.

    python mine_allowlist.py ./corpus --out allowlist-candidates.txt

Then: review the file, delete anything that is genuinely PII, and append the
rest to allowlist.txt. Review is required -- an all-caps surname could appear
in this list, and allowlisting it would create a leak.

The corpus MAY contain real ticket text -- this runs locally, inside your
boundary, and writes only the candidate tokens. Do not commit the corpus or
an unreviewed candidates file.
"""

import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("SCRUBBER_ENGINE", "presidio")

import app as scrubber  # noqa: E402

# A technical-looking token: uppercase letters/digits, optional _ - / .
TECHNICAL_SHAPE = re.compile(r"^[A-Z][A-Z0-9_\-/\.]{1,29}$")


def looks_technical(text: str) -> bool:
    t = text.strip().strip(".,;:'\"()")
    if not TECHNICAL_SHAPE.match(t):
        return False
    if any(c.islower() for c in t):
        return False
    return True


def read_corpus(path: Path):
    exts = {".txt", ".md", ".csv", ".json", ".log"}
    if path.is_file():
        yield path.name, path.read_text(errors="ignore")
        return
    for p in sorted(path.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            yield str(p.relative_to(path)), p.read_text(errors="ignore")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", type=Path, help="File or folder of ticket/spec text")
    ap.add_argument("--out", type=Path, default=Path("allowlist-candidates.txt"))
    ap.add_argument("--min-count", type=int, default=1,
                    help="Only propose tokens seen at least this many times")
    args = ap.parse_args()

    if not args.corpus.exists():
        print(f"ERROR: {args.corpus} not found", file=sys.stderr)
        return 1

    counts: Counter = Counter()
    by_type: dict = {}
    docs = 0

    for name, text in read_corpus(args.corpus):
        docs += 1
        for span in scrubber.detect(text, scrubber.ENGINE):
            if span["type"] not in scrubber.REDACT_TYPES:
                continue
            tok = span["text"].strip().strip(".,;:'\"()")
            if not looks_technical(tok):
                continue
            if tok in scrubber.ALLOWLIST_EXACT:
                continue
            if scrubber.is_custom_sap_object(tok):
                continue          # already handled deterministically
            counts[tok] += 1
            by_type.setdefault(tok, Counter())[span["type"]] += 1

    proposed = [(t, c) for t, c in counts.most_common() if c >= args.min_count]

    with open(args.out, "w") as fh:
        fh.write("# Allowlist CANDIDATES -- REVIEW BEFORE USE\n")
        fh.write(f"# Mined from {docs} document(s) in {args.corpus}\n")
        fh.write("#\n")
        fh.write("# Each line is a token the scrubber WOULD redact but which looks\n")
        fh.write("# technical. Delete any line that is genuinely PII (an all-caps\n")
        fh.write("# surname, a customer acronym), then append the rest to allowlist.txt.\n")
        fh.write("#\n")
        fh.write("# format:  TOKEN   # count=N  detected_as=TYPE\n\n")
        for tok, c in proposed:
            types = ",".join(f"{k}:{v}" for k, v in by_type[tok].most_common())
            fh.write(f"{tok}   # count={c}  detected_as={types}\n")

    print(f"Scanned {docs} document(s)")
    print(f"Proposed {len(proposed)} allowlist candidate(s) -> {args.out}")
    if proposed:
        print("\nTop candidates:")
        for tok, c in proposed[:20]:
            types = ",".join(f"{k}:{v}" for k, v in by_type[tok].most_common())
            print(f"  {tok:<22} count={c:<4} as={types}")
    print("\nREVIEW REQUIRED before appending to allowlist.txt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
