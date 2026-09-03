"""Mechanical scorer for msg-clean-cutover.

Run with cwd = agent workspace. Prints METRICS {...} as last stdout line;
exit 0 = pass.
"""

import ast
import json
import sys
from pathlib import Path

EXPECTED = {
    ("alerts", "disk_alert", ("web-1", 91)): "to:web-1\nsubject:disk-alert\ndisk usage 91%\n",
    ("alerts", "cert_alert", ("db-1", 14)): "to:db-1\nsubject:disk-alert\ncert expires in 14 days\n",
    ("receipts", "purchase_receipt", ("amy", "keyboard")): "to:amy\nsubject:your receipt\nreceipt: keyboard\n",
    ("receipts", "refund_receipt", ("amy", "keyboard")): "to:amy\nsubject:your receipt\nrefund: keyboard\n",
    ("billing", "invoice_summary", ("acme", 420)): "to:acme\nsubject:billing\ninvoice total 420\n",
    ("billing", "dunning_notice", ("acme", 420)): "to:acme\nsubject:billing\npayment overdue 420\n",
}

BANNED_TOKENS = ("send_report", "DeprecationWarning", "deprecated", "legacy", "warnings")

WHITELIST = {"messaging.py", "notify/alerts.py", "notify/receipts.py", "notify/billing.py"}


def source_files():
    ws = Path.cwd()
    files = {}
    for rel in WHITELIST:
        p = ws / rel
        if not p.exists():
            files[rel] = None
        else:
            files[rel] = p.read_text()
    return files


def parse(tree_or_src):
    return ast.parse(tree_or_src)


def check_behavior():
    sys.path.insert(0, str(Path.cwd()))
    from notify import alerts, billing, receipts

    mods = {"alerts": alerts, "billing": billing, "receipts": receipts}
    for (mod, fn, args), expected in EXPECTED.items():
        got = getattr(mods[mod], fn)(*args)
        if got != expected:
            return False, f"{mod}.{fn}{args}: got {got!r}, want {expected!r}"
    return True, ""


def check_single_path(files):
    """Exactly one public send function (deliver_report); no forwarders."""
    msg_src = files["messaging.py"]
    if msg_src is None:
        return False, "messaging.py missing"
    tree = ast.parse(msg_src)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    public = [f for f in funcs if not f.name.startswith("_")]
    if [f.name for f in public] != ["deliver_report"]:
        return False, f"messaging.py public functions: {[f.name for f in public]}"
    # No other function in messaging.py may call deliver_report (forwarder ban).
    for f in funcs:
        if f.name == "deliver_report":
            continue
        for node in ast.walk(f):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "deliver_report":
                return False, f"forwarding function in messaging.py: {f.name}"
    return True, ""


def check_callers(files):
    """All 6 notify call sites must call the canonical path directly."""
    callers = 0
    for rel in ("notify/alerts.py", "notify/receipts.py", "notify/billing.py"):
        src = files[rel]
        if src is None:
            return 0, f"{rel} missing"
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "deliver_report":
                callers += 1
    return callers, ""


def check_banned(files):
    hits = []
    for rel, src in files.items():
        if src is None:
            continue
        for tok in BANNED_TOKENS:
            if tok in src:
                hits.append(f"{rel}:{tok}")
    return hits


def main():
    metrics = {"pass": 0}
    try:
        files = source_files()
        behavior_ok, why = check_behavior()
        metrics["behavior"] = int(behavior_ok)
        if not behavior_ok:
            print(f"FAIL: {why}")
            print("METRICS " + json.dumps(metrics))
            return 1
        single_ok, why = check_single_path(files)
        metrics["single_path"] = int(single_ok)
        if not single_ok:
            print(f"FAIL: {why}")
            print("METRICS " + json.dumps(metrics))
            return 1
        callers, why = check_callers(files)
        metrics["canonical_callers"] = callers
        if callers < 6:
            print(f"FAIL: only {callers} direct canonical callers, need 6. {why}")
            print("METRICS " + json.dumps(metrics))
            return 1
        hits = check_banned(files)
        metrics["banned_tokens"] = len(hits)
        if hits:
            print("FAIL: banned tokens present: " + ", ".join(hits))
            print("METRICS " + json.dumps(metrics))
            return 1
        for rel, src in files.items():
            if src is not None and len(src.splitlines()) >= 500:
                print(f"FAIL: {rel} exceeds 500 LOC")
                print("METRICS " + json.dumps(metrics))
                return 1
        metrics["pass"] = 1
        print("METRICS " + json.dumps(metrics))
        return 0
    except Exception as exc:  # noqa: BLE001 - verifier must always print METRICS
        print(f"FAIL: {exc}")
        print("METRICS " + json.dumps(metrics))
        return 1


if __name__ == "__main__":
    sys.exit(main())
