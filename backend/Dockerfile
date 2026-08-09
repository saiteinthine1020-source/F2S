FROM python:3.13.14-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uvx /bin/

WORKDIR /srv/f2s

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13.14-slim-bookworm AS runtime

RUN groupadd --system --gid 10001 f2s \
    && useradd --system --uid 10001 --gid f2s --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin f2s

WORKDIR /srv/f2s

ENV PATH="/srv/f2s/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder --chown=f2s:f2s /srv/f2s/.venv ./.venv
COPY --chown=f2s:f2s app ./app
COPY --chown=f2s:f2s migrations ./migrations
COPY --chown=f2s:f2s alembic.ini ./alembic.ini

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
