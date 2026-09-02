#!/usr/bin/env python3
"""
Parity Test Suite for Control Flow Guard Refactoring

Verifies 100% behavioral equivalence between baseline nested parser and simplified guard parser
across edge cases, invalid payloads, and 5,000 randomized property tests.
"""

from __future__ import annotations

import copy
import random
import string
import time
from typing import Any, Dict, List, Tuple

import baseline_nested_parser as baseline
import simplified_guard_parser as simplified


def generate_random_string(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_test_payload(valid: bool = True) -> Tuple[Any, Dict[str, Dict[str, Any]], set[str], int]:
    now = 1700000000
    account_id = f"acc_{generate_random_string(6)}"
    tx_id = f"tx_{generate_random_string(8)}"

    account_db = {
        account_id: {
            "is_active": True,
            "balance": 10000.0,
        }
    }
    processed_set: set[str] = set()

    if valid:
        payload = {
            "version": "v2",
            "timestamp": now - random.randint(0, 100),
            "tx_id": tx_id,
            "account_id": account_id,
            "amount": round(random.uniform(10.0, 500.0), 2),
        }
        return payload, account_db, processed_set, now

    # Generate various invalid permutations
    error_mode = random.choice([
        "invalid_root",
        "wrong_version",
        "missing_timestamp",
        "expired_timestamp",
        "duplicate_tx",
        "missing_account",
        "suspended_account",
        "negative_amount",
        "nan_amount",
        "inf_amount",
        "-inf_amount",
        "insufficient_funds",
    ])

    if error_mode == "invalid_root":
        return None, account_db, processed_set, now  # type: ignore
    elif error_mode == "wrong_version":
        payload = {"version": "v1", "timestamp": now, "tx_id": tx_id, "account_id": account_id, "amount": 50.0}
    elif error_mode == "missing_timestamp":
        payload = {"version": "v2", "timestamp": "invalid", "tx_id": tx_id, "account_id": account_id, "amount": 50.0}
    elif error_mode == "expired_timestamp":
        payload = {"version": "v2", "timestamp": now - 500, "tx_id": tx_id, "account_id": account_id, "amount": 50.0}
    elif error_mode == "duplicate_tx":
        processed_set.add(tx_id)
        payload = {"version": "v2", "timestamp": now, "tx_id": tx_id, "account_id": account_id, "amount": 50.0}
    elif error_mode == "missing_account":
        payload = {"version": "v2", "timestamp": now, "tx_id": tx_id, "account_id": "nonexistent", "amount": 50.0}
    elif error_mode == "suspended_account":
        account_db[account_id]["is_active"] = False
        payload = {"version": "v2", "timestamp": now, "tx_id": tx_id, "account_id": account_id, "amount": 50.0}
    elif error_mode == "negative_amount":
        payload = {"version": "v2", "timestamp": now, "tx_id": tx_id, "account_id": account_id, "amount": -10.0}
    elif error_mode == "nan_amount":
        payload = {"version": "v2", "timestamp": now, "tx_id": tx_id, "account_id": account_id, "amount": float("nan")}
    elif error_mode == "inf_amount":
        payload = {"version": "v2", "timestamp": now, "tx_id": tx_id, "account_id": account_id, "amount": float("inf")}
    elif error_mode == "-inf_amount":
        payload = {"version": "v2", "timestamp": now, "tx_id": tx_id, "account_id": account_id, "amount": float("-inf")}
    else:  # insufficient_funds
        account_db[account_id]["balance"] = 5.0
        payload = {"version": "v2", "timestamp": now, "tx_id": tx_id, "account_id": account_id, "amount": 100.0}

    return payload, account_db, processed_set, now


def run_deterministic_edge_cases() -> int:
    now = 1700000000
    cases: List[Tuple[str, Any, Dict[str, Any], set[str]]] = [
        ("None payload", None, {}, set()),
        ("Empty dict payload", {}, {}, set()),
        ("Wrong version", {"version": "v3"}, {}, set()),
        ("Expired timestamp", {"version": "v2", "timestamp": now - 1000}, {}, set()),
        ("Valid tx", {"version": "v2", "timestamp": now, "tx_id": "tx1", "account_id": "a1", "amount": 100.0},
         {"a1": {"is_active": True, "balance": 1000.0}}, set()),
        ("NaN amount", {"version": "v2", "timestamp": now, "tx_id": "tx_nan", "account_id": "a1", "amount": float("nan")},
         {"a1": {"is_active": True, "balance": 1000.0}}, set()),
        ("Inf amount", {"version": "v2", "timestamp": now, "tx_id": "tx_inf", "account_id": "a1", "amount": float("inf")},
         {"a1": {"is_active": True, "balance": 1000.0}}, set()),
        ("-Inf amount", {"version": "v2", "timestamp": now, "tx_id": "tx_ninf", "account_id": "a1", "amount": float("-inf")},
         {"a1": {"is_active": True, "balance": 1000.0}}, set()),
        ("Zero amount", {"version": "v2", "timestamp": now, "tx_id": "tx_zero", "account_id": "a1", "amount": 0.0},
         {"a1": {"is_active": True, "balance": 1000.0}}, set()),
        ("Negative amount", {"version": "v2", "timestamp": now, "tx_id": "tx_neg", "account_id": "a1", "amount": -50.0},
         {"a1": {"is_active": True, "balance": 1000.0}}, set()),
        ("String amount", {"version": "v2", "timestamp": now, "tx_id": "tx_str", "account_id": "a1", "amount": "100.0"},
         {"a1": {"is_active": True, "balance": 1000.0}}, set()),
    ]

    for name, payload, db, processed in cases:
        db_base = copy.deepcopy(db)
        db_simp = copy.deepcopy(db)
        set_base = copy.deepcopy(processed)
        set_simp = copy.deepcopy(processed)

        res_base = baseline.parse_and_validate_transaction(payload, db_base, set_base, now)
        res_simp = simplified.parse_and_validate_transaction(payload, db_simp, set_simp, now)

        assert res_base == res_simp, f"Edge case mismatch on '{name}': {res_base} != {res_simp}"
        assert db_base == db_simp, f"DB state mismatch on '{name}'"
        assert set_base == set_simp, f"Processed set mismatch on '{name}'"

    print(f"✓ Deterministic edge cases passed ({len(cases)} cases).")
    return len(cases)


def run_fuzzed_property_tests(num_iterations: int = 5000) -> Tuple[int, float, float]:
    base_total_time = 0.0
    simp_total_time = 0.0

    for i in range(num_iterations):
        valid = (i % 2 == 0)
        payload, db, processed, now = generate_test_payload(valid=valid)

        db_base = copy.deepcopy(db)
        db_simp = copy.deepcopy(db)
        set_base = copy.deepcopy(processed)
        set_simp = copy.deepcopy(processed)

        t0 = time.perf_counter()
        res_base = baseline.parse_and_validate_transaction(payload, db_base, set_base, now)
        base_total_time += time.perf_counter() - t0

        t0 = time.perf_counter()
        res_simp = simplified.parse_and_validate_transaction(payload, db_simp, set_simp, now)
        simp_total_time += time.perf_counter() - t0

        if res_base != res_simp:
            raise AssertionError(f"Parity failure on iteration {i}:\nBase: {res_base}\nSimp: {res_simp}")
        if db_base != db_simp:
            raise AssertionError(f"Database mutation parity failure on iteration {i}")
        if set_base != set_simp:
            raise AssertionError(f"Set mutation parity failure on iteration {i}")

    print(f"✓ Randomized differential fuzzing passed ({num_iterations} iterations, 100% parity).")
    return num_iterations, base_total_time, simp_total_time


def main() -> int:
    print("=================================================================")
    print(" Running Control Flow Refactoring Parity & Performance Suite")
    print("=================================================================")
    edge_count = run_deterministic_edge_cases()
    fuzz_count, base_t, simp_t = run_fuzzed_property_tests(5000)

    speedup = (base_t / simp_t) if simp_t > 0 else 1.0
    print("-----------------------------------------------------------------")
    print(f"Total test executions : {edge_count + fuzz_count}")
    print(f"Baseline total time   : {base_t * 1000.0:.2f} ms")
    print(f"Simplified total time : {simp_t * 1000.0:.2f} ms")
    print(f"Performance ratio     : {speedup:.2f}x speedup")
    print("Status                : 100% Invariant Parity PASSED")
    print("=================================================================")
    return 0


if __name__ == "__main__":
    main()
