"""Evaluation helpers: WER with the dataset's scoring protocol and frame-level DER.

WER measures word-level transcription errors under one stated normalisation. It is
not a general accuracy figure for the system, and 1 - WER is never reported as one.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import jiwer
import numpy as np
from whisper_normalizer.english import EnglishTextNormalizer

_MAPPING_NAMES = ("hesitations", "number_normalisations", "word_normalisations")


def load_word_mappings(path: Path) -> dict[str, str]:
    """Read the dataset's word_mappings.py without executing it.

    The file comes from a downloaded repository, so its dictionaries are parsed as
    literals instead of being imported.
    """
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    mappings: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in _MAPPING_NAMES:
            mappings.update(ast.literal_eval(node.value))
    return mappings


class WerScorer:
    """Re-implementation of the dataset's score.py normalisation pipeline.

    Steps: remove truncated reference words (trailing "~") and "oh" in predictions,
    apply the Whisper English normaliser, join split digit runs, then lowercase,
    remove punctuation, apply dataset word mappings, and tokenise.
    Speaker labels are not part of the scored text.
    """

    def __init__(self, word_mappings: dict[str, str] | None = None):
        self._normalizer = EnglishTextNormalizer()
        steps = [jiwer.ToLowerCase(), jiwer.RemovePunctuation(), jiwer.RemoveMultipleSpaces(), jiwer.Strip()]
        if word_mappings:
            steps.append(jiwer.SubstituteWords(word_mappings))
        steps.append(jiwer.ReduceToListOfListOfWords())
        self._transform = jiwer.Compose(steps)
        self._pred_cleaner = jiwer.SubstituteWords({"oh": ""})
        self._ref_cleaner = jiwer.SubstituteRegexes({r"\b(\w+)~(?=\W|$)": ""})

    @staticmethod
    def _join_digits(text: str) -> str:
        return re.sub(r"\b\d+(?:\s+\d+)+\b", lambda m: m.group(0).replace(" ", ""), text)

    def normalise_pair(self, reference: str, prediction: str) -> tuple[str, str]:
        ref = self._normalizer(self._ref_cleaner.process_string(reference))
        pred = self._normalizer(self._pred_cleaner.process_string(prediction))
        return self._join_digits(ref), self._join_digits(pred)

    def score(self, references: list[str], predictions: list[str]) -> dict:
        """Pooled WER over aligned reference and prediction texts."""
        pairs = [self.normalise_pair(r, p) for r, p in zip(references, predictions)]
        measures = jiwer.process_words(
            [pair[0] for pair in pairs],
            [pair[1] for pair in pairs],
            reference_transform=self._transform,
            hypothesis_transform=self._transform,
        )
        reference_words = measures.hits + measures.substitutions + measures.deletions
        return {
            "wer": measures.wer,
            "hits": measures.hits,
            "substitutions": measures.substitutions,
            "deletions": measures.deletions,
            "insertions": measures.insertions,
            "reference_words": reference_words,
        }


def _activity(segments: list[tuple[float, float]], n_frames: int, frame_s: float) -> np.ndarray:
    """Boolean activity track for one speaker."""
    track = np.zeros(n_frames, dtype=bool)
    for start, end in segments:
        track[int(start / frame_s) : int(np.ceil(end / frame_s))] = True
    return track


def diarization_error(
    reference: dict[str, list[tuple[float, float]]],
    hypothesis: dict[str, list[tuple[float, float]]],
    duration_s: float,
    frame_s: float = 0.01,
    collar_s: float = 0.25,
) -> dict:
    """Frame-level DER for exactly two speakers with known or mapped identities.

    Frames within `collar_s` of a reference boundary are not scored. For hypotheses
    with anonymous speakers, pass them through `best_speaker_mapping` first.
    Overlapped speech is scored per speaker, as in the standard DER definition.
    """
    n_frames = int(np.ceil(duration_s / frame_s)) + 1
    names = sorted(reference)
    ref = np.stack([_activity(reference[name], n_frames, frame_s) for name in names])
    hyp = np.stack([_activity(hypothesis.get(name, []), n_frames, frame_s) for name in names])

    # Build the mask of frames forgiven around every reference boundary.
    scored = np.ones(n_frames, dtype=bool)
    collar_frames = int(collar_s / frame_s)
    for name in names:
        for start, end in reference[name]:
            for edge in (start, end):
                centre = int(edge / frame_s)
                scored[max(centre - collar_frames, 0) : centre + collar_frames] = False

    ref_count = ref[:, scored].sum(axis=0)
    hyp_count = hyp[:, scored].sum(axis=0)
    correct = (ref[:, scored] & hyp[:, scored]).sum(axis=0)
    total = int(ref_count.sum())
    missed = int(np.maximum(ref_count - hyp_count, 0).sum())
    false_alarm = int(np.maximum(hyp_count - ref_count, 0).sum())
    confusion = int((np.minimum(ref_count, hyp_count) - correct).sum())
    denominator = max(total, 1)
    return {
        "der": (missed + false_alarm + confusion) / denominator,
        "missed": missed / denominator,
        "false_alarm": false_alarm / denominator,
        "confusion": confusion / denominator,
        "scored_speech_s": total * frame_s,
    }


def best_speaker_mapping(
    reference: dict[str, list[tuple[float, float]]],
    anonymous: dict[str, list[tuple[float, float]]],
    duration_s: float,
    frame_s: float = 0.01,
) -> dict[str, str]:
    """Map anonymous cluster names to reference names by greatest overlap."""
    n_frames = int(np.ceil(duration_s / frame_s)) + 1
    ref_names = sorted(reference)
    ref_tracks = {name: _activity(reference[name], n_frames, frame_s) for name in ref_names}
    clusters = sorted(anonymous, key=lambda c: -sum(e - s for s, e in anonymous[c]))
    mapping: dict[str, str] = {}
    available = list(ref_names)
    for cluster in clusters:
        if not available:
            break
        track = _activity(anonymous[cluster], n_frames, frame_s)
        best = max(available, key=lambda name: int((track & ref_tracks[name]).sum()))
        mapping[cluster] = best
        available.remove(best)
    return mapping
