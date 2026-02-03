"""Minimal Celery app for reproducing _sentinel_poll AttributeError."""

import os

from celery import Celery

broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

app = Celery(
    "repro",
    broker=broker,
    backend=backend,
    include=["tasks"],
)

# Worker restarts after each task - maximizes pool churn during shutdown
app.conf.worker_max_tasks_per_child = 1
# Multiple workers to increase race window (higher = more pool churn)
app.conf.worker_concurrency = int(os.environ.get("CELERY_CONCURRENCY", "8"))
