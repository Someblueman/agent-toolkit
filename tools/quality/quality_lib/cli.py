"""Command-line interface."""

import argparse
import subprocess
from pathlib import Path

from . import work_review
from .codex_hooks import install_codex, plan_codex, uninstall_global
from .config import SetupError, SnapshotChanged, find_root, load
from .profiles import PINS
from .runner import check, doctor
from .setup import provision


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
    setup.add_argument(
        "--codex",
        action="store_true",
        help="Opt this repository into local lifecycle hooks",
    )
    sub.add_parser(
        "doctor", help="Check tools, versions and source coverage without installing"
    )
    checks = sub.add_parser(
        "check", help="Run configured native checks without installing"
    )
    checks.add_argument("--fast", action="store_true")
    review = sub.add_parser(
        "review", help="Run a visible scoped review before completion"
    )
    review.add_argument("--session", help="Owning task ID; defaults to CODEX_THREAD_ID")
    review.add_argument(
        "--accept",
        metavar="ASSESSMENT",
        help="Record assessment of a current completed review",
    )
    review.add_argument(
        "--same-scope",
        action="store_true",
        help="With --accept, confirm later messages did not change review requirements",
    )
    install = sub.add_parser(
        "install-codex", help="Merge project-local Codex hooks; preserve other hooks"
    )
    install.add_argument("--dry-run", action="store_true")
    uninstall = sub.add_parser(
        "uninstall-codex", help="Remove former global quality registration"
    )
    uninstall.add_argument("--global", action="store_true", required=True)
    uninstall.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        toolkit = Path(__file__).resolve().parents[3]
        if args.command == "setup":
            if args.codex:
                plan_codex(root, toolkit)  # Detect hook conflicts before provisioning.
            provision(root, args.profile, args.version, args.source, args.dry_run)
            if args.codex:
                install_codex(root, toolkit, args.dry_run)
        elif args.command == "install-codex":
            root = find_root(root, require_config=False)
            install_codex(root, toolkit, args.dry_run)
        elif args.command == "uninstall-codex":
            uninstall_global(toolkit, args.dry_run)
        else:
            return configured_command(args, root)
        return 0
    except SnapshotChanged as exc:
        print(f"SNAPSHOT CHANGED: {exc}")
        return 2
    except (SetupError, OSError, subprocess.SubprocessError) as exc:
        print(f"SETUP REQUIRED: {exc}")
        return 2


def configured_command(args, root):
    root = find_root(root)
    config = load(root)
    if args.command == "doctor":
        print("\n".join(doctor(root, config)))
        return 0
    if args.command == "check":
        code, output = check(root, config, "fast" if args.fast else "full")
        print(output)
        return code
    return work_review.review(root, config, args.session, args.accept, args.same_scope)
