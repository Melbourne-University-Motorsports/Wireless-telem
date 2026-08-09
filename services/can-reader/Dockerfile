FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/can-reader/pyproject.toml ./services/can-reader/
RUN uv sync --frozen --no-dev --package can-reader
COPY services/can-reader/main.py ./services/can-reader/main.py
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "services/can-reader/main.py"]

