FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/rf-sender/pyproject.toml ./services/rf-sender/
RUN uv sync --frozen --no-dev --package rf-sender
COPY services/rf-sender/main.py ./services/rf-sender/main.py
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "main.py"]

