"""Minimaler Worker (Beispiel)."""

import os
import time

if __name__ == "__main__":
    print("worker started", flush=True)
    while True:
        time.sleep(float(os.environ.get("WORKER_INTERVAL", "5")))
