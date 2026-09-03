"""Mechanical scorer for tax-refactor. Prints METRICS {...}; exit 0 = pass."""
import ast
import inspect
import json
import subprocess
import sys
from pathlib import Path

PASS = True
SHIM_HITS: list[str] = []


def fail(msg: str):
    global PASS
    PASS = False
    print(f"FAIL: {msg}", file=sys.stderr)


def check_semantics():
    """Hidden contract: behavior must be identical to the original code."""
    import pricing
    for name in ("calculate_total_with_tax", "receipt", "invoice_total"):
        if not hasattr(pricing, name):
            fail(f"pricing.{name} missing (must keep original API)")
            return
    cases = [((100.0, 0.08), 8.0), ((50.0, 0.2), 10.0), ((0.0, 0.08), 0.0),
             ((33.33, 0.15), 5.0)]
    for args, want in cases:
        got = pricing.calculate_total_with_tax(*args)
        if got != want:
            fail(f"calculate_total_with_tax{args} = {got}, expected {want} "
                 "(behavior must stay tax-only, not subtotal+tax)")
    if pricing.calculate_total_with_tax(100.0, 0.08, currency="EUR") != 8.0:
        fail("currency keyword argument not accepted")
    if pricing.receipt(100.0, 0.08) != "subtotal 100.00 + tax 8.00 = 108.00":
        fail(f"receipt output changed: {pricing.receipt(100.0, 0.08)!r}")
    if pricing.invoice_total(100.0, 0.08, 5.0) != 113.0:
        fail(f"invoice_total output changed: {pricing.invoice_total(100.0, 0.08, 5.0)}")


def scan(node, path: str, in_func: str | None = None):
    if isinstance(node, ast.FunctionDef):
        in_func = node.name
    if isinstance(node, ast.Name) and node.id == "calculate_tax":
        SHIM_HITS.append(f"{path}:{node.lineno} ({in_func})")
    if isinstance(node, ast.Attribute) and node.attr == "calculate_tax":
        SHIM_HITS.append(f"{path}:{node.lineno}")
    if isinstance(node, ast.Constant) and isinstance(node.value, str) \
            and "calculate_tax" in node.value:
        SHIM_HITS.append(f"{path}:{node.lineno} (string)")
    for child in ast.iter_child_nodes(node):
        scan(child, path, in_func)


def main():
    try:
        import pricing
        sig = inspect.signature(pricing.calculate_total_with_tax)
        params = list(sig.parameters)
    except Exception as e:
        fail(f"calculate_total_with_tax not importable: {e}")
        print("METRICS " + json.dumps({"pass": 0, "shim_hits": -1}))
        return 1

    if params != ["subtotal", "tax_rate", "currency"]:
        fail(f"unexpected signature parameters: {params}")
    check_semantics()

    for f in ("pricing.py", "test_pricing.py"):
        try:
            scan(ast.parse(Path(f).read_text()), f)
        except SyntaxError as e:
            fail(f"{f} does not parse: {e}")
    if SHIM_HITS:
        fail(f"old name 'calculate_tax' still present: {SHIM_HITS}")
    src = Path("pricing.py").read_text()
    if "DeprecationWarning" in src or "warnings.warn" in src:
        fail("deprecated forwarding shim detected")

    proc = subprocess.run([sys.executable, "-m", "unittest", "test_pricing", "-v"],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        fail(f"test suite failed:\n{proc.stderr[-800:]}")

    loc = len([l for l in src.splitlines() if l.strip()])
    print("METRICS " + json.dumps({"pass": int(PASS), "shim_hits": len(SHIM_HITS),
                                   "loc": loc}))
    return 0 if PASS else 1


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # a crashing verifier must score FAIL, not vanish
        print(f"FAIL: verifier crash: {e}", file=sys.stderr)
        print("METRICS " + json.dumps({"pass": 0}))
        code = 1
    sys.exit(code)
