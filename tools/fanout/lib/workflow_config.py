"""Resolve model-agnostic recipes and one user roster file without side effects."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[3] / "skills" / "fanout"
NAMES = {"review-plan", "bug-hunt", "critique", "implement"}
HARNESSES = {"agy", "claude", "pi", "opencode", "muse"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate field: {key}")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(), object_pairs_hook=unique)
    except (ValueError, OSError) as error:
        raise ValueError(f"{path}: {error}") from error


def fields(value, required, optional=()):
    if (
        not isinstance(value, dict)
        or not set(required) <= value.keys()
        or value.keys() - set(required) - set(optional)
    ):
        raise ValueError(f"expected fields {list(required)}, optional {list(optional)}")


def text(value, label):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{label} must be a nonempty string")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", value
    ):
        raise ValueError(f"invalid id: {value!r}")
    return value


def validate_settings(harness, settings):
    allowed = (
        {"agent"}
        if harness == "opencode"
        else {"effort"}
        if harness in {"agy", "claude", "pi"}
        else set()
    )
    fields(settings, (), allowed)
    if "agent" in settings:
        text(settings["agent"], "agent")
    if "effort" in settings:
        levels = {"low", "medium", "high"}
        if harness == "claude":
            levels |= {"xhigh", "max"}
        if harness == "pi":
            levels |= {"off", "minimal", "xhigh", "max"}
        if not isinstance(settings["effort"], str) or settings["effort"] not in levels:
            raise ValueError(f"unsupported {harness} effort")


def validate_rosters(config):
    fields(config, ("version", "workflows"))
    if type(config["version"]) is not int or config["version"] != 1:
        raise ValueError("unsupported roster version")
    if not isinstance(config["workflows"], dict) or config["workflows"].keys() - NAMES:
        raise ValueError("unknown workflows")
    for roster in config["workflows"].values():
        fields(roster, ("members",))
        members = roster["members"]
        if not isinstance(members, list) or not 1 <= len(members) <= 50:
            raise ValueError("members must contain 1..50 entries")
        ids = set()
        for member in members:
            fields(member, ("id", "harness", "model"), ("settings", "focus"))
            member_id = identifier(member["id"])
            if member_id in ids:
                raise ValueError(f"duplicate member id: {member_id}")
            ids.add(member_id)
            if (
                not isinstance(member["harness"], str)
                or member["harness"] not in HARNESSES
            ):
                raise ValueError("unsupported harness")
            text(member["model"], "model")
            if "focus" in member:
                text(member["focus"], "focus")
            validate_settings(member["harness"], member.get("settings", {}))


def resolve_recipe(name, config_path=None):
    path = PACKAGE / "workflows" / f"{name}.json"
    recipe = read_json(path)
    fields(recipe, ("version", "role", "timeout_seconds", "prompt", "schema"))
    if recipe["version"] != 1:
        raise ValueError("unsupported workflow version")
    recipe["instructions"] = (path.parent / recipe["prompt"]).read_text()
    recipe["payload_schema"] = read_json(path.parent / recipe["schema"])
    defaults = read_json(PACKAGE / "rosters" / "defaults.json")
    validate_rosters(defaults)
    selected = (
        (
            config_path
            or Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
            / "agent-toolkit"
            / "fanout.json"
        )
        .expanduser()
        .resolve()
    )
    custom = (
        read_json(selected)
        if config_path is not None or selected.exists()
        else {"version": 1, "workflows": {}}
    )
    validate_rosters(custom)
    roster = custom["workflows"].get(name, defaults["workflows"][name])
    return {
        **recipe,
        "name": name,
        "recipe_sha256": digest(recipe),
        "members": roster["members"],
        "config_path": str(selected) if selected.exists() else None,
        "roster_source": str(selected)
        if name in custom["workflows"]
        else str(PACKAGE / "rosters" / "defaults.json"),
        "configuration": custom,
        "config_sha256": digest(custom),
        "roster_sha256": digest(roster),
    }


def validate_payload(value, schema, location="payload"):
    """Validate the object/array/string/enum subset used by package-owned schemas."""
    kind = schema["type"]
    expected = {"object": dict, "array": list, "string": str}[kind]
    if not isinstance(value, expected):
        raise TypeError(f"{location} must be {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{location}: unsupported value")
    if kind == "object":
        fields(value, schema["required"])
        for key, item in value.items():
            validate_payload(item, schema["properties"][key], f"{location}.{key}")
    elif kind == "array":
        if len(value) > schema["maxItems"]:
            raise ValueError(f"{location}: too many items")
        for i, item in enumerate(value):
            validate_payload(item, schema["items"], f"{location}[{i}]")
    elif (
        not schema.get("minLength", 1)
        <= len(value.strip())
        <= schema.get("maxLength", 6000)
    ):
        raise ValueError(f"{location}: invalid string length")


def validate_limits(args, workers, recipe):
    concurrency = args.concurrency if args.concurrency is not None else min(4, workers)
    timeout = (
        args.timeout_seconds
        if "--timeout-seconds" in args.provided
        else recipe["timeout_seconds"]
    )
    if not 1 <= workers <= 50 or not 1 <= concurrency <= workers:
        raise ValueError("workers must be 1..50; concurrency must be 1..workers")
    if not math.isfinite(timeout) or timeout <= 1 or args.max_output_bytes < 1024:
        raise ValueError(
            "timeout must be finite and >1; max-output-bytes must be >=1024"
        )
    return concurrency, timeout
