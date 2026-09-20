"""Placeholder celery beat scheduler for Phase 1.1 (D-02).

Periodic tick loop. Phase 1.2 replaces this with the real beat schedule.
"""

import time

if __name__ == "__main__":
    print("[celery_beat placeholder] scheduler started", flush=True)
    try:
        while True:
            print("[celery_beat placeholder] scheduler tick", flush=True)
            time.sleep(60)
    except KeyboardInterrupt:
        pass
