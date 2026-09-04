from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import skill_eval as evaluation
import skill_eval_report as reporting
import skill_eval_runners as runners
import skill_eval_validation as validation


class RepoFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.task_dir = root / "evals" / "tasks" / "quote-paths"
        self.skill_dir = root / "skills" / "shell-engineering"
        self.suite_path = root / "evals" / "suites" / "shell-native-v2.toml"

        (self.task_dir / "scaffold").mkdir(parents=True)
        (self.task_dir / "reference").mkdir()
        (self.task_dir / "flawed").mkdir()
        self.skill_dir.mkdir(parents=True)
        self.suite_path.parent.mkdir(parents=True)
        (root / "scripts").mkdir()

        (self.task_dir / "task.md").write_text("Fix the path handling.\n")
        (self.task_dir / "verify.py").write_text("print('METRICS {}')\n")
        (self.task_dir / "grader_support.py").write_text("fixture = 1\n")
        (self.task_dir / "scaffold" / "run.sh").write_text("broken\n")
        (self.task_dir / "reference" / "run.sh").write_text("fixed\n")
        (self.task_dir / "flawed" / "run.sh").write_text("partial\n")
        (self.skill_dir / "SKILL.md").write_text("# Shell skill\n")
        (self.skill_dir / "references").mkdir()
        (self.skill_dir / "references" / "quoting.md").write_text("Quote values.\n")
        (root / "scripts" / "skill_eval.py").write_text("executor = 1\n")
        (root / "scripts" / "skill_eval_contract.py").write_text("contract = 1\n")
        (root / "scripts" / "skill_eval_runners.py").write_text("runners = 1\n")
        (root / "scripts" / "skill_eval_telemetry.py").write_text("telemetry = 1\n")
        (root / "scripts" / "skill_eval_validation.py").write_text("validation = 1\n")
        (root / "scripts" / "skill_eval_report.py").write_text("report = 1\n")
        self.suite_path.write_text(textwrap.dedent("""\
            series = "native-v2"
            skill = "shell-engineering"
            calibration_basis = "prior shell pilot"
            screen_samples = 2
            samples = 2
            concurrency = 1
            timeout_seconds = 60
            ceiling_threshold = 0.95
            quality_effect = 0.10
            efficiency_effect = 0.15
            instability_threshold = 0.25

            [runners.codex]
            model = "gpt-test"
            thinking = "medium"

            [runners.omp]
            model = "omp-test"
            thinking = "medium"

            [[tasks]]
            id = "quote-paths"
            family = "argument-boundaries"
            source = "scripts/install.sh SC2294"
            pristine_max = 0.30
            correctness_min = 0.95
            flawed_quality_max = 0.50
            reference_quality_min = 0.95
        """))


class SuiteAndFingerprintTests(unittest.TestCase):
    def test_task_skill_and_runtime_identities_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RepoFixture(Path(tmp))
            suite = evaluation.load_suite(fixture.suite_path, fixture.root)
            task = suite.tasks[0]

            task_before = evaluation.task_fingerprint(task, fixture.root)
            skill_before = evaluation.skill_fingerprint(suite.skill, fixture.root)
            runtime_before = evaluation.runtime_fingerprint(
                "codex", "codex 1.0", suite, 60, 1, fixture.root
            )

            (fixture.skill_dir / "references" / "quoting.md").write_text("Changed.\n")
            self.assertEqual(task_before, evaluation.task_fingerprint(task, fixture.root))
            self.assertNotEqual(
                skill_before, evaluation.skill_fingerprint(suite.skill, fixture.root)
            )

            (fixture.task_dir / "grader_support.py").write_text("fixture = 2\n")
            self.assertNotEqual(
                task_before, evaluation.task_fingerprint(task, fixture.root)
            )

            (fixture.root / "scripts" / "skill_eval_report.py").write_text("report = 2\n")
            self.assertEqual(
                runtime_before,
                evaluation.runtime_fingerprint(
                    "codex", "codex 1.0", suite, 60, 1, fixture.root
                ),
            )
            self.assertNotEqual(
                runtime_before,
                evaluation.runtime_fingerprint(
                    "codex", "codex 2.0", suite, 60, 1, fixture.root
                ),
            )

            fixture.suite_path.write_text(
                fixture.suite_path.read_text().replace(
                    "quality_effect = 0.10", "quality_effect = 0.20"
                )
            )
            changed_suite = evaluation.load_suite(fixture.suite_path, fixture.root)
            self.assertNotEqual(
                runtime_before,
                evaluation.runtime_fingerprint(
                    "codex", "codex 1.0", changed_suite, 60, 1, fixture.root
                ),
            )

    def test_suite_rejects_unknown_task_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RepoFixture(Path(tmp))
            with fixture.suite_path.open("a") as stream:
                stream.write("unknown = true\n")
            with self.assertRaisesRegex(ValueError, "unknown task field"):
                evaluation.load_suite(fixture.suite_path, fixture.root)


class NativeRunnerTests(unittest.TestCase):
    def test_complete_skill_is_materialized_only_in_with_arm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = RepoFixture(root / "repo")
            user_home = root / "user"
            (user_home / ".codex").mkdir(parents=True)
            (user_home / ".codex" / "auth.json").write_text("{}\n")
            (user_home / ".omp" / "agent").mkdir(parents=True)
            (user_home / ".omp" / "agent" / "config.yml").write_text("model: test\n")

            for runner in ("codex", "omp"):
                with_context = runners.prepare_runner(
                    runner, root / f"{runner}-with", "with",
                    fixture.skill_dir, "shell-engineering", user_home
                )
                without_context = runners.prepare_runner(
                    runner, root / f"{runner}-without", "without",
                    fixture.skill_dir, "shell-engineering", user_home
                )
                self.assertTrue((with_context.skill_path / "SKILL.md").is_file())
                self.assertTrue(
                    (with_context.skill_path / "references" / "quoting.md").is_file()
                )
                self.assertFalse(without_context.skill_path.exists())
                self.assertEqual(
                    with_context.env_contract, without_context.env_contract
                )
                self.assertEqual(
                    with_context.command_args[:1], without_context.command_args[:1]
                )
                if runner == "omp":
                    self.assertEqual(
                        Path(with_context.command_args[1]).read_text(),
                        Path(without_context.command_args[1]).read_text(),
                    )
                self.assertTrue(evaluation.package_matches(
                    fixture.skill_dir, with_context.skill_path
                ))

    def test_commands_enable_native_skills_and_structured_output(self) -> None:
        run_dir = Path("/work")
        codex = runners.build_command(
            "codex", run_dir, 60, "gpt-test", "medium", ()
        )
        omp = runners.build_command(
            "omp", run_dir, 60, "omp-test", "medium",
            ("--config", "/run/eval-config.yml"),
        )
        self.assertIn("--json", codex)
        self.assertNotIn("--no-skills", codex)
        self.assertEqual(omp[omp.index("--mode") + 1], "json")
        self.assertNotIn("--no-skills", omp)
        self.assertEqual(
            omp[omp.index("--config") + 1], "/run/eval-config.yml"
        )

    def test_omp_profile_disables_model_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = RepoFixture(root / "repo")
            user_home = root / "user"
            source_agent = user_home / ".omp" / "agent"
            source_agent.mkdir(parents=True)
            (source_agent / "config.yml").write_text(
                "retry:\n  modelFallback: true\n"
            )
            prepared = runners.prepare_runner(
                "omp", root / "run", "with", fixture.skill_dir,
                "shell-engineering", user_home,
            )

            overlay = Path(prepared.command_args[1])
            self.assertEqual(prepared.command_args[0], "--config")
            self.assertEqual(
                overlay.read_text(),
                "retry:\n  modelFallback: false\n  usageAwareFallback: false\n",
            )

    def test_omp_runtime_trace_rejects_model_fallback(self) -> None:
        trace = "\n".join([
            json.dumps({
                "type": "message_end",
                "message": {"role": "assistant", "provider": "openai-codex",
                            "model": "gpt-5.6-sol", "stopReason": "error",
                            "errorMessage": "usage limit has been reached"},
            }),
            json.dumps({
                "type": "retry_fallback_applied",
                "from": "openai-codex/gpt-5.6-sol:medium",
                "to": "opencode-go/glm-5.3-flash:high",
            }),
            json.dumps({
                "type": "message_end",
                "message": {"role": "assistant", "provider": "opencode-go",
                            "model": "glm-5.3-flash", "stopReason": "stop"},
            }),
        ])

        observation = runners.inspect_runtime(
            "omp", trace, "openai-codex/gpt-5.6-sol"
        )
        self.assertFalse(observation.identity_ok)
        self.assertTrue(observation.fallback_applied)
        self.assertEqual(observation.actual_model, "opencode-go/glm-5.3-flash")
        self.assertEqual(
            observation.observed_models,
            ("openai-codex/gpt-5.6-sol", "opencode-go/glm-5.3-flash"),
        )
        self.assertIsNone(observation.provider_error)
        self.assertIsNone(observation.total_tokens)
        self.assertFalse(observation.task_started)

    def test_omp_terminal_provider_error_is_structured(self) -> None:
        trace = json.dumps({
            "type": "message_end",
            "message": {"role": "assistant", "provider": "openai-codex",
                        "model": "gpt-5.6-sol", "stopReason": "error",
                        "errorMessage": "usage limit has been reached"},
        })
        observation = runners.inspect_runtime(
            "omp", trace, "openai-codex/gpt-5.6-sol"
        )
        self.assertTrue(observation.identity_ok)
        self.assertEqual(
            observation.provider_error, "usage limit has been reached"
        )

    def test_codex_runtime_extracts_terminal_usage_and_failure(self) -> None:
        completed = json.dumps({
            "type": "turn.completed",
            "usage": {"input_tokens": 100, "cached_input_tokens": 60,
                      "output_tokens": 20},
        })
        observation = runners.inspect_runtime("codex", completed, "gpt-test")
        self.assertTrue(observation.identity_ok)
        self.assertIsNone(observation.provider_error)
        self.assertEqual(observation.total_tokens, 120)
        self.assertEqual(observation.cached_input_tokens, 60)

        failed = json.dumps({
            "type": "turn.failed", "error": {"message": "model unavailable"},
        })
        observation = runners.inspect_runtime("codex", failed, "gpt-test")
        self.assertTrue(observation.identity_ok)
        self.assertEqual(observation.provider_error, "model unavailable")

        started = runners.inspect_runtime(
            "codex", json.dumps({"type": "turn.started"}), "gpt-test"
        )
        self.assertTrue(started.identity_ok)
        self.assertTrue(started.task_started)

    def test_codex_activation_requires_a_successful_structured_read(self) -> None:
        event = {
            "type": "item.completed",
            "item": {"type": "command_execution", "status": "completed",
                     "exit_code": 0,
                     "command": "sed -n 1,200p /tmp/skills/shell-engineering/SKILL.md"},
        }
        self.assertTrue(runners.detect_activation(
            "codex", json.dumps(event), "shell-engineering"
        ))
        self.assertEqual(
            runners.detect_activation("omp", "{}", "shell-engineering"), "unknown"
        )


class OutcomeClassificationTests(unittest.TestCase):
    def test_failure_boundaries(self) -> None:
        cases = [
            ({"started": False, "exit_code": None, "budget_exhausted": False,
              "verifier_scored": False, "isolation_ok": True,
              "runtime_identity_ok": True, "provider_error": None,
              "stderr": "missing"},
             (False, "infrastructure")),
            ({"started": True, "exit_code": 1, "budget_exhausted": False,
              "verifier_scored": True, "isolation_ok": True,
              "runtime_identity_ok": True, "provider_error": None,
              "stderr": "backend returned 404"}, (False, "infrastructure")),
            ({"started": True, "exit_code": 0, "budget_exhausted": False,
              "verifier_scored": True, "isolation_ok": True,
              "runtime_identity_ok": True,
              "provider_error": "usage limit has been reached", "stderr": ""},
             (False, "infrastructure")),
            ({"started": True, "exit_code": 0, "budget_exhausted": False,
              "verifier_scored": False, "isolation_ok": True,
              "runtime_identity_ok": True, "provider_error": None, "stderr": ""},
             (False, "evaluator")),
            ({"started": True, "exit_code": 0, "budget_exhausted": False,
              "verifier_scored": True, "isolation_ok": False,
              "runtime_identity_ok": True, "provider_error": None, "stderr": ""},
             (False, "isolation")),
            ({"started": True, "exit_code": 0, "budget_exhausted": False,
              "verifier_scored": True, "isolation_ok": True,
              "runtime_identity_ok": False, "provider_error": None, "stderr": ""},
             (False, "infrastructure")),
            ({"started": True, "exit_code": -9, "budget_exhausted": True,
              "verifier_scored": True, "isolation_ok": True,
              "runtime_identity_ok": True, "provider_error": None, "stderr": ""},
             (True, None)),
            ({"started": True, "exit_code": 1, "budget_exhausted": False,
              "verifier_scored": True, "isolation_ok": True,
              "runtime_identity_ok": True, "provider_error": None,
              "stderr": "agent stopped"},
             (True, None)),
        ]
        for inputs, expected in cases:
            with self.subTest(inputs=inputs):
                result = validation.classify_run(**inputs)
                self.assertEqual((result.valid, result.invalid_class), expected)


class AnalysisAndOrchestrationTests(unittest.TestCase):
    def test_validation_pairs_do_not_enter_effect_estimates(self) -> None:
        records = []
        for arm in ("with", "without"):
            records.append({
                "purpose": "validation", "valid": True,
                "skill": "shell-engineering", "task": "task-a",
                "runner": "codex", "model": "gpt-test",
                "runtime_fingerprint": "runtime", "arm": arm, "score": 1.0,
                "pass": 1, "batch": "batch", "pair_id": "pair",
            })
        self.assertEqual(reporting.summarize_records(records), [])

    def test_sanitized_history_omits_raw_provider_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp)
            artifact = results / "batch" / "stderr.log"
            sanitized = evaluation._sanitized_record({
                "provider_error": "secret backend detail",
                "artifacts": {"stderr": str(artifact)},
            }, results)
            self.assertNotIn("provider_error", sanitized)
            self.assertEqual(
                sanitized["artifacts"]["stderr"], "batch/stderr.log"
            )

    def test_report_exposes_all_fingerprint_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp)
            batch_dir = history / "batch"
            batch_dir.mkdir()
            manifest = {
                "schema_version": 2, "batch": "batch", "purpose": "validation",
                "skill": "shell-engineering", "tasks": [{"id": "task-a"}],
                "samples_per_arm": 1, "runners": {"codex": {}},
                "fingerprints": {
                    "skill": "skill-hash", "tasks": {"task-a": "task-hash"},
                    "runtimes": {"codex": "runtime-hash"},
                },
            }
            (batch_dir / "manifest.json").write_text(json.dumps(manifest))
            record = {
                "schema_version": 2, "batch": "batch", "valid": False,
                "invalid_class": "infrastructure", "invalid_reason": "offline",
                "purpose": "validation",
            }
            (batch_dir / "runs.jsonl").write_text(json.dumps(record) + "\n")

            report = reporting.build_report(("batch",), history)
            self.assertIn("`batch` skill: `skill-hash`", report)
            self.assertIn("task `task-a`: `task-hash`", report)
            self.assertIn("runtime `codex`: `runtime-hash`", report)

    def test_completed_batch_returns_both_arms_for_each_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = RepoFixture(Path(tmp))
            suite = evaluation.load_suite(fixture.suite_path, fixture.root)

            def fake_one_run(**kwargs):
                return {
                    "task": kwargs["task"].id, "runner": kwargs["runner"],
                    "arm": kwargs["arm"], "sample": kwargs["sample"],
                    "pair_id": kwargs["pair_id"], "valid": True, "score": 1.0,
                }

            with mock.patch.object(evaluation, "one_run", side_effect=fake_one_run), \
                    mock.patch.object(evaluation, "runner_version", return_value="test"):
                records = evaluation.run_batch(
                    suite=suite, tasks=suite.tasks, runners=("codex",),
                    samples=2, concurrency=1, batch="batch", timeout=60,
                    repo_root=fixture.root,
                    results_root=fixture.root / "evals" / "results",
                )

            self.assertEqual(len(records), 4)
            pairs: dict[str, set[str]] = {}
            for record in records:
                pairs.setdefault(record["pair_id"], set()).add(record["arm"])
            self.assertEqual(list(pairs.values()), [{"with", "without"}] * 2)


if __name__ == "__main__":
    unittest.main()
