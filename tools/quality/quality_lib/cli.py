"""Command-line interface."""

import argparse
import subprocess
from pathlib import Path

from .config import SetupError, find_root, load
from .profiles import PINS
from .runner import check, doctor
from .setup import install_codex, provision


def main():
    parser = argparse.ArgumentParser(
        description="Provision and run local repository quality checks"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser(
        "setup", help="Provision explicitly selected tools (may use network)"
    )
    setup.add_argument("--profile", choices=PINS, action="append")
    setup.add_argument("--version")
    setup.add_argument("--source", action="append")
    setup.add_argument("--dry-run", action="store_true")
    sub.add_parser(
        "doctor", help="Check tools, versions and source coverage without installing"
    )
    checks = sub.add_parser(
        "check", help="Run configured native checks without installing"
    )
    checks.add_argument("--fast", action="store_true")
    install = sub.add_parser(
        "install-codex", help="Merge project-local Codex hooks; preserve other hooks"
    )
    install.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.command == "setup":
            provision(root, args.profile, args.version, args.source, args.dry_run)
        else:
            root = find_root(root)
            config = load(root)
            if args.command == "doctor":
                print("\n".join(doctor(root, config)))
            elif args.command == "check":
                code, output = check(root, config, "fast" if args.fast else "full")
                print(output)
                return code
            else:
                install_codex(root, Path(__file__).resolve().parents[3], args.dry_run)
        return 0
    except (SetupError, OSError, subprocess.SubprocessError) as exc:
        print(f"SETUP REQUIRED: {exc}")
        return 2
