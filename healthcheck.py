#!/usr/bin/env python3
import json
import os
import sys
import time

HEALTH_FILE = "/tmp/docklog-forwarder.health"
MAX_AGE_SECONDS = int(os.environ.get("HEALTH_MAX_AGE_SECONDS", "180"))


def main() -> int:
    if not os.path.exists(HEALTH_FILE):
        print("health file missing")
        return 1

    try:
        with open(HEALTH_FILE, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception as exc:
        print(f"failed to read health file: {exc}")
        return 1

    timestamp = payload.get("timestamp")
    if not isinstance(timestamp, int):
        print("invalid timestamp")
        return 1

    age = time.time() - timestamp
    if age > MAX_AGE_SECONDS:
        print(f"stale heartbeat: {age:.1f}s")
        return 1

    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
