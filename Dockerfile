# PII Scrubber -- SAP AI Core BYOM serving image
# Model weights are BAKED IN: nothing is downloaded at runtime, so the
# container never reaches outside the boundary and startup is deterministic.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/hfcache \
    TRANSFORMERS_OFFLINE=0

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# CPU-only torch keeps the image ~2GB smaller than the CUDA build.
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements.txt

# spaCy model for Presidio
ARG SPACY_MODEL=en_core_web_sm
RUN python -m spacy download ${SPACY_MODEL}

# Pre-download GLiNER weights into the image.
# Comment out this block if you built without the gliner/torch requirements.
ARG GLINER_MODEL=urchade/gliner_multi_pii-v1
ENV GLINER_MODEL=${GLINER_MODEL}
# ⚠️ THIS STEP MUST BE ABLE TO FAIL THE BUILD, and until 2026-08-16 it could
# not. It ended `|| echo "WARN: GLiNER prefetch skipped"`, so a failed weight
# download produced a GREEN BUILD WITH NO WEIGHTS -- an image that looked
# correct and could not load a model. That is how finding 11 survived three
# releases: the one step that would have caught it was written so it always
# passed. A build step whose failure branch is `echo` is not a build step.
#
# The absent-by-design case is still handled, and ONLY that case: if gliner is
# deliberately commented out of requirements.txt for a slim Presidio-only
# image, the prefetch is skipped and says so. If gliner IS installed and the
# weights cannot be baked in, the build stops here.
RUN mkdir -p /app/hfcache && \
    if python -c "import gliner" 2>/dev/null; then \
      python -c "import os; from gliner import GLiNER; \
m = GLiNER.from_pretrained(os.environ['GLINER_MODEL']); \
print('GLiNER weights baked in OK:', type(m).__name__)"; \
    else \
      echo "GLiNER not installed -- slim presidio-only build, prefetch skipped BY DESIGN"; \
    fi \
 && chmod -R 777 /app/hfcache
# ^ chmod IN THIS LAYER, deliberately. KServe may run as a non-root UID and
# huggingface_hub writes lock files into the cache even when offline, so the
# tree must stay writable. Doing it here costs nothing; doing it in a LATER
# layer re-wrote every file's mode and made overlayfs duplicate the whole
# 1.1 GB of weights into a second layer.

# allowlist.txt MUST ship in the image -- without it ALLOWLIST_PATH resolves
# to a missing file and the service silently falls back to the 27-token seed,
# so extracted TSTC/DD02L tokens exist locally but not in production.
# (Defect found by the VS Code plan review, 2026-08-15.)
# AI Core / KServe may run the container as a non-root UID.
#
# ⚠️ --chmod ON THE COPY, NOT A `RUN chmod -R 777 /app` AFTERWARDS.
# The old form ran after the GLiNER prefetch and rewrote every file's mode
# under /app, so overlayfs copied the whole directory into a new layer --
# storing the 1.1 GB of model weights TWICE. Measured in `docker history`:
# a 1.16 GB prefetch layer followed by a 1.16 GB chmod layer, byte-for-byte
# duplicate. Applying the mode at COPY time touches only the copied files and
# leaves the weights in one layer.
COPY --chmod=777 app.py recognizers.py samples.json allowlist.txt glossary.txt ./

# Presidio is the DEFAULT mode. As of 1faf3e9 it is no longer the only mode
# that can run -- but "can run" and "is approved to run" are different things,
# and the difference is the whole content of this comment.
#
# FINDING 11 IS CLOSED (1faf3e9, 2026-08-16). An image built from THIS
# Dockerfile loads GLiNER and serves SCRUBBER_ENGINE=both without crashing.
# The fix is the coupled pin in requirements.txt -- huggingface_hub==0.36.2
# with transformers==4.57.6 -- and the prefetch above now fails the build
# rather than warning, so an image either has weights or does not exist.
#
# ⚠️ BUT DO NOT FLIP THE DEPLOYED CONFIGURATION TO `both`. Every image ever
# deployed predates the fix:
#
#   pin fix 1faf3e9   committed 2026-08-16 13:12:43
#   image   1.2.3     built     2026-08-16 12:08:32   <- 64 minutes EARLIER
#
# 1.0.0 through 1.2.3 all resolve huggingface_hub above 1.0, so on any of them
# get_gliner() still raises
#
#   TypeError: GLiNER._from_pretrained() missing 2 required keyword-only
#   arguments: 'proxies' and 'resume_download'
#
# at the first request and takes the deployment down. Enabling GLiNER needs a
# NEW image built from this file, not a configuration change on the running
# pod. Whether such an image ships at all is the open question owned by the
# GLiNER bake-off plan (docs/superpowers/plans/2026-08-16-pii-scrubber-gliner-bakeoff.md).
#
# ⚠️ This block was FALSE from 1faf3e9 until 2026-08-16 -- it still claimed
# finding 11 was open and that enabling GLiNER "needs a huggingface_hub pin
# (Rule 7, needs approval)" a day after that pin shipped. Its own closing
# paragraph noted that the same false claim had already been missed once in
# README-DEPLOY.html s7 and corrected by a9bed3e. It was then missed here, in
# the file that had just finished pointing out the pattern. That is the third
# occurrence of one correction applied in two of three places, and it is why
# correction commits now carry a repo-wide grep transcript (HANDOVER,
# "Settled"). Comments produce no layers, so this edit does not change the
# tested image.
ENV SCRUBBER_ENGINE=presidio \
    SPACY_MODEL=${SPACY_MODEL} \
    GLINER_THRESHOLD=0.4

# Build identity, passed at build time:
#   docker buildx build --build-arg BUILD_VERSION=1.2.1 ...
#
# Placed HERE, after every COPY, on purpose: an ENV invalidates every layer
# below it, so an early placement would re-run pip and the spaCy download on
# every version bump -- minutes of emulated build, for a string.
#
# The default is "dev" and must stay that way. A version-shaped default makes
# an image built without --build-arg indistinguishable from a correct one,
# which is precisely the incident this exists to prevent. Both properties are
# asserted structurally by test_build_version.py.
ARG BUILD_VERSION=dev
ENV BUILD_VERSION=${BUILD_VERSION}

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
