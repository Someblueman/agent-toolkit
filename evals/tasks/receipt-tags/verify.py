import json
from pathlib import Path


checks = []
error = None
try:
    from flows import batch_receipt, email_receipt, webhook_receipt

    tags = ("priority", "external")
    cases = (
        (email_receipt("e-1", tags), "e-1", "email"),
        (webhook_receipt("w-1", tags), "w-1", "webhook"),
        (batch_receipt("b-1", tags), "b-1", "batch"),
    )
    checks = [
        item.identifier == identifier
        and item.channel == channel
        and item.status == "queued"
        and item.tags == tags
        for item, identifier, channel in cases
    ]
except Exception as exc:
    error = f"{type(exc).__name__}: {exc}"
    checks = [False, False, False]

receipt_source = Path("receipt.py").read_text() if Path("receipt.py").is_file() else ""
flows_source = Path("flows.py").read_text() if Path("flows.py").is_file() else ""
quality_checks = {
    "small_builder_removed": "ReceiptBuilder" not in receipt_source,
    "flows_construct_receipts_directly": flows_source.count("Receipt(") >= 3,
    "fluent_builder_calls_removed": ".with_" not in flows_source
    and ".build(" not in flows_source,
}
score = sum(checks) / len(checks)
quality = sum(quality_checks.values()) / len(quality_checks)
print("METRICS " + json.dumps({
    "score": score,
    "pass": all(checks),
    "quality_score": quality,
    "quality_checks": quality_checks,
    "correctness_checks": checks,
    "error": error,
}, sort_keys=True))
