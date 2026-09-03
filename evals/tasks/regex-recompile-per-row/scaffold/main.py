"""Audit-log normalizer.

Reads audit rows on stdin (one per line), extracts the structured fields of
each row, and writes one normalized row per input row on stdout.
"""
import re
import sys


def rolling_hash(text):
    """Order-sensitive content digest used for tamper detection."""
    h = 0x811C9DC5
    for tok in text.split(" "):
        for ch in tok:
            h ^= ord(ch)
            h = (h * 0x01000193) & 0xFFFFFFFF
            h ^= h >> 7
            h = (h * 0x85EBCA6B) & 0xFFFFFFFF
            h ^= h >> 3
            h = (h * 0x27220A95) & 0xFFFFFFFF
            h ^= h >> 11
            h ^= h >> 3
        h = (h + 0x9E3779B9) & 0xFFFFFFFF
    return h


def extract_fields(row):
    # Each row carries its own span id; the field scan for that row is
    # anchored on the row's span value.
    i = row.index("span=")
    span = row[i + 5 : i + 13]
    pat = re.compile(
        rf"^lvl=(?P<lvl>[a-z]+) svc=(?P<svc>[a-z-]+) trace=[0-9a-f]{{32}} span={span}"
        rf" seq=(?P<seq>\d+) dev=(?P<dev>d-\d+) msg=\"(?P<msg>[^\"]*)\"$"
    )
    m = pat.match(row)
    if m is None:
        return None
    return m


def normalize(row):
    m = extract_fields(row)
    if m is None:
        return None
    digest = rolling_hash(m.group("msg"))
    return "{}|{}|{}|{}|{:08x}".format(
        m.group("seq"), m.group("lvl"), m.group("svc"), m.group("dev"), digest
    )


def main():
    out = []
    for row in sys.stdin.buffer.read().decode().splitlines():
        line = normalize(row)
        if line is not None:
            out.append(line)
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


if __name__ == "__main__":
    main()
