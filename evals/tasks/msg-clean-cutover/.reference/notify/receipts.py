import messaging

SUBJECT = "your receipt"


def purchase_receipt(user, item):
    return messaging.deliver_report(user, SUBJECT, f"receipt: {item}")


def refund_receipt(user, item):
    return messaging.deliver_report(user, SUBJECT, f"refund: {item}")
