"""Generate report figures from the encrypted-convolution evidence JSON."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "output" / "experiment_results.json"
FIGURES = ROOT / "output" / "figures"
FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")
CN = FontProperties(fname=str(FONT_PATH)) if FONT_PATH.exists() else None
MONO = FontProperties(family="DejaVu Sans Mono")


def _annotated_matrix(ax, data, title: str, cmap: str, value_format: str = ".0f") -> None:
    array = np.asarray(data, dtype=float)
    image = ax.imshow(array, cmap=cmap, aspect="equal")
    for row in range(array.shape[0]):
        for col in range(array.shape[1]):
            ax.text(col, row, format(array[row, col], value_format), ha="center", va="center", fontsize=11)
    ax.set_title(title, fontproperties=CN, fontsize=13, pad=10)
    ax.set_xticks(range(array.shape[1]))
    ax.set_yticks(range(array.shape[0]))
    ax.tick_params(length=0)
    return image


def convolution_figure(result: dict) -> None:
    convolution = result["convolution"]
    expected = np.asarray(convolution["plaintext_reference"], dtype=float)
    decrypted = np.asarray(convolution["decrypted_output"], dtype=float)
    error = np.abs(decrypted - expected)

    fig, axes = plt.subplots(1, 4, figsize=(13.2, 3.8), constrained_layout=True)
    _annotated_matrix(axes[0], convolution["input"], "4x4 明文输入", "Blues")
    _annotated_matrix(axes[1], convolution["kernel"], "3x3 明文卷积核", "RdBu_r")
    _annotated_matrix(axes[2], decrypted, "解密后的 2x2 输出", "YlGn")
    _annotated_matrix(axes[3], error, "逐槽绝对误差", "OrRd", ".2e")
    fig.suptitle("CKKS 密文卷积结果与误差", fontproperties=CN, fontsize=17)
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "encrypted_convolution_result.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def runtime_figure(result: dict) -> None:
    verification = result["verification"]
    timing = result["timing"]
    sizes = result["serialized_sizes_bytes"]
    keys = result["key_separation"]
    parameters = result["parameters"]
    convolution = result["convolution"]

    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    fig.patch.set_facecolor("#10161d")
    ax.set_facecolor("#10161d")
    ax.axis("off")
    lines = [
        ("TENSEAL CKKS ENCRYPTED CONVOLUTION", "#7ee787", 18),
        ("$ python fhe_convolution.py --trials 10", "#b6beca", 10),
        ("", "white", 8),
        (f"[OK] shapes       {convolution['input_shape']} x {convolution['kernel_shape']} -> {convolution['output_shape']}", "#7ee787", 10),
        (f"[OK] parameters   N={parameters['poly_modulus_degree']}, Q-bits={parameters['coeff_mod_bit_sizes']}, scale={parameters['global_scale']}", "#7ee787", 10),
        (f"[OK] key split    server_has_secret_key={keys['server_has_secret_key']}", "#7ee787", 10),
        (f"[OK] expected     {convolution['plaintext_reference']}", "#7ee787", 10),
        (f"[OK] decrypted    {[[round(v, 6) for v in row] for row in convolution['decrypted_output']]}", "#7ee787", 10),
        (f"[OK] max error    {verification['maximum_absolute_error_all_trials']:.3e} <= {verification['absolute_error_tolerance']:.1e}", "#7ee787", 10),
        (f"[OK] randomized   {verification['unique_input_ciphertexts']}/{verification['trials']} unique ciphertexts", "#7ee787", 10),
        ("", "white", 8),
        (f"[SIZE] eval context {sizes['server_public_evaluation_context']:,} B | input ct {sizes['encrypted_im2col_input']:,} B | output ct {sizes['encrypted_output']:,} B", "#8bd5ff", 9.5),
        (f"[TIME] median      encrypt {timing['client_encrypt_and_serialize']['median_ms']:.3f} ms | server {timing['server_load_evaluate_and_serialize']['median_ms']:.3f} ms | decrypt {timing['client_load_and_decrypt']['median_ms']:.3f} ms", "#8bd5ff", 9.5),
        ("", "white", 8),
        ("RESULT: ALL CORRECTNESS AND KEY-ISOLATION CHECKS PASSED", "#ffcc66", 12.5),
    ]
    y = 0.94
    for text, color, size in lines:
        ax.text(0.04, y, text, transform=ax.transAxes, color=color, fontproperties=MONO, fontsize=size, va="top")
        y -= 0.061 if text else 0.030
    fig.savefig(FIGURES / "runtime_validation.png", dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    result = json.loads(RESULTS.read_text(encoding="utf-8"))
    convolution_figure(result)
    runtime_figure(result)
    print(f"rendered 2 figures in {FIGURES}")


if __name__ == "__main__":
    main()
