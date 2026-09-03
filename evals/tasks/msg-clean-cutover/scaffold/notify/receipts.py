import messaging

SUBJECT = "your receipt"


def purchase_receipt(user, item):
    return messaging.send_report(user, f"receipt: {item}")


def refund_receipt(user, item):
    return messaging.send_report(user, f"refund: {item}")
