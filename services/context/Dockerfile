FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CONTEXT_BIND=0.0.0.0
WORKDIR /app
COPY server.py /app/server.py
COPY static/ /app/static/
USER 65532:65532
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=3s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/healthz',timeout=2)"]
ENTRYPOINT ["python", "/app/server.py"]
