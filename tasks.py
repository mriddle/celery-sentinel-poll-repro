"""Tasks that keep the worker pool busy and churning."""

from celery_app import app


@app.task
def churn_task(n: int = 100_000) -> int:
    """Simple CPU work to keep worker busy. Worker exits after this (max_tasks=1)."""
    return sum(i * i for i in range(n))
