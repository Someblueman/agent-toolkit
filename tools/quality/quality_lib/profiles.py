"""Explicit starter recipes. Native project configurations remain authoritative."""

import json
import re
import shutil
import subprocess
import sys

from .config import SetupError

PINS = {
    "python": "0.16.6",
    "biome": "2.5.12",
    "eslint": "10.10.0",
    "rust": "1.97.1",
    "go": "2.4.0",
    "c-cpp": "22.1.8",
    "haskell": "3.8",
    "shell": "0.11.0",
}
PATTERNS = {
    "python": ["*.py", "*.pyi"],
    "biome": ["*.js", "*.jsx", "*.ts", "*.tsx"],
    "eslint": ["*.js", "*.jsx", "*.ts", "*.tsx", "*.mjs", "*.cjs"],
    "rust": ["*.rs"],
    "go": ["*.go"],
    "c-cpp": ["*.c", "*.cpp", "*.cc", "*.cxx", "*.h", "*.hpp"],
    "haskell": ["*.hs", "*.lhs"],
    "shell": ["*.sh", "*.bash"],
}


def build_many(root, profiles, version=None, roots=None):
    if len(set(profiles)) != len(profiles):
        raise SetupError("Duplicate profiles")
    if "biome" in profiles and "eslint" in profiles:
        raise SetupError("Choose the existing JS linter, not both Biome and ESLint")
    if version and len(profiles) != 1:
        raise SetupError(
            "--version requires a single profile; edit tool pins in quality.json otherwise"
        )
    result = None
    for name in profiles:
        config = build(root, name, version, roots)
        native = config["tools"].pop("native")
        config["tools"][name] = native
        for check in config["checks"]:
            check["tool"] = name
        if result is None:
            result = config
        else:
            result["tools"].update(config["tools"])
            result["checks"].extend(config["checks"])
    return result


def reuse_hlint(native):
    existing = shutil.which("hlint")
    if existing:
        result = subprocess.run(
            [existing, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0 and re.search(
            r"\bv" + re.escape(native["version"]) + r"(?:\s|,|$)", result.stdout
        ):
            native["command"] = [existing]
            native["install"] = []
    return native


def tool(command, version, install, version_args=None):
    return {
        "command": command,
        "version": version,
        "install": install,
        "version_args": version_args or ["--version"],
    }


def spec(name, args, patterns, files=True, stage="fast", tool_name="native"):
    return {
        "name": name,
        "tool": tool_name,
        "args": args,
        "patterns": list(patterns),
        "files": files,
        "failure_codes": [1, 101] if name in ("Clippy", "rustfmt") else [1],
        "stage": stage,
    }


def pip_tool(name, package, version, package_version=None):
    destination = "{root}/.quality/" + name
    install = [
        ["uv", "venv", destination],
        [
            "uv",
            "pip",
            "install",
            "--python",
            destination + "/bin/python",
            package + "==" + (package_version or version),
        ],
    ]
    return tool([destination + "/bin/" + name], version, install)


def javascript(root, name, version):
    package = "@biomejs/biome" if name == "biome" else "eslint"
    managers = [
        ("pnpm-lock.yaml", ["pnpm", "add", "--save-dev", "--save-exact"]),
        ("yarn.lock", ["yarn", "add", "--dev", "--exact"]),
        ("bun.lock", ["bun", "add", "--dev", "--exact"]),
        ("package-lock.json", ["npm", "install", "--save-dev", "--save-exact"]),
    ]
    found = [args for lock, args in managers if (root / lock).exists()]
    if len(found) > 1:
        raise SetupError(
            "Multiple JS lockfiles: select the installer in quality.json explicitly"
        )
    manager = found[0] if found else ["npm", "install", "--save-dev", "--save-exact"]
    return tool(
        ["{root}/node_modules/.bin/" + name],
        version,
        [manager + [package + "@" + version]],
    )


def build(root, profile, version=None, roots=None):
    version = version or PINS[profile]
    patterns = PATTERNS[profile]
    checks = []
    if profile == "python":
        native = pip_tool("ruff", "ruff", version)
        checks = [
            spec(
                "Ruff lint + C901",
                [
                    "check",
                    "--no-fix",
                    "--extend-select",
                    "C901",
                    "--config",
                    "lint.mccabe.max-complexity=10",
                ],
                patterns,
            ),
            spec("Ruff format", ["format", "--check"], patterns),
        ]
    elif profile in ("biome", "eslint"):
        native = javascript(root, profile, version)
        args = (
            ["check", "--config-path=quality.biome.json"]
            if profile == "biome"
            else ["--rule", 'complexity:["error",10]']
        )
        checks = [spec(profile, args, patterns)]
        if profile == "biome":
            checks.append(
                spec(
                    "Biome cognitive complexity",
                    [
                        "lint",
                        "--config-path=quality.biome.json",
                        "--only",
                        "complexity/noExcessiveCognitiveComplexity",
                    ],
                    patterns,
                )
            )
    elif profile == "shell":
        if version != "0.11.0":
            raise SetupError(
                "Shell starter pins shellcheck-py 0.11.0.1; customize quality.json for other versions"
            )
        native = pip_tool("shellcheck", "shellcheck-py", version, "0.11.0.1")
        checks = [spec("ShellCheck", ["--severity=style"], patterns)]
    elif profile == "c-cpp":
        native = pip_tool("clang-tidy", "clang-tidy", version)
        options = {
            "InheritParentConfig": True,
            "CheckOptions": {"readability-function-cognitive-complexity.Threshold": 15},
        }
        checks = [
            spec(
                "clang-tidy",
                [
                    "-p",
                    "build",
                    "--checks=readability-function-cognitive-complexity",
                    "--warnings-as-errors=*",
                    "--config=" + json.dumps(options),
                ],
                patterns,
            )
        ]
    elif profile == "rust":
        native = tool(
            ["rustup", "run", version, "cargo"],
            version,
            [
                [
                    "rustup",
                    "toolchain",
                    "install",
                    version,
                    "--profile",
                    "minimal",
                    "--component",
                    "clippy,rustfmt",
                ]
            ],
        )
        checks = [
            spec("rustfmt", ["fmt", "--all", "--", "--check"], patterns, False),
            spec(
                "Clippy",
                [
                    "clippy",
                    "--workspace",
                    "--all-targets",
                    "--locked",
                    "--offline",
                    "--",
                    "-D",
                    "warnings",
                ],
                patterns,
                False,
                "full",
            ),
        ]
    elif profile == "go":
        native = tool(
            ["{root}/.quality/bin/golangci-lint"],
            version,
            [
                [
                    sys.executable,
                    "-c",
                    (
                        "import os,subprocess,sys; "
                        "subprocess.run(sys.argv[1:],check=True,env=dict(os.environ,GOBIN=os.path.abspath('.quality/bin')))"
                    ),
                    "go",
                    "install",
                    "github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v"
                    + version,
                ]
            ],
            ["version"],
        )
        checks = [
            spec(
                "golangci-lint",
                ["run", "--enable=gocyclo,gocognit", "./..."],
                patterns,
                False,
                "full",
            )
        ]
    else:
        native = tool(
            ["{root}/.quality/bin/hlint"],
            version,
            [
                [
                    "cabal",
                    "install",
                    "hlint-" + version,
                    "--install-method=copy",
                    "--installdir={root}/.quality/bin",
                    "--overwrite-policy=always",
                ]
            ],
        )
        checks = [spec("HLint", [], patterns)]
        native = reuse_hlint(native)
    return {
        "version": 1,
        "roots": roots or ["."],
        "exclude": [
            ".git/*",
            ".quality/*",
            "node_modules/*",
            "*/node_modules/*",
            ".venv/*",
            "target/*",
            "build/*",
            "__pycache__/*",
            "*/__pycache__/*",
        ],
        "tools": {"native": native},
        "checks": checks,
        "size": {"limit": 500, "mode": "review"},
    }
