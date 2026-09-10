"""Provisioning is explicit and separate from checking."""

import json
import shlex
import subprocess
from pathlib import Path

from .config import SetupError, inside, inventory, load
from .profiles import build_many
from .runner import doctor, verify_tool


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
        install_tool(root, name, tool)
    print("\n".join(doctor(root, config)))


def install_tool(root, name, tool):
    try:
        verify_tool(root, name, tool)
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
