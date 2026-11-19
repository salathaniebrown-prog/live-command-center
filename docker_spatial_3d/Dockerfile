FROM python:3.12-slim
LABEL maintainer="Salathaniel Brown Sr. <alstra-edge>"
LABEL description="Alstra Off-Axis 3D WebGL/WebXR Anamorphic Spatial Artifact Engine"

WORKDIR /app
COPY astra_spatial_3d_server_8151.py /app/astra_spatial_3d_server_8151.py
COPY ALSTRA_SPATIAL_3D_ENGINE.html /root/ALSTRA_SPATIAL_3D_ENGINE.html

ENV ALSTRA_SHADOW_PORT=8151
EXPOSE 8151

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8151/health')" || exit 1

CMD ["python3", "/app/astra_spatial_3d_server_8151.py"]
