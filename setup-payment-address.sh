#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Alpha Sentinel MCP - Payment Address Setup Script
# ==============================================================================

DEFAULT_ADDRESS="0x0d25A44f74868eCE53B305C97139CF4B62963410"
ENV_FILE=".env"
ENV_EXAMPLE=".env.example"

echo "============================================================"
echo "  Alpha Sentinel MCP — x402 Payment Address Configuration   "
echo "============================================================"

# Resolve target address
TARGET_ADDRESS="${1:-${PAY_TO_ADDRESS:-}}"

if [ -z "$TARGET_ADDRESS" ]; then
    if [ -t 0 ]; then
        read -r -p "Enter your x402 receive wallet address (default: $DEFAULT_ADDRESS): " INPUT_ADDRESS
        TARGET_ADDRESS="${INPUT_ADDRESS:-$DEFAULT_ADDRESS}"
    else
        TARGET_ADDRESS="$DEFAULT_ADDRESS"
    fi
fi

# Trim whitespace
TARGET_ADDRESS=$(echo "$TARGET_ADDRESS" | tr -d '[:space:]')

# Refuse retired seller wallets (never write them into .env).
case "$(echo "$TARGET_ADDRESS" | tr '[:upper:]' '[:lower:]')" in
  0xab745e5f576667037696e78ba7da28e193e4423d|0x05e1720bb82f86b5bc7940a99fdc702e32256357)
    echo "ERROR: $TARGET_ADDRESS is a retired seller wallet. Use $DEFAULT_ADDRESS." >&2
    exit 1
    ;;
esac

# Validate EVM address format (0x + 40 hex characters)
if [[ ! "$TARGET_ADDRESS" =~ ^0x[0-9a-fA-F]{40}$ ]]; then
    echo "❌ Error: Invalid EVM address format '$TARGET_ADDRESS'."
    echo "   An Ethereum/Base address must start with '0x' followed by 40 hex characters."
    exit 1
fi

# Ensure .env exists
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        echo "📄 Creating $ENV_FILE from $ENV_EXAMPLE..."
        cp "$ENV_EXAMPLE" "$ENV_FILE"
    else
        echo "📄 Initializing new $ENV_FILE..."
        touch "$ENV_FILE"
    fi
fi

# Update or insert X402_PAY_TO_ADDRESS in .env
if grep -q "^X402_PAY_TO_ADDRESS=" "$ENV_FILE"; then
    sed -i "s|^X402_PAY_TO_ADDRESS=.*|X402_PAY_TO_ADDRESS=$TARGET_ADDRESS|" "$ENV_FILE"
else
    echo "X402_PAY_TO_ADDRESS=$TARGET_ADDRESS" >> "$ENV_FILE"
fi

echo ""
echo "✅ Payment address successfully configured in $ENV_FILE!"
echo "   X402_PAY_TO_ADDRESS = $TARGET_ADDRESS"
echo ""
echo "🔐 Note: This cold wallet address receives revenue on Base Mainnet (x402)."
echo "   Keep your hot wallet EVM_PRIVATE_KEY separate and local-only."
echo "============================================================"
