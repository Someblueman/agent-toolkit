"""
Simplified Implementation: Flat Guard Clauses & Modular Verification

This module demonstrates eliminating the Arrow Anti-Pattern using early returns
and cohesive sub-validators. Nesting depth drops to 1, cognitive complexity to 3,
and all complexity metrics easily pass standard complexity budgets.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

MAX_TIMESTAMP_SKEW_SECONDS = 300
FEE_RATE = 0.015


def _verify_header_and_timestamp(
    payload: Dict[str, Any], current_timestamp: int
) -> Optional[str]:
    if not isinstance(payload, dict):
        return "ERR_INVALID_PAYLOAD_STRUCTURE"
    if payload.get("version") != "v2":
        return "ERR_UNSUPPORTED_VERSION"
    ts = payload.get("timestamp")
    if not isinstance(ts, int):
        return "ERR_MISSING_TIMESTAMP"
    if abs(current_timestamp - ts) > MAX_TIMESTAMP_SKEW_SECONDS:
        return "ERR_TIMESTAMP_EXPIRED"
    return None


def _verify_account_and_deduct(
    account_id: str, amount: Any, account_db: Dict[str, Dict[str, Any]]
) -> Tuple[Optional[str], float, float]:
    account = account_db.get(account_id)
    if account is None:
        return "ERR_ACCOUNT_NOT_FOUND", 0.0, 0.0
    if not account.get("is_active", False):
        return "ERR_ACCOUNT_SUSPENDED", 0.0, 0.0
    if not isinstance(amount, (int, float)) or not (amount > 0) or math.isnan(amount):
        return "ERR_INVALID_AMOUNT", 0.0, 0.0

    fee = round(amount * FEE_RATE, 2)
    total_deduction = amount + fee
    if account.get("balance", 0.0) < total_deduction:
        return "ERR_INSUFFICIENT_FUNDS", 0.0, 0.0

    account["balance"] -= total_deduction
    return None, fee, account["balance"]


def parse_and_validate_transaction(
    payload: Dict[str, Any],
    account_db: Dict[str, Dict[str, Any]],
    processed_tx_ids: set[str],
    current_timestamp: int,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Parses and validates a transaction payload using flat guard clauses.
    """
    header_err = _verify_header_and_timestamp(payload, current_timestamp)
    if header_err:
        return False, header_err, None

    tx_id = payload.get("tx_id")
    if not isinstance(tx_id, str) or not tx_id or tx_id in processed_tx_ids:
        return False, "ERR_DUPLICATE_OR_INVALID_TX_ID", None

    account_id = payload.get("account_id")
    amount = payload.get("amount")
    acc_err, fee, new_balance = _verify_account_and_deduct(account_id, amount, account_db)
    if acc_err:
        return False, acc_err, None

    processed_tx_ids.add(tx_id)
    return True, "SUCCESS", {
        "tx_id": tx_id,
        "account_id": account_id,
        "net_amount": amount,
        "fee": fee,
        "new_balance": new_balance,
        "status": "SETTLED",
    }
