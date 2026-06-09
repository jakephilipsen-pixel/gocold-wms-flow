# syntax=docker/dockerfile:1
#
# Shared image for BOTH FastAPI consoles:
#   - picks  → web.app:app           (wave pick console,   port 8077)
#   - runs   → web_dispatch.app:app  (dispatch run console, port 8078)
#
# They are one codebase (src/) with one dependency set; the compose service
# decides which ASGI app + port to launch. Build context is the REPO ROOT so
# src/ + config/ can be copied. data/ and .env are NEVER baked in — they are
# bind-mounted at run time (customer data + live CC creds stay on the host).

# ---- builder: resolve deps into an isolated venv -------------------------
FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt ./
# Strip dev-only deps (pytest) from the runtime image.
RUN sed '/pytest/d' requirements.txt > requirements.runtime.txt \
 && pip install -r requirements.runtime.txt

# ---- runtime: slim, non-root, venv only ----------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    MPLCONFIGDIR=/tmp/matplotlib \
    PATH="/opt/venv/bin:$PATH"
# Fixed-UID non-root user so the host bind-mount (./data) has predictable
# ownership — see DEPLOY.md for the one-time `chown -R 10001:10001 data`.
RUN groupadd -g 10001 app \
 && useradd -u 10001 -g app -M -s /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# Application code + static config only. NO data/, NO .env (bind-mounted).
COPY src ./src
COPY config ./config
USER app
# Default command = picks console; the `runs` service overrides it in compose.
EXPOSE 8077
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8077"]
