# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app

WORKDIR /app

FROM base AS builder

RUN python -m venv /opt/venv

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

FROM base AS runtime

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . .

USER app

CMD ["python", "-c", "import knowledge_base; print('AI Knowledge Base ready')"]

FROM runtime AS development

USER root
RUN pip install --no-cache-dir -e '.[dev]'
USER app

CMD ["python", "-m", "pytest"]

