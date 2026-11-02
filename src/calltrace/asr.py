"""Speech recognition per speaker channel.

Each dataset recording holds one speaker, so the speaker is known from the file and
ASR only has to produce words with timestamps. Two engines share one small interface:
Parakeet (the selected model) and Whisper (used only in the pilot comparison).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path

from .schemas import Word


class Transcriber(ABC):
    """Common interface so that engines can be swapped through the configuration."""

    name: str = "base"
    load_seconds: float = 0.0

    @abstractmethod
    def load(self) -> None:
        """Load model weights. Timed separately from per-call inference."""

    @abstractmethod
    def transcribe(self, audio_path: Path) -> list[Word]:
        """Return time-ordered words for one single-speaker audio file."""


def tokens_to_words(start_offset: float, tokens, timestamps, logprobs) -> list[Word]:
    """Group sub-word tokens into words.

    Parakeet tokens that open a new word begin with a space. A token's timestamp marks
    where it starts, so a word's end is taken from the next token, or a short fixed
    length for the last token of a segment.
    """
    words: list[Word] = []
    current_text, current_start, current_logprobs = "", 0.0, []
    for index, token in enumerate(tokens):
        begins_word = token.startswith(" ") or not current_text
        if begins_word and current_text:
            end = start_offset + timestamps[index]
            words.append(_make_word(current_text, current_start, end, current_logprobs))
            current_text, current_logprobs = "", []
        if not current_text:
            current_start = start_offset + timestamps[index]
        current_text += token
        if logprobs:
            current_logprobs.append(logprobs[index])
    if current_text:
        end = start_offset + timestamps[-1] + 0.3
        words.append(_make_word(current_text, current_start, end, current_logprobs))
    return words


def _make_word(text: str, start: float, end: float, logprobs: list[float]) -> Word:
    # Cap a word's length: the next token can come after a long pause in the same chunk.
    end = min(end, start + 1.5)
    mean_logprob = sum(logprobs) / len(logprobs) if logprobs else None
    return Word(text=text.strip(), start=round(start, 3), end=round(end, 3), logprob=mean_logprob)


class ParakeetTranscriber(Transcriber):
    """NVIDIA Parakeet TDT 0.6B v3 (ONNX export), segmented with Silero VAD."""

    name = "parakeet"

    def __init__(self, model_id: str, quantization: str, vad_settings: dict):
        self.model_id = model_id
        self.quantization = quantization
        self.vad_settings = vad_settings
        self._model = None

    def load(self) -> None:
        import onnx_asr

        began = time.perf_counter()
        model = onnx_asr.load_model(self.model_id, quantization=self.quantization)
        vad = onnx_asr.load_vad("silero")
        self._model = model.with_vad(vad, **self.vad_settings).with_timestamps()
        self.load_seconds = time.perf_counter() - began

    def transcribe(self, audio_path: Path) -> list[Word]:
        if self._model is None:
            self.load()
        words: list[Word] = []
        # One result per VAD chunk. Token timestamps are relative to the chunk start.
        for chunk in self._model.recognize(str(audio_path)):
            if chunk.tokens:
                words.extend(tokens_to_words(chunk.start, chunk.tokens, chunk.timestamps, chunk.logprobs))
        return words


class WhisperTranscriber(Transcriber):
    """faster-whisper baseline. Used only to compare engines on the pilot call."""

    name = "whisper"

    def __init__(self, model_id: str = "large-v3", device: str = "cpu", compute_type: str = "int8"):
        self.model_id = model_id
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def load(self) -> None:
        from faster_whisper import WhisperModel

        began = time.perf_counter()
        self._model = WhisperModel(self.model_id, device=self.device, compute_type=self.compute_type)
        self.load_seconds = time.perf_counter() - began

    def transcribe(self, audio_path: Path) -> list[Word]:
        if self._model is None:
            self.load()
        segments, _ = self._model.transcribe(
            str(audio_path),
            language="en",
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 10000,
                "min_speech_duration_ms": 250,
                "max_speech_duration_s": 30,
            },
            condition_on_previous_text=False,
        )
        words: list[Word] = []
        for segment in segments:
            for word in segment.words or []:
                words.append(
                    Word(text=word.word.strip(), start=round(word.start, 3), end=round(word.end, 3))
                )
        return words


def build_transcriber(settings: dict) -> Transcriber:
    """Create the transcriber named in the configuration."""
    if settings["engine"] == "parakeet":
        return ParakeetTranscriber(settings["model_id"], settings["quantization"], settings["vad"])
    if settings["engine"] == "whisper":
        return WhisperTranscriber(settings["model_id"])
    raise ValueError(f"unknown ASR engine: {settings['engine']}")
