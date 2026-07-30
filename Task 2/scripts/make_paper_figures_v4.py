from __future__ import annotations

import csv
import random
import statistics
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "work" / "assignment2_secp256k1_latex"
OUT = PROJECT / "imgs"
EVIDENCE = PROJECT / "evidence" / "revision"

INK = "#20242A"
GRAY = "#6B7280"
GRID = "#D7DBE0"
RED = "#8A151B"
BLUE = "#355F86"
GREEN = "#356B48"


def font(size: int, bold: bool = False, mono: bool = False):
    if mono:
        path = Path(r"C:\Windows\Fonts\consolab.ttf" if bold else r"C:\Windows\Fonts\consola.ttf")
    else:
        path = Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc")
    return ImageFont.truetype(str(path), size)


BODY = font(29)
BOLD = font(30, bold=True)
SMALL = font(23)
MONO = font(27, mono=True)


def centered(draw, xy, text, use_font, fill=INK, spacing=7):
    box = draw.multiline_textbbox((0, 0), text, font=use_font, align="center", spacing=spacing)
    w, h = box[2] - box[0], box[3] - box[1]
    draw.multiline_text((xy[0] - w / 2, xy[1] - h / 2), text, font=use_font,
                        fill=fill, align="center", spacing=spacing)


def rounded(draw, bounds, fill, outline, width=3, radius=20):
    draw.rounded_rectangle(bounds, radius=radius, fill=fill, outline=outline, width=width)


def arrow(draw, start, end, color=INK):
    draw.line([start, end], fill=color, width=4)
    x, y = end
    draw.polygon([(x, y), (x - 15, y - 9), (x - 15, y + 9)], fill=color)


def make_call_path():
    image = Image.new("RGB", (2200, 690), "white")
    draw = ImageDraw.Draw(image)
    rows = [
        (105, "#FAEEEE", RED, [
            ("钱包/密钥操作", 315), ("CKey::Sign\nkey.cpp", 340),
            ("secp256k1_ecdsa_sign", 400), ("ecmult_gen\n固定基点乘法", 385)
        ], "PR #1058"),
        (390, "#EDF3F8", BLUE, [
            ("OP_CHECKSIG", 315), ("CheckECDSASignature\ninterpreter.cpp", 420),
            ("CPubKey::Verify\npubkey.cpp", 385), ("ecdsa_verify\nfield arithmetic", 390)
        ], "PR #1446"),
    ]
    for y, fill, edge, nodes, tag in rows:
        x = 70
        last = None
        for i, (label, width) in enumerate(nodes):
            rounded(draw, (x, y, x + width, y + 135), fill, edge)
            centered(draw, (x + width / 2, y + 67), label, BOLD)
            if i < len(nodes) - 1:
                arrow(draw, (x + width + 12, y + 67), (x + width + 68, y + 67), edge)
            last = (x, width)
            x += width + 82
        tag_x = last[0] + last[1] / 2
        rounded(draw, (tag_x - 105, y + 160, tag_x + 105, y + 212), "white", edge, width=2, radius=14)
        centered(draw, (tag_x, y + 186), tag, SMALL, edge)
        draw.line((tag_x, y + 135, tag_x, y + 160), fill=edge, width=3)
    rounded(draw, (910, 620, 1290, 675), "#F5F6F7", "#9AA1AA", width=2, radius=14)
    centered(draw, (1100, 647), "PR #1257：条件移动实现", SMALL, GRAY)
    image.save(OUT / "13_bitcoin_core_call_path_paper.png")


def make_assembly():
    image = Image.new("RGB", (2200, 760), "white")
    draw = ImageDraw.Draw(image)
    panels = [
        ((70, 55, 1060, 715), "修复前：条件选择指针", "#FBF3E7", RED, [
            "test    r8d, r8d",
            "cmove   rdx, rcx",
            "mov     rdx, qword ptr [rdx]",
            "cmove   rax, r9",
            "mov     rax, qword ptr [rax]",
            "cmove   r11, r10",
            "mov     rax, qword ptr [r11]",
            "cmove   rdi, rsi",
            "mov     rax, qword ptr [rdi]",
        ]),
        ((1140, 55, 2130, 715), "修复后：双侧加载后掩码合并", "#EEF4F1", GREEN, [
            "test    r8d, r8d",
            "setne   al",
            "mov     dword ptr [rsp+4], eax",
            "mov     r9, qword ptr [rcx]",
            "mov     rax, qword ptr [rdx]",
            "and     r9, r8",
            "and     rax, r10",
            "or      rax, r9",
            "mov     qword ptr [rcx], rax",
        ]),
    ]
    for bounds, heading, fill, edge, lines in panels:
        rounded(draw, bounds, fill, edge)
        draw.text((bounds[0] + 45, bounds[1] + 38), heading, font=BOLD, fill=edge)
        y = bounds[1] + 125
        for line in lines:
            draw.text((bounds[0] + 55, y), line, font=MONO, fill=INK)
            y += 54
    image.save(OUT / "10_pr1257_assembly_paper.png")


def read_csv(name):
    with (EVIDENCE / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def make_blocks():
    rows = read_csv("benchmark_detail_30.csv")
    summaries = {r["comparison"]: r for r in read_csv("benchmark_comparison_30.csv")}
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["comparison"], int(r["block"]), r["phase"])].append(float(r["avg_us"]))
    specs = [
        ("pr1446-ecdsa_verify", "PR #1446\nECDSA verify", BLUE, "circle"),
        ("pr1058-ecdsa_sign", "PR #1058\nECDSA sign", RED, "square"),
        ("pr1058-ec_keygen", "PR #1058\nEC keygen", GREEN, "triangle"),
    ]
    image = Image.new("RGB", (2200, 900), "white")
    draw = ImageDraw.Draw(image)
    left, right, top, bottom = 190, 2100, 55, 700
    y_min, y_max = -25.0, 5.0
    for value in range(-25, 6, 5):
        y = bottom - (value - y_min) / (y_max - y_min) * (bottom - top)
        draw.line((left, y, right, y), fill=RED if value == 0 else GRID, width=4 if value == 0 else 2)
        draw.text((left - 22, y), f"{value}", font=SMALL, fill=GRAY, anchor="rm")
    draw.line((left, top, left, bottom), fill="#8B929A", width=3)
    draw.text((42, (top + bottom) / 2), "相对变化 / %", font=BODY, fill=INK, anchor="mm")
    rng = random.Random(20260730)
    xs = [500, 1135, 1770]
    for (key, label, color, shape), x0 in zip(specs, xs):
        values = []
        for block in range(1, 16):
            before = statistics.median(grouped[(key, block, "before")])
            after = statistics.median(grouped[(key, block, "after")])
            values.append((after - before) / before * 100)
        for value in values:
            x = x0 + rng.randint(-82, 82)
            y = bottom - (value - y_min) / (y_max - y_min) * (bottom - top)
            if shape == "circle":
                draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill="white", outline=color, width=4)
            elif shape == "square":
                draw.rectangle((x - 10, y - 10, x + 10, y + 10), fill="white", outline=color, width=4)
            else:
                draw.polygon([(x, y - 12), (x + 12, y + 10), (x - 12, y + 10)], fill="white", outline=color)
        s = summaries[key]
        med = float(s["median_block_relative_change_pct"])
        lo = float(s["bootstrap_median_change_ci95_low_pct"])
        hi = float(s["bootstrap_median_change_ci95_high_pct"])
        conv = lambda v: bottom - (v - y_min) / (y_max - y_min) * (bottom - top)
        draw.line((x0, conv(lo), x0, conv(hi)), fill=color, width=8)
        draw.line((x0 - 28, conv(lo), x0 + 28, conv(lo)), fill=color, width=8)
        draw.line((x0 - 28, conv(hi), x0 + 28, conv(hi)), fill=color, width=8)
        ym = conv(med)
        draw.polygon([(x0, ym - 15), (x0 + 15, ym), (x0, ym + 15), (x0 - 15, ym)],
                     fill="white", outline=color)
        centered(draw, (x0, 785), label, BOLD, color)
    image.save(OUT / "12_block_changes_paper.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    make_call_path()
    make_assembly()
    make_blocks()
    print("paper figures written")
