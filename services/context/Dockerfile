FROM python:3.15-alpine3.23@sha256:8d77d813a53e534dec9e1e5182cbd5b651b70d63b27e4ea7c1f616b37cf9aad2
RUN python -m pip uninstall --yes pip
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CONTEXT_BIND=0.0.0.0
WORKDIR /app
COPY server.py /app/server.py
COPY static/ /app/static/
USER 65532:65532
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/healthz',timeout=2)"]
ENTRYPOINT ["python", "/app/server.py"]
