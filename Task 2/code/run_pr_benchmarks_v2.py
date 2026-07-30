from __future__ import annotations

import csv
import ctypes
import json
import os
import platform
import random
import statistics
import time
from pathlib import Path

from run_benchmarks import (
    CSV_RESULT_RE,
    RESULT_RE,
    run,
    to_us,
)
from run_pr_benchmarks import VARIANTS, build_variant


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data"
BLOCKS = 15
BOOTSTRAP_SAMPLES = 10_000
RNG_SEED = 20260730

COMPARISONS = [
    {
        "comparison": "pr1446-ecdsa_verify",
        "before": "pr1446-before",
        "after": "pr1446-after",
        "operation": "ecdsa_verify",
        "iterations": 4000,
    },
    {
        "comparison": "pr1058-ecdsa_sign",
        "before": "pr1058-before",
        "after": "pr1058-after",
        "operation": "ecdsa_sign",
        "iterations": 7000,
    },
    {
        "comparison": "pr1058-ec_keygen",
        "before": "pr1058-before",
        "after": "pr1058-after",
        "operation": "ec_keygen",
        "iterations": 7000,
    },
]


def set_windows_execution_controls(cpu_index: int = 0) -> dict[str, object]:
    """Pin the process to one logical CPU and request high priority on Windows."""
    result: dict[str, object] = {
        "requested_cpu_index": cpu_index,
        "affinity_applied": False,
        "high_priority_applied": False,
    }
    if os.name != "nt":
        result["note"] = "Windows execution controls not applicable"
        return result
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.GetCurrentProcess()
    affinity_mask = ctypes.c_size_t(1 << cpu_index)
    result["affinity_applied"] = bool(kernel32.SetProcessAffinityMask(handle, affinity_mask))
    result["affinity_error"] = ctypes.get_last_error()
    high_priority_class = 0x00000080
    result["high_priority_applied"] = bool(kernel32.SetPriorityClass(handle, high_priority_class))
    result["priority_error"] = ctypes.get_last_error()
    return result


def parse_result(output: str) -> dict[str, float]:
    match = RESULT_RE.search(output)
    csv_match = CSV_RESULT_RE.search(output) if not match else None
    if not match and not csv_match:
        raise RuntimeError(f"Could not parse benchmark output:\n{output}")
    if csv_match:
        return {
            "min_us": float(csv_match.group("min")),
            "avg_us": float(csv_match.group("avg")),
            "max_us": float(csv_match.group("max")),
        }
    return {
        "min_us": to_us(float(match.group("min")), match.group("minunit")),
        "avg_us": to_us(float(match.group("avg")), match.group("avgunit")),
        "max_us": to_us(float(match.group("max")), match.group("maxunit")),
    }


def benchmark_once(exe: Path, operation: str, iterations: int) -> tuple[dict[str, float], str, float]:
    env = os.environ.copy()
    env["SECP256K1_BENCH_ITERS"] = str(iterations)
    started = time.perf_counter()
    completed = run([str(exe), operation], cwd=exe.parent, env=env)
    wall_s = time.perf_counter() - started
    return parse_result(completed.stdout), completed.stdout.rstrip(), wall_s


def percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("empty sample")
    index = probability * (len(sorted_values) - 1)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def bootstrap_median_ci(values: list[float], seed: int) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(values)
    medians = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))
    medians.sort()
    return percentile(medians, 0.025), percentile(medians, 0.975)


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    execution_controls = set_windows_execution_controls(cpu_index=0)
    executables: dict[str, Path] = {}
    for variant in sorted({c["before"] for c in COMPARISONS} | {c["after"] for c in COMPARISONS}):
        print(f"[build] {variant}", flush=True)
        executables[variant] = build_variant(variant, VARIANTS[variant])

    details: list[dict[str, object]] = []
    raw_sections: list[str] = []
    pair_deltas: dict[str, list[float]] = {}

    for comparison_index, comparison in enumerate(COMPARISONS):
        name = str(comparison["comparison"])
        before = str(comparison["before"])
        after = str(comparison["after"])
        operation = str(comparison["operation"])
        iterations = int(comparison["iterations"])
        pair_deltas[name] = []

        print(f"[warmup] {name}", flush=True)
        for variant in (before, after, after, before):
            benchmark_once(executables[variant], operation, iterations)

        for block in range(1, BLOCKS + 1):
            order = [before, after, after, before] if block % 2 else [after, before, before, after]
            block_values: dict[str, list[float]] = {before: [], after: []}
            print(f"[bench] {name} block={block:02d}/{BLOCKS} order={'/'.join(order)}", flush=True)
            for slot, variant in enumerate(order, start=1):
                values, raw, wall_s = benchmark_once(executables[variant], operation, iterations)
                phase = "before" if variant == before else "after"
                block_values[variant].append(values["avg_us"])
                details.append(
                    {
                        "comparison": name,
                        "phase": phase,
                        "variant": variant,
                        "commit": VARIANTS[variant]["commit"],
                        "operation": operation,
                        "iterations": iterations,
                        "block": block,
                        "slot": slot,
                        "order_pattern": "ABBA" if block % 2 else "BAAB",
                        **values,
                        "wall_s": wall_s,
                    }
                )
                raw_sections.append(
                    f"===== {name} / block {block:02d} / slot {slot} / {variant} =====\n"
                    f"wall_s={wall_s:.6f}\n{raw}\n"
                )
            before_mean = statistics.mean(block_values[before])
            after_mean = statistics.mean(block_values[after])
            pair_deltas[name].append((after_mean - before_mean) / before_mean * 100.0)

    summaries: list[dict[str, object]] = []
    for comparison_index, comparison in enumerate(COMPARISONS):
        name = str(comparison["comparison"])
        for phase in ("before", "after"):
            rows = [r for r in details if r["comparison"] == name and r["phase"] == phase]
            values = [float(r["avg_us"]) for r in rows]
            median = statistics.median(values)
            mad = statistics.median(abs(value - median) for value in values)
            ci_low, ci_high = bootstrap_median_ci(
                values, RNG_SEED + comparison_index * 10 + (0 if phase == "before" else 1)
            )
            summaries.append(
                {
                    "comparison": name,
                    "phase": phase,
                    "variant": rows[0]["variant"],
                    "commit": rows[0]["commit"],
                    "operation": rows[0]["operation"],
                    "iterations": rows[0]["iterations"],
                    "runs": len(values),
                    "median_avg_us": median,
                    "mad_avg_us": mad,
                    "bootstrap_median_ci95_low_us": ci_low,
                    "bootstrap_median_ci95_high_us": ci_high,
                    "min_avg_us": min(values),
                    "max_avg_us": max(values),
                }
            )

    comparison_summaries: list[dict[str, object]] = []
    for comparison_index, comparison in enumerate(COMPARISONS):
        name = str(comparison["comparison"])
        deltas = pair_deltas[name]
        ci_low, ci_high = bootstrap_median_ci(deltas, RNG_SEED + 100 + comparison_index)
        comparison_summaries.append(
            {
                "comparison": name,
                "operation": comparison["operation"],
                "blocks": BLOCKS,
                "runs_per_phase": BLOCKS * 2,
                "median_block_relative_change_pct": statistics.median(deltas),
                "mad_block_relative_change_pct": statistics.median(
                    abs(value - statistics.median(deltas)) for value in deltas
                ),
                "bootstrap_median_change_ci95_low_pct": ci_low,
                "bootstrap_median_change_ci95_high_pct": ci_high,
                "interpretation": "negative means after is faster",
            }
        )

    with (EVIDENCE / "benchmark_detail_30.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(details[0].keys()))
        writer.writeheader()
        writer.writerows(details)
    with (EVIDENCE / "benchmark_summary_30.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)
    with (EVIDENCE / "benchmark_comparison_30.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison_summaries[0].keys()))
        writer.writeheader()
        writer.writerows(comparison_summaries)

    (EVIDENCE / "benchmark_raw_30.txt").write_text("\n".join(raw_sections), encoding="utf-8")
    (EVIDENCE / "benchmark_results_30.json").write_text(
        json.dumps(
            {
                "phase_summaries": summaries,
                "comparison_summaries": comparison_summaries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (EVIDENCE / "benchmark_environment_30.json").write_text(
        json.dumps(
            {
                "timestamp_local": time.strftime("%Y-%m-%d %H:%M:%S %z"),
                "platform": platform.platform(),
                "python": platform.python_version(),
                "processor": platform.processor(),
                "execution_controls": execution_controls,
                "design": "15 four-run blocks; odd blocks ABBA, even blocks BAAB; 30 retained runs per phase",
                "warmup": "ABBA once per comparison and discarded",
                "bootstrap_samples": BOOTSTRAP_SAMPLES,
                "bootstrap_seed": RNG_SEED,
                "compiler": "GCC 15.2.0, -O2 -std=c90 -fno-omit-frame-pointer",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(comparison_summaries, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
