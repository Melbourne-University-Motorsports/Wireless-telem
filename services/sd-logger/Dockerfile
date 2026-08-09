FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/sd-logger/pyproject.toml ./services/sd-logger/
RUN uv sync --frozen --no-dev --package sd-logger
COPY services/sd-logger/main.py ./services/sd-logger/main.py
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "main.py"]
