#!/usr/bin/env python3
"""
Holdout evaluation against the DEPLOYED PII scrubber on SAP AI Core.

Unlike /v1/selftest (which scores the 13 tuned-against samples baked into the
image), this sends UNSEEN samples through the live /v1/scrub endpoint and
checks, end to end, whether each planted PII value actually disappeared from
the scrubbed output. That is the honest production-shaped number.

Usage (same terminal where $AI_API and $TOKEN are set):

    export DEPLOYMENT_ID=db3d9cc5eea296cd
    python3 test_deployed.py holdout_samples.json

Or against a local service, with the same scorer:

    SCRUB_URL=http://localhost:8080/v1/scrub python3 test_deployed.py holdout_samples.json

No dependencies beyond the standard library.
Scoring: a value counts as CAUGHT only if the (whitespace-normalised,
case-insensitive) value string no longer appears in scrubbed_text. If any
part of it survives verbatim, that is a LEAK. Controls (no-PII samples) are
checked for over-redaction damage instead.
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def main() -> int:
    ai_api = os.environ.get("AI_API")
    token = os.environ.get("TOKEN")
    dep = os.environ.get("DEPLOYMENT_ID", "db3d9cc5eea296cd")
    # Point at a local service instead of the deployment, for pre-deploy
    # verification:  SCRUB_URL=http://localhost:8080/v1/scrub
    # Unset -> deployed behaviour below, unchanged. Deliberately one scorer for
    # both targets so local and deployed numbers stay comparable.
    scrub_url = os.environ.get("SCRUB_URL")
    if not scrub_url and (not ai_api or not token):
        print("ERROR: export AI_API and TOKEN first (same block used for the selftest),"
              " or set SCRUB_URL to run against a local service.")
        return 1

    path = sys.argv[1] if len(sys.argv) > 1 else "holdout_samples.json"
    with open(path) as fh:
        samples = json.load(fh)["samples"]

    url = scrub_url or f"{ai_api}/v2/inference/deployments/{dep}/v1/scrub"
    headers = {"Content-Type": "application/json"}
    if not scrub_url:
        headers["Authorization"] = f"Bearer {token}"
        headers["AI-Resource-Group"] = "default"

    # Stamp the artifact these numbers came from. Pre-1.2.1 images have no
    # build_version -- say so and carry on rather than aborting, because the
    # 1.2.0 and 1.1.0 rollback images must stay measurable.
    info_url = url.rsplit("/v1/scrub", 1)[0] + "/info"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(info_url, headers=headers), timeout=30) as r:
            build = json.load(r).get("build_version") or "unknown (pre-1.2.1 image)"
    except Exception as e:  # noqa: BLE001 -- identity is advisory, never fatal
        build = f"unreachable ({type(e).__name__})"

    per_type = defaultdict(lambda: {"expected": 0, "caught": 0})
    leaks = []
    control_notes = []
    total_expected = total_caught = 0
    t0 = time.time()

    for i, smp in enumerate(samples, 1):
        body = json.dumps({"text": smp["text"], "mode": "batch"}).encode()
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                out = json.load(resp)
        except urllib.error.HTTPError as e:
            print(f"[{smp['id']}] HTTP {e.code}: {e.read()[:200]!r} -- aborting"
                  " (401 = token expired; re-mint and re-run)")
            return 1
        scrubbed = out.get("scrubbed_text", "")
        nscrub = norm(scrubbed)

        if not smp["pii"]:
            # Control sample: nothing should have been damaged badly.
            n_red = out.get("redacted_count", 0)
            if n_red:
                control_notes.append((smp["id"], n_red, scrubbed))
            continue

        for gt in smp["pii"]:
            t = gt["type"]
            per_type[t]["expected"] += 1
            total_expected += 1
            if norm(gt["value"]) in nscrub:
                leaks.append({
                    "id": smp["id"], "type": t, "value": gt["value"],
                    "scrubbed": scrubbed,
                })
            else:
                per_type[t]["caught"] += 1
                total_caught += 1

        print(f"  [{i:2d}/{len(samples)}] {smp['id']} done", end="\r")

    dt = time.time() - t0
    print(" " * 40, end="\r")

    print("=" * 62)
    # NOT "HOLDOUT RESULT". This harness scores whatever file it is handed,
    # and it printed that banner for every one of them -- run against
    # eval_samples_v2.json it announced a holdout result for a set that is
    # explicitly not a holdout. The caller names the set; the harness never
    # does. Same trap class as the version string this release added.
    print("SCRUBBER EVALUATION — one scorer, caller names the set")
    print("=" * 62)
    recall = 100.0 * total_caught / total_expected if total_expected else 0.0
    print(f"build: {build}   samples: {path}")
    print(f"target: {url}")
    print(f"samples: {len(samples)}   planted PII: {total_expected}   "
          f"caught: {total_caught}   LEAKED: {total_expected - total_caught}")
    print(f"RECALL: {recall:.1f}%   ({dt:.0f}s total)")
    print()
    print(f"{'TYPE':<13}{'EXPECT':>8}{'CAUGHT':>8}{'RECALL%':>9}")
    for t in sorted(per_type):
        c = per_type[t]
        r = 100.0 * c["caught"] / c["expected"] if c["expected"] else 0.0
        flag = "  <-- " if r < 100 else ""
        print(f"{t:<13}{c['expected']:>8}{c['caught']:>8}{r:>8.1f}%{flag}")
    print()
    if leaks:
        print(f"LEAKS ({len(leaks)}) — value survived in scrubbed output:")
        for l in leaks:
            print(f"  [{l['id']}] {l['type']:<11} {l['value']!r}")
        print()
        print("First 3 leak outputs for inspection:")
        for l in leaks[:3]:
            print(f"  [{l['id']}] -> {l['scrubbed']}")
    else:
        print("NO LEAKS. Every planted value was removed.")
    print()
    if control_notes:
        print(f"CONTROL SAMPLES with redactions (over-redaction check, {len(control_notes)}):")
        for cid, n, s in control_notes:
            print(f"  [{cid}] {n} redaction(s): {s}")
    else:
        print("Controls: clean — no over-redaction on no-PII samples.")
    print()
    print("Interpretation: leaks = the tuning backlog + what the BPA human gate")
    print("must catch. A holdout number below 100% is EXPECTED and honest;")
    print("do not tune recognizers against this set, or it stops being a holdout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
