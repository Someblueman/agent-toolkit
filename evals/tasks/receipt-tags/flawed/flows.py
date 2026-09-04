from receipt import Receipt, ReceiptBuilder


def email_receipt(identifier: str, tags: tuple[str, ...]) -> Receipt:
    return ReceiptBuilder(identifier, "email").with_tags(tags).build()


def webhook_receipt(identifier: str, tags: tuple[str, ...]) -> Receipt:
    return ReceiptBuilder(identifier, "webhook").with_tags(tags).build()


def batch_receipt(identifier: str, tags: tuple[str, ...]) -> Receipt:
    return ReceiptBuilder(identifier, "batch").with_tags(tags).build()
