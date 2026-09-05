"""Generate the README's headline comparison chart: control vs. pattern,
per module, 3 metrics, plus a verdict strip (does the module confirm the
"pattern costs less" thesis?).

Source numbers are the locked gpt-4.1-mini gate results recorded in each
module's ticket 03/04/05 (`.scratch/*/issues/`), 3 runs x 8 tasks each.
Not re-read from `results/` because that directory is gitignored -- the
numbers are final and already reviewed, so they're hardcoded here.

Palette: dataviz skill's default categorical slots 1 (blue, Control) and 2
(orange, Pattern) -- validated via validate_palette.js: CVD dE 24.7, normal
dE 33.6, both well clear of the >=8 / >=15 floors. Verdict strip uses the
skill's fixed status colors (good/critical), always paired with an icon and
a text label, never color alone.

Run: python docs/phase6_chart.py
Writes: docs/phase6-chart.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CONTROL = "#2a78d6"   # categorical slot 1 (blue)
PATTERN = "#eb6834"   # categorical slot 2 (orange)
GOOD = "#0ca30c"       # status: confirms the thesis
CRITICAL = "#d03b3b"   # status: negative finding

# module: (control, pattern) per metric; verdict is True when the module
# confirms "pattern costs less at equal-or-better success" (see README).
DATA = {
    "Tool\nOrchestrator": {
        "success": (1.000, 1.000), "turns": (3.79, 2.00),
        "tokens": (2427.25, 809.00), "verdict": True,
    },
    "Domain\nAdapter": {
        "success": (1.000, 1.000), "turns": (3.00, 2.00),
        "tokens": (2924.75, 700.00), "verdict": True,
    },
    "Stateful\nSession Server": {
        "success": (1.000, 1.000), "turns": (5.75, 5.96),
        "tokens": (6563.17, 6970.33), "verdict": False,
    },
    "Proxy\nAggregator": {
        "success": (0.667, 0.375), "turns": (7.38, 18.29),
        "tokens": (14432.71, 27680.96), "verdict": False,
    },
    "Resource\nGateway": {
        "success": (0.417, 0.625), "turns": (2.88, 4.08),
        "tokens": (2814.20, 2559.30), "verdict": True,
    },
}

PANELS = [
    ("success", "Success rate", lambda v: v * 100, "{:.0f}%"),
    ("turns", "Avg turns", lambda v: v, "{:.1f}"),
    ("tokens", "Avg input tokens", lambda v: v, "{:.0f}"),
]


def _bar_panel(ax, metric, title, scale, fmt, modules):
    x = range(len(modules))
    width = 0.32
    control_vals = [scale(DATA[m][metric][0]) for m in modules]
    pattern_vals = [scale(DATA[m][metric][1]) for m in modules]

    ax.bar([i - width / 2 for i in x], control_vals, width,
           color=CONTROL, edgecolor="white", linewidth=1, label="Control")
    ax.bar([i + width / 2 for i in x], pattern_vals, width,
           color=PATTERN, edgecolor="white", linewidth=1, label="Pattern")

    for i, (c, p) in enumerate(zip(control_vals, pattern_vals)):
        if fmt.format(c) == fmt.format(p):
            # Same displayed value on both bars: one centered label, not two
            # that would collide (this hits every 100%-success module).
            ax.text(i, max(c, p), fmt.format(c), ha="center", va="bottom", fontsize=7)
        else:
            ax.text(i - width / 2, c, fmt.format(c), ha="center", va="bottom", fontsize=7)
            ax.text(i + width / 2, p, fmt.format(p), ha="center", va="bottom", fontsize=7)

    ax.set_title(title, fontsize=10)
    ax.set_xticks(list(x))
    ax.set_xticklabels(modules, fontsize=7.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.margins(y=0.15)


def make_chart(out_path: str) -> None:
    modules = list(DATA)
    fig, axes = plt.subplots(1, 3, figsize=(13, 5))

    for ax, (metric, title, scale, fmt) in zip(axes, PANELS):
        _bar_panel(ax, metric, title, scale, fmt, modules)

    # One shared legend (identity: Control vs. Pattern -- same 2 series in
    # every panel, so one legend for the figure, not one per panel).
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2,
               bbox_to_anchor=(0.5, 1.04), frameon=False)

    # Verdict strip: icon + label, never color alone (status colors are
    # reserved and never carry meaning by hue by itself).
    for i, m in enumerate(modules):
        wins = DATA[m]["verdict"]
        icon, color, word = ("✓", GOOD, "Confirms") if wins else ("✗", CRITICAL, "Negative")
        axes[1].text(i, -0.30, f"{icon} {word}", transform=axes[1].get_xaxis_transform(),
                     ha="center", va="top", fontsize=7.5, color=color, fontweight="bold")

    fig.suptitle(
        "MCP pattern server vs. control, gpt-4.1-mini, 3 runs x 8 tasks per module",
        fontsize=12, y=1.10,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(out_path, dpi=150, facecolor="white", bbox_inches="tight")


def demo() -> None:
    """ponytail: smallest self-check that the data and verdicts line up."""
    assert len(DATA) == 5
    for m, d in DATA.items():
        for metric in ("success", "turns", "tokens"):
            control, pattern = d[metric]
            assert control > 0 and pattern > 0, f"{m}/{metric} has a non-positive value"
    wins = sum(1 for d in DATA.values() if d["verdict"])
    assert wins == 3, f"expected 3 confirming modules, got {wins}"
    print("phase6_chart demo: ok")


if __name__ == "__main__":
    demo()
    make_chart("docs/phase6-chart.png")
    print("wrote docs/phase6-chart.png")
