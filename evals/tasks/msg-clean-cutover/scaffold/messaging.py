"""Report sending helpers."""


def send_report(recipient, body):
    """Send a plain report (legacy entry point)."""
    return f"to:{recipient}\n{body}\n"


def deliver_report(recipient, subject, body):
    """Send a report with a subject header (canonical path)."""
    return f"to:{recipient}\nsubject:{subject}\n{body}\n"
