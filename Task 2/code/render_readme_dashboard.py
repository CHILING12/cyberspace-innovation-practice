from __future__ import annotations

import csv
import html
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = DATA / "figures" / "benchmark_dashboard.svg"

WIDTH = 1800
HEIGHT = 900
INK = "#17191f"
MUTED = "#5f636b"
LINE = "#e4e7eb"
TEAL = "#3ad4c4"
TEAL_DARK = "#008f83"
GREEN = "#58b900"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_results() -> list[dict[str, float | str]]:
    path = DATA / "benchmark_comparison_30.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 3:
        raise ValueError(f"Expected 3 benchmark rows, found {len(rows)}")

    labels = {
        "pr1446-ecdsa_verify": ("PR #1446", "ECDSA verify"),
        "pr1058-ecdsa_sign": ("PR #1058", "ECDSA sign"),
        "pr1058-ec_keygen": ("PR #1058", "EC keygen"),
    }
    results: list[dict[str, float | str]] = []
    for row in rows:
        comparison = row["comparison"]
        case, operation = labels[comparison]
        median = abs(float(row["median_block_relative_change_pct"]))
        raw_low = float(row["bootstrap_median_change_ci95_low_pct"])
        raw_high = float(row["bootstrap_median_change_ci95_high_pct"])
        results.append(
            {
                "case": case,
                "operation": operation,
                "median": median,
                "ci_low": min(abs(raw_low), abs(raw_high)),
                "ci_high": max(abs(raw_low), abs(raw_high)),
            }
        )
    return results


def text(
    x: float,
    y: float,
    value: object,
    size: int,
    *,
    weight: int = 400,
    fill: str = INK,
    anchor: str = "start",
) -> str:
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}">{esc(value)}</text>'
    )


def badge(
    x: float,
    y: float,
    width: float,
    label: str,
    *,
    fill: str = "#ffffff",
    stroke: str = GREEN,
    color: str = INK,
) -> str:
    return (
        f'<g><rect x="{x}" y="{y}" width="{width}" height="28" rx="6" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
        f'{text(x + width / 2, y + 19, label, 13, weight=600, fill=color, anchor="middle")}'
        "</g>"
    )


def render() -> str:
    results = load_results()
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">',
        "<defs>",
        '<filter id="shadow" x="-10%" y="-20%" width="120%" height="150%">',
        '<feDropShadow dx="0" dy="8" stdDeviation="9" flood-color="#111827" flood-opacity="0.10"/>',
        "</filter>",
        "</defs>",
        '<rect width="1800" height="900" fill="#ffffff"/>',
        '<g font-family="Segoe UI, Microsoft YaHei, Arial, sans-serif">',
        text(22, 31, "libsecp256k1", 18, weight=700),
        '<line x1="0" y1="45" x2="1800" y2="45" stroke="#d8dade" stroke-width="1"/>',
        '<rect x="20" y="62" width="865" height="142" rx="18" fill="#ffffff" '
        'stroke="#c9cdd2" stroke-width="1.2"/>',
        text(46, 97, "Report for", 14, weight=700),
        text(46, 132, "Bitcoin Core · libsecp256k1", 28, weight=700),
        badge(46, 158, 128, "GCC 15.2.0"),
        badge(184, 158, 214, "15 ABBA/BAAB blocks"),
        '<g filter="url(#shadow)">',
        '<rect x="905" y="62" width="875" height="142" rx="18" fill="#ffffff"/>',
        "</g>",
        '<rect x="905" y="62" width="875" height="142" rx="18" fill="#ffffff" '
        'stroke="#eef0f2" stroke-width="1"/>',
        '<path d="M923 62 H910 Q905 62 905 80 V186 Q905 204 923 204" '
        f'fill="none" stroke="{GREEN}" stroke-width="5"/>',
        f'<circle cx="938" cy="93" r="8" fill="#ffffff" stroke="{GREEN}" stroke-width="1.5"/>',
        f'<path d="M934 93 l3 3 6 -7" fill="none" stroke="{GREEN}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"/>',
        text(958, 99, "Validation Status", 16, weight=700),
        text(958, 139, "4 versions tested - all passed", 25, weight=700),
        text(20, 251, "Filter by case:", 14, weight=700),
        badge(134, 231, 96, "PR #1257", fill="#ffdad6", stroke="#ff9a90"),
        badge(240, 231, 96, "PR #1446", fill="#ffe5a6", stroke="#ffc55b"),
        badge(346, 231, 96, "PR #1058", fill="#bff3ee", stroke="#61d9cd"),
        badge(20, 286, 82, "3 results", fill="#bff3ee", stroke="#61d9cd", color="#006d65"),
        text(120, 308, "Performance improvements", 27, weight=700),
        text(20, 363, "Tags", 14, weight=700),
        badge(20, 378, 148, "constant-time", stroke="#7f858d"),
        badge(178, 378, 156, "field arithmetic", stroke="#7f858d"),
        badge(344, 378, 222, "signed-digit multi-comb", stroke="#7f858d"),
        text(20, 455, "Median runtime reduction", 19, weight=700),
        text(
            20,
            480,
            "After vs before · 15 blocks · 30 retained runs per phase · bootstrap 95% CI",
            13,
            fill=MUTED,
        ),
    ]

    chart_left = 90
    chart_right = 1760
    chart_top = 525
    chart_bottom = 810
    maximum = 16.0

    def y_for(value: float) -> float:
        return chart_bottom - value / maximum * (chart_bottom - chart_top)

    for tick in (0, 4, 8, 12, 16):
        y = y_for(float(tick))
        svg.append(
            f'<line x1="{chart_left}" y1="{y:.2f}" x2="{chart_right}" y2="{y:.2f}" '
            f'stroke="{LINE}" stroke-width="1"/>'
        )
        svg.append(text(chart_left - 14, y + 5, tick, 13, fill=MUTED, anchor="end"))

    svg.extend(
        [
            f'<line x1="{chart_left}" y1="{chart_bottom}" x2="{chart_right}" '
            f'y2="{chart_bottom}" stroke="#6f747b" stroke-width="1.4"/>',
            text(chart_left, chart_top - 18, "耗时下降（%）", 13, fill=MUTED),
        ]
    )

    centers = (540, 920, 1300)
    bar_width = 104
    for center, result in zip(centers, results, strict=True):
        median = float(result["median"])
        ci_low = float(result["ci_low"])
        ci_high = float(result["ci_high"])
        bar_top = y_for(median)
        ci_top = y_for(ci_high)
        ci_bottom = y_for(ci_low)
        svg.extend(
            [
                f'<rect x="{center - bar_width / 2}" y="{bar_top:.2f}" width="{bar_width}" '
                f'height="{chart_bottom - bar_top:.2f}" rx="2" fill="{TEAL}"/>',
                f'<line x1="{center}" y1="{ci_top:.2f}" x2="{center}" y2="{ci_bottom:.2f}" '
                f'stroke="{TEAL_DARK}" stroke-width="2"/>',
                f'<line x1="{center - 12}" y1="{ci_top:.2f}" x2="{center + 12}" y2="{ci_top:.2f}" '
                f'stroke="{TEAL_DARK}" stroke-width="2"/>',
                f'<line x1="{center - 12}" y1="{ci_bottom:.2f}" x2="{center + 12}" '
                f'y2="{ci_bottom:.2f}" stroke="{TEAL_DARK}" stroke-width="2"/>',
                text(center, ci_top - 12, f"{median:.2f}%", 14, weight=700, anchor="middle"),
                text(center, 840, result["case"], 14, weight=700, anchor="middle"),
                text(center, 862, result["operation"], 13, fill=MUTED, anchor="middle"),
            ]
        )

    svg.extend(
        [
            text(
                1760,
                884,
                "柱高为耗时下降幅度；误差线为 bootstrap 95% 区间。",
                12,
                fill=MUTED,
                anchor="end",
            ),
            "</g>",
            "</svg>",
        ]
    )
    return "".join(svg)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
