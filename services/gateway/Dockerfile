FROM python:3.15-alpine3.23@sha256:4b777652b7ca0a1fae98a847e83e538605d0fb8de3812f3403076aca74368e74
RUN python -m pip uninstall --yes pip
WORKDIR /app
COPY gateway.py /app/gateway.py
USER 65532:65532
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8081
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8081')+'/healthz', timeout=2)"]
CMD ["python", "/app/gateway.py"]
