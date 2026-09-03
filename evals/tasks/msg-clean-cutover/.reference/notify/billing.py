import messaging

SUBJECT = "billing"


def invoice_summary(account, amount):
    return messaging.deliver_report(account, SUBJECT, f"invoice total {amount}")


def dunning_notice(account, amount):
    return messaging.deliver_report(account, SUBJECT, f"payment overdue {amount}")
