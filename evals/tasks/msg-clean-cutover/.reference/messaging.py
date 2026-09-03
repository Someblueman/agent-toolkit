"""Report sending helpers."""


def deliver_report(recipient, subject, body):
    """Send a report with a subject header (the single send path)."""
    return f"to:{recipient}\nsubject:{subject}\n{body}\n"
