#!/usr/bin/env python3
"""
Score distribution of over-detections vs true positives, per engine and type.

Gate 0 Q1 deliverable of GATE0-overlap-suppression-plan.md. It exists to feed
the NAMED SUCCESSOR investigation -- whether the residual batch over-redaction
is better attacked with glossary vocabulary or with per-type thresholds for
GLiNER spans -- and it answers exactly one question:

    is there a score at which GLiNER's over-detections separate from its
    true positives?

If the two distributions overlap, no threshold can split them and the lever is
vocabulary. If they separate, a per-type floor is worth pre-registering.

⚠️ CONFIGURATION-LEVEL, NEVER ENGINE-LEVEL. presidio spans have already passed
per-type floors (TYPE_THRESHOLDS) before they reach here; GLiNER spans have
passed one global GLINER_THRESHOLD and never touch TYPE_THRESHOLDS. The two
columns are therefore not comparable as engines, and presidio's scores are
truncated from below by its own filter. The confound travels with every number
this prints.

⚠️ Burned corpora: engineering comparison only. Nothing here is quotable.

    python score_distribution.py http://127.0.0.1:8087/v1/scrub both-ovlp
"""
import json
import os
import statistics
import sys
import urllib.request

CORPORA = ["samples.json", "holdout_samples.json", "eval_samples_v2.json",
           "holdout_v3.json"]
REDACT_TYPES = {"PERSON", "EMAIL", "PHONE", "ADDRESS", "ORG_NAME",
                "IP_ADDRESS", "IBAN", "CUSTOMER_NO", "VENDOR_NO", "USER_ID"}


def post(url, text):
    body = json.dumps({"text": text, "mode": "batch"}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def value_ranges(text, pii):
    out = []
    for p in pii:
        v = p.get("value")
        if not v:
            continue
        i = text.find(v)
        while i != -1:
            out.append((i, i + len(v)))
            i = text.find(v, i + 1)
    return out


def pct(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))]


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8087/v1/scrub"
    label = sys.argv[2] if len(sys.argv) > 2 else "arm"

    present = [c for c in CORPORA if os.path.exists(c)]
    missing = [c for c in CORPORA if not os.path.exists(c)]
    print(f"arm: {label}   target: {url}")
    print(f"corpora read: {present}")
    if missing:
        print(f"  ⚠️  ABSENT, NOT SCANNED: {missing}")

    samples = []
    for fn in present:
        for s in json.load(open(fn))["samples"]:
            if s.get("text"):
                samples.append(s)
    print(f"samples: {len(samples)}\n")

    # (engine, type) -> {"on_value": [scores], "over": [scores]}
    buckets = {}
    for s in samples:
        r = post(url, s["text"])
        ranges = value_ranges(s["text"], s.get("pii", []))
        for e in r.get("entities", []):
            if e["type"] not in REDACT_TYPES:
                continue
            hit = any(e["start"] < b and a < e["end"] for a, b in ranges)
            slot = buckets.setdefault((e.get("engine", "?"), e["type"]),
                                      {"on_value": [], "over": []})
            slot["on_value" if hit else "over"].append(float(e.get("score", 0)))

    print(f"{'engine':9s} {'type':12s} {'n_tp':>5s} {'n_over':>6s} "
          f"{'tp_min':>7s} {'tp_p10':>7s} {'over_max':>8s} {'over_p90':>8s} "
          f"  separable?")
    print("-" * 82)
    per_engine = {}
    for (eng, typ), v in sorted(buckets.items()):
        tp, ov = v["on_value"], v["over"]
        tp_min, tp_p10 = (min(tp) if tp else None), pct(tp, 0.10)
        ov_max, ov_p90 = (max(ov) if ov else None), pct(ov, 0.90)
        if not tp or not ov:
            verdict = "n/a"
        elif ov_max < tp_min:
            verdict = f"YES  cut at {ov_max:.3f}"
        else:
            overlap = sum(1 for x in ov if x >= tp_min)
            verdict = (f"NO   {overlap}/{len(ov)} over-detections score "
                       f">= the lowest TP")
        f = lambda x: "  -   " if x is None else f"{x:.3f} "
        print(f"{eng:9s} {typ:12s} {len(tp):5d} {len(ov):6d} "
              f"{f(tp_min):>7s} {f(tp_p10):>7s} {f(ov_max):>8s} "
              f"{f(ov_p90):>8s}   {verdict}")
        pe = per_engine.setdefault(eng, {"tp": [], "over": []})
        pe["tp"] += tp
        pe["over"] += ov

    print()
    for eng, v in sorted(per_engine.items()):
        tp, ov = v["tp"], v["over"]
        print(f"{eng}: {len(tp)} true positives, {len(ov)} over-detections")
        if tp:
            print(f"   TP   median {statistics.median(tp):.3f}   "
                  f"min {min(tp):.3f}   p10 {pct(tp, 0.10):.3f}")
        if ov:
            print(f"   OVER median {statistics.median(ov):.3f}   "
                  f"max {max(ov):.3f}   p90 {pct(ov, 0.90):.3f}")
        if tp and ov:
            killable = sum(1 for x in ov if x < min(tp))
            print(f"   a global floor at the lowest TP ({min(tp):.3f}) would "
                  f"remove {killable} of {len(ov)} over-detections "
                  f"and 0 true positives")

    out = f"score-distribution-{label}.json"
    json.dump({f"{e}|{t}": v for (e, t), v in buckets.items()},
              open(out, "w"), indent=1)
    print(f"\nfull dump: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
