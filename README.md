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
- NTFY notifications with filtering by selected levels
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
enabled=false
ntfy_url=https://ntfy.sh/your-topic
auth_token=
levels=WARN,ERROR,CRITICAL
title_prefix=system-log-to-docker

[Syslog]
input=/var/log/syslog*
regex=
strip_syslog_hostname=true

[PHP-fpm]
input=/var/log/php.log
# regex=
# strip_syslog_hostname=false
```

### Explanation of key fields

- `[General]`
  - `tz`: Time zone used for log timestamps
  - `updatefreq`: Polling interval (`5`, `5s`, `1min`). Default is `5s`.
- `[Notification]`
  - `enabled`: `true/false`
  - `ntfy_url`: Full URL to the ntfy topic
  - `auth_token`: Optional bearer token
  - `levels`: Comma-separated list of levels that trigger notifications
- `[SourceName]`
  - `input`: File path or glob pattern
  - `regex`: Optional regex filtering on line content
  - `strip_syslog_hostname`: If `true`, strips hostname from classic syslog lines like `Feb 25 18:54:47 test systemd[1]: ...`

## Startup and tracking overview

At startup, the application logs which files are matched/tracked for each section. If no files match a pattern yet, a `WARN` message is logged.

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
