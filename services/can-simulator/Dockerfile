FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/can-simulator/pyproject.toml ./services/can-simulator/
RUN uv sync --frozen --no-dev --package can-simulator
COPY services/can-simulator/main.py ./services/can-simulator/main.py
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "services/can-simulator/main.py"]

