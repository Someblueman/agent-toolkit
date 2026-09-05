"""Setup-only native Go rule merge; preserve unrelated settings and YAML comments."""

import json
import sys
from pathlib import Path


def main():
    from ruamel.yaml import YAML

    root = Path.cwd()
    existing = [
        p
        for p in (
            root / ".golangci.yml",
            root / ".golangci.yaml",
            root / ".golangci.json",
        )
        if p.exists()
    ]
    if len(existing) > 1:
        raise ValueError("Multiple golangci configurations; choose one before setup")
    if (root / ".golangci.toml").exists():
        raise ValueError(
            "Use a YAML/JSON golangci config before generating the quality overlay"
        )
    yaml = YAML()
    config = yaml.load(existing[0].read_text()) if existing else {"version": "2"}
    if not isinstance(config, dict) or str(config.get("version")) != "2":
        raise ValueError("A golangci-lint v2 configuration is required")
    linters = config.setdefault("linters", {})
    enabled = linters.setdefault("enable", [])
    disabled = linters.get("disable", [])
    for name, limit in (("gocyclo", 10), ("gocognit", 15)):
        if name in disabled:
            disabled.remove(name)
        if name not in enabled:
            enabled.append(name)
        linters.setdefault("settings", {}).setdefault(name, {})["min-complexity"] = (
            limit
        )
    destination = existing[0] if existing else root / ".golangci.yml"
    if destination.is_symlink():
        raise ValueError("Refusing a symlinked golangci config")
    if destination.suffix == ".json":
        destination.write_text(json.dumps(config, indent=2) + "\n")
    else:
        with destination.open("w") as stream:
            yaml.dump(config, stream)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
