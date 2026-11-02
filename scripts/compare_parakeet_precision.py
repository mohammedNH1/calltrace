"""Test whether int8 quantization causes the high Parakeet WER on hard channels.

Usage: python scripts/compare_parakeet_precision.py

Runs full-precision Parakeet with the same VAD settings on the channels where Whisper did
much better. Writes results/evaluation/asr_parakeet_precision.csv.
"""

from __future__ import annotations

import time

from calltrace.asr import ParakeetTranscriber
from calltrace.config import load_config
from calltrace.data import AppTekDataset
from calltrace.evaluation import WerScorer, load_word_mappings
from calltrace.export import _write_csv

TARGETS = [("003", "1"), ("009", "2"), ("010", "2"), ("012", "1")]


def main() -> None:
    config = load_config()
    dataset = AppTekDataset(config)
    records = {r["call_id"]: r for r in dataset.load_manifest()["selected"]}
    scorer = WerScorer(load_word_mappings(dataset._fetch("word_mappings.py")))
    settings = config["asr"]
    transcriber = ParakeetTranscriber(settings["model_id"], None, settings["vad"])
    transcriber.load()
    print("load seconds", round(transcriber.load_seconds, 1), flush=True)

    rows = []
    for call_id, channel in TARGETS:
        record = records[call_id]
        path = dataset.download_call(record)[f"channel{channel}"]
        began = time.perf_counter()
        words = transcriber.transcribe(path)
        score = scorer.score([dataset.reference_channel_text(record)[channel]], [" ".join(w.text for w in words)])
        rows.append({"call_id": call_id, "channel": channel, "parakeet_full_precision_wer_pct": round(100 * score["wer"], 2),
                     "deletions": score["deletions"], "reference_words": score["reference_words"],
                     "seconds": round(time.perf_counter() - began, 1)})
        print(rows[-1], flush=True)
        _write_csv(config.path("results") / "evaluation" / "asr_parakeet_precision.csv", rows)


if __name__ == "__main__":
    main()
