# docklog-forwarder

`docklog-forwarder` er en Python-basert Docker-applikasjon som leser systemlogger fra host (via mount) og skriver dem videre til containerens stdout.

Dette gjør at loggene kan leses med:

- `docker compose logs`
- dockmon eller andre verktøy som leser container-logger

## Hovedfunksjoner

- Leser én eller flere loggfiler, inkludert glob-mønstre (`/var/log/syslog*`)
- Valgfri regex-filtrering per loggkilde
- Automatisk nivå-deteksjon i output: `INFO`, `WARN`, `ERROR`, `CRITICAL`
- NTFY-notifikasjoner med filtrering på ønskede nivåer
- Periodisk heartbeat/health-status
- Innebygd `HEALTHCHECK` i Docker-image

## Konfigurasjon

Konfigurasjonsfil i container:

`/etc/docklog-forwarder/docklog-forwarder.config`

Eksempel (`config/docklog-forwarder.config`):

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

### Forklaring av nøkkelfelt

- `[General]`
  - `tz`: Tidssone brukt i loggtidsstempel
  - `updatefreq`: Polling-intervall (`60`, `30s`, `1min`)
- `[Notification]`
  - `enabled`: `true/false`
  - `ntfy_url`: Full URL til ntfy topic
  - `auth_token`: Valgfri bearer token
  - `levels`: Komma-separert liste av nivåer som skal trigge notifikasjon
- `[KildeNavn]`
  - `input`: filsti eller glob-mønster
  - `regex`: valgfri regex-filtering på linjeinnhold

## Oppstart og tracking-oversikt

Ved oppstart logger applikasjonen hvilke filer som matches/tracked for hver seksjon. Hvis ingen filer matcher et mønster ennå, logges en `WARN`.

## Docker Compose eksempel

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

## Bygg og kjør

```bash
docker build -t docklog-forwarder .
docker run --rm \
  -v /var/log:/var/log:ro \
  -v $(pwd)/config/docklog-forwarder.config:/etc/docklog-forwarder/docklog-forwarder.config:ro \
  docklog-forwarder
```
