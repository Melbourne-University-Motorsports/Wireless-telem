FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        libzstd-dev \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
COPY services/sd-logger/pyproject.toml ./services/sd-logger/
RUN uv sync --frozen --no-dev --package sd-logger
COPY services/sd-logger/main.py ./services/sd-logger/main.py
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "services/sd-logger/main.py"]
