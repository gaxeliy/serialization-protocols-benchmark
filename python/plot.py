"""Plot benchmark results with matplotlib.

Reads results/*.json and produces charts saved to plots/.
"""

import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np


RESULTS_DIR = "results"
PLOTS_DIR = "plots"
DATASETS = ["small", "medium", "large"]
COLORS = {
    "protobuf": "#4285F4",
    "flatbuffers": "#EA4335",
    "flatbuffers-reuse": "#FF7043",
    "msgpack": "#FBBC04",
    "pickle": "#34A853",
}


def load_results() -> list[dict]:
    all_results = []
    for fname in sorted(os.listdir(RESULTS_DIR)):
        if fname.endswith(".json"):
            with open(os.path.join(RESULTS_DIR, fname)) as f:
                data = json.load(f)
                all_results.extend(data)
    return all_results


def make_chart(results: list[dict], language: str):
    """Create a 3-column figure: size | ser time | deser time."""
    lang_results = [r for r in results if r["language"] == language]
    protocols = sorted(set(r["protocol"] for r in lang_results))

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    fig.suptitle(
        f"Serialization Benchmarks — {language.upper()}",
        fontsize=14, fontweight="bold", y=1.02,
    )

    x = np.arange(len(DATASETS))
    width = 0.8 / len(protocols)

    # ── Size ──
    ax = axes[0]
    for pi, proto in enumerate(protocols):
        vals = []
        for ds in DATASETS:
            r = [r for r in lang_results if r["protocol"] == proto and r["dataset"] == ds]
            vals.append(r[0]["size_bytes"] if r else 0)
        bars = ax.bar(x + pi * width, vals, width, label=proto, color=COLORS.get(proto, "#999"),
                      edgecolor="white", linewidth=0.5)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(vals) * 0.01,
                    str(v), ha="center", va="bottom", fontsize=8, rotation=90 if v > 1000 else 0)

    ax.set_title("Message size (bytes)")
    ax.set_xticks(x + width * (len(protocols) - 1) / 2)
    ax.set_xticklabels(DATASETS)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)

    # ── Serialization time ──
    ax = axes[1]
    for pi, proto in enumerate(protocols):
        vals = []
        for ds in DATASETS:
            r = [r for r in lang_results if r["protocol"] == proto and r["dataset"] == ds]
            vals.append(r[0]["serialization_time_us"] if r else 0)
        ax.bar(x + pi * width, vals, width, label=proto, color=COLORS.get(proto, "#999"),
               edgecolor="white", linewidth=0.5)

    ax.set_title("Serialization time (us)")
    ax.set_xticks(x + width * (len(protocols) - 1) / 2)
    ax.set_xticklabels(DATASETS)
    ax.grid(axis="y", alpha=0.3)

    # ── Deserialization time ──
    ax = axes[2]
    for pi, proto in enumerate(protocols):
        vals = []
        for ds in DATASETS:
            r = [r for r in lang_results if r["protocol"] == proto and r["dataset"] == ds]
            vals.append(r[0]["deserialization_time_us"] if r else 0)
        ax.bar(x + pi * width, vals, width, label=proto, color=COLORS.get(proto, "#999"),
               edgecolor="white", linewidth=0.5)

    ax.set_title("Deserialization time (us)")
    ax.set_xticks(x + width * (len(protocols) - 1) / 2)
    ax.set_xticklabels(DATASETS)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    path = os.path.join(PLOTS_DIR, f"{language}_benchmark.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {path}")


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 11, "axes.labelsize": 9})

    results = load_results()
    if not results:
        print("No results found! Run benchmarks first.", file=sys.stderr)
        sys.exit(1)

    for lang in sorted(set(r["language"] for r in results)):
        make_chart(results, lang)


if __name__ == "__main__":
    main()
