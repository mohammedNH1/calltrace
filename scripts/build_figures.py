"""Draw the WER figure into reports/figures/ from measured results only."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from calltrace.config import load_config

FULL, INT8, GREY, CHARCOAL, PAPER = "#0D9488", "#B45309", "#9CA3AF", "#1F2937", "#FBFAF7"


def main() -> None:
    config = load_config()
    evaluation = config.path("results") / "evaluation"
    final = pd.read_csv(evaluation / "wer_per_call.csv", dtype={"call_id": str})
    old = pd.read_csv(evaluation / "parakeet_int8" / "wer_per_call.csv")
    old["call_id"] = old["call_id"].astype(str).str.zfill(3)
    data = final.merge(old[["call_id", "wer_pct"]], on="call_id", suffixes=("", "_int8")).sort_values("wer_pct")

    fig, ax = plt.subplots(figsize=(10.5, 5.4), facecolor=PAPER)
    ax.set_facecolor(PAPER)
    y = range(len(data))
    # A thin line shows how far each call moved. Marker shape also separates the series.
    ax.hlines(y, data["wer_pct"], data["wer_pct_int8"], color="#D1D5DB", linewidth=2, zorder=1)
    ax.scatter(data["published_accent_wer_pct"], y, marker="|", s=170, color=GREY, linewidths=2.2, zorder=2,
               label="Published mean for that accent, Parakeet v3 (all calls)")
    ax.scatter(data["wer_pct_int8"], y, marker="o", s=62, facecolor=PAPER, edgecolor=INT8, linewidths=2, zorder=3,
               label="Parakeet int8 weights (first run)")
    ax.scatter(data["wer_pct"], y, marker="o", s=62, color=FULL, edgecolor=PAPER, linewidths=1.5, zorder=4,
               label="Parakeet full precision (final)")

    ax.set_yticks(list(y), [f"{row.call_id}  {row.accent}" for row in data.itertuples()], fontsize=10, color=CHARCOAL)
    ax.set_xlabel("Word error rate per call (%), both channels pooled", fontsize=10.5, color=CHARCOAL)
    ax.set_xlim(0, 42)
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#D1D5DB")
    ax.tick_params(axis="both", length=0, labelcolor=CHARCOAL)
    ax.set_title("Quantized weights caused most of the worst errors", loc="left", fontsize=14, fontweight="bold",
                 color=CHARCOAL, pad=26)
    ax.text(0, 1.015, "14 calls, 19,248 reference words. Lower is better. WER is not overall system accuracy.",
            transform=ax.transAxes, fontsize=9.5, color="#4B5563")

    # Label only the call with the largest change, which carries the message.
    largest = data.assign(change=data["wer_pct_int8"] - data["wer_pct"]).sort_values("change").iloc[-1]
    row = list(data["call_id"]).index(largest["call_id"])
    ax.annotate(f"{largest['wer_pct_int8']:.1f}%", (largest["wer_pct_int8"], row), xytext=(8, -4),
                textcoords="offset points", fontsize=9.5, color=CHARCOAL)
    ax.annotate(f"{largest['wer_pct']:.1f}%", (largest["wer_pct"], row), xytext=(-8, 7), ha="center",
                textcoords="offset points", fontsize=9.5, color=CHARCOAL)
    ax.legend(loc="lower right", frameon=False, fontsize=9.5, labelcolor=CHARCOAL)

    out = config.path("reports") / "figures" / "wer_by_call.png"
    fig.savefig(out, dpi=170, bbox_inches="tight", facecolor=PAPER)
    print(out)


if __name__ == "__main__":
    main()
