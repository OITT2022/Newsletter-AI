"""
Generate chart images from data using matplotlib.

Usage:
    python tools/generate_chart.py bar --data '{"labels":["A","B","C"],"values":[10,20,30]}' --title "Comparison"
    python tools/generate_chart.py stat_card --data '{"value":"73%","label":"of companies use AI"}' --title "Key Stat"
    python tools/generate_chart.py line --data '{"labels":["2022","2023","2024","2025"],"values":[10,25,45,73]}' --title "Growth"
"""

import argparse
import json
import re
import sys
from pathlib import Path

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from bidi.algorithm import get_display


def fix_hebrew(text: str) -> str:
    """Apply BiDi algorithm to fix Hebrew text rendering in matplotlib."""
    if any("\u0590" <= c <= "\u05FF" for c in text):
        return get_display(text)
    return text

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
OUTPUT_DIR = TMP_DIR / "charts"
STYLE_FILE = Path(__file__).resolve().parent / "assets" / "newsletter.mplstyle"

# Brand colors
COLORS = ["#6c63ff", "#ff6584", "#43b88c", "#f5a623", "#4a90d9"]
BG_COLOR = "#ffffff"
TEXT_COLOR = "#1a1a2e"
SUBTLE_COLOR = "#9999b3"


def apply_style():
    if STYLE_FILE.exists():
        plt.style.use(str(STYLE_FILE))
    else:
        plt.rcParams.update({
            "figure.facecolor": BG_COLOR,
            "axes.facecolor": BG_COLOR,
            "axes.edgecolor": SUBTLE_COLOR,
            "axes.labelcolor": TEXT_COLOR,
            "text.color": TEXT_COLOR,
            "xtick.color": TEXT_COLOR,
            "ytick.color": TEXT_COLOR,
            "grid.color": "#e8e8ed",
            "grid.alpha": 0.7,
            "font.family": "sans-serif",
            "font.size": 12,
        })


def chart_bar(data: dict, title: str, output: str):
    labels = [fix_hebrew(l) for l in data["labels"]]
    values = data["values"]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=COLORS[:len(labels)], width=0.6, edgecolor="none")

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.02,
                str(val), ha="center", va="bottom", fontweight="bold", fontsize=13, color=TEXT_COLOR)

    ax.set_title(fix_hebrew(title), fontsize=18, fontweight="bold", pad=20)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(0, max(values) * 1.2)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)


def chart_line(data: dict, title: str, output: str):
    labels = [fix_hebrew(l) for l in data["labels"]]
    values = data["values"]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(labels, values, color=COLORS[0], linewidth=3, marker="o", markersize=8, markerfacecolor=COLORS[0])
    ax.fill_between(range(len(labels)), values, alpha=0.1, color=COLORS[0])

    for i, (label, val) in enumerate(zip(labels, values)):
        ax.annotate(str(val), (i, val), textcoords="offset points", xytext=(0, 12),
                    ha="center", fontweight="bold", fontsize=12, color=TEXT_COLOR)

    ax.set_title(fix_hebrew(title), fontsize=18, fontweight="bold", pad=20)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)


def chart_pie(data: dict, title: str, output: str):
    labels = [fix_hebrew(l) for l in data["labels"]]
    values = data["values"]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=COLORS[:len(labels)],
        autopct="%1.0f%%", startangle=90, pctdistance=0.75,
        wedgeprops={"edgecolor": BG_COLOR, "linewidth": 2}
    )
    for text in autotexts:
        text.set_fontweight("bold")
        text.set_fontsize(13)

    ax.set_title(fix_hebrew(title), fontsize=18, fontweight="bold", pad=20)

    plt.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)


def chart_stat_card(data: dict, title: str, output: str):
    value = data["value"]
    label = fix_hebrew(data["label"])

    fig, ax = plt.subplots(figsize=(6, 3))
    ax.axis("off")

    ax.text(0.5, 0.65, str(value), ha="center", va="center",
            fontsize=56, fontweight="bold", color=COLORS[0],
            transform=ax.transAxes)
    ax.text(0.5, 0.25, label, ha="center", va="center",
            fontsize=16, color=SUBTLE_COLOR,
            transform=ax.transAxes)

    fig.patch.set_facecolor("#f0efff")
    fig.patch.set_alpha(1)

    plt.tight_layout(pad=1)
    fig.savefig(output, dpi=200, bbox_inches="tight", facecolor="#f0efff")
    plt.close(fig)


CHART_TYPES = {
    "bar": chart_bar,
    "line": chart_line,
    "pie": chart_pie,
    "stat_card": chart_stat_card,
}


def main():
    parser = argparse.ArgumentParser(description="Generate chart images")
    parser.add_argument("type", choices=CHART_TYPES.keys(), help="Chart type")
    parser.add_argument("--data", required=True, help="JSON data string or file path")
    parser.add_argument("--title", default="", help="Chart title")
    parser.add_argument("--output", default="", help="Output file path")
    args = parser.parse_args()

    # Parse data
    if Path(args.data).exists():
        with open(args.data, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.loads(args.data)

    # Output path
    if args.output:
        output_path = args.output
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        existing = list(OUTPUT_DIR.glob("chart_*.png"))
        next_num = len(existing) + 1
        output_path = str(OUTPUT_DIR / f"chart_{next_num}.png")

    apply_style()
    CHART_TYPES[args.type](data, args.title, output_path)
    print(f"Chart saved: {output_path}")


if __name__ == "__main__":
    main()
