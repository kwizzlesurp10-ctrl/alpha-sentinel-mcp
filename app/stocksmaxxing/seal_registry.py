"""Seal Proof-of-Research hashes on Base via a minimal registry contract."""

from __future__ import annotations

import logging
from typing import Any

from eth_account import Account
from web3 import Web3
from web3.constants import ADDRESS_ZERO

from app.config import settings
from app.stocksmaxxing.research_receipt import brief_id_from_hash, bytes32_from_hex

logger = logging.getLogger(__name__)

REGISTRY_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "contentHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "briefId", "type": "bytes32"},
        ],
        "name": "seal",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "name": "sealedAt",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "bytes32", "name": "contentHash", "type": "bytes32"},
            {"indexed": True, "internalType": "bytes32", "name": "briefId", "type": "bytes32"},
            {"indexed": True, "internalType": "address", "name": "sealer", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "sealedAt", "type": "uint256"},
        ],
        "name": "ResearchSealed",
        "type": "event",
    },
]

CHAIN_PRESETS: dict[str, dict[str, Any]] = {
    "base-sepolia": {"chain_id": 84532, "network": "eip155:84532", "name": "Base Sepolia"},
    "base-mainnet": {"chain_id": 8453, "network": "eip155:8453", "name": "Base Mainnet"},
}


def resolve_seal_chain() -> dict[str, Any]:
    key = (settings.stocksmaxxing_seal_chain or "base-sepolia").strip().lower()
    preset = CHAIN_PRESETS.get(key)
    if not preset:
        raise ValueError(f"Unknown STOCKSMAXXING_SEAL_CHAIN: {key}")
    if key == "base-mainnet" and not settings.stocksmaxxing_seal_allow_mainnet:
        raise ValueError(
            "Base mainnet sealing requires STOCKSMAXXING_SEAL_ALLOW_MAINNET=true (default is Base Sepolia only)"
        )
    return dict(preset, chain_key=key)


def _web3() -> Web3:
    rpc = settings.stocksmaxxing_seal_rpc_url
    if not rpc:
        chain = resolve_seal_chain()
        rpc = (
            "https://sepolia.base.org"
            if chain["chain_key"] == "base-sepolia"
            else settings.base_rpc_url
        )
    return Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))


def _registry_contract(w3: Web3):
    addr = settings.research_receipt_registry_address
    if not addr:
        return None
    return w3.eth.contract(address=Web3.to_checksum_address(addr), abi=REGISTRY_ABI)


def brief_id_to_bytes32(brief_id: str) -> bytes:
    return Web3.keccak(text=brief_id)


async def read_onchain_sealed_at(content_hash: str) -> int | None:
    if not settings.research_receipt_registry_address:
        return None
    try:
        w3 = _web3()
        contract = _registry_contract(w3)
        if contract is None:
            return None
        h = bytes32_from_hex(content_hash)
        ts = int(contract.functions.sealedAt(h).call())
        return ts if ts > 0 else None
    except Exception as exc:
        logger.warning("onchain sealedAt read failed: %s", exc)
        return None


async def seal_receipt_on_base(
    *,
    content_hash: str,
    brief_id: str | None = None,
) -> dict[str, Any]:
    brief_id = brief_id or brief_id_from_hash(content_hash)
    chain = resolve_seal_chain()
    registry = settings.research_receipt_registry_address
    if not registry:
        return {
            "status": "registry_not_configured",
            "content_hash": content_hash,
            "brief_id": brief_id,
            "chain": chain,
            "contract_source": "app/stocksmaxxing/contracts/ResearchReceiptRegistry.sol",
            "env_required": "RESEARCH_RECEIPT_REGISTRY_ADDRESS",
            "note": "Deploy ResearchReceiptRegistry on Base Sepolia for demo; set address in env.",
        }

    w3 = _web3()
    contract = _registry_contract(w3)
    assert contract is not None
    content_b = bytes32_from_hex(content_hash)
    brief_b = brief_id_to_bytes32(brief_id)

    existing = int(contract.functions.sealedAt(content_b).call())
    if existing > 0:
        return {
            "status": "already_sealed",
            "content_hash": content_hash,
            "brief_id": brief_id,
            "onchain_sealed_at_unix": existing,
            "chain": chain,
            "registry_address": registry,
        }

    fn = contract.functions.seal(content_b, brief_b)
    if not settings.stocksmaxxing_seal_submit:
        data = fn._encode_transaction_data()  # type: ignore[attr-defined]
        return {
            "status": "prepared_unsigned",
            "content_hash": content_hash,
            "brief_id": brief_id,
            "chain": chain,
            "registry_address": registry,
            "to": registry,
            "calldata": data,
            "method": "seal(bytes32,bytes32)",
            "submit_env": "Set STOCKSMAXXING_SEAL_SUBMIT=true and STOCKSMAXXING_SEAL_PRIVATE_KEY to broadcast",
        }

    key = settings.stocksmaxxing_seal_private_key
    if not key:
        return {
            "status": "signer_missing",
            "content_hash": content_hash,
            "brief_id": brief_id,
            "chain": chain,
            "env_required": "STOCKSMAXXING_SEAL_PRIVATE_KEY",
        }

    acct = Account.from_key(key)
    nonce = w3.eth.get_transaction_count(acct.address)
    tx = fn.build_transaction(
        {
            "from": acct.address,
            "nonce": nonce,
            "chainId": chain["chain_id"],
            "gas": settings.stocksmaxxing_seal_gas_limit,
            "maxFeePerGas": w3.to_wei(settings.stocksmaxxing_seal_max_fee_gwei, "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(settings.stocksmaxxing_seal_priority_fee_gwei, "gwei"),
        }
    )
    if tx.get("to") in (None, ADDRESS_ZERO):
        return {"status": "tx_build_failed", "error": "invalid registry address"}

    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return {
        "status": "submitted",
        "content_hash": content_hash,
        "brief_id": brief_id,
        "chain": chain,
        "registry_address": registry,
        "tx_hash": tx_hash.hex(),
        "explorer_hint": "Confirm sealedAt via verify-receipt after inclusion",
    }


async def verify_receipt_onchain(content_hash: str, brief_id: str | None = None) -> dict[str, Any]:
    brief_id = brief_id or brief_id_from_hash(content_hash)
    chain = resolve_seal_chain()
    onchain_ts = await read_onchain_sealed_at(content_hash)
    return {
        "content_hash": content_hash,
        "brief_id": brief_id,
        "chain": chain,
        "registry_address": settings.research_receipt_registry_address,
        "onchain_sealed_at_unix": onchain_ts,
        "onchain_match": onchain_ts is not None and onchain_ts > 0,
    }
