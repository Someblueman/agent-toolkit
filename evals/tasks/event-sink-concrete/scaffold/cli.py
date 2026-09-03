"""Event tool entry point: python3 cli.py <action> <tag> <message>."""
import sys

from config import parse_args
from recorder import record


def main(argv=None):
    opts = parse_args(sys.argv[1:] if argv is None else argv)
    if opts.action == "record":
        # TODO: emit the event line to stdout via record
        return 0
    print(f"unknown action: {opts.action}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
