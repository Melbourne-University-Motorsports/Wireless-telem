FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/broker/pyproject.toml ./services/broker/
RUN uv sync --frozen --no-dev --package broker
COPY services/broker/main.py ./services/broker/main.py
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "main.py"]
