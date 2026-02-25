#!/usr/bin/env python3
import configparser
import glob
import json
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Pattern, Set, Tuple

APP_NAME = "docklog-forwarder"
DEFAULT_CONFIG_PATH = f"/etc/{APP_NAME}/{APP_NAME}.config"
HEALTH_FILE = "/tmp/docklog-forwarder.health"


@dataclass
class SourceConfig:
    name: str
    pattern: str
    regex: Optional[Pattern[str]]


@dataclass
class NotificationConfig:
    enabled: bool
    ntfy_url: Optional[str]
    levels: Set[str]
    title_prefix: str
    auth_token: Optional[str]


class LogForwarder:
    LEVEL_PATTERN = re.compile(r"\b(CRITICAL|ERROR|WARN(?:ING)?|INFO)\b", re.IGNORECASE)

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.shutdown_requested = False
        self.offsets: Dict[Tuple[int, int], int] = {}
        self.key_to_path: Dict[Tuple[int, int], str] = {}
        self.touched_keys: Set[Tuple[int, int]] = set()

        self.update_seconds = 60
        self.sources: List[SourceConfig] = []
        self.notifications = NotificationConfig(False, None, set(), APP_NAME, None)

    def load(self) -> None:
        parser = configparser.ConfigParser()
        with open(self.config_path, "r", encoding="utf-8") as fh:
            parser.read_file(fh)

        tz_name = parser.get("General", "tz", fallback="UTC")
        os.environ["TZ"] = tz_name
        try:
            time.tzset()
        except AttributeError:
            pass

        updatefreq = parser.get("General", "updatefreq", fallback="1min")
        self.update_seconds = self.parse_duration(updatefreq)

        self.notifications = NotificationConfig(
            enabled=parser.getboolean("Notification", "enabled", fallback=False),
            ntfy_url=parser.get("Notification", "ntfy_url", fallback=None),
            levels={lvl.strip().upper() for lvl in parser.get("Notification", "levels", fallback="ERROR,CRITICAL").split(",") if lvl.strip()},
            title_prefix=parser.get("Notification", "title_prefix", fallback=APP_NAME),
            auth_token=parser.get("Notification", "auth_token", fallback=None),
        )

        reserved = {"General", "Notification"}
        self.sources = []
        for section in parser.sections():
            if section in reserved:
                continue
            pattern = parser.get(section, "input", fallback="").strip()
            if not pattern:
                continue
            regex_raw = parser.get(section, "regex", fallback="").strip()
            compiled = re.compile(regex_raw) if regex_raw else None
            self.sources.append(SourceConfig(name=section, pattern=pattern, regex=compiled))

        if not self.sources:
            raise ValueError("No log sources found in config. Add at least one section with input=... pattern.")

    @staticmethod
    def parse_duration(raw: str) -> int:
        value = raw.strip().lower()
        if value.endswith("min"):
            return max(1, int(value[:-3])) * 60
        if value.endswith("s"):
            return max(1, int(value[:-1]))
        return max(1, int(value))

    def run(self) -> None:
        self.register_signals()
        self.load()
        self.print_startup_summary()

        while not self.shutdown_requested:
            self.touched_keys = set()
            for source in self.sources:
                self.process_source(source)
            self.cleanup_stale_offsets()
            self.write_health()
            time.sleep(self.update_seconds)

        self.log("INFO", "general", "Shutdown requested, exiting cleanly")

    def register_signals(self) -> None:
        def _handler(signum, _frame):
            self.shutdown_requested = True
            self.log("INFO", "general", f"Received signal {signum}")

        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)

    def print_startup_summary(self) -> None:
        self.log("INFO", "general", f"Starting {APP_NAME} with config={self.config_path}")
        self.log("INFO", "general", f"updatefreq={self.update_seconds}s, notifications_enabled={self.notifications.enabled}")
        for source in self.sources:
            paths = sorted(glob.glob(source.pattern))
            if paths:
                for path in paths:
                    self.log("INFO", source.name, f"Tracking file: {path}")
            else:
                self.log("WARN", source.name, f"No files currently match pattern: {source.pattern}")

    def process_source(self, source: SourceConfig) -> None:
        for path in sorted(glob.glob(source.pattern)):
            try:
                stat_result = os.stat(path)
                key = (stat_result.st_dev, stat_result.st_ino)
                self.touched_keys.add(key)

                if key not in self.offsets:
                    self.offsets[key] = stat_result.st_size
                    self.key_to_path[key] = path
                    continue

                offset = self.offsets[key]
                if stat_result.st_size < offset:
                    offset = 0

                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(offset)
                    for line in fh:
                        self.emit_line(source, line.rstrip("\n"))
                    self.offsets[key] = fh.tell()
                    self.key_to_path[key] = path
            except FileNotFoundError:
                continue
            except PermissionError as exc:
                self.log("ERROR", source.name, f"Permission denied for {path}: {exc}")
            except OSError as exc:
                self.log("ERROR", source.name, f"Failed reading {path}: {exc}")

    def cleanup_stale_offsets(self) -> None:
        stale = [key for key in self.offsets.keys() if key not in self.touched_keys]
        for key in stale:
            self.offsets.pop(key, None)
            self.key_to_path.pop(key, None)

    def emit_line(self, source: SourceConfig, line: str) -> None:
        if source.regex and not source.regex.search(line):
            return

        level = self.detect_level(line)
        self.log(level, source.name, line)

        if self.notifications.enabled and self.notifications.ntfy_url and level in self.notifications.levels:
            self.notify_ntfy(level, source.name, line)

    def detect_level(self, line: str) -> str:
        found = self.LEVEL_PATTERN.search(line)
        if not found:
            return "INFO"

        level = found.group(1).upper()
        if level == "WARNING":
            return "WARN"
        return level

    def log(self, level: str, source: str, message: str) -> None:
        timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        print(f"{timestamp} [{level}] [{source}] {message}", flush=True)

    def notify_ntfy(self, level: str, source: str, message: str) -> None:
        payload = json.dumps({
            "app": APP_NAME,
            "source": source,
            "level": level,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }).encode("utf-8")

        request = urllib.request.Request(
            self.notifications.ntfy_url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Title": f"{self.notifications.title_prefix} {level} [{source}]",
                "Tags": level.lower(),
                **({"Authorization": f"Bearer {self.notifications.auth_token}"} if self.notifications.auth_token else {}),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=10):
                return
        except urllib.error.URLError as exc:
            self.log("ERROR", "notification", f"Failed to deliver ntfy notification: {exc}")

    def write_health(self) -> None:
        payload = {
            "status": "ok",
            "timestamp": int(time.time()),
            "updatefreq": self.update_seconds,
            "sources": [source.name for source in self.sources],
        }
        with open(HEALTH_FILE, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)


def main() -> int:
    config_path = os.environ.get("LOG_FORWARDER_CONFIG", DEFAULT_CONFIG_PATH)
    if not os.path.exists(config_path):
        print(f"Config file does not exist: {config_path}", file=sys.stderr)
        return 2

    try:
        LogForwarder(config_path).run()
        return 0
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
