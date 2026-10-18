#!/usr/bin/env bash
# Smoke probes for Alpha Sentinel on Vercel (routing + x402 gate).
# Usage: ./scripts/smoke_live_deployment.sh [BASE_URL]
set -euo pipefail

BASE_URL="${1:-https://alpha-sentinel-mcp.vercel.app}"
BASE_URL="${BASE_URL%/}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

check_not_html() {
  local path="$1"
  local expect_code="${2:-200}"
  local tmp
  tmp="$(mktemp)"
  local code
  code="$(curl -sS -o "$tmp" -w "%{http_code}" "${BASE_URL}${path}")"
  local ctype
  ctype="$(curl -sS -I "${BASE_URL}${path}" | awk -F': ' 'tolower($1)=="content-type"{print $2}' | tr -d '\r' | head -1)"
  if [[ "$ctype" == *"text/html"* ]]; then
    fail "${path} returned HTML (SPA leak) — content-type: ${ctype}"
  fi
  if [[ "$code" != "$expect_code" ]]; then
    echo "body:" >&2
    head -c 400 "$tmp" >&2 || true
    fail "${path} expected HTTP ${expect_code}, got ${code}"
  fi
  echo "OK ${path} (${code}, ${ctype:-unknown})"
  rm -f "$tmp"
}

echo "Probing ${BASE_URL}"

check_not_html "/health" 200
check_not_html "/.well-known/x402" 200
check_not_html "/llms.txt" 200
check_not_html "/mcp" 200

code="$(curl -sS -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/mcp" \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}')"
if [[ "$code" != "200" ]]; then
  fail "POST /mcp initialize expected 200, got ${code}"
fi
echo "OK POST /mcp initialize (200)"

code="$(curl -sS -o /dev/null -w "%{http_code}" "${BASE_URL}/tools/fetch_price?symbol=BTC")"
if [[ "$code" != "402" ]]; then
  fail "/tools/fetch_price unpaid expected 402, got ${code}"
fi
echo "OK /tools/fetch_price unpaid (402)"

code="$(curl -sS -o /dev/null -w "%{http_code}" "${BASE_URL}/api/tools/fetch_price?symbol=BTC")"
if [[ "$code" != "402" ]]; then
  fail "/api/tools/fetch_price unpaid expected 402, got ${code}"
fi
echo "OK /api/tools/fetch_price unpaid (402)"

check_not_html "/tools/fetch_price/sample" 200

facilitator="$(curl -sS "${BASE_URL}/api/health" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("components",{}).get("x402",{}).get("facilitator",""))')"
if [[ "$facilitator" != "CDP" ]]; then
  echo "WARN: /api/health x402.facilitator is '${facilitator}' (expected CDP when CDP creds set on Vercel)"
else
  echo "OK /api/health facilitator CDP"
fi

echo "All smoke checks passed for ${BASE_URL}"
