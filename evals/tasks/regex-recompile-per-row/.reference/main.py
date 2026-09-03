"""Audit-log normalizer (reference).

Same stdin -> stdout contract as the original pipeline. Profiling the
original shows the dominant cost is building and compiling a fresh regex
pattern for every row (sre parse/compile of a runtime-unique pattern), not
the digest loop. The fix keeps the observable behavior identical: compile
the constant pattern once at module scope and match the variable span
value as a captured group, then assert it equals the row's own span id —
a literal in the pattern and an equality check on the captured group are
equivalent here, so stdout is byte-identical.
"""
import re
import sys

FIELDS_RE = re.compile(
    r"^lvl=(?P<lvl>[a-z]+) svc=(?P<svc>[a-z-]+) trace=[0-9a-f]{32}"
    r" span=(?P<span>[0-9a-f]{8}) seq=(?P<seq>\d+) dev=(?P<dev>d-\d+)"
    r" msg=\"(?P<msg>[^\"]*)\"$"
)


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
    m = FIELDS_RE.match(row)
    if m is None or m.group("span") != span:
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
