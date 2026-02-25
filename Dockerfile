FROM python:3.12-slim

ARG APP_NAME=docklog-forwarder
ENV APP_NAME=${APP_NAME}
ENV LOG_FORWARDER_CONFIG=/etc/${APP_NAME}/${APP_NAME}.config
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY main.py /app/main.py
COPY healthcheck.py /app/healthcheck.py
COPY config/docklog-forwarder.config /etc/docklog-forwarder/docklog-forwarder.config

RUN chmod +x /app/main.py /app/healthcheck.py

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "/app/healthcheck.py"]

CMD ["python", "/app/main.py"]
