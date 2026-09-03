import messaging

SUBJECT = "disk-alert"


def disk_alert(host, used_pct):
    return messaging.send_report(host, f"disk usage {used_pct}%")


def cert_alert(host, days):
    return messaging.send_report(host, f"cert expires in {days} days")
