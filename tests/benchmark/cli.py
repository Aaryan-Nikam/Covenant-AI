"""
Ironpass — Benchmark CLI.

Runs the detection engine against massive external datasets to calculate
precision and recall for compliance policies (HIPAA, PCI, GDPR, SOC2).

Usage:
    python -m tests.benchmark.cli --dataset kaggle_pii --limit 1000
    python -m tests.benchmark.cli --dataset huggingface_pii --limit 500
"""

import argparse
import asyncio
import logging
import os
import time

# Minimal env setup for engine imports
os.environ.setdefault("REDIS_URL", "redis://localhost")
os.environ.setdefault("KEY_BACKEND", "local")
os.environ.setdefault("LOCAL_VAULT_KEY", "c" * 64)
os.environ.setdefault("IRONPASS_ADMIN_SECRET", "test")
os.environ.setdefault("AUDIT_HMAC_KEY", "a" * 64)
os.environ.setdefault("PSEUDONYM_SECRET_KEY", "b" * 64)

from tqdm import tqdm

from engine.detection.engine import DetectionEngine
from engine.rulesets.registry import RulesetRegistry
from engine.rulesets.loader import RulesetLoader
from tests.benchmark.parsers import KagglePIIParser, HuggingFacePIIParser

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("ironpass.benchmark")

DATASETS = {
    "kaggle_pii": KagglePIIParser(),
    "huggingface_pii": HuggingFacePIIParser(),
}


def compute_metrics(expected_types: set[str], detected_types: set[str]) -> tuple[int, int, int]:
    """Calculate true positives, false negatives, and false positives."""
    tp = len(expected_types.intersection(detected_types))
    fn = len(expected_types - detected_types)
    fp = len(detected_types - expected_types)
    return tp, fn, fp


async def main():
    parser = argparse.ArgumentParser(description="Ironpass Bulk Compliance Benchmark")
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()),
        required=True,
        help="Dataset to benchmark against",
    )
    parser.add_argument(
        "--rulesets",
        default="pci_dss,hipaa,gdpr,soc2",
        help="Comma-separated ruleset IDs to test",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max number of items to process",
    )
    args = parser.parse_args()

    active_rulesets = [r.strip() for r in args.rulesets.split(",")]
    
    # Initialize Engine
    print("⏳ Initializing Detection Engine (loading spaCy)...")
    registry = RulesetRegistry()
    loader = RulesetLoader()
    registry.register_all(loader.load_all())
    engine = DetectionEngine(ruleset_registry=registry)
    print("✅ Engine Ready\n")

    print(f"📥 Loading dataset '{args.dataset}' (limit={args.limit})...")
    parser_impl = DATASETS[args.dataset]
    
    start_time = time.perf_counter()
    cases = parser_impl.load(limit=args.limit)
    
    if not cases:
        print("❌ Failed to load dataset or dataset was empty.")
        return

    print(f"🚀 Running {len(cases)} cases through engine...")
    
    total_latency_ms = 0
    total_tp = 0
    total_fn = 0
    total_fp = 0

    progress_bar = tqdm(total=len(cases), desc="Scanning", unit="doc")

    for case in cases:
        scan_start = time.perf_counter()
        
        # Run detection pipeline
        detections = await engine.scan(case.input, active_rulesets=active_rulesets)
        
        latency = (time.perf_counter() - scan_start) * 1000
        total_latency_ms += latency

        # Calculate metrics for this payload
        expected_types = {e.data_type for e in case.expected_entities}
        detected_types = {d.data_type for d in detections}

        tp, fn, fp = compute_metrics(expected_types, detected_types)
        total_tp += tp
        total_fn += fn
        total_fp += fp

        progress_bar.update(1)

    progress_bar.close()

    # Final calculations
    runtime = time.perf_counter() - start_time
    avg_latency = total_latency_ms / len(cases) if len(cases) > 0 else 0
    
    precision = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else 1.0
    recall = (total_tp / (total_tp + total_fn)) if (total_tp + total_fn) > 0 else 1.0
    
    if precision + recall > 0:
        f1_score = 2 * (precision * recall) / (precision + recall)
    else:
        f1_score = 0.0

    print("\n" + "═" * 60)
    print(f"  IRONPASS BULK BENCHMARK: {args.dataset.upper()}")
    print("═" * 60)
    print(f"  Documents Scanned : {len(cases)}")
    print(f"  Rulesets Active   : {', '.join(active_rulesets)}")
    print(f"  Total Runtime     : {runtime:.2f}s")
    print(f"  Avg Doc Latency   : {avg_latency:.2f}ms")
    print("─" * 60)
    print(f"  True Positives    : {total_tp}")
    print(f"  False Negatives   : {total_fn}")
    print(f"  False Positives   : {total_fp}")
    print("─" * 60)
    print(f"  Precision         : {precision * 100:.1f}%")
    print(f"  Recall            : {recall * 100:.1f}%")
    print(f"  F1-Score          : {f1_score * 100:.1f}%")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
