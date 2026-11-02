"""Compare ASR engines on the pilot call, which is not part of the analysed sample.

Usage: python scripts/compare_asr_pilot.py --engine parakeet
       python scripts/compare_asr_pilot.py --engine whisper --whisper-model large-v3

Each engine appends one row to results/evaluation/asr_pilot_comparison.jsonl.
"""

from __future__ import annotations

import argparse
import json
import platform
import time

from calltrace.asr import WhisperTranscriber, build_transcriber
from calltrace.config import load_config
from calltrace.data import AppTekDataset
from calltrace.evaluation import WerScorer, load_word_mappings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["parakeet", "whisper"], required=True)
    parser.add_argument("--whisper-model", default="large-v3")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    args = parser.parse_args()

    config = load_config()
    dataset = AppTekDataset(config)
    pilot = dataset.load_manifest()["pilot"]
    paths = dataset.download_call(pilot)
    references = dataset.reference_channel_text(pilot)
    scorer = WerScorer(load_word_mappings(dataset._fetch("word_mappings.py")))

    # Build the engine, timing model loading apart from inference.
    if args.engine == "whisper":
        transcriber = WhisperTranscriber(args.whisper_model, args.device, args.compute_type)
        model_name = f"faster-whisper {args.whisper_model} ({args.device}, {args.compute_type})"
    else:
        transcriber = build_transcriber(config["asr"])
        model_name = f"{config['asr']['model_id']} ({config['asr']['quantization'] or 'full precision'}, CPU)"
    transcriber.load()

    began = time.perf_counter()
    predictions = {}
    for channel in references:
        words = transcriber.transcribe(paths[f"channel{channel}"])
        predictions[channel] = " ".join(word.text for word in words)
    inference_s = time.perf_counter() - began

    channels = sorted(references)
    score = scorer.score([references[c] for c in channels], [predictions[c] for c in channels])
    row = {
        "engine": args.engine,
        "model": model_name,
        "source_id": pilot["source_id"],
        "wer": score["wer"],
        "reference_words": score["reference_words"],
        "substitutions": score["substitutions"],
        "deletions": score["deletions"],
        "insertions": score["insertions"],
        "load_s": round(transcriber.load_seconds, 1),
        "inference_s": round(inference_s, 1),
        "audio_s_two_channels": round(pilot["duration_s"] * 2, 1),
        "machine": platform.processor(),
    }
    out_dir = config.path("results") / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "asr_pilot_comparison.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    print(json.dumps(row, indent=2))


if __name__ == "__main__":
    main()
