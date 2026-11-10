"""Research-only disclaimers for Stocks Maxxing tools."""

DISCLAIMER_SHORT = (
    "Research only — not investment advice. No order execution, trading, routing, "
    "custody, or swaps. Coinbase tokenized stocks are not offered to U.S. persons; "
    "integrators must enforce jurisdictional restrictions."
)

DISCLAIMER_FIELDS = {
    "research_only": True,
    "not_investment_advice": True,
    "no_trading_or_execution": True,
    "us_person_trading_not_supported": True,
    "disclaimer": DISCLAIMER_SHORT,
}


def with_disclaimer(payload: dict) -> dict:
    """Attach standard disclaimer fields to a tool response payload."""
    out = dict(payload)
    out.update(DISCLAIMER_FIELDS)
    return out
