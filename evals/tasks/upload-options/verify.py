import json
from pathlib import Path


checks = []
error = None
try:
    from paths import avatar_upload, document_upload, export_upload

    cases = (
        (document_upload("doc", b"d", "text/plain"), "text/plain", False),
        (avatar_upload("avatar", b"a", "image/webp"), "image/webp", True),
        (export_upload("data", b"e", "text/csv"), "text/csv", False),
    )
    checks = [
        item.name == name
        and item.content == content
        and item.content_type == content_type
        and item.private == private
        for item, name, content, content_type, private in (
            (cases[0][0], "doc", b"d", cases[0][1], cases[0][2]),
            (cases[1][0], "avatar", b"a", cases[1][1], cases[1][2]),
            (cases[2][0], "data", b"e", cases[2][1], cases[2][2]),
        )
    ]
except Exception as exc:
    error = f"{type(exc).__name__}: {exc}"
    checks = [False, False, False]

upload_source = Path("upload.py").read_text() if Path("upload.py").is_file() else ""
paths_source = Path("paths.py").read_text() if Path("paths.py").is_file() else ""
quality_checks = {
    "small_builder_removed": "UploadBuilder" not in upload_source,
    "paths_construct_uploads_directly": paths_source.count("Upload(") >= 3,
    "fluent_builder_calls_removed": ".content_type(" not in paths_source
    and ".private(" not in paths_source and ".build(" not in paths_source,
}
score = sum(checks) / len(checks)
quality = sum(quality_checks.values()) / len(quality_checks)
print("METRICS " + json.dumps({
    "score": score, "pass": all(checks), "quality_score": quality,
    "quality_checks": quality_checks, "correctness_checks": checks,
    "error": error,
}, sort_keys=True))
