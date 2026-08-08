FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY rf-sender/pyproject.toml ./rf-sender/
RUN uv sync --frozen --no-dev --package rf-sender
COPY rf-sender/main.py ./main.py
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "main.py"]

