# Alpha Sentinel MCP — production image (seller host). Never bake EVM_PRIVATE_KEY.
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r /app/requirements.txt

FROM python:3.12-slim AS production

WORKDIR /app

RUN groupadd --system appgroup && useradd --system --gid appgroup --home /app appuser

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8403

COPY app/ ./app/
COPY scripts/ ./scripts/
COPY run_stdio.py ./
COPY server.json ./

RUN chmod +x /app/scripts/entrypoint.sh \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8403

HEALTHCHECK --interval=30s --timeout=8s --start-period=15s --retries=3 \
    CMD python /app/scripts/healthcheck.py

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
