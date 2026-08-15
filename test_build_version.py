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

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} -> {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
