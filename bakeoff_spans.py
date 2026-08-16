#!/usr/bin/env python3
"""
Per-engine, per-path span attribution for the GLiNER bake-off.

test_deployed.py answers "was the planted value redacted?". This answers the
other half the plan requires: WHICH ENGINE produced each span, and what did it
redact that nothing planted -- split by PATH, because over-redaction is only a
defect on one of them.

    batch -> the KB text must stay readable, so an extra redaction has a cost
    live  -> the caller re-maps inside the boundary, so it costs nothing

The magnitude is the same detection either way; the CONSEQUENCE is not. Both
paths are measured rather than assumed identical, because "it must be the
same" is how this project has been wrong before.

    python bakeoff_spans.py http://127.0.0.1:8086/v1/scrub gliner

Prints what it inspected. Writes the full dump next to the label.
"""
import json
import os
import sys
import urllib.request

CORPORA = ["samples.json", "holdout_samples.json", "eval_samples_v2.json",
           "holdout_v3.json"]
REDACT_TYPES = {"PERSON", "EMAIL", "PHONE", "ADDRESS", "ORG_NAME",
                "IP_ADDRESS", "IBAN", "CUSTOMER_NO", "VENDOR_NO", "USER_ID"}


def post(url, text, mode):
    body = json.dumps({"text": text, "mode": mode}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def value_ranges(text, pii):
    """Every occurrence of every planted value, as (start, end)."""
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


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8086/v1/scrub"
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
                samples.append((fn, s))
    print(f"samples: {len(samples)}\n")

    dump = {}
    for mode in ("batch", "live"):
        # engine -> {"on_value": n, "over": n}, plus over-detections by type
        by_engine = {}
        over_rows = []
        n_spans = 0
        for fn, s in samples:
            r = post(url, s["text"], mode)
            ranges = value_ranges(s["text"], s.get("pii", []))
            for e in r.get("entities", []):
                if e["type"] not in REDACT_TYPES:
                    continue
                n_spans += 1
                eng = e.get("engine", "?")
                slot = by_engine.setdefault(eng, {"on_value": 0, "over": 0})
                hit = any(e["start"] < b and a < e["end"] for a, b in ranges)
                if hit:
                    slot["on_value"] += 1
                else:
                    slot["over"] += 1
                    over_rows.append({"corpus": fn, "id": s.get("id"),
                                      "engine": eng, "type": e["type"],
                                      "score": e.get("score"),
                                      "text": e["text"]})
        dump[mode] = {"by_engine": by_engine, "over": over_rows,
                      "redacting_spans": n_spans}

        print(f"--- path: {mode} ---")
        print(f"  redacting spans emitted: {n_spans}")
        for eng in sorted(by_engine):
            v = by_engine[eng]
            tot = v["on_value"] + v["over"]
            pct = (100.0 * v["over"] / tot) if tot else 0.0
            print(f"  {eng:9s} on-value {v['on_value']:4d}   "
                  f"over {v['over']:4d}   ({pct:.1f}% of its spans)")
        types = {}
        for row in over_rows:
            types[(row["engine"], row["type"])] = \
                types.get((row["engine"], row["type"]), 0) + 1
        if types:
            print("  over-detections by engine/type:")
            for (eng, t), n in sorted(types.items(), key=lambda kv: -kv[1]):
                print(f"    {eng:9s} {t:12s} {n}")
        print()

    b, l = dump["batch"], dump["live"]
    same = (b["by_engine"] == l["by_engine"])
    print(f"batch vs live identical span attribution: {same}")
    if not same:
        print("  ⚠️  PATHS DIVERGE -- detection is supposed to be mode-independent")

    out = f"bakeoff-spans-{label}.json"
    json.dump(dump, open(out, "w"), indent=1)
    print(f"full dump: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
