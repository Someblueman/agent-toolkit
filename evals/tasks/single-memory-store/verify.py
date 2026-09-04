import json
from pathlib import Path


checks = []
error = None
try:
    from service import save_event
    from storage import MemoryStore

    payload = {"id": 7, "total": 42}
    store = save_event("invoice.created", payload)
    checks = [
        isinstance(store, MemoryStore),
        store.items == {"invoice.created": payload},
        save_event("user.deleted", {"id": 3}).items
        == {"user.deleted": {"id": 3}},
    ]
except Exception as exc:
    error = f"{type(exc).__name__}: {exc}"
    checks = [False, False, False]

storage = Path("storage.py").read_text() if Path("storage.py").is_file() else ""
service = Path("service.py").read_text() if Path("service.py").is_file() else ""
quality_checks = {
    "single_use_protocol_removed": "Protocol" not in storage
    and "class Store" not in storage,
    "factory_removed": "StoreFactory" not in storage and "StoreFactory" not in service,
    "concrete_store_used_directly": "MemoryStore()" in service
    and "-> MemoryStore" in service,
}
score = sum(checks) / len(checks)
quality = sum(quality_checks.values()) / len(quality_checks)
print("METRICS " + json.dumps({
    "score": score, "pass": all(checks), "quality_score": quality,
    "quality_checks": quality_checks, "correctness_checks": checks,
    "error": error,
}, sort_keys=True))
