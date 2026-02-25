# system-log-to-docker

`system-log-to-docker` is a Python-based Docker utility that reads host system logs (through mounted files) and presents them as container stdout/stderr.

This makes host logs visible through:

- `docker compose logs`
- Docker log drivers and log collectors that already read container logs

## Main features

- Reads one or more log files, including glob patterns (`/var/log/syslog*`)
- Optional regex filtering per log source
- Automatic level detection in output: `INFO`, `WARN`, `ERROR`, `CRITICAL`
- Optional hostname stripping for classic syslog lines (so hostnames like `test` are not repeated in every message)
- NTFY notifications with per-source enable/disable and level filtering
- Periodic heartbeat/health status
- Built-in Docker image `HEALTHCHECK`

## Configuration

Configuration file inside the container:

`/etc/system-log-to-docker/system-log-to-docker.config`

Example (`config/system-log-to-docker.config`):

```ini
[General]
tz=Europe/Oslo
updatefreq=5s

[Notification]
url=https://ntfy.sh
topic=your-topic
auth_token=
title_prefix=system-log-to-docker

[Syslog]
input=/var/log/syslog*
regex=
strip_syslog_hostname=true
enable_notifications=false
notification_levels=WARN,ERROR,CRITICAL

[PHP-fpm]
input=/var/log/php.log
# regex=
# strip_syslog_hostname=false
enable_notifications=true
notification_levels=ERROR,CRITICAL
```

### Explanation of key fields

- `[General]`
  - `tz`: Time zone used for log timestamps
  - `updatefreq`: Polling interval (`5`, `5s`, `1min`). Default is `5s`.
- `[Notification]`
  - `url`: Base ntfy URL (for example `https://ntfy.sh`)
  - `topic`: ntfy topic name (for example `my-alerts`)
  - `ntfy_url`: Optional full topic URL (legacy/override, e.g. `https://ntfy.sh/my-alerts`)
  - `auth_token`: Optional bearer token
  - `title_prefix`: Prefix used for notification titles
  - `allow_insecure_http`: Set to `true` to permit plain HTTP ntfy endpoints (default `false`; HTTPS only).
- `[SourceName]`
  - `input`: File path or glob pattern
  - `regex`: Optional regex filtering on line content
  - `strip_syslog_hostname`: If `true`, strips hostname from classic syslog lines like `Feb 25 18:54:47 test systemd[1]: ...`
  - `enable_notifications`: `true/false` per source
  - `notification_levels`: Comma-separated list of levels that trigger notifications for this source

## Startup and tracking overview

At startup, the application logs which files are matched/tracked for each section. If no files match a pattern yet, a `WARN` message is logged.

It also logs a notification summary, including:

- Global notification readiness (`notifications_enabled=true/false`) based on whether at least one source has `enable_notifications=true`
- Which sources have notifications enabled, and which `notification_levels` are active for each source
- A warning when source notifications are enabled but ntfy URL/topic is not configured

## Docker Compose example

```yaml
services:
  system-log-to-docker:
    image: ghcr.io/your-org/system-log-to-docker:latest
    container_name: system-log-to-docker
    volumes:
      - /var/log:/var/log:ro
      - ./config/system-log-to-docker.config:/etc/system-log-to-docker/system-log-to-docker.config:ro
    environment:
      - HEALTH_MAX_AGE_SECONDS=180
      - HEALTH_FILE=/run/system-log-to-docker/health.json
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
docker build -t system-log-to-docker .
docker run --rm \
  -v /var/log:/var/log:ro \
  -v $(pwd)/config/system-log-to-docker.config:/etc/system-log-to-docker/system-log-to-docker.config:ro \
  system-log-to-docker
```
