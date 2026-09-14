"""One bounded mixed-harness workflow round with inspectable inputs and outcomes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import signal
import time
from pathlib import Path

from harnesses import dispatch_worker, resolve_dependencies
from structured_worker import (
    capture_worker_errors,
    extract_cost,
    extract_tokens,
    write_private,
)
from workflow_config import (
    digest,
    resolve_recipe,
    validate_limits,
    validate_payload,
)
from workflow_ownership import audit_assignment, resolve_assignments, snapshot


def input_files(paths):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def prepare(args):
    forbidden = args.provided & {
        "--harness",
        "--model",
        "--workers",
        "--agent",
        "--min-results",
        "--agy-retries",
    }
    if forbidden:
        raise ValueError(f"workflow roster owns these options: {sorted(forbidden)}")
    if "--max-output-bytes" not in args.provided:
        args.max_output_bytes = 8_000_000
    recipe = resolve_recipe(args.workflow, args.config)
    prompt_path = args.prompt_file.expanduser().resolve()
    prompt = prompt_path.read_text()
    directory = args.working_directory.expanduser().resolve()
    if not directory.is_dir():
        raise ValueError("working directory does not exist")
    inputs = [prompt_path, *(p.expanduser().resolve() for p in args.input)]
    assignments = []
    if args.workflow == "implement":
        if args.assignments is None:
            raise ValueError("--assignments is required for implement")
        assignments = resolve_assignments(
            args.assignments.expanduser().resolve(), recipe["members"]
        )
    elif args.assignments is not None:
        raise ValueError("--assignments is only valid for implement")
    targets = assignments or [
        {
            "id": m["id"],
            "member": m["id"],
            "route": m,
            "working_directory": str(directory),
        }
        for m in recipe["members"]
    ]
    concurrency, timeout = validate_limits(args, len(targets), recipe)
    output = args.output.expanduser().resolve() if args.output else None
    if output:
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError("output must be an empty directory or absent")
        if any(
            output == Path(t["working_directory"])
            or output.is_relative_to(Path(t["working_directory"]))
            for t in targets
        ):
            raise ValueError("workflow output must be outside worker checkouts")
    dependencies = resolve_dependencies(args, [t["route"] for t in targets])
    return recipe, prompt, inputs, targets, concurrency, timeout, output, dependencies


def worker_prompt(recipe, prompt, target):
    assignment = {k: v for k, v in target.items() if k not in {"before", "route"}}
    return (
        f"{recipe['instructions']}\n\nUser task and supplied context:\n{prompt}\n\n"
        f"Assignment: {json.dumps(assignment)}\nOptional focus: {target['route'].get('focus', 'Full workflow scope')}\n\n"
        "For a completed outcome, payload must be an object matching this schema. "
        "For blocked/failed, explain why in summary and use {} for payload.\n"
        + json.dumps(recipe["payload_schema"])
    )


def observed_models(worker, harness, output):
    """Read model identities only where the native protocol actually supplies them."""
    attempt = worker["attempts"][-1]
    if "stdout_path" not in attempt:
        return None
    try:
        data = (output / attempt["stdout_path"]).read_bytes()
        if harness == "claude":
            models = json.loads(data).get("modelUsage", {})
            return sorted(models) or None
        if harness == "pi":
            messages = [
                e.get("message", {})
                for e in map(json.loads, data.splitlines())
                if e.get("type") == "message_end"
            ]
            return (
                sorted(
                    {
                        f"{m['provider']}/{m['model']}"
                        for m in messages
                        if m.get("provider") and m.get("model")
                    }
                )
                or None
            )
        if harness == "opencode":
            return json.loads(data).get("observed_models")
    except (ValueError, OSError, TypeError, KeyError, AttributeError):
        pass
    return None


async def execute_target(
    index, target, recipe, prompt, semaphore, dependencies, output, timeout, max_output
):
    worker_id = f"worker-{index:04d}"
    common = {
        "index": index,
        "semaphore": semaphore,
        "base_prompt": worker_prompt(recipe, prompt, target),
        "working_directory": Path(target["working_directory"]),
        "output": output,
        "timeout_seconds": timeout,
        "max_output_bytes": max_output,
    }
    worker = await capture_worker_errors(
        worker_id,
        dispatch_worker(
            target["route"],
            common,
            dependencies,
            payload_schema=recipe["payload_schema"],
        ),
    )
    worker.update(
        {
            "member_id": target["member"],
            "assignment_id": target["id"],
            "role": recipe["role"],
            "harness": target["route"]["harness"],
            "requested_model": target["route"]["model"],
            "settings": target["route"].get("settings", {}),
            "working_directory": target["working_directory"],
            "assignment_sha256": digest(
                {k: v for k, v in target.items() if k != "before"}
            ),
        }
    )
    worker["observed_models"] = observed_models(worker, worker["harness"], output)
    if worker["harness"] == "agy" and worker["status"] != "ok":
        attempt = worker["attempts"][-1]
        try:
            native = json.loads((output / attempt["stdout_path"]).read_bytes())
            if isinstance(native, dict) and isinstance(native.get("error"), str):
                attempt["native_error"] = native["error"]
        except (ValueError, OSError, KeyError):
            pass

    if worker["status"] == "ok":
        try:
            validate_payload(worker["result"]["payload"], recipe["payload_schema"])
            if recipe["name"] == "implement":
                payload = worker["result"]["payload"]
                checks = {c["command"]: c for c in payload["checks"]}
                if payload["blockers"] or any(
                    checks.get(command, {}).get("status") != "passed"
                    for command in target["acceptance"]
                ):
                    raise ValueError(
                        "assigned acceptance checks did not all pass or blockers remain"
                    )
        except (ValueError, TypeError) as error:
            worker["status"] = "invalid_result"
            worker["validation_error"] = str(error)
    if recipe["name"] == "implement":
        try:
            worker["ownership"] = await asyncio.to_thread(audit_assignment, target)
            if not worker["ownership"]["conforming"]:
                worker["status"] = "nonconforming"
        except (ValueError, OSError) as error:
            worker["status"] = "nonconforming"
            worker["ownership"] = {"conforming": False, "error": str(error)}
    return worker


async def run_workflow(args):
    (
        recipe,
        prompt,
        inputs,
        targets,
        concurrency,
        timeout,
        output,
        dependencies,
    ) = await asyncio.to_thread(prepare, args)
    description = {
        "schema_version": 4,
        "workflow": recipe["name"],
        "recipe_sha256": recipe["recipe_sha256"],
        "config_path": recipe["config_path"],
        "roster_source": recipe["roster_source"],
        "config_sha256": recipe["config_sha256"],
        "configuration": recipe["configuration"],
        "roster_sha256": recipe["roster_sha256"],
        "roster": recipe["members"],
        "assignments": [
            {k: v for k, v in t.items() if k not in {"before", "route"}}
            for t in targets
        ],
        "requested_workers": len(targets),
        "concurrency": concurrency,
        "timeout_seconds": timeout,
        "max_output_bytes": args.max_output_bytes,
        "completion_rule": "all_assigned_workers",
        "inputs": await asyncio.to_thread(input_files, inputs),
    }
    if args.describe:
        print(json.dumps(description, indent=2, sort_keys=True))
        return 0
    assert output is not None
    review_before = None
    if recipe["name"] != "implement":
        review_before = await asyncio.to_thread(
            snapshot, targets[0]["working_directory"]
        )
    source_identity = review_before or {t["id"]: t["before"] for t in targets}
    description["source_identity_sha256"] = digest(source_identity)
    description["source_manifest_path"] = "inputs.json"
    output.mkdir(parents=True, mode=0o700, exist_ok=True)
    output.chmod(0o700)
    write_private(
        output / "resolved.json", (json.dumps(description, indent=2) + "\n").encode()
    )
    write_private(
        output / "inputs.json",
        (
            json.dumps(
                review_before or {t["id"]: t["before"] for t in targets}, indent=2
            )
            + "\n"
        ).encode(),
    )
    started = time.monotonic()
    semaphore = asyncio.Semaphore(concurrency)
    loop, task = asyncio.get_running_loop(), asyncio.current_task()
    loop.add_signal_handler(signal.SIGTERM, task.cancel)
    try:
        workers = await asyncio.gather(
            *(
                execute_target(
                    i,
                    t,
                    recipe,
                    prompt,
                    semaphore,
                    dependencies,
                    output,
                    timeout,
                    args.max_output_bytes,
                )
                for i, t in enumerate(targets, 1)
            )
        )
    finally:
        loop.remove_signal_handler(signal.SIGTERM)
    input_change = None
    try:
        if await asyncio.to_thread(input_files, inputs) != description["inputs"]:
            input_change = "supplied input files changed during the round"
        if (
            review_before is not None
            and await asyncio.to_thread(snapshot, targets[0]["working_directory"])
            != review_before
        ):
            input_change = "review workspace changed during the round"
    except (ValueError, OSError) as error:
        input_change = f"input verification failed: {error}"
    valid = sum(w["status"] == "ok" for w in workers)
    complete = valid == len(targets) and input_change is None
    usage = [a.get("usage") for w in workers for a in w["attempts"]]
    tokens = [extract_tokens(u) for u in usage]
    costs = [extract_cost(u) for u in usage]
    packet = {
        "total_tokens": sum(t for t in tokens if t is not None)
        if any(t is not None for t in tokens)
        else None,
        "total_cost_usd": sum(c for c in costs if c is not None)
        if any(c is not None for c in costs)
        else None,
        "usage_complete": all(t is not None for t in tokens)
        and all(c is not None for c in costs),
        **description,
        "status": "completed" if complete else "incomplete",
        "valid_results": valid,
        "missing_assignments": [
            w["assignment_id"] for w in workers if w["status"] != "ok"
        ],
        "input_change": input_change,
        "workers": workers,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "scope": "assigned_work_delivered; integration_and_verification_pending"
        if recipe["name"] == "implement"
        else "feedback_delivered; caller_verification_pending",
    }
    temporary = output / "packet.json.tmp"
    write_private(
        temporary, (json.dumps(packet, indent=2, sort_keys=True) + "\n").encode()
    )
    temporary.replace(output / "packet.json")
    print(
        json.dumps(
            {
                "status": packet["status"],
                "valid_results": valid,
                "requested_workers": len(targets),
                "packet_path": str(output / "packet.json"),
            }
        )
    )
    return 0 if complete else 1
