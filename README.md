# docklog-forwarder

`docklog-forwarder` is a Python-based Docker application that reads system logs from the host (through a mounted volume) and forwards them to the container's stdout.

This makes logs available through:

- `docker compose logs`
- dockmon or other tools that read container logs

## Main features

- Reads one or more log files, including glob patterns (`/var/log/syslog*`)
- Optional regex filtering per log source
- Automatic level detection in output: `INFO`, `WARN`, `ERROR`, `CRITICAL`
- NTFY notifications with filtering by selected levels
- Periodic heartbeat/health status
- Built-in Docker image `HEALTHCHECK`

## Configuration

Configuration file inside the container:

`/etc/docklog-forwarder/docklog-forwarder.config`

Example (`config/docklog-forwarder.config`):

```ini
[General]
tz=Europe/Oslo
updatefreq=1min

[Notification]
enabled=false
ntfy_url=https://ntfy.sh/your-topic
auth_token=
levels=WARN,ERROR,CRITICAL
title_prefix=docklog-forwarder

[Syslog]
input=/var/log/syslog*
regex=\bsystemd\b.*$

[PHP-fpm]
input=/var/log/php.log
# regex=
```

### Explanation of key fields

- `[General]`
  - `tz`: Time zone used for log timestamps
  - `updatefreq`: Polling interval (`60`, `30s`, `1min`)
- `[Notification]`
  - `enabled`: `true/false`
  - `ntfy_url`: Full URL to the ntfy topic
  - `auth_token`: Optional bearer token
  - `levels`: Comma-separated list of levels that trigger notifications
- `[SourceName]`
  - `input`: file path or glob pattern
  - `regex`: optional regex filtering on line content

## Startup and tracking overview

At startup, the application logs which files are matched/tracked for each section. If no files match a pattern yet, a `WARN` message is logged.

## Docker Compose example

```yaml
services:
  docklog-forwarder:
    build: .
    container_name: docklog-forwarder
    volumes:
      - /var/log:/var/log:ro
      - ./config/docklog-forwarder.config:/etc/docklog-forwarder/docklog-forwarder.config:ro
    environment:
      - HEALTH_MAX_AGE_SECONDS=180
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "/app/healthcheck.py"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
```

## Build and run

```bash
docker build -t docklog-forwarder .
docker run --rm \
  -v /var/log:/var/log:ro \
  -v $(pwd)/config/docklog-forwarder.config:/etc/docklog-forwarder/docklog-forwarder.config:ro \
  docklog-forwarder
```
