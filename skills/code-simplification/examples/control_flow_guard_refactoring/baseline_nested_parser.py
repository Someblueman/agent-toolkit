"""
Baseline Implementation: Deeply Nested Conditional Validator (Arrow Anti-Pattern)

This module demonstrates the classic "Pyramid of Doom" where 6+ levels of nested
if-else statements make the logic difficult to read, reason about, and maintain.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def parse_and_validate_transaction(
    payload: Dict[str, Any],
    account_db: Dict[str, Dict[str, Any]],
    processed_tx_ids: set[str],
    current_timestamp: int,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Parses and validates a raw transaction payload against business rules.
    Returns (is_valid, error_or_success_message, processed_record).
    """
    # Level 1: Check payload root
    if payload is not None and isinstance(payload, dict):
        # Level 2: Check schema version
        if "version" in payload and payload["version"] == "v2":
            # Level 3: Check timestamp within 300s window
            if "timestamp" in payload and isinstance(payload["timestamp"], int):
                if abs(current_timestamp - payload["timestamp"]) <= 300:
                    # Level 4: Check deduplication
                    tx_id = payload.get("tx_id")
                    if tx_id and isinstance(tx_id, str) and tx_id not in processed_tx_ids:
                        # Level 5: Check account existence and active status
                        account_id = payload.get("account_id")
                        if account_id in account_db:
                            account = account_db[account_id]
                            if account.get("is_active", False):
                                # Level 6: Check amount and funds
                                amount = payload.get("amount")
                                if isinstance(amount, (int, float)) and amount > 0:
                                    fee = round(amount * 0.015, 2)
                                    total_deduction = amount + fee
                                    if account.get("balance", 0.0) >= total_deduction:
                                        # Success branch at indentation level 10
                                        processed_tx_ids.add(tx_id)
                                        account["balance"] -= total_deduction
                                        return True, "SUCCESS", {
                                            "tx_id": tx_id,
                                            "account_id": account_id,
                                            "net_amount": amount,
                                            "fee": fee,
                                            "new_balance": account["balance"],
                                            "status": "SETTLED",
                                        }
                                    else:
                                        return False, "ERR_INSUFFICIENT_FUNDS", None
                                else:
                                    return False, "ERR_INVALID_AMOUNT", None
                            else:
                                return False, "ERR_ACCOUNT_SUSPENDED", None
                        else:
                            return False, "ERR_ACCOUNT_NOT_FOUND", None
                    else:
                        return False, "ERR_DUPLICATE_OR_INVALID_TX_ID", None
                else:
                    return False, "ERR_TIMESTAMP_EXPIRED", None
            else:
                return False, "ERR_MISSING_TIMESTAMP", None
        else:
            return False, "ERR_UNSUPPORTED_VERSION", None
    else:
        return False, "ERR_INVALID_PAYLOAD_STRUCTURE", None
