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
    fi

# allowlist.txt MUST ship in the image -- without it ALLOWLIST_PATH resolves
# to a missing file and the service silently falls back to the 27-token seed,
# so extracted TSTC/DD02L tokens exist locally but not in production.
# (Defect found by the VS Code plan review, 2026-08-15.)
COPY app.py recognizers.py samples.json allowlist.txt glossary.txt ./

# AI Core / KServe may run the container as a non-root UID.
RUN chmod -R 777 /app

# Presidio-only. This is not a starting point -- it is the only mode that runs.
#
# This comment previously read "Flip to 'both' in the AI Core configuration to
# bring GLiNER online -- no rebuild needed." That is FALSE and it is finding 11:
# gliner==0.2.16 is incompatible with the huggingface_hub version pip resolves,
# so GLiNER.from_pretrained raises
#
#   TypeError: GLiNER._from_pretrained() missing 2 required keyword-only
#   arguments: 'proxies' and 'resume_download'
#
# get_gliner() calls exactly that at runtime, so setting engine=both takes the
# deployment down -- and the prefetch above fails too, so no weights are baked
# in either. Enabling GLiNER needs a huggingface_hub pin (Rule 7, needs
# approval) and a rebuild. Owner: the GLiNER bake-off session.
#
# The same false claim was corrected in README-DEPLOY.html s7 by a9bed3e; this
# copy was missed. Comments produce no layers, so this edit does not change the
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
