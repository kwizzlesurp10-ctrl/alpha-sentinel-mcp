#!/bin/sh
set -eu

cd /app

python -c "from app.server_boot import assert_seller_safe, bind_address; assert_seller_safe(); addr = bind_address(); print(f'binding {addr.host}:{addr.port}', flush=True)"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8403}"

exec uvicorn app.application:app \
  --host "$HOST" \
  --port "$PORT" \
  --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-127.0.0.1}"
