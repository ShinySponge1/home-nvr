FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
WORKDIR /app
COPY gateway.py /app/gateway.py
USER 65532:65532
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8081
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8081')+'/healthz', timeout=2)"]
CMD ["python", "/app/gateway.py"]
