"""Analyze rotation complexity for TenSEAL CKKS im2col convolution.

The numerical outputs, serialized sizes, and timings are measured at runtime.
Rotation counts are derived from TenSEAL's deterministic
``enc_matmul_plain_inplace`` rotate-and-add loop; they are not collected by
instrumenting Microsoft SEAL's evaluator.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
TASK5_CODE_DIR = SCRIPT_DIR.parents[1] / "task5" / "code"
if not TASK5_CODE_DIR.is_dir():
    raise RuntimeError(f"Task 5 code directory not found: {TASK5_CODE_DIR}")
sys.path.insert(0, str(TASK5_CODE_DIR))

try:
    import tenseal as ts
except (ImportError, ModuleNotFoundError) as exc:
    raise RuntimeError(
        "TenSEAL could not be imported. On Windows, run this project with "
        "'py -3.13' and install code/requirements.txt for that interpreter. "
        f"Current interpreter: {sys.version.split()[0]}"
    ) from exc

from fhe_convolution import (  # noqa: E402
    CKKSParameters,
    DEFAULT_INPUT,
    DEFAULT_KERNEL,
    client_decrypt_output,
    client_encrypt_im2col,
    create_client_context,
    load_server_context,
    plaintext_valid_convolution,
    serialize_evaluation_context,
    server_encrypted_convolution,
)


Matrix = list[list[float]]
ROTATION_SOURCE_URL = (
    "https://github.com/OpenMined/TenSEAL/blob/main/"
    "tenseal/cpp/tensors/ckksvector.cpp"
)


def flatten(matrix: Sequence[Sequence[float]]) -> list[float]:
    """Return a row-major floating-point copy of a matrix."""
    return [float(value) for row in matrix for value in row]


def next_power_of_two(value: int) -> int:
    """Return the smallest power of two greater than or equal to ``value``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("value must be an integer")
    if value <= 0:
        raise ValueError("value must be positive")
    return 1 << (value - 1).bit_length()


def rotation_plan(term_count: int, windows: int) -> dict[str, Any]:
    """Derive TenSEAL's deterministic binary rotate-and-add plan.

    The lower bound only applies to this single-ciphertext reduction model:
    each rotation is followed by an addition to the current accumulator, so
    one stage can at most double the number of contributing terms.
    """
    if isinstance(term_count, bool) or not isinstance(term_count, int):
        raise TypeError("term_count must be an integer")
    if isinstance(windows, bool) or not isinstance(windows, int):
        raise TypeError("windows must be an integer")
    if term_count <= 0:
        raise ValueError("term_count must be positive")
    if windows <= 0:
        raise ValueError("windows must be positive")

    padded_terms = next_power_of_two(term_count)
    chunks = padded_terms
    rotation_steps: list[int] = []
    while chunks > 1:
        chunks //= 2
        rotation_steps.append(windows * chunks)

    lower_bound = math.ceil(math.log2(term_count)) if term_count > 1 else 0
    derived_count = len(rotation_steps)
    return {
        "model": "single-ciphertext binary rotate-and-add reduction",
        "original_terms": term_count,
        "padded_terms": padded_terms,
        "windows": windows,
        "logical_packed_slots": windows * padded_terms,
        "rotation_steps": rotation_steps,
        "implementation_derived_rotation_count": derived_count,
        "model_lower_bound": lower_bound,
        "meets_model_lower_bound": derived_count == lower_bound,
        "runtime_instrumented": False,
        "evidence_note": (
            "Count derived from TenSEAL's deterministic "
            "enc_matmul_plain_inplace loop, not from an evaluator hook."
        ),
        "source_url": ROTATION_SOURCE_URL,
    }


def build_im2col_matrix(
    image: Sequence[Sequence[float]],
    kernel_rows: int = 3,
    kernel_cols: int = 3,
    stride: int = 1,
) -> Matrix:
    """Build the valid-convolution im2col matrix in row-major window order."""
    if kernel_rows <= 0 or kernel_cols <= 0 or stride <= 0:
        raise ValueError("kernel dimensions and stride must be positive")
    if not image or not image[0]:
        raise ValueError("image must not be empty")
    width = len(image[0])
    if any(len(row) != width for row in image):
        raise ValueError("image rows must have equal length")
    height = len(image)
    if kernel_rows > height or kernel_cols > width:
        raise ValueError("kernel must fit inside image")

    output_rows = 1 + (height - kernel_rows) // stride
    output_cols = 1 + (width - kernel_cols) // stride
    windows: Matrix = []
    for output_row in range(output_rows):
        for output_col in range(output_cols):
            window: list[float] = []
            row_start = output_row * stride
            col_start = output_col * stride
            for kernel_row in range(kernel_rows):
                for kernel_col in range(kernel_cols):
                    window.append(
                        float(
                            image[row_start + kernel_row]
                            [col_start + kernel_col]
                        )
                    )
            windows.append(window)
    return windows


def decrypt_vector(
    client_context: ts.Context,
    encrypted_output: bytes,
    output_count: int,
) -> list[float]:
    values = ts.ckks_vector_from(client_context, encrypted_output).decrypt()
    if len(values) < output_count:
        raise RuntimeError(
            f"decrypted vector has {len(values)} values; "
            f"expected at least {output_count}"
        )
    return [float(value) for value in values[:output_count]]


def _timing_summary(values: Sequence[float]) -> dict[str, float]:
    if not values:
        raise ValueError("timing sample must not be empty")
    return {
        "mean_ms": statistics.fmean(values),
        "median_ms": statistics.median(values),
        "min_ms": min(values),
        "max_ms": max(values),
        "stdev_ms": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def _integer_summary(values: Sequence[int]) -> dict[str, float | int]:
    if not values:
        raise ValueError("size sample must not be empty")
    return {
        "median_bytes": statistics.median(values),
        "min_bytes": min(values),
        "max_bytes": max(values),
    }


def _relative_reduction(before: float, after: float) -> float:
    if before <= 0:
        raise ValueError("baseline must be positive")
    return (before - after) / before


def _generic_trial(
    client_context: ts.Context,
    server_context: ts.Context,
    expected: Matrix,
) -> dict[str, Any]:
    start = time.perf_counter_ns()
    encrypted_input, windows, logical_size = client_encrypt_im2col(
        client_context,
        DEFAULT_INPUT,
    )
    encode_ms = (time.perf_counter_ns() - start) / 1_000_000

    start = time.perf_counter_ns()
    encrypted_output = server_encrypted_convolution(
        server_context,
        encrypted_input,
        DEFAULT_KERNEL,
        windows,
    )
    evaluate_ms = (time.perf_counter_ns() - start) / 1_000_000

    start = time.perf_counter_ns()
    decrypted = client_decrypt_output(
        client_context,
        encrypted_output,
        windows,
    )
    decrypt_ms = (time.perf_counter_ns() - start) / 1_000_000

    errors = [
        abs(actual - reference)
        for actual, reference in zip(flatten(decrypted), flatten(expected))
    ]
    return {
        "logical_packed_slots": logical_size,
        "input_ciphertext_bytes": len(encrypted_input),
        "output_ciphertext_bytes": len(encrypted_output),
        "input_ciphertext_sha256": hashlib.sha256(encrypted_input).hexdigest(),
        "decrypted_output": decrypted,
        "maximum_absolute_error": max(errors),
        "mean_absolute_error": statistics.fmean(errors),
        "timing_ms": {
            "client_encode_encrypt_serialize": encode_ms,
            "server_load_evaluate_serialize": evaluate_ms,
            "client_load_decrypt": decrypt_ms,
        },
    }


def _sparse_trial(
    client_context: ts.Context,
    server_context: ts.Context,
    sparse_matrix: Matrix,
    active_weights: list[float],
    expected: Matrix,
) -> dict[str, Any]:
    windows = len(sparse_matrix)
    start = time.perf_counter_ns()
    encrypted_vector = ts.enc_matmul_encoding(client_context, sparse_matrix)
    encrypted_input = encrypted_vector.serialize()
    logical_size = encrypted_vector.size()
    encode_ms = (time.perf_counter_ns() - start) / 1_000_000

    start = time.perf_counter_ns()
    server_vector = ts.ckks_vector_from(server_context, encrypted_input)
    encrypted_result = server_vector.enc_matmul_plain(active_weights, windows)
    encrypted_output = encrypted_result.serialize()
    evaluate_ms = (time.perf_counter_ns() - start) / 1_000_000

    start = time.perf_counter_ns()
    decrypted_flat = decrypt_vector(
        client_context,
        encrypted_output,
        windows,
    )
    decrypt_ms = (time.perf_counter_ns() - start) / 1_000_000
    decrypted = [decrypted_flat[:2], decrypted_flat[2:4]]
    errors = [
        abs(actual - reference)
        for actual, reference in zip(decrypted_flat, flatten(expected))
    ]
    return {
        "logical_packed_slots": logical_size,
        "input_ciphertext_bytes": len(encrypted_input),
        "output_ciphertext_bytes": len(encrypted_output),
        "input_ciphertext_sha256": hashlib.sha256(encrypted_input).hexdigest(),
        "decrypted_output": decrypted,
        "maximum_absolute_error": max(errors),
        "mean_absolute_error": statistics.fmean(errors),
        "timing_ms": {
            "client_encode_encrypt_serialize": encode_ms,
            "server_load_evaluate_serialize": evaluate_ms,
            "client_load_decrypt": decrypt_ms,
        },
    }


def _aggregate_scenario(
    *,
    name: str,
    packing_method: str,
    plan: dict[str, Any],
    trials: list[dict[str, Any]],
    expected: Matrix,
    tolerance: float,
) -> dict[str, Any]:
    max_errors = [trial["maximum_absolute_error"] for trial in trials]
    mean_errors = [trial["mean_absolute_error"] for trial in trials]
    input_sizes = [trial["input_ciphertext_bytes"] for trial in trials]
    output_sizes = [trial["output_ciphertext_bytes"] for trial in trials]
    hashes = [trial["input_ciphertext_sha256"] for trial in trials]
    timings = {
        key: _timing_summary(
            [trial["timing_ms"][key] for trial in trials]
        )
        for key in trials[0]["timing_ms"]
    }
    return {
        "name": name,
        "packing_method": packing_method,
        "logical_packed_slots": trials[0]["logical_packed_slots"],
        "physical_ciphertext_count": 1,
        "rotation_analysis": plan,
        "expected_output": expected,
        "last_decrypted_output": trials[-1]["decrypted_output"],
        "verification": {
            "trials": len(trials),
            "absolute_error_tolerance": tolerance,
            "maximum_absolute_error_all_trials": max(max_errors),
            "mean_of_trial_mean_absolute_errors": statistics.fmean(mean_errors),
            "all_trials_within_tolerance": all(
                error <= tolerance for error in max_errors
            ),
            "unique_input_ciphertexts": len(set(hashes)),
            "ciphertexts_randomized_across_trials": (
                len(set(hashes)) == len(hashes)
            ),
        },
        "serialized_sizes": {
            "input_ciphertext": _integer_summary(input_sizes),
            "output_ciphertext": _integer_summary(output_sizes),
        },
        "timing": timings,
        "trials_data": trials,
    }


def run_experiment(
    trials: int = 5,
    tolerance: float = 1e-3,
) -> dict[str, Any]:
    """Run repeated generic and sparse numerical experiments."""
    if isinstance(trials, bool) or not isinstance(trials, int):
        raise TypeError("trials must be an integer")
    if trials < 2:
        raise ValueError("at least two trials are required")
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("tolerance must be a positive finite number")

    expected = plaintext_valid_convolution(DEFAULT_INPUT, DEFAULT_KERNEL)
    im2col_matrix = build_im2col_matrix(DEFAULT_INPUT)
    kernel_flat = flatten(DEFAULT_KERNEL)
    active_indices = [
        index for index, weight in enumerate(kernel_flat) if weight != 0.0
    ]
    active_weights = [kernel_flat[index] for index in active_indices]
    sparse_matrix = [
        [window[index] for index in active_indices]
        for window in im2col_matrix
    ]
    windows = len(im2col_matrix)

    parameters = CKKSParameters()
    start = time.perf_counter_ns()
    client_context = create_client_context(parameters)
    evaluation_context = serialize_evaluation_context(client_context)
    server_context = load_server_context(evaluation_context)
    context_setup_ms = (time.perf_counter_ns() - start) / 1_000_000
    if server_context.has_secret_key() or server_context.is_private():
        raise RuntimeError("server context unexpectedly contains a secret key")

    generic_trials: list[dict[str, Any]] = []
    sparse_trials: list[dict[str, Any]] = []
    for _ in range(trials):
        generic_trials.append(
            _generic_trial(client_context, server_context, expected)
        )
        sparse_trials.append(
            _sparse_trial(
                client_context,
                server_context,
                sparse_matrix,
                active_weights,
                expected,
            )
        )

    generic = _aggregate_scenario(
        name="generic_3x3_im2col",
        packing_method="im2col_encoding + conv2d_im2col",
        plan=rotation_plan(term_count=len(kernel_flat), windows=windows),
        trials=generic_trials,
        expected=expected,
        tolerance=tolerance,
    )
    sparse = _aggregate_scenario(
        name="fixed_sparse_kernel",
        packing_method=(
            "remove zero kernel positions + "
            "enc_matmul_encoding + enc_matmul_plain"
        ),
        plan=rotation_plan(term_count=len(active_weights), windows=windows),
        trials=sparse_trials,
        expected=expected,
        tolerance=tolerance,
    )
    sparse["active_kernel_indices_zero_based"] = active_indices
    sparse["active_kernel_weights"] = active_weights

    generic_input_median = float(
        generic["serialized_sizes"]["input_ciphertext"]["median_bytes"]
    )
    sparse_input_median = float(
        sparse["serialized_sizes"]["input_ciphertext"]["median_bytes"]
    )
    generic_eval_median = generic["timing"][
        "server_load_evaluate_serialize"
    ]["median_ms"]
    sparse_eval_median = sparse["timing"][
        "server_load_evaluate_serialize"
    ]["median_ms"]

    result = {
        "schema_version": 2,
        "assignment": "rotation minimization for encrypted convolution",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "tenseal": ts.__version__,
        },
        "scheme": "CKKS",
        "parameters": {
            **asdict(parameters),
            "coeff_mod_bit_sizes": list(parameters.coeff_mod_bit_sizes),
            "global_scale": f"2^{parameters.global_scale_bits}",
            "physical_slot_capacity": parameters.poly_modulus_degree // 2,
        },
        "methodology": {
            "measured_at_runtime": [
                "decrypted numerical output",
                "absolute error",
                "serialized byte size",
                "wall-clock timing",
                "ciphertext randomization",
            ],
            "source_derived": [
                "rotation steps",
                "rotation count",
                "binary-reduction lower bound",
            ],
            "rotation_runtime_instrumented": False,
            "scope": (
                "Optimality is claimed only for TenSEAL's current "
                "single-ciphertext binary rotate-and-add reduction model."
            ),
        },
        "context_setup_ms": context_setup_ms,
        "server_evaluation_context_bytes": len(evaluation_context),
        "key_separation": {
            "client_has_secret_key": client_context.has_secret_key(),
            "server_has_secret_key": server_context.has_secret_key(),
            "server_context_is_private": server_context.is_private(),
        },
        "generic": generic,
        "sparse": sparse,
        "comparison": {
            "logical_packed_slot_reduction_fraction": _relative_reduction(
                generic["logical_packed_slots"],
                sparse["logical_packed_slots"],
            ),
            "derived_rotation_reduction_fraction": _relative_reduction(
                generic["rotation_analysis"][
                    "implementation_derived_rotation_count"
                ],
                sparse["rotation_analysis"][
                    "implementation_derived_rotation_count"
                ],
            ),
            "median_serialized_input_byte_reduction_fraction": (
                _relative_reduction(
                    generic_input_median,
                    sparse_input_median,
                )
            ),
            "median_server_evaluation_time_reduction_fraction": (
                _relative_reduction(
                    generic_eval_median,
                    sparse_eval_median,
                )
            ),
            "physical_ciphertext_count_changed": False,
        },
        "conclusion": {
            "generic_meets_scoped_model_lower_bound": generic[
                "rotation_analysis"
            ]["meets_model_lower_bound"],
            "sparse_meets_scoped_model_lower_bound": sparse[
                "rotation_analysis"
            ]["meets_model_lower_bound"],
            "all_numerical_trials_pass": (
                generic["verification"]["all_trials_within_tolerance"]
                and sparse["verification"]["all_trials_within_tolerance"]
            ),
            "storage_halved": False,
            "storage_note": (
                "Logical packed slots fall from 64 to 32, but both inputs "
                "remain one CKKS ciphertext; serialized bytes must be "
                "reported separately."
            ),
        },
    }
    return result


def print_result(result: dict[str, Any]) -> None:
    generic = result["generic"]
    sparse = result["sparse"]
    comparison = result["comparison"]

    print("CKKS ROTATION ANALYSIS")
    print("======================")
    print(
        f"runtime: Python {result['environment']['python']}, "
        f"TenSEAL {result['environment']['tenseal']}"
    )
    for title, scenario in (
        ("Generic 3x3 convolution", generic),
        ("Sparse fixed-kernel convolution", sparse),
    ):
        plan = scenario["rotation_analysis"]
        verification = scenario["verification"]
        input_size = scenario["serialized_sizes"]["input_ciphertext"]
        timing = scenario["timing"]["server_load_evaluate_serialize"]
        print(f"\n[{title}]")
        print(f"logical packed slots : {scenario['logical_packed_slots']}")
        print(f"physical ciphertexts : {scenario['physical_ciphertext_count']}")
        print(f"derived rotation steps: {plan['rotation_steps']}")
        print(
            "derived rotations    :",
            plan["implementation_derived_rotation_count"],
        )
        print(f"model lower bound    : {plan['model_lower_bound']}")
        print(
            "max error (all trials):",
            f"{verification['maximum_absolute_error_all_trials']:.6e}",
        )
        print(
            "median input bytes   :",
            f"{input_size['median_bytes']:,.0f}",
        )
        print(
            "median server time ms:",
            f"{timing['median_ms']:.3f}",
        )

    print("\n[Comparison]")
    print(
        "logical slot reduction:",
        f"{comparison['logical_packed_slot_reduction_fraction']:.1%}",
    )
    print(
        "rotation reduction    :",
        f"{comparison['derived_rotation_reduction_fraction']:.1%}",
    )
    print(
        "serialized-byte change:",
        f"{comparison['median_serialized_input_byte_reduction_fraction']:.1%}",
        "reduction",
    )
    print(
        "server-time change    :",
        f"{comparison['median_server_evaluation_time_reduction_fraction']:.1%}",
        "reduction",
    )
    print("rotation count source : implementation-derived, not instrumented")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trials",
        type=int,
        default=5,
        help="number of randomized trials per scenario (default: 5)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-3,
        help="maximum accepted absolute error (default: 1e-3)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=SCRIPT_DIR / "output" / "rotation_experiment_results.json",
        help="JSON evidence path",
    )
    args = parser.parse_args()

    result = run_experiment(trials=args.trials, tolerance=args.tolerance)
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print_result(result)
    print(f"\nEvidence JSON: {output_path}")
    if not result["conclusion"]["all_numerical_trials_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
