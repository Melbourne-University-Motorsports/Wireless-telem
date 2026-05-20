FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install deps first (cached layer — only re-runs if pyproject.toml/uv.lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source
COPY src/ ./src/

# Put the venv on PATH so you don't need `uv run` in CMD
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "broker.main"]
