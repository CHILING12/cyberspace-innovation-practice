from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_benchmarks import BUILD, EVIDENCE, REPO, benchmark, build_variant  # noqa: E402


VARIANTS = {
    "pr1446-before": {
        "src": REPO / "pr1446_before",
        "defines": ["SECP256K1_STATIC", "USE_ASM_X86_64", "ECMULT_WINDOW_SIZE=15", "ECMULT_GEN_PREC_BITS=4"],
        "commit": "07687e811d1c9700e6fe9d658aef080e3568c0f1",
        "description": "PR #1446 first parent; handwritten x86_64 field assembly enabled",
    },
    "pr1446-after": {
        "src": REPO / "pr1446_after",
        "defines": ["SECP256K1_STATIC", "USE_ASM_X86_64", "ECMULT_WINDOW_SIZE=15", "ECMULT_GEN_PREC_BITS=4"],
        "commit": "10e6d29b60c3931e327bc18e6c50cea78296b1ba",
        "description": "PR #1446 merge; field assembly removed while scalar assembly remains",
    },
    "pr1058-before": {
        "src": REPO / "pr1058_before",
        "defines": ["SECP256K1_STATIC", "USE_ASM_X86_64", "ECMULT_WINDOW_SIZE=15", "ECMULT_GEN_PREC_BITS=4"],
        "commit": "d8311688bd383d3a923a1b11789cded3cc8e5e03",
        "description": "PR #1058 first parent; legacy fixed-base multiplication",
    },
    "pr1058-after": {
        "src": REPO / "pr1058_after",
        "defines": ["SECP256K1_STATIC", "USE_ASM_X86_64", "ECMULT_WINDOW_SIZE=15", "COMB_BLOCKS=11", "COMB_TEETH=6"],
        "commit": "da515074e3ebc8abc85a4fff3a31d7694ecf897b",
        "description": "PR #1058 merge; default 22 KiB signed-digit multi-comb",
    },
}

EXPERIMENTS = [
    ("pr1446-before", "ecdsa_verify", 4000),
    ("pr1446-after", "ecdsa_verify", 4000),
    ("pr1058-before", "ecdsa_sign", 7000),
    ("pr1058-after", "ecdsa_sign", 7000),
    ("pr1058-before", "ec_keygen", 7000),
    ("pr1058-after", "ec_keygen", 7000),
]


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    executables = {}
    for name, cfg in VARIANTS.items():
        print(f"[build] {name}", flush=True)
        executables[name] = build_variant(name, cfg)

    details = []
    summaries = []
    raw_sections = []
    for variant, operation, iterations in EXPERIMENTS:
        print(f"[bench] {variant} {operation}", flush=True)
        rows, raw = benchmark(executables[variant], operation, iterations, repeats=7)
        avgs = [row["avg_us"] for row in rows]
        median = statistics.median(avgs)
        abs_deviations = [abs(x - median) for x in avgs]
        for row in rows:
            details.append({
                "variant": variant,
                "commit": VARIANTS[variant]["commit"],
                "operation": operation,
                "iterations": iterations,
                **row,
            })
        summaries.append({
            "variant": variant,
            "commit": VARIANTS[variant]["commit"],
            "operation": operation,
            "iterations": iterations,
            "repeats": len(rows),
            "median_avg_us": median,
            "mad_avg_us": statistics.median(abs_deviations),
            "min_avg_us": min(avgs),
            "max_avg_us": max(avgs),
            "description": VARIANTS[variant]["description"],
        })
        raw_sections.append(f"===== {variant} / {operation} =====\n" + "\n".join(raw))

    for filename, rows in [("pr_benchmark_detail.csv", details), ("pr_benchmark_summary.csv", summaries)]:
        with (EVIDENCE / filename).open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    (EVIDENCE / "pr_benchmark_raw.txt").write_text("\n".join(raw_sections), encoding="utf-8")
    (EVIDENCE / "pr_benchmark_summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
