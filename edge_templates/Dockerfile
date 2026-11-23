FROM python:3.12-slim
WORKDIR /app
COPY main_head_router.py /app/
COPY nodes_manifest/ /app/nodes_manifest/
EXPOSE 8140
HEALTHCHECK --interval=15s --timeout=3s CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8140/health')" || exit 1
CMD ["python3", "main_head_router.py"]
