"""Regression cases for the skill audit's demonstrated false-success paths."""

import importlib.util
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def load(skill, filename):
    path = SKILLS / skill / "scripts" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def command(source):
    return shlex.join([sys.executable, "-c", source])


class SkillHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parity = load("hardware-aware-optimization", "differential_test_runner.py")
        cls.invariant = load("code-simplification", "invariant_regression_checker.py")
        cls.stats = load(
            "profiling-software-performance", "run_benchmark_with_stats.py"
        )
        cls.comparator = load("hardware-aware-optimization", "benchmark_comparator.py")
        cls.ghc = load("profiling-software-performance", "analyze_ghc_prof.py")

    def cli(self, module, *args):
        return subprocess.run(
            [sys.executable, module.__file__, *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )

    def test_parity_numeric_contract(self):
        for left, right in [
            ("0", "999"),
            ("0", "0.000001"),
            ("1", "nan"),
            ("inf", "1"),
            ("9007199254740992", "9007199254740993"),
        ]:
            for tolerance in [0, 1e-5]:
                with self.subTest(left=left, right=right, tolerance=tolerance):
                    self.assertFalse(
                        self.parity.compare_outputs(left, right, tolerance)[0]
                    )
        self.assertTrue(self.parity.compare_outputs("1.000001", "1.000002", 1e-4)[0])
        self.assertFalse(self.parity.compare_outputs("1.0 ", "1.0")[0])
        for tolerance in [-1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                self.parity.compare_outputs("1", "1", tolerance)

    def test_parity_cli_requires_successful_cases(self):
        for source, iterations in [
            ("print(999)", "1"),
            ("print(0)", "0"),
            ("raise SystemExit(1)", "1"),
        ]:
            result = self.cli(
                self.parity,
                "--baseline",
                command("print(0)"),
                "--optimized",
                command(source),
                "--iterations",
                iterations,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
        result = self.cli(
            self.parity,
            "--baseline",
            command("raise SystemExit(1)"),
            "--optimized",
            command("raise SystemExit(1)"),
            "--iterations",
            "1",
        )
        self.assertNotEqual(result.returncode, 0)
        result = self.cli(
            self.parity,
            "--baseline",
            command("print(0)"),
            "--optimized",
            command("print(0)"),
            "--iterations",
            "1",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invariant_types_and_mutations(self):
        for left, right in [(True, 1), (2**53, 2**53 + 1), ({True: 1}, {1: 1})]:
            self.assertFalse(self.invariant.deep_compare(left, right)[0])
        data = []

        def baseline(value):
            value.append(1)
            return value

        report = self.invariant.run_differential_python_functions(
            baseline, lambda value: value, [((data,), {})]
        )
        self.assertEqual(report.failed_tests, 1)
        self.assertEqual(data, [])
        report = self.invariant.run_differential_python_functions(
            baseline, baseline, [((data,), {})]
        )
        self.assertEqual(report.passed_tests, 1)

    def test_invariant_empty_corpus_and_literal_cli(self):
        with self.assertRaises(ValueError):
            self.invariant.run_differential_python_functions(lambda: 1, lambda: 1, [])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            golden = path / "golden.json"
            golden.write_text('{"test_cases": []}')
            with self.assertRaises(ValueError):
                self.invariant.verify_golden_master(lambda x: x, golden)
            marker = path / "injected"
            payload = f"'; touch {marker}; echo '"
            cmd = command("import sys; print(sys.argv[1])")
            report = self.invariant.run_differential_cli(cmd, cmd, [payload])
            self.assertEqual(report.passed_tests, 1)
            self.assertIn(payload, report.results[0].baseline_output[1])
            self.assertFalse(marker.exists())
            golden.write_text(
                json.dumps(
                    {
                        "test_cases": [
                            {"id": "error", "input": 1, "expected": "ValueError: bad"}
                        ]
                    }
                )
            )

            def raises(_):
                raise ValueError("bad")

            self.assertEqual(
                self.invariant.verify_golden_master(raises, golden).failed_tests, 1
            )

    def test_invariant_cli_does_not_invent_cases(self):
        result = self.cli(
            self.invariant,
            "--baseline",
            command("print(1)"),
            "--candidate",
            command("print(1)"),
        )
        self.assertEqual(result.returncode, 2)

    def test_unsupported_complexity_input_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "example.c"
            path.write_text("int main(void) { return 0; }")
            script = (
                SKILLS / "code-simplification/scripts/complexity_budget_analyzer.py"
            )
            result = subprocess.run(
                [sys.executable, str(script), str(path), "--json", "--no-fail"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)

    def test_stats_reject_insufficient_evidence_and_keep_raw(self):
        for values in [[], [123.0], [1.0, float("nan")]]:
            with self.assertRaises(ValueError):
                self.stats.compute_statistics(values)
        samples = [0.000123456789, 0.000223456789, 0.000323456789]
        stats = self.stats.compute_statistics(samples)
        self.assertEqual(stats["raw_samples_ms"], samples)
        self.assertIn("bootstrap", stats["ci_method"])
        self.assertNotIn("STABLE", stats["noise_status"])
        result = self.cli(
            self.stats, "--iterations", "1", "--", sys.executable, "-c", "pass"
        )
        self.assertEqual(result.returncode, 2)

    def test_bootstrap_uses_even_sample_median(self):
        with patch("random.Random.choice", side_effect=[1, 9, 1, 1] * 2):
            self.assertEqual(
                self.comparator.bootstrap_speedup_ci([1, 9], [1, 1], iterations=2),
                (5, 5),
            )

    def test_comparator_alternates_real_processes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            log = path / "order.txt"
            report = path / "report.json"

            def cmd(label):
                return command(
                    f'from pathlib import Path; p=Path({str(log)!r}); p.open("a").write({label!r})'
                )

            result = self.cli(
                self.comparator,
                "--baseline",
                cmd("B"),
                "--optimized",
                cmd("O"),
                "--runs",
                "2",
                "--warmups",
                "0",
                "--json-output",
                str(report),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text(), "BOOB")
            self.assertEqual(
                len(json.loads(report.read_text())["baseline_samples_ms"]), 2
            )

    def test_ghc_requires_recognized_observations(self):
        with self.assertRaises(ValueError):
            self.ghc.parse_ghc_prof("not a GHC profile")
        profile = """Time and Allocation Profiling Report
 total time  = 1.42 secs (1420 ticks @ 1000 us, 1 cores)
 total alloc = 1,024 bytes (excludes profiling overheads)
COST CENTRE MODULE SRC %time %alloc
work Main Main.hs:1:1 70.0 50.0
"""
        parsed = self.ghc.parse_ghc_prof(profile)
        self.assertEqual(parsed["metadata"]["total_alloc_bytes"], 1024)
        self.assertEqual(parsed["top_summary"][0]["cost_centre"], "work")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "invalid.prof"
            path.write_text("not a GHC profile")
            self.assertEqual(self.cli(self.ghc, str(path)).returncode, 2)

    def test_flamegraph_stdin_and_punctuation(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output.svg"
            frame = "worker's<&\\\""
            result = subprocess.run(
                [
                    "bash",
                    str(
                        SKILLS
                        / "profiling-software-performance/scripts/generate_flamegraph.sh"
                    ),
                    "--title",
                    "A&B <report>",
                    "-",
                    str(output),
                ],
                check=False,
                input=f"root;{frame} 2\n",
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            svg = ET.parse(output).getroot()
            self.assertEqual(
                svg.find('.//{*}text[@id="header-title"]').text, "A&B <report>"
            )
            groups = svg.findall(".//{*}g")
            self.assertIn(frame, [g.attrib["data-name"] for g in groups])
            self.assertTrue(
                all(g.attrib["onmouseover"] == "showInfo(this)" for g in groups)
            )

    def test_size_checker_is_advisory_by_default(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "large.py"
            path.write_text("x = 1\n" * 501)
            script = SKILLS / "pragmatic-engineering/scripts/check_anti_bloat.py"
            result = subprocess.run(
                [sys.executable, str(script), str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("FILE_LENGTH_EXCEEDED", result.stderr)


if __name__ == "__main__":
    unittest.main()
