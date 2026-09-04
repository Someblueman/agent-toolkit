from receipt import Receipt


def email_receipt(identifier: str, tags: tuple[str, ...]) -> Receipt:
    return Receipt(identifier, "email", "queued", tags)


def webhook_receipt(identifier: str, tags: tuple[str, ...]) -> Receipt:
    return Receipt(identifier, "webhook", "queued", tags)


def batch_receipt(identifier: str, tags: tuple[str, ...]) -> Receipt:
    return Receipt(identifier, "batch", "queued", tags)
