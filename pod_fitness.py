#!/usr/bin/env python3
"""
Pod-fitness gates for the GLiNER bake-off. Required before any engine choice.

The AI Core Starter plan is **1 vCPU / 3 GB**. Both halves have burned this
project once already:

  - 3 GB is a MEMORY ceiling, not an image-size cap. The task list recorded
    "460 MiB under a 3 GB cap", setting an image size against a RAM limit.
    `en_core_web_lg` was dropped in 1.2.0 partly for "2.2x RSS", which is the
    same ceiling.
  - 1 vCPU is the part every latency number so far has ignored. GLiNER timed
    at 44 ms median on Apple Silicon with torch threading across many cores.
    That is an upper bound on the hardware, not a prediction for the pod.

So this measures the pod, not the laptop: one CPU, threads capped, against the
real corpora rather than a hand-picked sentence.

    python3 pod_fitness.py http://127.0.0.1:8086/v1/scrub

Prints what it inspected, never just a verdict.
"""
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

CORPORA = ["holdout_samples.json", "eval_samples_v2.json", "holdout_v3.json",
           "samples.json"]


def post(url, text, mode="batch", timeout=600):
    body = json.dumps({"text": text, "mode": mode}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        r.read()
    return (time.time() - t0) * 1000.0


def load_texts():
    """Every sample text we own, plus which file it came from."""
    out = []
    for fn in CORPORA:
        if not os.path.exists(fn):
            print(f"  (absent, skipped: {fn})")
            continue
        with open(fn) as fh:
            for s in json.load(fh)["samples"]:
                t = s.get("text")
                if t:
                    out.append((fn, t))
    return out


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8086/v1/scrub"
    print(f"target: {url}\n")

    print("Corpora read (a gate-sized batch is the real load, not one sentence)")
    texts = load_texts()
    if not texts:
        print("ERROR: no corpora found; run from the repo root.")
        return 1
    lengths = [len(t) for _, t in texts]
    longest_file, longest = max(texts, key=lambda p: len(p[1]))
    print(f"  samples: {len(texts)}   chars: min {min(lengths)} / "
          f"median {int(statistics.median(lengths))} / max {max(lengths)}")
    print(f"  longest sample: {len(longest)} chars, from {longest_file}\n")

    # -- warm, so model load is not billed to the first measurement ----------
    print("Warm-up (model load excluded from every number below)")
    t_load = post(url, "warm up the analyzer please")
    print(f"  first call (includes lazy load): {t_load:,.0f} ms\n")

    # -- 1. single-request latency on the median-ish sample ------------------
    print("GATE 1 -- single-request latency, warm")
    med_text = sorted(texts, key=lambda p: len(p[1]))[len(texts) // 2][1]
    lat = sorted(post(url, med_text) for _ in range(7))
    p50, p95 = lat[len(lat) // 2], lat[-1]
    print(f"  median sample ({len(med_text)} chars), n=7")
    print(f"  p50 {p50:,.0f} ms   min {lat[0]:,.0f}   max {p95:,.0f}\n")

    # -- 2. longest document -------------------------------------------------
    print("GATE 2 -- longest document in any corpus")
    lat_long = sorted(post(url, longest) for _ in range(3))
    print(f"  {len(longest)} chars, n=3: median {lat_long[1]:,.0f} ms   "
          f"max {lat_long[-1]:,.0f} ms\n")

    # -- 3. gate-sized batch, sequential -------------------------------------
    print("GATE 3 -- gate-sized batch, sequential (this is what a gate run does)")
    batch = [t for _, t in texts[:65]]
    t0 = time.time()
    per = [post(url, t) for t in batch]
    wall = time.time() - t0
    print(f"  {len(batch)} samples in {wall:,.1f} s   "
          f"mean {statistics.mean(per):,.0f} ms/sample   max {max(per):,.0f} ms\n")

    # -- 4. concurrency probe ------------------------------------------------
    print("GATE 4 -- concurrency probe (1 vCPU: contention, not parallelism)")
    probe = batch[:8]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        conc = list(ex.map(lambda t: post(url, t), probe))
    wall_c = time.time() - t0
    seq_est = sum(per[:len(probe)]) / 1000.0
    print(f"  {len(probe)} requests, 4 concurrent: wall {wall_c:,.1f} s")
    print(f"  same 8 sequential earlier: {seq_est:,.1f} s")
    print(f"  per-request max under contention: {max(conc):,.0f} ms")
    print(f"  -> speedup {seq_est / wall_c:.2f}x "
          f"({'contention, as expected on 1 vCPU' if seq_est / wall_c < 1.5 else 'unexpectedly parallel -- check the CPU cap'})\n")

    print("Memory is NOT measured here -- read it from `docker stats` outside,")
    print("after this run, so the peak includes everything above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
