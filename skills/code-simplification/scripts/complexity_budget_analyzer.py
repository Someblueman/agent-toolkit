#!/usr/bin/env python3
"""
Complexity Budget Analyzer CLI

Analyzes source code to compute structural and cognitive complexity metrics:
- Cyclomatic Complexity (McCabe)
- Maximum AST Nesting Depth
- Cognitive Complexity (SonarQube-style nesting-weighted metric)
- Function Length (Physical and Logical Lines of Code)
- Function Parameter Counts

Enforces configurable complexity budgets and outputs formatted terminal reports,
JSON summaries, or CSV exports.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FunctionMetrics:
    name: str
    file_path: str
    line_start: int
    line_end: int
    loc: int
    param_count: int
    cyclomatic_complexity: int
    cognitive_complexity: int
    max_nesting_depth: int
    violations: List[str] = field(default_factory=list)


@dataclass
class FileMetrics:
    file_path: str
    total_loc: int
    function_count: int
    max_cyclomatic: int
    max_cognitive: int
    max_nesting: int
    functions: List[FunctionMetrics] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)


@dataclass
class BudgetThresholds:
    max_cyclomatic: int = 10
    max_cognitive: int = 15
    max_nesting: int = 3
    max_loc: int = 50
    max_params: int = 4


class CognitiveComplexityVisitor(ast.NodeVisitor):
    """
    Computes Cognitive Complexity by penalizing nested control flow breaks.
    """

    def __init__(self) -> None:
        self.complexity: int = 0
        self.current_nesting: int = 0
        self.max_nesting: int = 0

    def _enter_nesting(self) -> None:
        self.current_nesting += 1
        if self.current_nesting > self.max_nesting:
            self.max_nesting = self.current_nesting

    def _leave_nesting(self) -> None:
        self.current_nesting -= 1

    def visit_If(self, node: ast.If) -> None:
        # Increment for 'if' + nesting penalty
        self.complexity += 1 + self.current_nesting
        self._enter_nesting()
        for child in node.body:
            self.visit(child)
        self._leave_nesting()

        # Handle 'elif' vs 'else'
        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                # Elif gets +1 (no nesting increment on the elif itself)
                self.visit_If_elif(node.orelse[0])
            else:
                self.complexity += 1  # 'else' gets +1
                self._enter_nesting()
                for child in node.orelse:
                    self.visit(child)
                self._leave_nesting()

    def visit_If_elif(self, node: ast.If) -> None:
        self.complexity += 1 + self.current_nesting
        self._enter_nesting()
        for child in node.body:
            self.visit(child)
        self._leave_nesting()

        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                self.visit_If_elif(node.orelse[0])
            else:
                self.complexity += 1
                self._enter_nesting()
                for child in node.orelse:
                    self.visit(child)
                self._leave_nesting()

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1 + self.current_nesting
        self._enter_nesting()
        for child in node.body:
            self.visit(child)
        self._leave_nesting()
        for child in node.orelse:
            self.visit(child)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.complexity += 1 + self.current_nesting
        self._enter_nesting()
        for child in node.body:
            self.visit(child)
        self._leave_nesting()
        for child in node.orelse:
            self.visit(child)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1 + self.current_nesting
        self._enter_nesting()
        for child in node.body:
            self.visit(child)
        self._leave_nesting()
        for child in node.orelse:
            self.visit(child)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1 + self.current_nesting
        self._enter_nesting()
        for child in node.body:
            self.visit(child)
        self._leave_nesting()

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # Each boolean operator in a sequence (and / or) adds +1
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_Match(self, node: Any) -> None:
        # Python 3.10+ match statement
        self.complexity += 1 + self.current_nesting
        self._enter_nesting()
        for case in getattr(node, "cases", []):
            if getattr(case, "guard", None):
                self.complexity += 1
            for child in case.body:
                self.visit(child)
        self._leave_nesting()


class ASTMetricsCollector(ast.NodeVisitor):
    """
    Visits Python AST to extract function-level metrics.
    """

    def __init__(self, file_path: str, thresholds: BudgetThresholds) -> None:
        self.file_path = file_path
        self.thresholds = thresholds
        self.functions: List[FunctionMetrics] = []

    def _calc_cyclomatic(self, node: ast.AST) -> int:
        """
        McCabe Cyclomatic Complexity: 1 + number of branching decision points.
        """
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.IfExp):
                complexity += 1
            elif hasattr(ast, "Match") and isinstance(child, getattr(ast, "Match")):
                # Count match cases
                cases = getattr(child, "cases", [])
                complexity += max(len(cases) - 1, 0)
        return complexity

    def _calc_max_nesting(self, node: ast.AST) -> int:
        """
        Calculates maximum control structure nesting depth within the function.
        """
        max_depth = 0

        def walk_depth(n: ast.AST, current_depth: int) -> None:
            nonlocal max_depth
            if current_depth > max_depth:
                max_depth = current_depth

            is_nesting_node = isinstance(
                n,
                (
                    ast.If,
                    ast.While,
                    ast.For,
                    ast.AsyncFor,
                    ast.Try,
                    ast.With,
                    ast.AsyncWith,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            if hasattr(ast, "Match") and isinstance(n, getattr(ast, "Match")):
                is_nesting_node = True

            next_depth = current_depth + (1 if is_nesting_node else 0)

            for child in ast.iter_child_nodes(n):
                walk_depth(child, next_depth)

        for child in ast.iter_child_nodes(node):
            walk_depth(child, 1)

        return max_depth

    def _calc_cognitive(self, node: ast.AST) -> Tuple[int, int]:
        cog_visitor = CognitiveComplexityVisitor()
        for child in ast.iter_child_nodes(node):
            cog_visitor.visit(child)
        return cog_visitor.complexity, cog_visitor.max_nesting

    def _count_params(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        args = node.args
        count = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
        if args.vararg:
            count += 1
        if args.kwarg:
            count += 1
        # Subtract self/cls for methods if present
        if count > 0 and args.args and args.args[0].arg in ("self", "cls"):
            count -= 1
        return count

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._analyze_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._analyze_function(node)
        self.generic_visit(node)

    def _analyze_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)
        loc = max(end_line - start_line + 1, 1)
        params = self._count_params(node)
        cyclo = self._calc_cyclomatic(node)
        cog, max_nest = self._calc_cognitive(node)

        violations: List[str] = []
        if cyclo > self.thresholds.max_cyclomatic:
            violations.append(
                f"Cyclomatic complexity {cyclo} > budget {self.thresholds.max_cyclomatic}"
            )
        if cog > self.thresholds.max_cognitive:
            violations.append(
                f"Cognitive complexity {cog} > budget {self.thresholds.max_cognitive}"
            )
        if max_nest > self.thresholds.max_nesting:
            violations.append(
                f"Nesting depth {max_nest} > budget {self.thresholds.max_nesting}"
            )
        if loc > self.thresholds.max_loc:
            violations.append(f"Function LOC {loc} > budget {self.thresholds.max_loc}")
        if params > self.thresholds.max_params:
            violations.append(
                f"Parameter count {params} > budget {self.thresholds.max_params}"
            )

        self.functions.append(
            FunctionMetrics(
                name=node.name,
                file_path=self.file_path,
                line_start=start_line,
                line_end=end_line,
                loc=loc,
                param_count=params,
                cyclomatic_complexity=cyclo,
                cognitive_complexity=cog,
                max_nesting_depth=max_nest,
                violations=violations,
            )
        )


def analyze_python_file(file_path: Path, thresholds: BudgetThresholds) -> Optional[FileMetrics]:
    """
    Parses and analyzes a single Python file.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError) as err:
        return FileMetrics(
            file_path=str(file_path),
            total_loc=0,
            function_count=0,
            max_cyclomatic=0,
            max_cognitive=0,
            max_nesting=0,
            violations=[f"Parse error: {err}"],
        )

    lines = [line for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
    total_loc = len(lines)

    collector = ASTMetricsCollector(str(file_path), thresholds)
    collector.visit(tree)

    max_cyclo = max((f.cyclomatic_complexity for f in collector.functions), default=0)
    max_cog = max((f.cognitive_complexity for f in collector.functions), default=0)
    max_nest = max((f.max_nesting_depth for f in collector.functions), default=0)

    file_violations: List[str] = []
    for fn in collector.functions:
        file_violations.extend(fn.violations)

    return FileMetrics(
        file_path=str(file_path),
        total_loc=total_loc,
        function_count=len(collector.functions),
        max_cyclomatic=max_cyclo,
        max_cognitive=max_cog,
        max_nesting=max_nest,
        functions=collector.functions,
        violations=file_violations,
    )


def _collect_py_files(target_path: Path) -> List[Path]:
    if target_path.is_file():
        return [target_path] if target_path.suffix == ".py" else []
    if target_path.is_dir():
        return sorted(target_path.rglob("*.py"))
    return []


def scan_target(target_path: Path, thresholds: BudgetThresholds) -> List[FileMetrics]:
    results: List[FileMetrics] = []
    for py_file in _collect_py_files(target_path):
        res = analyze_python_file(py_file, thresholds)
        if res:
            results.append(res)
    return results



def format_table(results: List[FileMetrics], thresholds: BudgetThresholds) -> str:
    """
    Generates a formatted CLI summary table.
    """
    lines: List[str] = []
    lines.append("=" * 96)
    lines.append(f"{'COMPLEXITY BUDGET ANALYSIS REPORT':^96}")
    lines.append("=" * 96)
    lines.append(
        f"Thresholds: Max Cyclomatic={thresholds.max_cyclomatic}, Max Cognitive={thresholds.max_cognitive}, "
        f"Max Nesting={thresholds.max_nesting}, Max LOC={thresholds.max_loc}, Max Params={thresholds.max_params}"
    )
    lines.append("-" * 96)
    lines.append(
        f"{'Function / Scope':<32} {'File:Line':<24} {'Cyclo':>6} {'Cognitive':>9} {'Nesting':>7} {'LOC':>5} {'Status':>8}"
    )
    lines.append("-" * 96)

    total_fns = 0
    total_violations = 0

    for file_res in results:
        for fn in file_res.functions:
            total_fns += 1
            loc_str = f"{Path(fn.file_path).name}:{fn.line_start}"
            status = "PASS" if not fn.violations else "FAIL"
            if fn.violations:
                total_violations += len(fn.violations)

            lines.append(
                f"{fn.name:<32} {loc_str:<24} {fn.cyclomatic_complexity:>6} {fn.cognitive_complexity:>9} "
                f"{fn.max_nesting_depth:>7} {fn.loc:>5} {status:>8}"
            )
            for v in fn.violations:
                lines.append(f"  └── ⚠️  {v}")

    lines.append("=" * 96)
    summary_status = "PASSED" if total_violations == 0 else f"FAILED ({total_violations} violations)"
    lines.append(
        f"Summary: {len(results)} files analyzed | {total_fns} functions scanned | Status: {summary_status}"
    )
    lines.append("=" * 96)
    return "\n".join(lines)


def export_json(results: List[FileMetrics], thresholds: BudgetThresholds) -> str:
    total_violations = sum(len(f.violations) for f in results)
    payload = {
        "thresholds": asdict(thresholds),
        "status": "PASSED" if total_violations == 0 else "FAILED",
        "total_files": len(results),
        "total_functions": sum(f.function_count for f in results),
        "total_violations": total_violations,
        "files": [asdict(f) for f in results],
    }
    return json.dumps(payload, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Complexity Budget Analyzer - Enforce structural & cognitive limits."
    )
    parser.add_argument("target", nargs="?", default=".", help="Target file or directory to analyze")
    parser.add_argument("--max-cyclomatic", type=int, default=10, help="Max cyclomatic complexity budget (default: 10)")
    parser.add_argument("--max-cognitive", type=int, default=15, help="Max cognitive complexity budget (default: 15)")
    parser.add_argument("--max-nesting", type=int, default=3, help="Max AST nesting depth budget (default: 3)")
    parser.add_argument("--max-loc", type=int, default=50, help="Max function lines of code (default: 50)")
    parser.add_argument("--max-params", type=int, default=4, help="Max function parameter count (default: 4)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--fail-on-violation", action="store_true", default=True, help="Exit with non-zero code on violations")
    parser.add_argument("--no-fail", action="store_false", dest="fail_on_violation", help="Always exit 0")

    args = parser.parse_args()

    thresholds = BudgetThresholds(
        max_cyclomatic=args.max_cyclomatic,
        max_cognitive=args.max_cognitive,
        max_nesting=args.max_nesting,
        max_loc=args.max_loc,
        max_params=args.max_params,
    )

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target path '{target_path}' does not exist.", file=sys.stderr)
        return 2

    results = scan_target(target_path, thresholds)
    if not results:
        print("No Python files analyzed; unsupported or empty input", file=sys.stderr)
        return 2

    if args.json:
        print(export_json(results, thresholds))
    else:
        print(format_table(results, thresholds))

    total_violations = sum(len(f.violations) for f in results)
    if total_violations > 0 and args.fail_on_violation:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
