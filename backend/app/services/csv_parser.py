"""Parse CSV portfolio exports into holdings data.

Supports:
- Trading 212 transaction history export
- Generic CSV with columns: ticker, name, quantity, average_cost_basis
"""

import csv
import io
import logging
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ParsedHolding:
    ticker: str
    name: str
    quantity: float
    average_cost_basis: float
    currency: str


def parse_trading212_csv(content: str) -> list[ParsedHolding]:
    """Parse Trading 212 transaction history CSV.

    Trading 212 exports transactions (buys/sells), not current holdings.
    We aggregate buy transactions to compute current positions.

    Expected columns: Action, Time, ISIN, Ticker, Name, No. of shares,
    Price / share, Currency (Price / share), ...
    """
    reader = csv.DictReader(io.StringIO(content))
    fields = reader.fieldnames or []

    # Detect Trading 212 format by checking for characteristic columns
    t212_markers = {"Ticker", "No. of shares", "Price / share", "Action"}
    if not t212_markers.issubset(set(fields)):
        raise ValueError(
            f"Not a Trading 212 CSV. Expected columns: {t212_markers}. "
            f"Got: {fields}"
        )

    # Aggregate: track total shares and total cost per ticker
    positions: dict[str, dict] = defaultdict(lambda: {
        "name": "",
        "total_shares": 0.0,
        "total_cost": 0.0,
        "currency": "GBP",
    })

    for row in reader:
        action = row.get("Action", "").strip()
        ticker = row.get("Ticker", "").strip()
        name = row.get("Name", "").strip()

        if not ticker:
            continue

        try:
            shares = float(row.get("No. of shares", "0") or "0")
            price = float(row.get("Price / share", "0") or "0")
        except ValueError:
            logger.warning(f"Skipping row with invalid numbers: {row}")
            continue

        currency = row.get("Currency (Price / share)", "GBP").strip() or "GBP"

        pos = positions[ticker]
        pos["name"] = name or ticker
        pos["currency"] = currency

        if action.startswith("Market buy") or action.startswith("Limit buy"):
            pos["total_shares"] += shares
            pos["total_cost"] += shares * price
        elif action.startswith("Market sell") or action.startswith("Limit sell"):
            pos["total_shares"] -= shares
            # Don't reduce cost basis on sell — keep avg cost from buys

    holdings = []
    for ticker, pos in positions.items():
        if pos["total_shares"] <= 0.001:
            continue  # Fully sold position
        avg_cost = pos["total_cost"] / pos["total_shares"] if pos["total_shares"] > 0 else 0
        holdings.append(ParsedHolding(
            ticker=ticker,
            name=pos["name"],
            quantity=round(pos["total_shares"], 8),
            average_cost_basis=round(avg_cost, 4),
            currency=pos["currency"],
        ))

    return holdings


def parse_generic_csv(content: str) -> list[ParsedHolding]:
    """Parse a simple CSV with columns: ticker, name, quantity, average_cost_basis.

    Also accepts: symbol (as ticker alias), qty/shares (as quantity alias),
    avg_cost/cost_basis (as average_cost_basis alias).
    """
    reader = csv.DictReader(io.StringIO(content))
    fields = {f.strip().lower() for f in (reader.fieldnames or [])}

    # Map common column name aliases
    def find_col(row: dict, candidates: list[str]) -> str:
        for c in candidates:
            for key in row:
                if key.strip().lower() == c:
                    return row[key].strip()
        return ""

    holdings = []
    for row in reader:
        ticker = find_col(row, ["ticker", "symbol", "code"])
        name = find_col(row, ["name", "company", "company_name", "security"])
        qty_str = find_col(row, ["quantity", "qty", "shares", "no. of shares", "units"])
        cost_str = find_col(row, ["average_cost_basis", "avg_cost", "cost_basis", "avg_price",
                                   "price / share", "price", "cost"])
        currency = find_col(row, ["currency", "ccy"]) or "GBP"

        if not ticker or not qty_str:
            continue

        try:
            quantity = float(qty_str)
            avg_cost = float(cost_str) if cost_str else 0.0
        except ValueError:
            logger.warning(f"Skipping row with invalid numbers: {row}")
            continue

        if quantity <= 0:
            continue

        holdings.append(ParsedHolding(
            ticker=ticker.upper(),
            name=name or ticker.upper(),
            quantity=round(quantity, 8),
            average_cost_basis=round(avg_cost, 4),
            currency=currency.upper(),
        ))

    return holdings


def parse_csv(content: str) -> list[ParsedHolding]:
    """Auto-detect CSV format and parse."""
    # Peek at headers to detect format
    first_line = content.split("\n")[0] if content else ""

    if "No. of shares" in first_line and "Action" in first_line:
        logger.info("Detected Trading 212 CSV format")
        return parse_trading212_csv(content)

    logger.info("Using generic CSV parser")
    return parse_generic_csv(content)
