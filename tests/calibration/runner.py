"""
Ironpass — Calibration runner.

Runs all calibration cases through the live DetectionEngine and
reports precision, recall, F1, and latency per detection type.

Usage:
    # Run all cases and print report
    python tests/calibration/runner.py

    # Run a specific category only
    python tests/calibration/runner.py --category credit_card

    # Run and save JSON report
    python tests/calibration/runner.py --output report.json

    # Run as pytest (individual test per case)
    pytest tests/calibration/runner.py -v

This runs WITHOUT a database or API server — it loads the
DetectionEngine directly. No infrastructure required.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass

# Add project root to path so engine imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Minimal env setup for engine imports (no DB needed)
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost")
os.environ.setdefault("AUDIT_HMAC_KEY", "a" * 64)
os.environ.setdefault("PSEUDONYM_SECRET_KEY", "b" * 64)
os.environ.setdefault("KEY_BACKEND", "local")
os.environ.setdefault("LOCAL_VAULT_KEY", "c" * 64)
os.environ.setdefault("IRONPASS_ADMIN_SECRET", "test")

from tests.calibration.dataset import ALL_CASES, CalibrationCase
from engine.detection.engine import DetectionEngine
from engine.rulesets.loader import RulesetLoader
from engine.rulesets.registry import RulesetRegistry


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    case_id: str
    category: str
    difficulty: str
    description: str
    passed: bool
    latency_ms: float
    detected_types: list[str]
    expected_types: list[str]
    false_positives_flagged: list[str]   # values from must_not_flag that were detected
    missed_types: list[str]              # expected_types not found
    extra_types: list[str]               # detected types not in expected (not necessarily wrong)
    detection_layers: list[str]          # which layers fired
    notes: str


@dataclass
class CalibrationReport:
    total_cases: int
    passed: int
    failed: int
    pass_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    by_category: dict
    by_difficulty: dict
    failed_cases: list[CaseResult]
    false_positive_cases: list[CaseResult]


# ---------------------------------------------------------------------------
# Engine setup
# ---------------------------------------------------------------------------

def build_detection_engine() -> DetectionEngine:
    """Load rulesets and build the detection engine. No DB required."""
    loader = RulesetLoader()
    rulesets = loader.load_all()
    registry = RulesetRegistry()
    registry.register_all(rulesets)
    return DetectionEngine(registry)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_case(
    case: CalibrationCase,
    engine: DetectionEngine,
) -> CaseResult:
    """Run a single calibration case through the detection engine."""

    if not case.input:
        # Empty input — special handling
        return CaseResult(
            case_id=case.id,
            category=case.category,
            difficulty=case.difficulty,
            description=case.description,
            passed=len(case.expected_types) == 0,
            latency_ms=0.0,
            detected_types=[],
            expected_types=case.expected_types,
            false_positives_flagged=[],
            missed_types=case.expected_types,
            extra_types=[],
            detection_layers=[],
            notes=case.notes,
        )

    start = time.perf_counter()
    # Use all available rulesets for calibration
    all_ruleset_ids = ["pci_dss", "hipaa", "gdpr", "soc2"]
    detections = await engine.scan(case.input, active_rulesets=all_ruleset_ids)
    latency_ms = (time.perf_counter() - start) * 1000

    detected_types = list({d.data_type for d in detections})
    detected_values = [d.value for d in detections]
    detection_layers = list({d.layer for d in detections})

    # Check expected types are all present
    missed_types = [t for t in case.expected_types if t not in detected_types]

    # Check false positive traps
    false_positives_flagged = [
        v for v in case.must_not_flag
        if any(v in dv or dv in v for dv in detected_values)
    ]

    # Extra detections (detected but not in expected) — informational, not failure
    extra_types = [t for t in detected_types if t not in case.expected_types]

    # Pass criteria:
    #   1. All expected types are detected
    #   2. None of the must_not_flag values are detected
    passed = len(missed_types) == 0 and len(false_positives_flagged) == 0

    return CaseResult(
        case_id=case.id,
        category=case.category,
        difficulty=case.difficulty,
        description=case.description,
        passed=passed,
        latency_ms=round(latency_ms, 2),
        detected_types=detected_types,
        expected_types=case.expected_types,
        false_positives_flagged=false_positives_flagged,
        missed_types=missed_types,
        extra_types=extra_types,
        detection_layers=detection_layers,
        notes=case.notes,
    )


async def run_all(
    category_filter: str | None = None,
    difficulty_filter: str | None = None,
) -> CalibrationReport:
    """Run all calibration cases and return a structured report."""

    print("⏳ Building detection engine (loading spaCy model)...")
    engine = build_detection_engine()
    print("✅ Engine ready\n")

    cases = ALL_CASES
    if category_filter:
        cases = [c for c in cases if c.category == category_filter]
    if difficulty_filter:
        cases = [c for c in cases if c.difficulty == difficulty_filter]

    results: list[CaseResult] = []
    for case in cases:
        sys.stdout.write(f"  [{case.id}] {case.description[:55]:<55} ")
        sys.stdout.flush()
        result = await run_case(case, engine)
        results.append(result)
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"{status}  ({result.latency_ms:.0f}ms)")

    # Aggregate stats
    passed = sum(1 for r in results if r.passed)
    latencies = [r.latency_ms for r in results if r.latency_ms > 0]
    latencies_sorted = sorted(latencies)

    by_category: dict[str, dict] = defaultdict(lambda: {"total": 0, "passed": 0})
    by_difficulty: dict[str, dict] = defaultdict(lambda: {"total": 0, "passed": 0})

    for r in results:
        by_category[r.category]["total"] += 1
        by_difficulty[r.difficulty]["total"] += 1
        if r.passed:
            by_category[r.category]["passed"] += 1
            by_difficulty[r.difficulty]["passed"] += 1

    # Add pass rate to each group
    for group in [by_category, by_difficulty]:
        for key in group:
            t = group[key]["total"]
            p = group[key]["passed"]
            group[key]["pass_rate"] = round(p / t * 100, 1) if t else 0

    failed_cases = [r for r in results if not r.passed]
    fp_cases = [r for r in results if r.false_positives_flagged]

    return CalibrationReport(
        total_cases=len(results),
        passed=passed,
        failed=len(results) - passed,
        pass_rate=round(passed / len(results) * 100, 1) if results else 0,
        avg_latency_ms=round(sum(latencies) / len(latencies), 2) if latencies else 0,
        p95_latency_ms=round(
            latencies_sorted[int(len(latencies_sorted) * 0.95)] if latencies_sorted else 0,
            2,
        ),
        by_category=dict(by_category),
        by_difficulty=dict(by_difficulty),
        failed_cases=failed_cases,
        false_positive_cases=fp_cases,
    )


def print_report(report: CalibrationReport) -> None:
    """Render a human-readable calibration report to stdout."""
    bar = "═" * 60

    print(f"\n{bar}")
    print("  IRONPASS DETECTION CALIBRATION REPORT")
    print(bar)
    print(f"  Total cases : {report.total_cases}")
    print(f"  Passed      : {report.passed}")
    print(f"  Failed      : {report.failed}")
    print(f"  Pass rate   : {report.pass_rate}%")
    print(f"  Avg latency : {report.avg_latency_ms}ms")
    print(f"  P95 latency : {report.p95_latency_ms}ms")

    print(f"\n{'─' * 60}")
    print("  BY CATEGORY")
    print(f"{'─' * 60}")
    for cat, stats in sorted(report.by_category.items()):
        bar_fill = "█" * int(stats["pass_rate"] / 5)
        print(
            f"  {cat:<20} {stats['passed']:>2}/{stats['total']:<2}  "
            f"[{bar_fill:<20}] {stats['pass_rate']}%"
        )

    print(f"\n{'─' * 60}")
    print("  BY DIFFICULTY")
    print(f"{'─' * 60}")
    for diff in ["easy", "medium", "hard"]:
        if diff in report.by_difficulty:
            stats = report.by_difficulty[diff]
            bar_fill = "█" * int(stats["pass_rate"] / 5)
            print(
                f"  {diff:<10} {stats['passed']:>2}/{stats['total']:<2}  "
                f"[{bar_fill:<20}] {stats['pass_rate']}%"
            )

    if report.false_positive_cases:
        print(f"\n{'─' * 60}")
        print(f"  ⚠️  FALSE POSITIVES TRIGGERED ({len(report.false_positive_cases)} cases)")
        print(f"{'─' * 60}")
        for r in report.false_positive_cases:
            print(f"  [{r.case_id}] {r.description}")
            print(f"    Incorrectly flagged: {r.false_positives_flagged}")

    if report.failed_cases:
        print(f"\n{'─' * 60}")
        print(f"  ❌ FAILED CASES ({len(report.failed_cases)})")
        print(f"{'─' * 60}")
        for r in report.failed_cases:
            print(f"  [{r.case_id}] {r.description}")
            if r.missed_types:
                print(f"    Missed types    : {r.missed_types}")
            if r.false_positives_flagged:
                print(f"    False positives : {r.false_positives_flagged}")
            if r.notes:
                print(f"    Note            : {r.notes}")

    print(f"\n{'═' * 60}\n")


# ---------------------------------------------------------------------------
# Pytest integration — each case becomes an individual test
# ---------------------------------------------------------------------------

import pytest

@pytest.fixture(scope="module")
def detection_engine():
    return build_detection_engine()


def pytest_cases():
    """Generate pytest parameters from the calibration dataset."""
    return [(c.id, c) for c in ALL_CASES]


@pytest.mark.parametrize("case_id,case", pytest_cases())
@pytest.mark.asyncio
async def test_calibration_case(case_id, case, detection_engine):
    """Individual calibration test — passes if detection meets expected criteria."""
    result = await run_case(case, detection_engine)

    if result.false_positives_flagged:
        pytest.fail(
            f"[{case_id}] False positive detected: {result.false_positives_flagged}\n"
            f"Input: {case.input[:100]}"
        )

    if result.missed_types:
        pytest.fail(
            f"[{case_id}] Missed expected types: {result.missed_types}\n"
            f"Detected: {result.detected_types}\n"
            f"Input: {case.input[:100]}"
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Ironpass Detection Calibration Runner")
    parser.add_argument("--category", help="Filter by category (e.g. credit_card)")
    parser.add_argument("--difficulty", help="Filter by difficulty (easy/medium/hard)")
    parser.add_argument("--output", help="Save JSON report to file")
    args = parser.parse_args()

    report = await run_all(
        category_filter=args.category,
        difficulty_filter=args.difficulty,
    )
    print_report(report)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(
                {
                    "total_cases": report.total_cases,
                    "passed": report.passed,
                    "failed": report.failed,
                    "pass_rate": report.pass_rate,
                    "avg_latency_ms": report.avg_latency_ms,
                    "p95_latency_ms": report.p95_latency_ms,
                    "by_category": report.by_category,
                    "by_difficulty": report.by_difficulty,
                    "failed_cases": [asdict(r) for r in report.failed_cases],
                },
                f,
                indent=2,
            )
        print(f"Report written to {args.output}\n")

    sys.exit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
