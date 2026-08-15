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
RUN mkdir -p /app/hfcache && \
    python -c "from gliner import GLiNER; GLiNER.from_pretrained('${GLINER_MODEL}')" || \
    echo "WARN: GLiNER prefetch skipped -- image will run in presidio-only mode"

# allowlist.txt MUST ship in the image -- without it ALLOWLIST_PATH resolves
# to a missing file and the service silently falls back to the 27-token seed,
# so extracted TSTC/DD02L tokens exist locally but not in production.
# (Defect found by the VS Code plan review, 2026-08-15.)
COPY app.py recognizers.py samples.json allowlist.txt ./

# AI Core / KServe may run the container as a non-root UID.
RUN chmod -R 777 /app

# Start in presidio-only mode: proves the deployment cheaply on the
# free-tier 'starter' plan. Flip to 'both' in the AI Core configuration
# to bring GLiNER online -- no rebuild needed.
ENV SCRUBBER_ENGINE=presidio \
    SPACY_MODEL=${SPACY_MODEL} \
    GLINER_THRESHOLD=0.4

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
