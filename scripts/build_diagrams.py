"""Draw the architecture and sequence diagrams into reports/figures/."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from calltrace.config import load_config

TEAL, CHARCOAL, GREY, PAPER, TINT, AMBER = "#0F766E", "#1F2937", "#6B7280", "#FBFAF7", "#E6F4F1", "#FEF3C7"
plt.rcParams["font.family"] = "DejaVu Sans"


def box(ax, x, y, w, h, title, body="", fill=TINT, edge=TEAL):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.012", facecolor=fill,
                                edgecolor=edge, linewidth=1.3))
    if body:
        ax.text(x + w / 2, y + h - 0.022, title, ha="center", va="top", fontsize=10.5, fontweight="bold", color=CHARCOAL)
        ax.text(x + w / 2, y + h - 0.058, body, ha="center", va="top", fontsize=8.6, color=CHARCOAL, linespacing=1.3)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=10.5, fontweight="bold", color=CHARCOAL)


def arrow(ax, start, end, colour=CHARCOAL, style="-|>", linestyle="-"):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=13, color=colour, linewidth=1.3,
                                 linestyle=linestyle, shrinkA=0, shrinkB=0))


def architecture(path) -> None:
    fig, ax = plt.subplots(figsize=(13, 7), facecolor=PAPER)
    ax.set_xlim(0, 1), ax.set_ylim(0, 1), ax.axis("off")
    ax.text(0.5, 0.97, "CallTrace architecture", ha="center", fontsize=15, fontweight="bold", color=CHARCOAL)

    # Top row: from data to validated analysis.
    w, h, y = 0.17, 0.24, 0.63
    columns = [0.02, 0.215, 0.41, 0.605, 0.80]
    entries = [
        ("Data", "AppTek dataset\n(pinned commit)\nseeded sample: 14 calls\nchecksums, audio checks"),
        ("Transcription", "Silero VAD segments\nParakeet TDT 0.6B v3\nrun per speaker channel\nword timestamps"),
        ("Turns", "Channel gives speaker\nmetadata gives role\nwords merged into turns\nstable turn IDs"),
        ("Analysis", "Local Qwen3.5-4B\nsummary, handling,\nsentiment windows\nJSON schema, cache"),
        ("Validation", "Turn IDs exist\nquotes match turn\nCustomer turns only\nbounded retries"),
    ]
    for x, (title, body) in zip(columns, entries):
        box(ax, x, y, w, h, title, body)
    for left, right in zip(columns, columns[1:]):
        arrow(ax, (left + w + 0.002, y + h / 2), (right - 0.002, y + h / 2))

    # Bottom row: outputs and uses.
    w2, h2, y2 = 0.27, 0.22, 0.2
    box(ax, 0.02, y2, w2, h2, "Results", "transcripts, turns.csv, summaries.csv\nsentiment.csv, calls.csv, calls.jsonl\nper-call JSON, failures, runtime")
    box(ax, 0.365, y2, w2, h2, "Evaluation", "WER and DER against manual reference\ngrounding audit, error analysis\nASR vs reference experiment")
    box(ax, 0.71, y2, w2, h2, "Review interface", "Streamlit: claim to turn to audio time\nnotebooks and reports stay usable\nwithout the app")
    arrow(ax, (0.885, 0.625), (0.155, 0.43))
    arrow(ax, (0.295, y2 + h2 / 2), (0.36, y2 + h2 / 2))
    arrow(ax, (0.64, y2 + h2 / 2), (0.705, y2 + h2 / 2))

    box(ax, 0.02, 0.04, 0.96, 0.085, "Human review worksheet: labels are entered blind to model output; agreement counts completed cells only",
        fill=AMBER, edge="#B45309")
    arrow(ax, (0.5, 0.195), (0.5, 0.13), colour=GREY)
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor=PAPER)
    plt.close(fig)


def sequence(path) -> None:
    participants = ["CLI /\npipeline", "Dataset", "Parakeet\nASR", "Turn\nbuilder", "Local LLM\n(llama.cpp)", "Validator", "Result\nfiles"]
    fig, ax = plt.subplots(figsize=(13, 8), facecolor=PAPER)
    ax.set_xlim(0, 1), ax.set_ylim(0, 1), ax.axis("off")
    ax.text(0.5, 0.98, "Processing sequence for one call", ha="center", fontsize=15, fontweight="bold", color=CHARCOAL)
    xs = [0.07 + i * (0.86 / (len(participants) - 1)) for i in range(len(participants))]
    top, bottom = 0.87, 0.03
    for x, name in zip(xs, participants):
        box(ax, x - 0.055, top, 0.11, 0.075, name)
        ax.plot([x, x], [top, bottom], color=GREY, linewidth=0.9, linestyle=(0, (4, 3)))

    messages = [
        (0, 6, "Finished call? If analysis.json exists, skip (resume)", True),
        (0, 1, "Download 2 channels + merged file (pinned commit)", False),
        (1, 0, "Audio; checks and SHA-256 recorded", True),
        (0, 2, "Transcribe channel 1, then channel 2 (cached per channel)", False),
        (2, 0, "Words with timestamps and log-probabilities", True),
        (0, 3, "Words + channel role metadata", False),
        (3, 0, "Turns with stable IDs, backchannel and courtesy flags", True),
        (0, 4, "Summary request: untrusted transcript + schema of allowed turn IDs", False),
        (4, 5, "Claims with turn IDs and quotes", False),
        (5, 4, "Quote not in turn: retry with errors (at most 2 times)", True),
        (0, 4, "Beginning, ending, overall, agent: separate sentiment requests", False),
        (5, 0, "Validation report; times copied from turns, never from the model", True),
        (0, 6, "transcript.json, analysis.json; on any error, failures.jsonl and next call", False),
    ]
    step = (top - bottom - 0.05) / len(messages)
    y = top - 0.04
    for source, target, label, dashed in messages:
        arrow(ax, (xs[source], y), (xs[target], y), colour=TEAL if not dashed else GREY,
              linestyle="--" if dashed else "-")
        low, high = sorted((xs[source], xs[target]))
        # The label sits in the widest gap so that it stays readable over the lifelines.
        ax.text((low + high) / 2 if high - low > 0.3 else min(high + 0.01, 0.62), y + 0.006, label,
                ha="center" if high - low > 0.3 else "left", va="bottom", fontsize=8.8, color=CHARCOAL,
                bbox={"facecolor": PAPER, "edgecolor": "none", "pad": 0.8})
        y -= step
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor=PAPER)
    plt.close(fig)


def main() -> None:
    figures = load_config().path("reports") / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    architecture(figures / "architecture.png")
    sequence(figures / "sequence.png")
    print(figures)


if __name__ == "__main__":
    main()
