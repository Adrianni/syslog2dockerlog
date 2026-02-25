FROM python:3.12-slim

ARG APP_NAME=system-log-to-docker
ENV APP_NAME=${APP_NAME}
ENV LOG_FORWARDER_CONFIG=/etc/${APP_NAME}/${APP_NAME}.config
ENV PYTHONUNBUFFERED=1
ENV HEALTH_FILE=/run/${APP_NAME}/health.json

WORKDIR /app
COPY main.py /app/main.py
COPY healthcheck.py /app/healthcheck.py
COPY config/system-log-to-docker.config /etc/system-log-to-docker/system-log-to-docker.config

RUN mkdir -p /run/${APP_NAME} \
    && chmod 700 /run/${APP_NAME} \
    && chmod +x /app/main.py /app/healthcheck.py

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "/app/healthcheck.py"]

CMD ["python", "/app/main.py"]
