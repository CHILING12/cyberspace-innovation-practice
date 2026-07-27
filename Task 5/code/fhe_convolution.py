"""Single-channel encrypted 2-D convolution with TenSEAL CKKS.

The client owns the secret key. The server receives only a public evaluation
context, an encrypted im2col representation of the input, and a plaintext
kernel. It returns an encrypted 2 x 2 output for client-side decryption.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Sequence

import tenseal as ts


Matrix = list[list[float]]

DEFAULT_INPUT: Matrix = [
    [1.0, 2.0, 3.0, 4.0],
    [5.0, 6.0, 7.0, 8.0],
    [9.0, 10.0, 11.0, 12.0],
    [13.0, 14.0, 15.0, 16.0],
]

DEFAULT_KERNEL: Matrix = [
    [1.0, -1.0, 2.0],
    [0.0, 3.0, -2.0],
    [2.0, 1.0, -1.0],
]


@dataclass(frozen=True)
class CKKSParameters:
    poly_modulus_degree: int = 8192
    coeff_mod_bit_sizes: tuple[int, ...] = (60, 40, 40, 60)
    global_scale_bits: int = 40
    target_security_level_bits: int = 128

    @property
    def total_coeff_modulus_bits(self) -> int:
        return sum(self.coeff_mod_bit_sizes)


def _validate_matrix(matrix: Sequence[Sequence[float]], rows: int, cols: int, name: str) -> None:
    if len(matrix) != rows or any(len(row) != cols for row in matrix):
        raise ValueError(f"{name} must have shape {rows}x{cols}")
    for row in matrix:
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} entries must be real numbers")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} entries must be finite")


def plaintext_valid_convolution(
    image: Sequence[Sequence[float]],
    kernel: Sequence[Sequence[float]],
    stride: int = 1,
) -> Matrix:
    """Return mathematical cross-correlation, as used by CNN Conv2D layers."""
    if stride != 1:
        raise ValueError("this assignment requires stride=1")
    _validate_matrix(image, 4, 4, "image")
    _validate_matrix(kernel, 3, 3, "kernel")

    output: Matrix = []
    for out_row in range(2):
        row: list[float] = []
        for out_col in range(2):
            value = 0.0
            for kernel_row in range(3):
                for kernel_col in range(3):
                    value += (
                        float(image[out_row + kernel_row][out_col + kernel_col])
                        * float(kernel[kernel_row][kernel_col])
                    )
            row.append(value)
        output.append(row)
    return output


def create_client_context(parameters: CKKSParameters) -> ts.Context:
    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=parameters.poly_modulus_degree,
        coeff_mod_bit_sizes=list(parameters.coeff_mod_bit_sizes),
    )
    context.global_scale = 2**parameters.global_scale_bits
    context.generate_galois_keys()
    if not context.is_private() or not context.has_secret_key():
        raise RuntimeError("client context unexpectedly lacks the secret key")
    return context


def serialize_evaluation_context(client_context: ts.Context) -> bytes:
    """Serialize public/evaluation material while explicitly excluding sk."""
    return client_context.serialize(
        save_public_key=True,
        save_secret_key=False,
        save_galois_keys=True,
        save_relin_keys=True,
    )


def load_server_context(serialized_context: bytes) -> ts.Context:
    context = ts.context_from(serialized_context)
    if context.is_private() or context.has_secret_key():
        raise RuntimeError("server context must not contain the secret key")
    return context


def client_encrypt_im2col(
    client_context: ts.Context,
    image: Sequence[Sequence[float]],
) -> tuple[bytes, int, int]:
    _validate_matrix(image, 4, 4, "image")
    encrypted, windows = ts.im2col_encoding(client_context, image, 3, 3, 1)
    if windows != 4:
        raise RuntimeError(f"expected four valid windows, got {windows}")
    return encrypted.serialize(), windows, encrypted.size()


def server_encrypted_convolution(
    server_context: ts.Context,
    encrypted_input: bytes,
    kernel: Sequence[Sequence[float]],
    windows: int,
) -> bytes:
    if server_context.is_private() or server_context.has_secret_key():
        raise RuntimeError("refusing to evaluate with a secret-bearing server context")
    _validate_matrix(kernel, 3, 3, "kernel")
    encrypted = ts.ckks_vector_from(server_context, encrypted_input)
    result = encrypted.conv2d_im2col(kernel, windows)
    return result.serialize()


def client_decrypt_output(
    client_context: ts.Context,
    encrypted_output: bytes,
    windows: int,
) -> Matrix:
    if not client_context.has_secret_key():
        raise RuntimeError("client context must contain the secret key")
    values = ts.ckks_vector_from(client_context, encrypted_output).decrypt()
    if len(values) < windows:
        raise RuntimeError("decrypted vector is shorter than the output window count")
    values = [float(value) for value in values[:windows]]
    return [values[:2], values[2:4]]


def _flatten(matrix: Sequence[Sequence[float]]) -> list[float]:
    return [float(value) for row in matrix for value in row]


def _timing_summary(values: Sequence[float]) -> dict[str, float]:
    return {
        "mean_ms": statistics.fmean(values),
        "median_ms": statistics.median(values),
        "min_ms": min(values),
        "max_ms": max(values),
        "stdev_ms": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def run_experiment(
    trials: int = 10,
    tolerance: float = 1e-3,
    image: Sequence[Sequence[float]] = DEFAULT_INPUT,
    kernel: Sequence[Sequence[float]] = DEFAULT_KERNEL,
) -> dict[str, object]:
    if trials < 2:
        raise ValueError("at least two trials are required to test randomized encryption")
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    _validate_matrix(image, 4, 4, "image")
    _validate_matrix(kernel, 3, 3, "kernel")

    parameters = CKKSParameters()
    context_start = time.perf_counter_ns()
    client_context = create_client_context(parameters)
    evaluation_context_bytes = serialize_evaluation_context(client_context)
    server_context = load_server_context(evaluation_context_bytes)
    context_setup_ms = (time.perf_counter_ns() - context_start) / 1_000_000

    secret_context_bytes = client_context.serialize(
        save_public_key=True,
        save_secret_key=True,
        save_galois_keys=True,
        save_relin_keys=True,
    )
    expected = plaintext_valid_convolution(image, kernel)
    expected_flat = _flatten(expected)

    trial_records: list[dict[str, object]] = []
    encryption_times: list[float] = []
    evaluation_times: list[float] = []
    decryption_times: list[float] = []
    input_hashes: list[str] = []
    all_errors: list[float] = []
    last_decrypted: Matrix | None = None
    input_ciphertext_size = 0
    output_ciphertext_size = 0
    encoded_slot_count = 0

    for trial in range(1, trials + 1):
        start = time.perf_counter_ns()
        encrypted_input, windows, encoded_slot_count = client_encrypt_im2col(client_context, image)
        encryption_ms = (time.perf_counter_ns() - start) / 1_000_000

        start = time.perf_counter_ns()
        encrypted_output = server_encrypted_convolution(
            server_context,
            encrypted_input,
            kernel,
            windows,
        )
        evaluation_ms = (time.perf_counter_ns() - start) / 1_000_000

        start = time.perf_counter_ns()
        decrypted = client_decrypt_output(client_context, encrypted_output, windows)
        decryption_ms = (time.perf_counter_ns() - start) / 1_000_000

        decrypted_flat = _flatten(decrypted)
        errors = [abs(actual - reference) for actual, reference in zip(decrypted_flat, expected_flat)]
        max_error = max(errors)
        all_errors.extend(errors)
        last_decrypted = decrypted
        input_ciphertext_size = len(encrypted_input)
        output_ciphertext_size = len(encrypted_output)
        digest = hashlib.sha256(encrypted_input).hexdigest()
        input_hashes.append(digest)
        encryption_times.append(encryption_ms)
        evaluation_times.append(evaluation_ms)
        decryption_times.append(decryption_ms)
        trial_records.append(
            {
                "trial": trial,
                "input_ciphertext_sha256": digest,
                "decrypted_output": decrypted,
                "max_absolute_error": max_error,
                "within_tolerance": max_error <= tolerance,
                "timing_ms": {
                    "client_encrypt_and_serialize": encryption_ms,
                    "server_load_evaluate_and_serialize": evaluation_ms,
                    "client_load_and_decrypt": decryption_ms,
                },
            }
        )

    assert last_decrypted is not None
    ciphertexts_are_randomized = len(set(input_hashes)) == len(input_hashes)
    max_absolute_error = max(all_errors)
    result: dict[str, object] = {
        "assignment": "single-input single-output 4x4 encrypted convolution with a 3x3 kernel",
        "library": {"name": "TenSEAL", "version": ts.__version__, "backend": "Microsoft SEAL"},
        "runtime": {"python": sys.version.split()[0], "platform": platform.platform()},
        "scheme": "CKKS",
        "parameters": {
            **asdict(parameters),
            "coeff_mod_bit_sizes": list(parameters.coeff_mod_bit_sizes),
            "total_coeff_modulus_bits": parameters.total_coeff_modulus_bits,
            "global_scale": f"2^{parameters.global_scale_bits}",
        },
        "convolution": {
            "input_shape": [1, 1, 4, 4],
            "kernel_shape": [1, 1, 3, 3],
            "output_shape": [1, 1, 2, 2],
            "stride": 1,
            "padding": 0,
            "operation_semantics": "cross-correlation (CNN Conv2D convention; kernel is not flipped)",
            "input": [[float(value) for value in row] for row in image],
            "kernel": [[float(value) for value in row] for row in kernel],
            "plaintext_reference": expected,
            "decrypted_output": last_decrypted,
        },
        "packing": {
            "method": "TenSEAL im2col_encoding + conv2d_im2col",
            "valid_windows": 4,
            "encrypted_vector_size": encoded_slot_count,
            "logical_output_slots": 4,
        },
        "key_separation": {
            "client_has_secret_key": client_context.has_secret_key(),
            "server_has_secret_key": server_context.has_secret_key(),
            "server_context_is_private": server_context.is_private(),
            "server_context_is_public": server_context.is_public(),
            "evaluation_context_excludes_secret_key": not server_context.has_secret_key(),
        },
        "serialized_sizes_bytes": {
            "client_private_context_serialization": len(secret_context_bytes),
            "server_public_evaluation_context": len(evaluation_context_bytes),
            "encrypted_im2col_input": input_ciphertext_size,
            "encrypted_output": output_ciphertext_size,
            "plaintext_input_payload": 16 * 8,
            "plaintext_output_payload": 4 * 8,
        },
        "verification": {
            "trials": trials,
            "absolute_error_tolerance": tolerance,
            "maximum_absolute_error_all_trials": max_absolute_error,
            "mean_absolute_error_all_slots": statistics.fmean(all_errors),
            "all_trials_within_tolerance": all(record["within_tolerance"] for record in trial_records),
            "ciphertexts_are_randomized": ciphertexts_are_randomized,
            "unique_input_ciphertexts": len(set(input_hashes)),
            "result_correct": max_absolute_error <= tolerance and ciphertexts_are_randomized,
        },
        "timing": {
            "context_and_key_setup_ms": context_setup_ms,
            "client_encrypt_and_serialize": _timing_summary(encryption_times),
            "server_load_evaluate_and_serialize": _timing_summary(evaluation_times),
            "client_load_and_decrypt": _timing_summary(decryption_times),
        },
        "trials": trial_records,
    }
    return result


def _print_summary(result: dict[str, object]) -> None:
    convolution = result["convolution"]
    verification = result["verification"]
    sizes = result["serialized_sizes_bytes"]
    timing = result["timing"]
    key_separation = result["key_separation"]
    print("TEN SEAL CKKS ENCRYPTED CONVOLUTION")
    print("====================================")
    print(f"input shape   : {convolution['input_shape']}")
    print(f"kernel shape  : {convolution['kernel_shape']}")
    print(f"output shape  : {convolution['output_shape']}")
    print(f"stride/padding: {convolution['stride']}/{convolution['padding']}")
    print(f"plain result  : {convolution['plaintext_reference']}")
    print(f"decrypt result: {convolution['decrypted_output']}")
    print(f"max abs error : {verification['maximum_absolute_error_all_trials']:.9e}")
    print(f"tolerance     : {verification['absolute_error_tolerance']:.1e}")
    print(f"trials passed : {verification['trials']}/{verification['trials']}")
    print(f"randomized ct : {verification['unique_input_ciphertexts']}/{verification['trials']} unique")
    print(f"server has sk : {key_separation['server_has_secret_key']}")
    print(f"input ct bytes: {sizes['encrypted_im2col_input']:,}")
    print(f"output ct bytes: {sizes['encrypted_output']:,}")
    print(f"median encrypt: {timing['client_encrypt_and_serialize']['median_ms']:.3f} ms")
    print(f"median server : {timing['server_load_evaluate_and_serialize']['median_ms']:.3f} ms")
    print(f"median decrypt: {timing['client_load_and_decrypt']['median_ms']:.3f} ms")
    print(f"RESULT        : {'PASS' if verification['result_correct'] else 'FAIL'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument("--output", type=Path, default=Path("output/experiment_results.json"))
    args = parser.parse_args()

    result = run_experiment(trials=args.trials, tolerance=args.tolerance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_summary(result)
    print(f"evidence json : {args.output.resolve()}")
    if not result["verification"]["result_correct"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
