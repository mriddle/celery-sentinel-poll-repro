#!/usr/bin/env python3
"""
Reproduce Celery ForkProcess _sentinel_poll AttributeError.

This script starts a Celery worker, floods it with tasks (causing constant
pool repopulation due to max_tasks_per_child=1), and sends SIGTERM at
random intervals to hit the race condition during shutdown.

Usage:
    docker compose up -d          # Start Redis
    uv run python run_repro.py    # Run reproduction (may take many attempts)
"""

import os
import random
import signal
import subprocess
import sys
import time

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    concurrency = os.environ.get("CELERY_CONCURRENCY", "8")
    print(f"Starting Celery worker (concurrency={concurrency}, background)...")
    worker_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "celery_app:app",
            "worker",
            "--loglevel=info",
            "--concurrency",
            concurrency,
            "--max-tasks-per-child=1",
        ],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        # stdout/stderr to terminal so you see the AttributeError when it occurs
    )

    try:
        # Give worker time to start
        time.sleep(3)

        from tasks import churn_task

        attempt = 0
        max_attempts = int(os.environ.get("REPRO_MAX_ATTEMPTS", "50"))
        while worker_proc.poll() is None and attempt < max_attempts:
            attempt += 1
            # Flood with tasks - each completes and kills a worker, pool repopulates
            for _ in range(16):
                churn_task.delay()
            print(f"Attempt {attempt}: sent tasks, waiting...")

            # Random delay 1-4 seconds before SIGTERM
            delay = random.uniform(1, 4)
            time.sleep(delay)

            # SIGQUIT = cold shutdown (where bug occurs); SIGTERM = warm
            print(f"Attempt {attempt}: sending SIGQUIT (cold shutdown, race window: pool repopulating)")
            worker_proc.send_signal(signal.SIGQUIT)

            # Wait for exit (with timeout)
            try:
                worker_proc.wait(timeout=10)
                # Worker exited - restart for next attempt (unless we hit max)
                if attempt >= max_attempts:
                    break
                print(f"Attempt {attempt}: worker exited, restarting for next attempt")
                worker_proc = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "celery",
                        "-A",
                        "celery_app:app",
                        "worker",
                        "--loglevel=info",
                        "--concurrency",
                        concurrency,
                        "--max-tasks-per-child=1",
                    ],
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                )
                time.sleep(2)
            except subprocess.TimeoutExpired:
                # Worker didn't exit - kill and restart
                print(f"Attempt {attempt}: worker still running, killing and retrying")
                worker_proc.kill()
                worker_proc.wait()
                worker_proc = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "celery",
                        "-A",
                        "celery_app:app",
                        "worker",
                        "--loglevel=info",
                        "--concurrency",
                        concurrency,
                        "--max-tasks-per-child=1",
                    ],
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                )
                time.sleep(2)

        print(f"\nCompleted {attempt} attempt(s). Error may not have occurred (race is timing-dependent).")
        if worker_proc.returncode != 0:
            print("Worker exited with non-zero code - check output above for errors.")
        print("If you saw 'AttributeError: ForkProcess object has no attribute _sentinel_poll' above, reproduction succeeded.")
        print("Otherwise run again - the bug is intermittent.")

    except KeyboardInterrupt:
        print("\nInterrupted")
        worker_proc.terminate()
        worker_proc.wait()
    finally:
        if worker_proc.poll() is None:
            worker_proc.kill()


if __name__ == "__main__":
    main()
