FROM python:3.15-alpine3.23@sha256:8d77d813a53e534dec9e1e5182cbd5b651b70d63b27e4ea7c1f616b37cf9aad2
RUN python -m pip uninstall --yes pip
WORKDIR /app
COPY gateway.py /app/gateway.py
USER 65532:65532
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8081
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8081')+'/healthz', timeout=2)"]
CMD ["python", "/app/gateway.py"]
