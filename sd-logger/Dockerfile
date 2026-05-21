FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY sd-logger/pyproject.toml ./sd-logger/
RUN uv sync --frozen --no-dev --package sd-logger
COPY sd-logger/main.py ./main.py
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "main.py"]
