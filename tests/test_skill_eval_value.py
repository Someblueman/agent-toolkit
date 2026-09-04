from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import skill_eval_telemetry as telemetry
import skill_eval_report as reporting
import skill_eval as evaluation
import skill_eval_contract as contract
import skill_eval_runners as runners
import skill_eval_validation as validation


def record(
    *, task: str = "task-a", runner: str = "codex", runtime: str = "runtime",
    arm: str = "without", pair: str = "pair-0", score: float = 1.0,
    quality: float = 0.5, valid: bool = True,
) -> dict:
    return {
        "schema_version": 2, "batch": "batch", "purpose": "confirmatory",
        "skill": "pragmatic-engineering", "skill_fingerprint": "skill-hash",
        "task": task, "task_fingerprint": f"hash-{task}", "runner": runner,
        "model": "model", "runtime_fingerprint": runtime, "arm": arm,
        "pair_id": pair, "valid": valid, "score": score,
        "quality_score": quality, "pass": score >= 0.9,
        "ceiling_threshold": 0.95, "quality_effect": 0.10,
        "efficiency_effect": 0.15, "instability_threshold": 0.25,
        "duration_s": 10.0 if arm == "without" else 7.0,
        "total_tokens": 1000 if arm == "without" else 700,
        "cached_input_tokens": 500 if arm == "without" else 300,
        "cost_usd": 1.0 if arm == "without" else 0.7,
        "tool_calls": 10 if arm == "without" else 7,
        "agent_steps": 4 if arm == "without" else 3,
        "files_changed": 2, "lines_added": 20, "lines_deleted": 2,
        "final_loc": 40, "budget_exhausted": False,
    }


class TelemetryTests(unittest.TestCase):
    def test_native_trace_counts_are_runner_specific(self) -> None:
        codex = "\n".join([
            json.dumps({
                "type": "item.completed",
                "item": {"type": "command_execution"},
            }),
            json.dumps({
                "type": "item.completed", "item": {"type": "file_change"},
            }),
            json.dumps({
                "type": "item.completed", "item": {"type": "agent_message"},
            }),
        ])
        omp = "\n".join([
            json.dumps({"type": "turn_start"}),
            json.dumps({"type": "tool_execution_start"}),
            json.dumps({"type": "tool_execution_end"}),
        ])

        self.assertEqual(
            telemetry.trace_metrics("codex", codex),
            {"tool_calls": 2, "agent_steps": 1},
        )
        self.assertEqual(
            telemetry.trace_metrics("omp", omp),
            {"tool_calls": 1, "agent_steps": 1},
        )

    def test_workspace_metrics_measure_patch_and_ignore_caches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, after = root / "before", root / "after"
            before.mkdir()
            after.mkdir()
            (before / "main.py").write_text("first\nsecond\n")
            (after / "main.py").write_text("first\nchanged\nthird\n")
            (after / "new.sh").write_text("#!/bin/sh\ntrue\n")
            cache = after / "__pycache__"
            cache.mkdir()
            (cache / "main.pyc").write_bytes(b"ignored")

            metrics = telemetry.workspace_metrics(before, after)

        self.assertEqual(metrics["changed_files"], ["main.py", "new.sh"])
        self.assertEqual(metrics["files_changed"], 2)
        self.assertEqual(metrics["lines_added"], 4)
        self.assertEqual(metrics["lines_deleted"], 1)
        self.assertEqual(metrics["final_loc"], 5)

    def test_agent_footprint_is_captured_before_verifier_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "evals" / "tasks" / "task-a"
            skill = root / "skills" / "pragmatic-engineering"
            (task / "scaffold").mkdir(parents=True)
            (task / "flawed").mkdir()
            (task / "reference").mkdir()
            skill.mkdir(parents=True)
            (task / "task.md").write_text("Make the change.\n")
            (task / "verify.py").write_text("grader\n")
            (task / "scaffold" / "base.py").write_text("base = 1\n")
            (skill / "SKILL.md").write_text("# Pragmatic\n")
            task_spec = contract.TaskSpec(
                id="task-a", family="local-change", source="test fixture",
                pristine_max=0.2, correctness_min=1.0,
                flawed_quality_max=0.5, reference_quality_min=1.0,
            )
            suite = contract.SuiteSpec(
                series="native-v2", skill="pragmatic-engineering",
                calibration_basis="test fixture", screen_samples=2, samples=2,
                concurrency=1, timeout_seconds=60, ceiling_threshold=0.95,
                quality_effect=0.1, efficiency_effect=0.15,
                instability_threshold=0.25,
                runners={"codex": contract.RunnerSpec("model", "medium")},
                tasks=(task_spec,), source_path=root / "suite.toml",
            )
            holder = {}

            def build_command(_runner, run_dir, *_args):
                holder["run_dir"] = run_dir
                return [str(run_dir)]

            def run_agent(command, *_args):
                (Path(command[0]) / "agent.py").write_text("changed = 1\n")
                return runners.RunnerResult(True, 0, False, 1.0, "", "")

            def verify(run_dir, _verifier):
                (run_dir / "verifier.tmp").write_text("not agent work\n")
                return {
                    "scored": True, "score": 1.0, "quality_score": 1.0,
                    "pass": True, "metrics": {"quality_checks": {"ok": True}},
                    "stderr": "",
                }

            prepared = runners.PreparedRunner(
                env={}, env_contract={}, skill_path=root / "absent",
                command_args=(),
            )
            runtime = runners.RuntimeObservation(
                None, (), False, True, None, 1, 1, 0, 2, None, True,
            )
            with mock.patch.object(evaluation, "prepare_runner", return_value=prepared), \
                    mock.patch.object(evaluation, "build_command", side_effect=build_command), \
                    mock.patch.object(evaluation, "run_agent", side_effect=run_agent), \
                    mock.patch.object(evaluation, "verify_workspace", side_effect=verify), \
                    mock.patch.object(evaluation, "inspect_runtime", return_value=runtime), \
                    mock.patch.object(evaluation, "runtime_fingerprint", return_value="runtime"), \
                    mock.patch.object(evaluation, "task_fingerprint", return_value="task"), \
                    mock.patch.object(evaluation, "skill_fingerprint", return_value="skill"):
                result = evaluation.one_run(
                    batch="batch", suite=suite, task=task_spec, runner="codex",
                    arm="without", sample=1, pair_id="pair", timeout=60,
                    concurrency=1, purpose="validation", version="test",
                    repo_root=root, results_root=root / "results",
                )

        self.assertIn("agent.py", result["changed_files"])
        self.assertNotIn("verifier.tmp", result["changed_files"])


class CalibrationTests(unittest.TestCase):
    def test_frozen_prompts_do_not_name_the_quality_decision(self) -> None:
        forbidden = {
            "receipt-tags": ("builder", "direct constructor"),
            "single-memory-store": ("protocol", "factory"),
            "upload-options": ("builder", "direct constructor"),
        }
        for task, terms in forbidden.items():
            prompt = (ROOT / "evals" / "tasks" / task / "task.md").read_text().lower()
            for term in terms:
                self.assertNotIn(term, prompt, f"{task} leaks {term}")

    def test_variants_are_complete_workspaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "evals" / "tasks" / "clean-replacement"
            for variant in ("scaffold", "flawed", "reference"):
                (task_dir / variant).mkdir(parents=True)
            (task_dir / "scaffold" / "obsolete.txt").write_text("old\n")
            (task_dir / "flawed" / "obsolete.txt").write_text("old\n")
            (task_dir / "flawed" / "result.txt").write_text("done\n")
            (task_dir / "reference" / "result.txt").write_text("done\n")
            (task_dir / "verify.py").write_text(
                "import json\n"
                "from pathlib import Path\n"
                "done = Path('result.txt').exists()\n"
                "clean = not Path('obsolete.txt').exists()\n"
                "print('METRICS ' + json.dumps({\n"
                "    'score': float(done), 'pass': done,\n"
                "    'quality_score': float(done and clean),\n"
                "    'quality_checks': {'obsolete_removed': clean},\n"
                "}))\n"
            )
            task = contract.TaskSpec(
                id="clean-replacement", family="local-change",
                source="test fixture", pristine_max=0.0,
                correctness_min=1.0, flawed_quality_max=0.0,
                reference_quality_min=1.0,
            )

            observed = validation.validate_task(task, root)

        self.assertEqual(observed["pristine"], {
            "score": 0.0, "quality_score": 0.0,
        })
        self.assertEqual(observed["flawed"], {
            "score": 1.0, "quality_score": 0.0,
        })
        self.assertEqual(observed["reference"], {
            "score": 1.0, "quality_score": 1.0,
        })


class ValueReportTests(unittest.TestCase):
    def test_screening_labels_saturated_informative_and_unstable(self) -> None:
        rows = []
        for task, samples in {
            "ceiling": ((1.0, 1.0), (1.0, 1.0)),
            "useful": ((1.0, 0.4), (1.0, 0.5)),
            "noisy": ((1.0, 0.2), (1.0, 0.8)),
        }.items():
            for index, (score, quality) in enumerate(samples):
                row = record(task=task, pair=f"pair-{index}", score=score,
                             quality=quality)
                row["purpose"] = "screen"
                rows.append(row)

        statuses = {
            row["task"]: row["status"]
            for row in reporting.summarize_screening(rows)
        }
        self.assertEqual(statuses, {
            "ceiling": "saturated", "useful": "informative", "noisy": "unstable",
        })

    def test_quality_value_and_efficiency_are_separate(self) -> None:
        rows = []
        for index in range(2):
            rows.extend([
                record(pair=f"pair-{index}", quality=0.4),
                record(pair=f"pair-{index}", arm="with", quality=0.8),
            ])

        summary = reporting.summarize_records(rows)[0]
        task = summary["task_rows"][0]
        self.assertEqual(summary["verdict"], "helpful-on-this-suite")
        self.assertEqual(task["value"], "helpful")
        self.assertEqual(task["efficiency_label"], "more-efficient")
        self.assertAlmostEqual(task["quality_delta"], 0.4)

    def test_screen_gate_requires_three_cross_harness_informative_tasks(self) -> None:
        rows = [
            {"task": f"task-{index}", "runner": runner,
             "status": "informative" if index == 0 else "saturated"}
            for index in range(6) for runner in ("codex", "omp")
        ]
        self.assertEqual(reporting.screening_gate(rows), {
            "status": "blocked-candidate-cap-exhausted",
            "eligible": ["task-0"], "screened": 6,
        })

    def test_cache_volume_does_not_determine_efficiency_direction(self) -> None:
        without = record()
        with_skill = record(arm="with", quality=0.5)
        for field in (
            "duration_s", "total_tokens", "cost_usd", "tool_calls", "agent_steps",
        ):
            with_skill[field] = without[field]
        with_skill["cached_input_tokens"] = without["cached_input_tokens"] * 2

        task = reporting.summarize_records([without, with_skill])[0]["task_rows"][0]
        self.assertEqual(task["efficiency_label"], "similar")

    def test_screen_to_confirmation_baseline_shift_is_unstable(self) -> None:
        screen = [record(pair=f"screen-{index}", quality=0.0) for index in range(2)]
        for row in screen:
            row["purpose"] = "screen"
        confirm = []
        for index in range(2):
            confirm.extend([
                record(pair=f"pair-{index}", quality=1.0),
                record(pair=f"pair-{index}", arm="with", quality=1.0),
            ])

        task = reporting.summarize_records(screen + confirm)[0]["task_rows"][0]

        self.assertEqual(task["value"], "unstable")
        self.assertEqual(task["baseline_spread"], 1.0)

    def test_invalid_run_blocks_and_runtime_fingerprints_do_not_pool(self) -> None:
        rows = [
            record(), record(arm="with", quality=0.8),
            record(runner="omp", runtime="other"),
            record(runner="omp", runtime="other", arm="with", quality=0.8),
            record(valid=False, pair="broken"),
        ]

        summaries = reporting.summarize_records(rows)
        self.assertEqual(len(summaries), 2)
        codex = next(row for row in summaries if row["runner"] == "codex")
        omp = next(row for row in summaries if row["runner"] == "omp")
        self.assertEqual(codex["verdict"], "blocked")
        self.assertEqual(omp["verdict"], "helpful-on-this-suite")


if __name__ == "__main__":
    unittest.main()
