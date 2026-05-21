FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY can-simulator/pyproject.toml ./can-simulator/
RUN uv sync --frozen --no-dev --package can-simulator
COPY can-simulator/main.py ./main.py
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "main.py"]

