FROM python:3.12-alpine
COPY --from=ghcr.io/astral-sh/uv-latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY source src/ ./src

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "can-simulator.main"]
