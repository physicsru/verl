"""Plot accuracy-vs-length curves for length-generalization experiments.

Reads JSONL results from run_eval.py and produces:
  - Per-task plots with IID, easy-to-hard, hard-to-easy regions
  - Combined figure for all tasks

Usage:
    python examples/lengthgen_trainer/eval/plot_results.py \
        --results_dir results/lengthgen \
        --output_dir plots/lengthgen
"""

import argparse
import json
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

TASK_LABELS = {
    "max_subarray": "Max Subarray (Kadane)",
    "lis": "LIS",
    "knapsack_01": "0/1 Knapsack",
}

CONDITION_STYLES = {
    "cot": {"label": "CoT (baseline)", "color": "tab:blue", "marker": "o"},
    "code": {"label": "Code reasoning", "color": "tab:red", "marker": "s"},
}

TRAIN_RANGE = {
    "max_subarray": (5, 20),
    "lis": (5, 20),
    "knapsack_01": (4, 12),
}


def load_results(results_dir):
    # data[task][condition] = list of {n, accuracy, split, ...}
    data = defaultdict(lambda: defaultdict(list))
    for fname in os.listdir(results_dir):
        if not fname.endswith(".jsonl") and not fname.endswith(".json"):
            continue
        with open(os.path.join(results_dir, fname)) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                data[entry["task"]][entry["condition"]].append(entry)
    return data


def plot_single_task(ax, task, task_data):
    train_lo, train_hi = TRAIN_RANGE.get(task, (5, 20))

    ax.set_title(TASK_LABELS.get(task, task), fontsize=13)
    ax.set_xlabel("Problem size (n)")
    ax.set_ylabel("Accuracy")
    ax.set_ylim(-0.05, 1.05)

    # Shade regions
    ax.axvspan(0, train_lo - 0.5, alpha=0.06, color="orange",
               label="Hard→Easy OOD")
    ax.axvspan(train_lo - 0.5, train_hi + 0.5, alpha=0.06, color="green",
               label="IID (train range)")
    ax.axvspan(train_hi + 0.5, 300, alpha=0.06, color="red",
               label="Easy→Hard OOD")
    ax.axvline(x=train_lo, color="gray", linestyle=":", alpha=0.5)
    ax.axvline(x=train_hi, color="gray", linestyle=":", alpha=0.5)

    for cond, style in CONDITION_STYLES.items():
        if cond not in task_data:
            continue
        entries = sorted(task_data[cond], key=lambda e: e["n"])
        ns = [e["n"] for e in entries]
        accs = [e["accuracy"] for e in entries]
        ax.plot(ns, accs, label=style["label"], color=style["color"],
                marker=style["marker"], linewidth=2, markersize=6)

    ax.legend(fontsize=8, loc="lower left")
    ax.grid(True, alpha=0.3)
    ax.set_xscale("log")
    ax.set_xticks([2, 5, 10, 20, 50, 100, 200])
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", required=True)
    parser.add_argument("--output_dir", default="plots/lengthgen")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    data = load_results(args.results_dir)

    tasks = [t for t in ["max_subarray", "lis", "knapsack_01"] if t in data]

    for task in tasks:
        fig, ax = plt.subplots(1, 1, figsize=(7, 4.5))
        plot_single_task(ax, task, data[task])
        fig.tight_layout()
        for ext in ("pdf", "png"):
            fig.savefig(os.path.join(args.output_dir, f"{task}.{ext}"), dpi=150)
        plt.close(fig)
        print(f"Saved {task} plot")

    if len(tasks) > 1:
        fig, axes = plt.subplots(1, len(tasks), figsize=(6 * len(tasks), 4.5))
        if len(tasks) == 1:
            axes = [axes]
        for ax, task in zip(axes, tasks):
            plot_single_task(ax, task, data[task])
        fig.suptitle("Length Generalization: Code Reasoning vs CoT",
                     fontsize=14, y=1.02)
        fig.tight_layout()
        for ext in ("pdf", "png"):
            fig.savefig(os.path.join(args.output_dir, f"combined.{ext}"),
                        dpi=150, bbox_inches="tight")
        plt.close(fig)
        print("Saved combined plot")


if __name__ == "__main__":
    main()
