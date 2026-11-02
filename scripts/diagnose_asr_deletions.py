"""Diagnose high-WER channels: are words lost by segmentation, low level, or recognition?

Usage: python scripts/diagnose_asr_deletions.py

Compares the default VAD with a more sensitive VAD and with peak-normalised audio on
the worst channels and on two easy control channels. Writes
results/evaluation/asr_deletion_diagnosis.csv. These calls belong to the analysed sample,
so any setting chosen from this run is reported as tuned on the sample.
"""

from __future__ import annotations

import csv
import time

import numpy as np
import onnx_asr
import soundfile as sf

from calltrace.asr import tokens_to_words
from calltrace.config import load_config
from calltrace.data import AppTekDataset
from calltrace.evaluation import WerScorer, load_word_mappings
from calltrace.export import _write_csv

BASE_VAD = {"min_silence_duration_ms": 10000, "min_speech_duration_ms": 250, "max_speech_duration_s": 30}
VARIANTS = {
    "default_vad": (dict(BASE_VAD), False),
    "sensitive_vad": ({**BASE_VAD, "threshold": 0.2, "neg_threshold": 0.1}, False),
    "default_vad_normalised": (dict(BASE_VAD), True),
    "sensitive_vad_normalised": ({**BASE_VAD, "threshold": 0.2, "neg_threshold": 0.1}, True),
}
TARGETS = [("003", "1"), ("003", "2"), ("010", "2"), ("009", "2"), ("008", "2"), ("012", "1"), ("001", "2")]


def main() -> None:
    config = load_config()
    dataset = AppTekDataset(config)
    records = {r["call_id"]: r for r in dataset.load_manifest()["selected"]}
    scorer = WerScorer(load_word_mappings(dataset._fetch("word_mappings.py")))
    settings = config["asr"]
    model = onnx_asr.load_model(settings["model_id"], quantization=settings["quantization"])
    vad = onnx_asr.load_vad("silero")

    rows = []
    for call_id, channel in TARGETS:
        record = records[call_id]
        path = dataset.download_call(record)[f"channel{channel}"]
        audio, rate = sf.read(str(path), dtype="float32")
        reference = dataset.reference_channel_text(record)[channel]
        # Level measures show whether quiet recordings line up with the lost words.
        frames = audio[: len(audio) // 480 * 480].reshape(-1, 480)
        rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
        speech_rms = float(np.percentile(rms[rms > 0.003], 50)) if (rms > 0.003).any() else 0.0
        for name, (vad_settings, normalise) in VARIANTS.items():
            signal = audio / max(float(np.abs(audio).max()), 1e-6) * 0.9 if normalise else audio
            recogniser = model.with_vad(vad, **vad_settings).with_timestamps()
            began = time.perf_counter()
            words = []
            for chunk in recogniser.recognize(signal, sample_rate=rate):
                if chunk.tokens:
                    words.extend(tokens_to_words(chunk.start, chunk.tokens, chunk.timestamps, chunk.logprobs))
            score = scorer.score([reference], [" ".join(word.text for word in words)])
            row = {
                "call_id": call_id,
                "channel": channel,
                "role": record["channels"][channel]["role"],
                "speech_rms": round(speech_rms, 4),
                "peak": round(float(np.abs(audio).max()), 3),
                "variant": name,
                "wer_pct": round(100 * score["wer"], 2),
                "deletions": score["deletions"],
                "substitutions": score["substitutions"],
                "insertions": score["insertions"],
                "reference_words": score["reference_words"],
                "seconds": round(time.perf_counter() - began, 1),
            }
            rows.append(row)
            print(row, flush=True)
    _write_csv(config.path("results") / "evaluation" / "asr_deletion_diagnosis.csv", rows)


if __name__ == "__main__":
    main()
