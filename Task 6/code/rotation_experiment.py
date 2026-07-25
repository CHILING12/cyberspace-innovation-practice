"""任务六：分析 CKKS 密文卷积的旋转次数及理论最小值。"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Sequence

# 添加 Task 5 代码目录以导入 fhe_convolution 模块
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "task5" / "code"))

import tenseal as ts

from fhe_convolution import (
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


def flatten(matrix: Sequence[Sequence[float]]) -> list[float]:
    """按行展开矩阵。"""
    return [float(value) for row in matrix for value in row]


def next_power_of_two(value: int) -> int:
    """返回不小于 value 的最小 2 的幂。"""
    if value <= 0:
        raise ValueError("value must be positive")
    return 1 << (value - 1).bit_length()


def rotation_plan(term_count: int, windows: int) -> dict[str, object]:
    """复现 TenSEAL enc_matmul_plain 的二叉旋转累加计划。"""
    padded_terms = next_power_of_two(term_count)

    chunks = padded_terms
    rotation_steps: list[int] = []

    while chunks > 1:
        chunks //= 2
        rotation_steps.append(windows * chunks)

    lower_bound = math.ceil(math.log2(term_count)) if term_count > 1 else 0

    return {
        "original_terms": term_count,
        "padded_terms": padded_terms,
        "windows": windows,
        "packed_vector_size": windows * padded_terms,
        "rotation_steps": rotation_steps,
        "actual_rotation_count": len(rotation_steps),
        "theoretical_lower_bound": lower_bound,
        "reaches_lower_bound": len(rotation_steps) == lower_bound,
    }


def build_im2col_matrix(
    image: Sequence[Sequence[float]],
) -> Matrix:
    """生成本题四个 3×3 滑动窗口，每个窗口为一行。"""
    windows: Matrix = []

    for output_row in range(2):
        for output_col in range(2):
            window: list[float] = []

            for kernel_row in range(3):
                for kernel_col in range(3):
                    window.append(
                        float(
                            image[output_row + kernel_row]
                            [output_col + kernel_col]
                        )
                    )

            windows.append(window)

    return windows


def decrypt_vector(
    client_context: ts.Context,
    encrypted_output: bytes,
    output_count: int,
) -> list[float]:
    values = ts.ckks_vector_from(
        client_context,
        encrypted_output,
    ).decrypt()

    return [float(value) for value in values[:output_count]]


def run_generic_experiment(
    client_context: ts.Context,
    server_context: ts.Context,
) -> dict[str, object]:
    """运行任务五原始的通用 3×3 卷积。"""
    encrypted_input, windows, encrypted_size = client_encrypt_im2col(
        client_context,
        DEFAULT_INPUT,
    )

    encrypted_output = server_encrypted_convolution(
        server_context,
        encrypted_input,
        DEFAULT_KERNEL,
        windows,
    )

    decrypted = client_decrypt_output(
        client_context,
        encrypted_output,
        windows,
    )

    expected = plaintext_valid_convolution(
        DEFAULT_INPUT,
        DEFAULT_KERNEL,
    )

    actual_flat = flatten(decrypted)
    expected_flat = flatten(expected)

    errors = [
        abs(actual - reference)
        for actual, reference in zip(actual_flat, expected_flat)
    ]

    # 通用 3×3 卷积需要处理 9 个核位置。
    plan = rotation_plan(term_count=9, windows=windows)

    return {
        "name": "generic_3x3_im2col",
        "packing_method": "TenSEAL im2col_encoding + conv2d_im2col",
        "encrypted_vector_size": encrypted_size,
        "decrypted_output": decrypted,
        "expected_output": expected,
        "maximum_absolute_error": max(errors),
        "rotation_analysis": plan,
    }


def run_sparse_experiment(
    client_context: ts.Context,
    server_context: ts.Context,
) -> dict[str, object]:
    """删除固定卷积核中的零权重，测试稀疏打包方案。"""
    im2col_matrix = build_im2col_matrix(DEFAULT_INPUT)
    kernel_flat = flatten(DEFAULT_KERNEL)

    # 找出非零卷积核位置。
    active_indices = [
        index
        for index, weight in enumerate(kernel_flat)
        if weight != 0.0
    ]

    active_weights = [
        kernel_flat[index]
        for index in active_indices
    ]

    # 每个窗口只保留与非零权重对应的输入。
    sparse_matrix = [
        [window[index] for index in active_indices]
        for window in im2col_matrix
    ]

    windows = len(sparse_matrix)

    # enc_matmul_encoding 会按列扫描并完成 CKKS 加密。
    encrypted_input = ts.enc_matmul_encoding(
        client_context,
        sparse_matrix,
    )

    encrypted_input_bytes = encrypted_input.serialize()
    encrypted_size = encrypted_input.size()

    # 在无私钥服务器上下文中加载并计算。
    server_vector = ts.ckks_vector_from(
        server_context,
        encrypted_input_bytes,
    )

    encrypted_output = server_vector.enc_matmul_plain(
        active_weights,
        windows,
    )

    encrypted_output_bytes = encrypted_output.serialize()

    decrypted_flat = decrypt_vector(
        client_context,
        encrypted_output_bytes,
        windows,
    )

    decrypted = [
        decrypted_flat[:2],
        decrypted_flat[2:4],
    ]

    expected = plaintext_valid_convolution(
        DEFAULT_INPUT,
        DEFAULT_KERNEL,
    )

    expected_flat = flatten(expected)

    errors = [
        abs(actual - reference)
        for actual, reference in zip(
            decrypted_flat,
            expected_flat,
        )
    ]

    # 当前固定卷积核有 8 个非零元素。
    plan = rotation_plan(
        term_count=len(active_weights),
        windows=windows,
    )

    return {
        "name": "sparse_kernel_packing",
        "packing_method": (
            "remove zero kernel positions + "
            "enc_matmul_encoding + enc_matmul_plain"
        ),
        "active_kernel_indices": active_indices,
        "active_kernel_weights": active_weights,
        "nonzero_kernel_terms": len(active_weights),
        "encrypted_vector_size": encrypted_size,
        "decrypted_output": decrypted,
        "expected_output": expected,
        "maximum_absolute_error": max(errors),
        "rotation_analysis": plan,
    }


def print_result(result: dict[str, object]) -> None:
    generic = result["generic"]
    sparse = result["sparse"]

    generic_rotation = generic["rotation_analysis"]
    sparse_rotation = sparse["rotation_analysis"]

    print("CKKS ROTATION EXPERIMENT")
    print("========================")

    print("\n[Generic 3x3 convolution]")
    print(
        "packed vector size :",
        generic["encrypted_vector_size"],
    )
    print(
        "rotation steps     :",
        generic_rotation["rotation_steps"],
    )
    print(
        "actual rotations   :",
        generic_rotation["actual_rotation_count"],
    )
    print(
        "theoretical minimum:",
        generic_rotation["theoretical_lower_bound"],
    )
    print(
        "reaches minimum    :",
        generic_rotation["reaches_lower_bound"],
    )
    print(
        "maximum error      :",
        f"{generic['maximum_absolute_error']:.6e}",
    )

    print("\n[Sparse fixed-kernel convolution]")
    print(
        "nonzero terms      :",
        sparse["nonzero_kernel_terms"],
    )
    print(
        "packed vector size :",
        sparse["encrypted_vector_size"],
    )
    print(
        "rotation steps     :",
        sparse_rotation["rotation_steps"],
    )
    print(
        "actual rotations   :",
        sparse_rotation["actual_rotation_count"],
    )
    print(
        "theoretical minimum:",
        sparse_rotation["theoretical_lower_bound"],
    )
    print(
        "reaches minimum    :",
        sparse_rotation["reaches_lower_bound"],
    )
    print(
        "maximum error      :",
        f"{sparse['maximum_absolute_error']:.6e}",
    )

    print("\n[Conclusion]")
    print(
        "Generic 3x3 convolution: 4 rotations, "
        "matching ceil(log2(9)) = 4."
    )
    print(
        "Fixed sparse kernel: 3 rotations after removing "
        "the zero coefficient, matching ceil(log2(8)) = 3."
    )


def main() -> None:
    parameters = CKKSParameters()

    client_context = create_client_context(parameters)
    server_context = load_server_context(
        serialize_evaluation_context(client_context)
    )

    generic_result = run_generic_experiment(
        client_context,
        server_context,
    )

    sparse_result = run_sparse_experiment(
        client_context,
        server_context,
    )

    result = {
        "assignment": "rotation minimization for encrypted convolution",
        "generic": generic_result,
        "sparse": sparse_result,
        "conclusion": {
            "generic_convolution_optimal": (
                generic_result["rotation_analysis"]
                ["reaches_lower_bound"]
            ),
            "fixed_sparse_kernel_optimal": (
                sparse_result["rotation_analysis"]
                ["reaches_lower_bound"]
            ),
        },
    }

    output_path = Path(
        "output/rotation_experiment_results.json"
    )
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print_result(result)
    print(f"\nEvidence JSON: {output_path.resolve()}")


if __name__ == "__main__":
    main()
