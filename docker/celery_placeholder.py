"""Placeholder celery worker for Phase 1.1 (D-02).

Announces the three spec queues (T1.2) on a loop. Phase 1.2 replaces this
with the real Celery app consuming default,notifications,maintenance.
"""

import time

QUEUES = "default,notifications,maintenance"

if __name__ == "__main__":
    print(f"[celery_worker placeholder] queues {QUEUES}", flush=True)
    try:
        while True:
            print(f"[celery_worker placeholder] heartbeat queues={QUEUES}", flush=True)
            time.sleep(30)
    except KeyboardInterrupt:
        pass
