"""Provisioning is explicit and separate from checking."""

import json
import shlex
import subprocess
import sys
from pathlib import Path

from .config import SetupError, inside, inventory, load
from .profiles import build_many
from .runner import doctor


def configure_native(root, config):
    arguments = [arg for c in config["checks"] for arg in c["args"]]
    if (
        "--config-path=quality.biome.json" in arguments
        and not (root / "quality.biome.json").exists()
    ):
        existing = [
            name for name in ("biome.json", "biome.jsonc") if (root / name).exists()
        ]
        if len(existing) > 1:
            raise SetupError(
                "Both biome.json and biome.jsonc exist; select the canonical config"
            )
        overlay = {
            "linter": {
                "rules": {
                    "complexity": {
                        "noExcessiveCognitiveComplexity": {
                            "level": "error",
                            "options": {"maxAllowedComplexity": 15},
                        }
                    }
                }
            }
        }
        if existing:
            overlay["extends"] = ["./" + existing[0]]
        inside(root, "quality.biome.json").write_text(
            json.dumps(overlay, indent=2) + "\n"
        )
    if "--enable=gocyclo,gocognit" in arguments:
        script = Path(__file__).with_name("native_config.py")
        subprocess.run(
            [
                "uv",
                "run",
                "--no-project",
                "--with",
                "ruamel.yaml==0.18.15",
                "python",
                str(script),
            ],
            cwd=root,
            check=True,
            timeout=120,
        )


def provision(root, profile=None, version=None, roots=None, dry_run=False):
    config_path = inside(root, "quality.json")
    if config_path.exists():
        if profile or version or roots:
            raise SetupError(
                "quality.json already exists; edit it to change the selected toolchain"
            )
        config = load(root)
    elif profile:
        config = build_many(root, profile, version, roots)
    else:
        raise SetupError("Choose --profile for initial setup")
    inventory(root, config)
    print(json.dumps(config, indent=2))
    if dry_run:
        print(
            "Native configuration: merge Go complexity 10/15; Biome overlay cognitive 15 where selected."
        )
        return
    if not config_path.exists():
        config_path.write_text(json.dumps(config, indent=2) + "\n")
    configure_native(root, config)
    inside(root, ".quality").mkdir(exist_ok=True)
    inside(root, ".quality/bin").mkdir(exist_ok=True)
    for name, tool in config["tools"].items():
        install_tool(root, config, name, tool)
    print("\n".join(doctor(root, config)))


def install_tool(root, config, name, tool):
    single = dict(
        config,
        tools={name: tool},
        checks=[c for c in config["checks"] if c["tool"] == name],
    )
    try:
        doctor(root, single)
        print(f"Already provisioned: {name}")
        return
    except SetupError:
        if not tool["install"]:
            raise SetupError(
                f"{name} needs setup; no install recipe configured"
            ) from None
    for args in tool["install"]:
        command = [a.replace("{root}", str(root)) for a in args]
        print("Installing: " + shlex.join(command), flush=True)
        try:
            subprocess.run(command, cwd=root, check=True, timeout=600)
        except (OSError, subprocess.SubprocessError) as exc:
            raise SetupError(f"Install failed for {name}: {exc}") from exc


def install_codex(root, toolkit, dry_run=False):
    destination = inside(root, ".codex")
    path = inside(root, ".codex/hooks.json")
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except ValueError as exc:
            raise SetupError(
                "Existing hooks.json is invalid; leaving it untouched"
            ) from exc
    else:
        data = {"hooks": {}}
    if not isinstance(data, dict) or not isinstance(data.get("hooks"), dict):
        raise SetupError("Existing hooks.json has an unsupported shape")
    command = shlex.join([sys.executable, str(toolkit / "hooks/session/quality.py")])
    for event in ("UserPromptSubmit", "PostToolUse", "Stop"):
        groups = data["hooks"].setdefault(event, [])
        if not isinstance(groups, list):
            raise SetupError(f"Invalid {event} hook list")
        entry = {
            "hooks": [
                {
                    "type": "command",
                    "command": command,
                    "timeout": 300,
                    "statusMessage": "Checking repository quality",
                }
            ]
        }
        if event == "PostToolUse":
            entry["matcher"] = "Bash|apply_patch|Edit|Write"
        if entry not in groups:
            if any("quality.py" in str(g) for g in groups):
                raise SetupError(
                    f"Existing quality adapter differs for {event}; review before replacing"
                )
            groups.append(entry)
    rendered = json.dumps(data, indent=2) + "\n"
    if dry_run:
        print(rendered)
        return
    destination.mkdir(exist_ok=True)
    path.write_text(rendered)
    print(
        f"Installed {path}. Review/trust the hook in Codex; installation does not grant trust."
    )
