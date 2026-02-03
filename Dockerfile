FROM python:3.13-slim

WORKDIR /app

# Install uv for fast dependency install
COPY pyproject.toml uv.lock* ./
RUN pip install uv && uv sync --no-dev

COPY celery_app.py tasks.py run_repro.py ./

# Broker URL override for container (redis service)
ENV CELERY_BROKER_URL=redis://redis:6379/0
ENV CELERY_RESULT_BACKEND=redis://redis:6379/1

# Use venv (uv installs deps into .venv)
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "run_repro.py"]
