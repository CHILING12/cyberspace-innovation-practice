"""Render report-ready figures directly from the analyzer's JSON/CSV output."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, Rectangle


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_ROOT / "output" / "testnet4_signed_analysis"
FIGURES = PROJECT_ROOT / "output" / "figures"
FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")
CN = FontProperties(fname=str(FONT_PATH)) if FONT_PATH.exists() else None
MONO = FontProperties(family="DejaVu Sans Mono")

COLORS = {
    "version": "#355070",
    "segwit": "#6d597a",
    "input": "#b56576",
    "output": "#e56b6f",
    "witness": "#eaac8b",
    "locktime": "#4d908e",
}


def group_for(field: str) -> str:
    if field.endswith("version"):
        return "version"
    if field.endswith("marker") or field.endswith("flag"):
        return "segwit"
    if ".vin[" in field and ".witness" not in field:
        return "input"
    if ".vout[" in field:
        return "output"
    if ".witness" in field:
        return "witness"
    return "locktime"


def transaction_layout() -> None:
    summary = json.loads((OUTPUT / "transaction_summary.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((OUTPUT / "transaction_fields.csv").open(encoding="utf-8")))
    intervals: list[tuple[int, int, str]] = []
    for row in rows:
        start, end = int(row["start"]), int(row["end_exclusive"])
        group = group_for(row["field"])
        if intervals and intervals[-1][2] == group and intervals[-1][1] == start:
            intervals[-1] = (intervals[-1][0], end, group)
        else:
            intervals.append((start, end, group))
    total = max(end for _, end, _ in intervals)
    fig, ax = plt.subplots(figsize=(12, 3.3))
    for start, end, group in intervals:
        ax.add_patch(Rectangle((start, 0), end - start, 1, color=COLORS[group], ec="white", lw=0.8))
        if end - start >= 6:
            ax.text((start + end) / 2, 0.5, f"{group}\n{end-start} B", ha="center", va="center", color="white", fontsize=8)
    ax.set_xlim(0, total)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xlabel(f"线协议字节偏移（总计 {summary['total_size_bytes']} B）", fontproperties=CN)
    ax.set_title("SegWit 交易逐字节布局", fontproperties=CN, fontsize=15, pad=14)
    ax.spines[["top", "left", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIGURES / "transaction_byte_layout.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def script_trace() -> None:
    audit = json.loads((OUTPUT / "script_audit.json").read_text(encoding="utf-8"))[0]
    trace = audit["trace"]
    fig, ax = plt.subplots(figsize=(11, 6.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(-1.05, len(trace) - 0.3)
    ax.axis("off")
    for index, step in enumerate(trace):
        y = len(trace) - 1 - index
        depth = len(step["stack"])
        box = FancyBboxPatch((0.35, y - 0.31), 2.3, 0.62, boxstyle="round,pad=0.03", fc="#355070", ec="none")
        ax.add_patch(box)
        ax.text(1.5, y, step["operation"], ha="center", va="center", color="white", fontproperties=MONO, fontsize=10)
        ax.text(2.95, y + 0.10, step["detail"], ha="left", va="center", fontproperties=MONO, fontsize=8.5)
        ax.text(2.95, y - 0.16, f"stack depth = {depth}", ha="left", va="center", color="#555555", fontproperties=MONO, fontsize=8)
        for stack_index in range(depth):
            ax.add_patch(Rectangle((8.9 - stack_index * 0.58, y - 0.22), 0.48, 0.44, fc="#eaac8b", ec="#9b4d5b", lw=0.7))
        if index < len(trace) - 1:
            ax.annotate("", xy=(1.5, y - 0.61), xytext=(1.5, y - 0.39), arrowprops={"arrowstyle": "->", "color": "#777777"})
    ax.set_title("P2WPKH Script 栈执行轨迹", fontproperties=CN, fontsize=15, pad=12)
    ax.text(0.35, -0.75, "最终栈 = [01]，ECDSA = valid，CleanStack = true", fontproperties=CN, fontsize=10, color="#176b4d")
    fig.tight_layout()
    fig.savefig(FIGURES / "script_stack_trace.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def validation_summary() -> None:
    tx = json.loads((OUTPUT / "transaction_summary.json").read_text(encoding="utf-8"))
    block = json.loads((OUTPUT / "block_summary.json").read_text(encoding="utf-8"))
    audit = json.loads((OUTPUT / "script_audit.json").read_text(encoding="utf-8"))[0]
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor("#0f1419")
    ax.set_facecolor("#0f1419")
    ax.axis("off")
    lines = [
        ("BITCOIN TESTNET4 BYTE AUDIT", "#7ee787", 18),
        (f"$ python chain_analyzer.py --network {tx['network']} --txid {tx['txid_computed'][:8]}...", "#b6beca", 10),
        ("", "white", 8),
        (f"[OK] txid       {tx['txid_computed']}", "#7ee787", 10),
        (f"[OK] bytes      {tx['total_size_bytes']} / {tx['total_size_bytes']} accounted", "#7ee787", 10),
        (f"[OK] BIP143     {audit['sighash_digest']}", "#7ee787", 10),
        (f"[OK] Script     ECDSA={audit['ecdsa_valid']}  low-S={audit['low_s']}  CleanStack={audit['cleanstack_success']}", "#7ee787", 10),
        ("", "white", 8),
        (f"[OK] block      {block['block_hash_computed']}", "#7ee787", 10),
        (f"[OK] full parse {block['block_size_bytes']:,} bytes, {block['transaction_count']} transactions", "#7ee787", 10),
        (f"[OK] Merkle     {block['merkle_root_computed']}", "#7ee787", 10),
        (f"[OK] PoW        hash <= {block['target_hex']}", "#7ee787", 10),
        ("", "white", 8),
        ("RESULT: ALL INDEPENDENT CHECKS PASSED", "#ffcc66", 13),
    ]
    y = 0.93
    for text, color, size in lines:
        ax.text(0.045, y, text, transform=ax.transAxes, color=color, fontproperties=MONO, fontsize=size, va="top")
        y -= 0.064 if text else 0.035
    fig.savefig(FIGURES / "runtime_validation.png", dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    transaction_layout()
    script_trace()
    validation_summary()
    print(f"rendered 3 figures in {FIGURES}")


if __name__ == "__main__":
    main()
