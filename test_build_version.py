#!/usr/bin/env python3
"""
BUILD_VERSION -- the image must be able to say which build it is.

From the stale-deployment incident: a script pointed at a deployment that was
live but not the one just shipped, and reported confident numbers for the
wrong artifact. Nothing in any response identified the build.

Two halves are asserted here, and the second is the one that actually breaks:
  1. the value reaches both endpoints and the FastAPI app object
  2. the Dockerfile wiring -- ARG default, and ENV placed after every COPY so
     a version bump does not invalidate the pip and spaCy layers

Run: python test_build_version.py
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


# Sentinel, not None. `getattr(A, "BUILD_VERSION", None) == payload.get(...)`
# reads as an equality check and is really a None == None tautology when
# BOTH sides are absent -- it reported PASS against an unmodified app.py.
# That is the "a check that reports clean may not have run" trap, instance
# four in this project. Presence is asserted before equality, always.
MISSING = object()
BV = getattr(A, "BUILD_VERSION", MISSING)

print("Service reports its build")
check("BUILD_VERSION exists and is a non-empty string",
      isinstance(BV, str) and BV != "",
      f"got {BV if BV is not MISSING else '<attribute absent>'!r}")
check("default is 'dev' when the env var is unset OR empty",
      BV is not MISSING and BV == (os.getenv("BUILD_VERSION") or "dev"),
      f"env={os.getenv('BUILD_VERSION')!r} constant="
      f"{BV if BV is not MISSING else '<attribute absent>'!r}")

# An empty BUILD_VERSION must fall back, not propagate. FastAPI asserts a
# truthy version when it builds the OpenAPI schema, so `--build-arg
# BUILD_VERSION=` on the two-arg os.getenv form stopped the service booting
# (exit 1, AssertionError). Asserted at source because reproducing it needs a
# subprocess and a full allowlist load for one string.
src = [l for l in open("app.py").read().splitlines()
       if l.startswith("BUILD_VERSION =")]
check("BUILD_VERSION uses the `or` fallback, not a two-arg default",
      src and src[0].strip() == 'BUILD_VERSION = os.getenv("BUILD_VERSION") or "dev"',
      f"found: {src[0].strip() if src else '<no assignment found>'!r} -- the "
      "two-arg form returns '' for an empty env var and FastAPI refuses to start")
check("FastAPI app version tracks the build, not a hardcoded string",
      BV is not MISSING and A.app.version == BV,
      f"app.version={A.app.version!r} BUILD_VERSION="
      f"{BV if BV is not MISSING else '<attribute absent>'!r}")

info_payload = A.info()
check("/info carries a build_version KEY",
      "build_version" in info_payload,
      f"info() keys: {sorted(info_payload)}")
check("/info build_version matches the constant",
      info_payload.get("build_version", MISSING) is not MISSING
      and info_payload["build_version"] == BV,
      f"info()={info_payload.get('build_version', '<key absent>')!r} constant="
      f"{BV if BV is not MISSING else '<attribute absent>'!r}")

selftest_payload = A.selftest()
check("/v1/selftest carries a build_version KEY",
      "build_version" in selftest_payload,
      f"selftest keys: {sorted(selftest_payload)}")
check("/v1/selftest build_version matches the constant",
      selftest_payload.get("build_version", MISSING) is not MISSING
      and selftest_payload["build_version"] == BV,
      f"selftest={selftest_payload.get('build_version', '<key absent>')!r} constant="
      f"{BV if BV is not MISSING else '<attribute absent>'!r}")

# ---------------------------------------------------------------------------
# Dockerfile wiring. A constant the image never populates is worse than no
# constant -- it looks like evidence. Same trap class as the __version__ line
# that printed "presidio unknown" for months.
# ---------------------------------------------------------------------------
print("Dockerfile wiring -- printed, not assumed")

lines = open("Dockerfile").read().splitlines()
arg_lines = [(i, l) for i, l in enumerate(lines) if l.strip().startswith("ARG BUILD_VERSION")]
env_lines = [(i, l) for i, l in enumerate(lines) if l.strip().startswith("ENV BUILD_VERSION")]
copy_lines = [i for i, l in enumerate(lines) if l.strip().startswith("COPY")]

check("Dockerfile declares ARG BUILD_VERSION", bool(arg_lines),
      "no ARG BUILD_VERSION line found")
check("Dockerfile exports ENV BUILD_VERSION", bool(env_lines),
      "no ENV BUILD_VERSION line found")

if arg_lines:
    check("ARG default is 'dev', not a version-shaped string",
          arg_lines[0][1].strip() == "ARG BUILD_VERSION=dev",
          f"line {arg_lines[0][0] + 1}: {arg_lines[0][1].strip()!r}")

if env_lines and copy_lines:
    env_i, last_copy = env_lines[0][0], max(copy_lines)
    check("ENV BUILD_VERSION sits AFTER every COPY (layer-cache guard)",
          env_i > last_copy,
          f"ENV at line {env_i + 1}, last COPY at line {last_copy + 1} -- "
          "an early ENV re-runs pip and the spaCy download on every bump")

# ---------------------------------------------------------------------------
# The harness must not read identity from /info ALONE. The AI Core inference
# gateway proxies /v1/* only -- /info returns "RBAC: access denied" there --
# so an /info-only stamp works on every local run and silently reports
# "unreachable" on every deployed one. Structural, because reproducing the
# gateway's RBAC locally is not possible.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 1.2.2 item 1. /info is not proxied by the AI Core gateway -- only /v1/* is,
# and GET $AI_API/v2/inference/deployments/<id>/info returns
# "RBAC: access denied" (confirmed on d08c99a19640540f). Without a /v1 route,
# reading a build off a deployment costs a 13-sample selftest, so nobody
# checks casually -- and an identity check people avoid is one that does not
# happen. Same handler, second decorator: no new payload to drift.
# ---------------------------------------------------------------------------
print("Identity is reachable through the gateway")

routes = {r.path for r in A.app.routes}
check("/v1/info route is registered", "/v1/info" in routes,
      f"routes: {sorted(p for p in routes if 'info' in p or 'health' in p)}")
check("/info route still registered (local callers unbroken)",
      "/info" in routes, f"routes: {sorted(routes)}")
check("both routes are the SAME handler, not a copied payload",
      len({tuple(sorted(A.info()))}) == 1
      and [r.endpoint for r in A.app.routes if r.path == "/v1/info"]
          == [r.endpoint for r in A.app.routes if r.path == "/info"],
      "a second handler would drift from the first")

# ---------------------------------------------------------------------------
# 1.2.3 item 2. The trap-8 warning fires on first analyzer build, not at
# process start, because model loading is lazy so /health stays instant. A pod
# created, health-checked and left idle never logs it. A field on /v1/info is
# always readable and costs nothing.
#
# null before the first build is DELIBERATE and informative: it says "no
# analyzer yet", not "no problem". [] would be a false negative -- a claim
# that nothing is unmapped, made before anything could have been checked.
# ---------------------------------------------------------------------------
print("Unmapped labels are readable without reading logs")

fresh = A.info()
check("/info carries an unmapped_labels KEY",
      "unmapped_labels" in fresh,
      f"info() keys: {sorted(fresh)}")

# app.selftest() ran earlier in this file, so the analyzer is already built by
# now; assert the populated shape here and the null-before-build shape in a
# fresh process below.
check("unmapped_labels is a list once the analyzer is built",
      isinstance(fresh.get("unmapped_labels"), list),
      f"got {fresh.get('unmapped_labels')!r} -- expected a list after build")
print("null before the first analyzer build -- fresh process, no eager load")
import json as _json  # noqa: E402
import subprocess as _sp  # noqa: E402

_proc = _sp.run(
    [sys.executable, "-c",
     "import os,json; os.environ.setdefault('SCRUBBER_ENGINE','presidio');"
     "import app; i=app.info();"
     "print(json.dumps({'k':'unmapped_labels' in i,"
     "'v':i.get('unmapped_labels'),'loaded':i['presidio_loaded']}))"],
    capture_output=True, text=True, timeout=600,
)
_line = [l for l in _proc.stdout.splitlines() if l.startswith("{")]
_payload = _json.loads(_line[-1]) if _line else {}
check("fresh process: key present before any analyzer build",
      _payload.get("k") is True, f"stdout tail: {_proc.stdout.strip()[-200:]}")
check("fresh process: value is null, not []",
      _payload.get("v") is None,
      f"got {_payload.get('v')!r} -- [] would claim 'nothing unmapped' "
      "before anything was checked")
check("fresh process: /info did NOT force an eager model load",
      _payload.get("loaded") is False,
      "presidio_loaded is True -- /info triggered a load and /health is no "
      "longer instant")

print("Harness identity routes -- gateway-reachable, printed")

harness = open("test_deployed.py").read()
route_line = [l.strip() for l in harness.splitlines()
              if 'for route in (' in l]
check("test_deployed.py falls back to a /v1/* identity route",
      route_line and "/v1/selftest" in route_line[0],
      f"found: {route_line[0] if route_line else '<no route loop found>'!r} -- "
      "/info alone is not proxied by the AI Core gateway")
check("identity fetch is non-fatal (bare except, run continues)",
      "identity is advisory, never fatal" in harness,
      "the identity fetch must never abort a measurement run")

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
