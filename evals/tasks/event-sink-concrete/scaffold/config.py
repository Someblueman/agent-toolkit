"""CLI option parsing for the event tool."""
from dataclasses import dataclass


@dataclass
class CliOpts:
    action: str
    tag: str
    message: str


def parse_args(argv):
    """Parse [action, tag, message] into CliOpts.

    Raises SystemExit with a usage message when the argument count is wrong.
    """
    if len(argv) != 3:
        raise SystemExit("usage: python3 cli.py <action> <tag> <message>")
    return CliOpts(argv[0], argv[1], argv[2])
