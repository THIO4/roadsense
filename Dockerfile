# syntax=docker/dockerfile:1
# RoadSense image. One image, two roles:
#   API (default):  docker run -p 8000:8000 --env-file .env roadsense
#   collector:      docker run --env-file .env roadsense roadsense-collector collect

# ---------- stage 1: build ----------------------------------------------------------
# Installs the package and its runtime deps into an isolated prefix. Build tools and pip
# caches stay in this stage and never reach the final image.
FROM python:3.12-slim AS builder

WORKDIR /build
# Layer 1 - dependencies only. Depends on pyproject.toml alone, so this (slow, ~30 s)
# layer is cached until a dependency changes. tomllib is in the stdlib since 3.11.
COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install \
    $(python -c "import tomllib; print(' '.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))")
# Layer 2 - our own code. Changes on every commit, but installs in ~1 s (--no-deps).
COPY README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps --prefix=/install .

# ---------- stage 2: runtime --------------------------------------------------------
FROM python:3.12-slim AS runtime

# Links the image to the repo on GHCR (package page, README, and automatic repo write access).
LABEL org.opencontainers.image.source="https://github.com/THIO4/roadsense"

# Python: no .pyc files, unbuffered stdout so logs appear immediately in the container log.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Never run as root: an exploited process should not own the container.
RUN useradd --create-home --uid 1000 app
COPY --from=builder /install /usr/local
USER app
WORKDIR /home/app

EXPOSE 8000
# The API is the default role; Azure will override the command for the collector job.
# Host 0.0.0.0 is required inside a container (127.0.0.1 would be unreachable from outside).
CMD ["sh", "-c", "uvicorn roadsense.api.app:app --host 0.0.0.0 --port ${PORT}"]
