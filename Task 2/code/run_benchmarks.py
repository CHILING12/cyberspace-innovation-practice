from __future__ import annotations

import csv
import json
import os
import platform
import re
import statistics
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "data" / "repo"
BUILD = ROOT / "builds"
EVIDENCE = ROOT / "data"
GCC = Path(os.environ.get("CC", "gcc"))


VARIANTS = {
    "v0.4.0-asm": {
        "src": REPO / "v0_4_0",
        "defines": ["SECP256K1_STATIC", "USE_ASM_X86_64", "ECMULT_WINDOW_SIZE=15", "ECMULT_GEN_PREC_BITS=4"],
        "tag": "v0.4.0",
        "table_kib": 64,
    },
    "v0.4.1-c": {
        "src": REPO / "v0_4_1",
        "defines": ["SECP256K1_STATIC", "USE_ASM_X86_64", "ECMULT_WINDOW_SIZE=15", "ECMULT_GEN_PREC_BITS=4"],
        "tag": "v0.4.1",
        "table_kib": 64,
    },
    "v0.5.0-comb2": {
        "src": REPO / "v0_5_0",
        "defines": ["SECP256K1_STATIC", "USE_ASM_X86_64", "ECMULT_WINDOW_SIZE=15", "COMB_BLOCKS=2", "COMB_TEETH=5"],
        "tag": "v0.5.0",
        "table_kib": 2,
    },
    "v0.5.0-comb22": {
        "src": REPO / "v0_5_0",
        "defines": ["SECP256K1_STATIC", "USE_ASM_X86_64", "ECMULT_WINDOW_SIZE=15", "COMB_BLOCKS=11", "COMB_TEETH=6"],
        "tag": "v0.5.0",
        "table_kib": 22,
    },
    "v0.5.0-comb86": {
        "src": REPO / "v0_5_0",
        "defines": ["SECP256K1_STATIC", "USE_ASM_X86_64", "ECMULT_WINDOW_SIZE=15", "COMB_BLOCKS=43", "COMB_TEETH=6"],
        "tag": "v0.5.0",
        "table_kib": 86,
    },
}


EXPERIMENTS = [
    ("v0.4.0-asm", "ecdsa_verify", 2500),
    ("v0.4.1-c", "ecdsa_verify", 2500),
    ("v0.4.1-c", "ecdsa_sign", 5000),
    ("v0.4.1-c", "ec_keygen", 5000),
    ("v0.5.0-comb2", "ecdsa_sign", 5000),
    ("v0.5.0-comb2", "ec_keygen", 5000),
    ("v0.5.0-comb22", "ecdsa_sign", 5000),
    ("v0.5.0-comb22", "ec_keygen", 5000),
    ("v0.5.0-comb86", "ecdsa_sign", 5000),
    ("v0.5.0-comb86", "ec_keygen", 5000),
]


RESULT_RE = re.compile(
    r"^(?P<name>[a-zA-Z0-9_]+)\s*:\s*min\s+(?P<min>[0-9.]+)(?P<minunit>ns|us|ms)\s*/\s*avg\s+(?P<avg>[0-9.]+)(?P<avgunit>ns|us|ms)\s*/\s*max\s+(?P<max>[0-9.]+)(?P<maxunit>ns|us|ms)",
    re.MULTILINE,
)
CSV_RESULT_RE = re.compile(
    r"^(?P<name>[a-zA-Z0-9_]+)\s*,\s*(?P<min>[0-9.]+)\s*,\s*(?P<avg>[0-9.]+)\s*,\s*(?P<max>[0-9.]+)",
    re.MULTILINE,
)


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )


def to_us(value: float, unit: str) -> float:
    if unit == "ns":
        return value / 1000.0
    if unit == "ms":
        return value * 1000.0
    return value


def build_variant(name: str, cfg: dict) -> Path:
    src = Path(cfg["src"])
    out = BUILD / name
    out.mkdir(parents=True, exist_ok=True)
    defs = [f"-D{x}" for x in cfg["defines"]]
    base = [
        str(GCC), "-O2", "-std=c90", "-fno-omit-frame-pointer",
        f"-I{src}", f"-I{src / 'include'}", f"-I{src / 'src'}", *defs,
    ]
    objects = []
    for source_name in ["secp256k1.c", "precomputed_ecmult.c", "precomputed_ecmult_gen.c"]:
        obj = out / (Path(source_name).stem + ".o")
        result = run(base + ["-c", str(src / "src" / source_name), "-o", str(obj)])
        (out / f"compile-{Path(source_name).stem}.log").write_text(result.stdout, encoding="utf-8")
        objects.append(obj)
    exe = out / "bench.exe"
    result = run(base + [str(src / "src" / "bench.c"), *map(str, objects), "-o", str(exe)])
    (out / "link.log").write_text(result.stdout, encoding="utf-8")
    return exe


def benchmark(exe: Path, operation: str, iterations: int, repeats: int = 5) -> tuple[list[dict], list[str]]:
    rows = []
    raw = []
    env = os.environ.copy()
    env["SECP256K1_BENCH_ITERS"] = str(iterations)
    for repeat in range(1, repeats + 1):
        started = time.perf_counter()
        result = run([str(exe), operation], cwd=exe.parent, env=env)
        elapsed = time.perf_counter() - started
        raw.append(f"--- repeat {repeat}; wall={elapsed:.3f}s ---\n{result.stdout.rstrip()}\n")
        match = RESULT_RE.search(result.stdout)
        csv_match = CSV_RESULT_RE.search(result.stdout) if not match else None
        if not match and not csv_match:
            raise RuntimeError(f"Could not parse benchmark output for {exe} {operation}:\n{result.stdout}")
        if csv_match:
            values = {
                "min_us": float(csv_match.group("min")),
                "avg_us": float(csv_match.group("avg")),
                "max_us": float(csv_match.group("max")),
            }
        else:
            values = {
                "min_us": to_us(float(match.group("min")), match.group("minunit")),
                "avg_us": to_us(float(match.group("avg")), match.group("avgunit")),
                "max_us": to_us(float(match.group("max")), match.group("maxunit")),
            }
        rows.append({
            "repeat": repeat,
            **values,
            "wall_s": elapsed,
        })
    return rows, raw


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    metadata = {
        "timestamp_local": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
        "gcc": run([str(GCC), "--version"]).stdout.splitlines()[0],
        "compiler_flags": "-O2 -std=c90 -fno-omit-frame-pointer",
        "repeats": 5,
        "note": "Manual GCC build used because CMake was unavailable; all paired comparisons use identical compiler and flags.",
    }
    executables = {}
    for name, cfg in VARIANTS.items():
        print(f"[build] {name}", flush=True)
        executables[name] = build_variant(name, cfg)

    detail_rows = []
    summary_rows = []
    raw_sections = []
    for variant, operation, iterations in EXPERIMENTS:
        print(f"[bench] {variant} {operation}", flush=True)
        rows, raw = benchmark(executables[variant], operation, iterations)
        for row in rows:
            detail_rows.append({
                "variant": variant,
                "tag": VARIANTS[variant]["tag"],
                "table_kib": VARIANTS[variant]["table_kib"],
                "operation": operation,
                "iterations": iterations,
                **row,
            })
        avgs = [r["avg_us"] for r in rows]
        summary_rows.append({
            "variant": variant,
            "tag": VARIANTS[variant]["tag"],
            "table_kib": VARIANTS[variant]["table_kib"],
            "operation": operation,
            "iterations": iterations,
            "repeats": len(rows),
            "median_avg_us": statistics.median(avgs),
            "mean_avg_us": statistics.mean(avgs),
            "stdev_avg_us": statistics.stdev(avgs),
            "min_avg_us": min(avgs),
            "max_avg_us": max(avgs),
        })
        raw_sections.append(f"===== {variant} / {operation} =====\n" + "\n".join(raw))

    for filename, rows in [("benchmark_detail.csv", detail_rows), ("benchmark_summary.csv", summary_rows)]:
        with (EVIDENCE / filename).open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    (EVIDENCE / "benchmark_raw.txt").write_text("\n".join(raw_sections), encoding="utf-8")
    (EVIDENCE / "environment.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary_rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
