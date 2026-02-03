# Celery _sentinel_poll AttributeError Reproduction

Minimal project to reproduce the Celery `AttributeError: 'ForkProcess' object has no attribute '_sentinel_poll'` that occurs during worker shutdown when SIGTERM hits during pool repopulation.

## Bug Summary

Race condition in `celery/concurrency/asynpool.py`: `_untrack_child_process` accesses `proc._sentinel_poll` without checking if the attribute exists. When SIGTERM arrives while a new worker is being spawned, the process may not have `_sentinel_poll` set yet.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (or pip)
- Docker (for Redis)

## Setup

```bash
cd ~/Code/work/celery-sentinel-poll-repro
uv sync
docker compose up -d
```

## Reproduction

### Option 1: Linux container (recommended – matches production)

```bash
cd ~/Code/work/celery-sentinel-poll-repro
docker compose run --rm -e REPRO_MAX_ATTEMPTS=100 repro
```

Runs in Python 3.13 on Linux with concurrency 16. Set `REPRO_MAX_ATTEMPTS` to control how many shutdown cycles to try.

### Option 2: Local (macOS)

```bash
docker compose up -d   # Start Redis
uv run python run_repro.py
```

The script will:
1. Start a Celery worker with `--max-tasks-per-child=1` (each task kills a worker, forcing pool repopulation)
2. Flood the worker with tasks to keep the pool churning
3. Send SIGTERM at random intervals (1–4 seconds) to hit the race window

**The bug is intermittent.** You may need to run multiple times. When reproduced, you'll see:

```
AttributeError: 'ForkProcess' object has no attribute '_sentinel_poll'
```

in the worker output during shutdown.

## Manual Reproduction

```bash
# Terminal 1: Start Redis
docker compose up -d

# Terminal 2: Start worker
uv run celery -A celery_app:app worker --concurrency=4 --max-tasks-per-child=1 --loglevel=info

# Terminal 3: Flood tasks and send SIGTERM
uv run python -c "
from tasks import churn_task
import time, signal, subprocess
for i in range(20):
    for _ in range(8): churn_task.delay()
    time.sleep(2)
    # Get worker PID and kill -TERM
    r = subprocess.run(['pgrep', '-f', 'celery.*worker'], capture_output=True, text=True)
    if r.stdout.strip():
        pid = r.stdout.strip().split()[0]
        subprocess.run(['kill', '-TERM', pid])
        break
"
```

## Dependencies

- `celery==5.6.2` (version from production)
- `redis` (broker)
