"""Baseline: diarize the merged mono file, to show what split channels spare us.

Usage: python scripts/mono_diarization_baseline.py [--calls 005 003 ...]

Uses sherpa-onnx with pyannote segmentation 3.0 and a 3D-Speaker embedding model,
both downloaded without a token. The result is scored against manual reference
segments with the same DER code as the channel-based approach. It is a contrast
only: the main pipeline never uses these predicted speakers.
"""

from __future__ import annotations

import argparse
import statistics
import tarfile
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf

from calltrace.config import PROJECT_ROOT, load_config
from calltrace.data import AppTekDataset
from calltrace.evaluation import best_speaker_mapping, diarization_error
from calltrace.export import _write_csv

RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
SEGMENTATION = f"{RELEASES}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
EMBEDDING = f"{RELEASES}/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"


def ensure_models(directory: Path) -> tuple[Path, Path]:
    """Download the two ONNX models once."""
    directory.mkdir(parents=True, exist_ok=True)
    segmentation = directory / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx"
    if not segmentation.exists():
        archive = directory / "segmentation.tar.bz2"
        urllib.request.urlretrieve(SEGMENTATION, archive)
        with tarfile.open(archive) as tar:
            tar.extractall(directory, filter="data")
    embedding = directory / Path(EMBEDDING).name
    if not embedding.exists():
        urllib.request.urlretrieve(EMBEDDING, embedding)
    return segmentation, embedding


def main() -> None:
    import sherpa_onnx

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls", nargs="*", default=None, help="call IDs; default is all calls")
    args = parser.parse_args()

    config = load_config()
    dataset = AppTekDataset(config)
    segmentation, embedding = ensure_models(PROJECT_ROOT / "models" / "diarization")
    settings = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(segmentation)),
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(embedding)),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=2),  # the call has two speakers
    )
    diarizer = sherpa_onnx.OfflineSpeakerDiarization(settings)

    rows = []
    evaluation = config["evaluation"]
    for record in dataset.load_manifest()["selected"]:
        if args.calls and record["call_id"] not in args.calls:
            continue
        audio_path = dataset.download_call(record)["merged"]
        audio, _ = sf.read(str(audio_path), dtype="float32")
        audio = audio if audio.ndim == 1 else np.mean(audio, axis=1)
        began = time.perf_counter()
        predicted = diarizer.process(audio).sort_by_start_time()
        seconds = time.perf_counter() - began

        anonymous: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for segment in predicted:
            anonymous[f"cluster{segment.speaker}"].append((segment.start, segment.end))
        reference: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for segment in dataset.reference_segments(record):
            reference[segment["role"].capitalize()].append((segment["start"], segment["end"]))

        # Clusters are anonymous, so they are mapped to speakers using the reference.
        # That mapping is only available in evaluation: it is not role identification.
        mapping = best_speaker_mapping(reference, anonymous, record["duration_s"], evaluation["frame_s"])
        hypothesis = {mapping[name]: spans for name, spans in anonymous.items() if name in mapping}
        metrics = diarization_error(reference, hypothesis, record["duration_s"], evaluation["frame_s"],
                                    evaluation["collar_s"])
        row = {
            "call_id": record["call_id"],
            "der_pct": round(100 * metrics["der"], 2),
            "missed_pct": round(100 * metrics["missed"], 2),
            "false_alarm_pct": round(100 * metrics["false_alarm"], 2),
            "confusion_pct": round(100 * metrics["confusion"], 2),
            "inference_s": round(seconds, 1),
            "audio_s": record["duration_s"],
        }
        rows.append(row)
        print(row, flush=True)

    out_dir = config.path("results") / "evaluation"
    _write_csv(out_dir / "mono_diarization_baseline.csv", rows)
    print("median DER %:", statistics.median(row["der_pct"] for row in rows))


if __name__ == "__main__":
    main()
