"""Event recorder: append one timestamped event line to a stream."""
from datetime import datetime, timezone


def record(tag, message, out):
    """Write one line 'YYYY-MM-DDTHH:MM:SS tag message' to out."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    out.write(f"{ts} {tag} {message}\n")
