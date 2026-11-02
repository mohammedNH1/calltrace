"""Check whether the hardest channels are hard for another ASR model too.

Usage: python scripts/compare_whisper_hard_channels.py

Runs faster-whisper large-v3 on the highest-WER channels and writes
results/evaluation/asr_hard_channels_whisper.csv. Parakeet remains the pipeline's model.
"""

from __future__ import annotations

import time

from calltrace.asr import WhisperTranscriber
from calltrace.config import load_config
from calltrace.data import AppTekDataset
from calltrace.evaluation import WerScorer, load_word_mappings
from calltrace.export import _write_csv

TARGETS = [("003", "1"), ("010", "2"), ("009", "2")]


def main() -> None:
    config = load_config()
    dataset = AppTekDataset(config)
    records = {r["call_id"]: r for r in dataset.load_manifest()["selected"]}
    scorer = WerScorer(load_word_mappings(dataset._fetch("word_mappings.py")))
    transcriber = WhisperTranscriber("large-v3", "cpu", "int8")
    transcriber.load()

    rows = []
    for call_id, channel in TARGETS:
        record = records[call_id]
        path = dataset.download_call(record)[f"channel{channel}"]
        began = time.perf_counter()
        words = transcriber.transcribe(path)
        score = scorer.score([dataset.reference_channel_text(record)[channel]], [" ".join(w.text for w in words)])
        rows.append({"call_id": call_id, "channel": channel, "role": record["channels"][channel]["role"],
                     "whisper_wer_pct": round(100 * score["wer"], 2), "deletions": score["deletions"],
                     "reference_words": score["reference_words"], "seconds": round(time.perf_counter() - began, 1)})
        print(rows[-1], flush=True)
        _write_csv(config.path("results") / "evaluation" / "asr_hard_channels_whisper.csv", rows)


if __name__ == "__main__":
    main()
