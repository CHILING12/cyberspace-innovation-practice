from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "data" / "repo"
BUILD = ROOT / "builds"
OUT = ROOT / "data"
GCC = Path(os.environ.get("CC", "gcc"))

VARIANTS = {
    "pr1446-before": (
        REPO / "pr1446_before",
        [
            "SECP256K1_STATIC",
            "USE_ASM_X86_64",
            "ECMULT_WINDOW_SIZE=15",
            "ECMULT_GEN_PREC_BITS=4",
        ],
    ),
    "pr1446-after": (
        REPO / "pr1446_after",
        [
            "SECP256K1_STATIC",
            "USE_ASM_X86_64",
            "ECMULT_WINDOW_SIZE=15",
            "ECMULT_GEN_PREC_BITS=4",
        ],
    ),
    "pr1058-before": (
        REPO / "pr1058_before",
        [
            "SECP256K1_STATIC",
            "USE_ASM_X86_64",
            "ECMULT_WINDOW_SIZE=15",
            "ECMULT_GEN_PREC_BITS=4",
        ],
    ),
    "pr1058-after": (
        REPO / "pr1058_after",
        [
            "SECP256K1_STATIC",
            "USE_ASM_X86_64",
            "ECMULT_WINDOW_SIZE=15",
            "COMB_BLOCKS=11",
            "COMB_TEETH=6",
        ],
    ),
}


def run_variant(name: str, source_root: Path, defines: list[str]) -> str:
    output_dir = BUILD / name
    executable = output_dir / "tests-default-all.exe"
    command = [
        str(GCC),
        "-O2",
        "-std=c90",
        "-fno-omit-frame-pointer",
        "-DVERIFY",
        *[f"-D{define}" for define in defines],
        f"-I{source_root}",
        f"-I{source_root / 'include'}",
        f"-I{source_root / 'src'}",
        str(source_root / "src" / "tests.c"),
        str(output_dir / "precomputed_ecmult.o"),
        str(output_dir / "precomputed_ecmult_gen.o"),
        "-o",
        str(executable),
    ]
    built = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    environment = os.environ.copy()
    environment.pop("SECP256K1_TEST_ITERS", None)
    started = time.perf_counter()
    tested = subprocess.run(
        [str(executable)],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=environment,
        check=False,
    )
    elapsed = time.perf_counter() - started
    return "\n".join(
        [
            f"===== {name} =====",
            "command: " + subprocess.list2cmdline(command),
            "SECP256K1_TEST_ITERS: unset (upstream default)",
            f"compile_exit_code: {built.returncode}",
            f"test_exit_code: {tested.returncode}",
            f"wall_s: {elapsed:.3f}",
            built.stdout.rstrip(),
            tested.stdout.rstrip(),
            "",
        ]
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sections = []
    for name, (source_root, defines) in VARIANTS.items():
        print(f"[default-test] {name}", flush=True)
        section = run_variant(name, source_root, defines)
        print(section.splitlines()[-2] if section.splitlines() else "", flush=True)
        sections.append(section)
    output = OUT / "default_tests_all_four_versions.txt"
    output.write_text("\n".join(sections), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
