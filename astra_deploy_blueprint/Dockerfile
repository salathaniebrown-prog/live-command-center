FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates procps \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 10001 -s /usr/sbin/nologin astra
WORKDIR /app
COPY --chown=astra:astra dashboard.py vserver.py orbital_crypto_spine.py shell_catcher_verify.sh /app/
RUN chmod +x /app/shell_catcher_verify.sh
USER astra
EXPOSE 8088 8099 8101 8102
CMD ["sh", "-c", "python3 /app/vserver.py & python3 /app/orbital_crypto_spine.py & exec python3 /app/dashboard.py"]
