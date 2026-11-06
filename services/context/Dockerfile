FROM python:3.15-alpine3.23@sha256:4b777652b7ca0a1fae98a847e83e538605d0fb8de3812f3403076aca74368e74
RUN python -m pip uninstall --yes pip
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CONTEXT_BIND=0.0.0.0
WORKDIR /app
COPY server.py /app/server.py
COPY static/ /app/static/
USER 65532:65532
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/healthz',timeout=2)"]
ENTRYPOINT ["python", "/app/server.py"]
