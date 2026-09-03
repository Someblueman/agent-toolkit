import messaging

SUBJECT = "billing"


def invoice_summary(account, amount):
    return messaging.send_report(account, f"invoice total {amount}")


def dunning_notice(account, amount):
    return messaging.send_report(account, f"payment overdue {amount}")
