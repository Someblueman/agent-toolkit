import messaging

SUBJECT = "disk-alert"


def disk_alert(host, used_pct):
    return messaging.deliver_report(host, SUBJECT, f"disk usage {used_pct}%")


def cert_alert(host, days):
    return messaging.deliver_report(host, SUBJECT, f"cert expires in {days} days")
