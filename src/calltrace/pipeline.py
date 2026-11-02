"""End-to-end orchestration with per-call resume and explicit failure reporting.

Directory layout for one run (`results/` for the full sample, `results/smoke/` for smoke):
    calls/<call_id>/asr_channel<N>.json   raw word-level ASR
    calls/<call_id>/transcript.json       speaker-separated turns
    calls/<call_id>/analysis.json         summary, sentiment, handling, validation
    failures.jsonl                        one row per failed call and step
    runtime.jsonl                         timings for each processed call
"""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path

from .analysis import CallAnalyzer
from .asr import Transcriber, build_transcriber
from .config import Config
from .data import AppTekDataset, audio_quality
from .llm import LLMClient, LLMError
from .schemas import CallAnalysis, CallTranscript, SpeakerInfo, Turn, Word
from .turns import build_turns, clean_reference_text, clean_text, count_agent_cues, is_courtesy_only, overlap_share

SPEAKER_LABELS = {1: "Speaker 1", 2: "Speaker 2"}
ROLE_NAMES = {"agent": "Agent", "customer": "Customer"}


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")


class CallPipeline:
    """Runs transcription, turn building, and analysis for a list of calls."""

    def __init__(self, config: Config, output_dir: Path | None = None, use_llm: bool = True):
        self.config = config
        self.dataset = AppTekDataset(config)
        self.output_dir = output_dir or config.path("results")
        self.calls_dir = self.output_dir / "calls"
        self.calls_dir.mkdir(parents=True, exist_ok=True)
        self.use_llm = use_llm
        self.transcriber: Transcriber | None = None
        self.client = LLMClient(config["llm"], config.path("results") / "cache" / "llm")
        self.analyzer = CallAnalyzer(self.client, config)

    # -- Transcription ---------------------------------------------------------------

    def _get_transcriber(self) -> Transcriber:
        """Load ASR only when a call really needs it, so that resumed runs start fast."""
        if self.transcriber is None:
            self.transcriber = build_transcriber(self.config["asr"])
            self.transcriber.load()
            self._log_runtime({"step": "asr_model_load", "seconds": round(self.transcriber.load_seconds, 2)})
        return self.transcriber

    def _channel_words(self, record: dict, channel: str, audio_path: Path) -> list[Word]:
        """Return cached ASR words for a channel, or run ASR and cache them."""
        cache = self.calls_dir / record["call_id"] / f"asr_channel{channel}.json"
        settings = self.config["asr"]
        if cache.exists():
            cached = json.loads(cache.read_text(encoding="utf-8"))
            # Different weights give different words, so both must match to reuse the cache.
            if cached["model_id"] == settings["model_id"] and cached.get("quantization") == settings["quantization"]:
                return [Word(**word) for word in cached["words"]]
        began = time.perf_counter()
        words = self._get_transcriber().transcribe(audio_path)
        _write_json(
            cache,
            {
                "model_id": settings["model_id"],
                "quantization": settings["quantization"],
                "vad": settings["vad"],
                "inference_s": round(time.perf_counter() - began, 2),
                "words": [word.model_dump() for word in words],
            },
        )
        return words

    def transcribe_call(self, record: dict) -> CallTranscript:
        """Produce the speaker-separated transcript for one call."""
        call_id = record["call_id"]
        target = self.calls_dir / call_id / "transcript.json"
        if target.exists():
            return CallTranscript.model_validate_json(target.read_text(encoding="utf-8"))

        paths = self.dataset.download_call(record)
        notes: list[str] = []
        words_by_channel: dict[int, list[Word]] = {}
        quality = {}
        for channel in sorted(record["channels"]):
            path = paths[f"channel{channel}"]
            # Raises for unreadable or empty audio. The caller records that as a failure.
            quality[channel] = audio_quality(path)
            if quality[channel]["active_share"] < 0.005:
                notes.append(f"Channel {channel} is almost silent ({quality[channel]['active_share']:.1%} active).")
            words_by_channel[int(channel)] = self._channel_words(record, channel, path)
            if not words_by_channel[int(channel)]:
                notes.append(f"No speech recognised on channel {channel}.")
        _write_json(self.calls_dir / call_id / "audio_quality.json", quality)
        if not any(words_by_channel.values()):
            raise ValueError("no speech recognised on either channel")

        roles = {int(ch): ROLE_NAMES[info["role"]] for ch, info in record["channels"].items()}
        turns = build_turns(
            call_id, words_by_channel, SPEAKER_LABELS, roles, self.config["turns"], self.config["asr"]
        )

        # Cross-check metadata roles against what each channel says. The metadata stays
        # authoritative, and a disagreement is reported instead of being silently fixed.
        cue_counts = {
            channel: count_agent_cues(" ".join(t.text_clean for t in turns if t.channel == channel))
            for channel in roles
        }
        speakers: list[SpeakerInfo] = []
        for channel, role in sorted(roles.items()):
            other = next(c for c in roles if c != channel)
            if role == "Agent":
                if cue_counts[channel] > cue_counts[other]:
                    check = f"agrees (agent cues: {cue_counts[channel]} vs {cue_counts[other]})"
                elif cue_counts[channel] == cue_counts[other]:
                    check = f"inconclusive (agent cues: {cue_counts[channel]} vs {cue_counts[other]})"
                else:
                    check = f"DISAGREES (agent cues: {cue_counts[channel]} vs {cue_counts[other]})"
                    notes.append("Agent-phrase check disagrees with role metadata; review roles.")
            else:
                check = "see agent channel"
            speakers.append(
                SpeakerInfo(
                    speaker=SPEAKER_LABELS[channel],
                    channel=channel,
                    role=role,
                    speaker_id=record["channels"][str(channel)]["speaker_id"],
                    role_method="dataset metadata for this channel file",
                    role_uncertainty="low: annotated by the dataset, cross-checked with agent phrases",
                    role_text_check=check,
                )
            )

        low_share = sum(turn.low_confidence for turn in turns) / max(len(turns), 1)
        if low_share:
            notes.append(f"{low_share:.0%} of turns flagged as low ASR confidence (uncalibrated heuristic).")
        if any(word in turns[0].text_clean.lower() for word in ("scenario", record["domain"])) and len(
            turns[0].text_clean.split()
        ) <= 8:
            notes.append("First turn looks like a spoken recording slate, not part of the conversation.")

        # Heavy overlap suggests the two channel files are out of sync, so order cannot be trusted.
        intervals = {
            channel: [(t.start, t.end) for t in turns if t.channel == channel] for channel in roles
        }
        overlap = overlap_share(*intervals.values())
        if overlap > self.config["turns"]["out_of_sync_overlap_share"]:
            notes.append(
                f"Speakers overlap on {overlap:.0%} of the quieter speaker's time: the channels may be out of "
                "sync, so turn order, the summary, and the sentiment windows are unreliable."
            )

        transcript = CallTranscript(
            call_id=call_id,
            source_id=record["source_id"],
            accent=record["accent"],
            domain=record["domain"],
            duration_s=record["duration_s"],
            transcript_source="asr",
            speaker_boundaries_source=(
                "Speaker identity: dataset split channels. Turn boundaries: predicted from ASR word timestamps."
            ),
            speakers=speakers,
            turns=turns,
            quality_notes=notes,
        )
        _write_json(target, transcript.model_dump())
        return transcript

    def reference_transcript(self, record: dict) -> CallTranscript:
        """Build a transcript from the manual reference, for the controlled experiment only."""
        segments = self.dataset.reference_segments(record)
        channel_of = {info["role"]: int(ch) for ch, info in record["channels"].items()}
        turns: list[Turn] = []
        for index, segment in enumerate(sorted(segments, key=lambda s: s["start"]), start=1):
            cleaned_reference = clean_reference_text(segment["text"])
            if not cleaned_reference:
                continue
            channel = channel_of[segment["role"]]
            cleaned = clean_text(cleaned_reference)
            turns.append(
                Turn(
                    turn_id=f"{record['call_id']}-R{index:04d}",
                    call_id=record["call_id"],
                    speaker=SPEAKER_LABELS[channel],
                    role=ROLE_NAMES[segment["role"]],
                    channel=channel,
                    start=segment["start"],
                    end=segment["end"],
                    text_raw=segment["text"],
                    text_clean=cleaned,
                    is_courtesy_only=is_courtesy_only(cleaned),
                )
            )
        return CallTranscript(
            call_id=record["call_id"],
            source_id=record["source_id"],
            accent=record["accent"],
            domain=record["domain"],
            duration_s=record["duration_s"],
            transcript_source="reference",
            speaker_boundaries_source="Manual reference segments supplied by the dataset.",
            speakers=[
                SpeakerInfo(
                    speaker=SPEAKER_LABELS[int(ch)],
                    channel=int(ch),
                    role=ROLE_NAMES[info["role"]],
                    speaker_id=info["speaker_id"],
                    role_method="dataset annotation",
                    role_uncertainty="low",
                    role_text_check="not applicable",
                )
                for ch, info in sorted(record["channels"].items())
            ],
            turns=turns,
        )

    # -- Analysis --------------------------------------------------------------------

    def analyse_call(self, transcript: CallTranscript, output_name: str = "analysis.json") -> CallAnalysis:
        target = self.calls_dir / transcript.call_id / output_name
        if target.exists():
            return CallAnalysis.model_validate_json(target.read_text(encoding="utf-8"))
        analysis = self.analyzer.analyse(transcript)
        _write_json(target, analysis.model_dump())
        return analysis

    # -- Run loop --------------------------------------------------------------------

    def _log_runtime(self, row: dict) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with open(self.output_dir / "runtime.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")

    def _log_failure(self, call_id: str, step: str, error: Exception) -> None:
        with open(self.output_dir / "failures.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"call_id": call_id, "step": step, "error": str(error)}) + "\n")
        print(f"[{call_id}] FAILED at {step}: {error}")

    def run(self, records: list[dict]) -> dict:
        """Process calls one at a time. A failure stops that call, not the whole run."""
        summary = {"processed": [], "failed": [], "resumed": []}
        # The server is needed only if some call still lacks an analysis.
        pending = [r for r in records if not (self.calls_dir / r["call_id"] / "analysis.json").exists()]
        if self.use_llm and pending and not self.client.is_available():
            raise LLMError(
                f"No LLM server at {self.client.base_url}. Start it with "
                "`python scripts/start_llm_server.py`, or pass --asr-only."
            )
        for record in records:
            call_id = record["call_id"]
            done = self.calls_dir / call_id / ("analysis.json" if self.use_llm else "transcript.json")
            if done.exists():
                summary["resumed"].append(call_id)
                print(f"[{call_id}] already complete, skipped")
                continue

            print(f"[{call_id}] {record['source_id']} ({record['duration_s']:.0f} s)")
            step = "transcription"
            try:
                began = time.perf_counter()
                transcript = self.transcribe_call(record)
                asr_seconds = time.perf_counter() - began
                llm_seconds = 0.0
                if self.use_llm:
                    step = "analysis"
                    began = time.perf_counter()
                    analysis = self.analyse_call(transcript)
                    llm_seconds = time.perf_counter() - began
                    print(f"[{call_id}] validation passed: {analysis.validation.passed}")
                self._log_runtime(
                    {
                        "step": "call",
                        "call_id": call_id,
                        "audio_s": record["duration_s"],
                        "transcription_s": round(asr_seconds, 2),
                        "analysis_s": round(llm_seconds, 2),
                        "turns": len(transcript.turns),
                        "machine": platform.processor(),
                    }
                )
                summary["processed"].append(call_id)
            except Exception as error:  # noqa: BLE001 - each failure is recorded per call
                self._log_failure(call_id, step, error)
                summary["failed"].append(call_id)
        return summary
