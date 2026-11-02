"""Merge two per-speaker word streams into one time-ordered list of turns.

The two audio channels tell us who spoke. Turn boundaries are predicted from word
timestamps, so they are ASR-derived and not taken from the dataset's annotations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .schemas import Turn, Word

FILLERS = {"um", "uh", "uhm", "umm", "hmm", "mm", "mhm", "er", "ah", "eh"}
COURTESY_PATTERN = re.compile(
    r"\b(thank(s| you)?|thank you (so|very) much|bye|goodbye|have a (nice|good|great|lovely) \w+|"
    r"you too|take care|cheers|okay|ok|alright|all right|great|perfect|sure|no problem|"
    r"appreciate it|much appreciated|welcome|yes|yeah|no|that'?s (all|it|great|perfect|fine)|"
    r"wonderful|awesome|lovely|nice|good|sounds good|very|so|much|for|your|help|time|day|"
    r"i|you|that|have|a)\b",
    re.IGNORECASE,
)
AGENT_CUES = re.compile(
    r"(thank you for calling|thanks for calling|how (can|may) i (help|assist)|this is \w+ (from|with)|"
    r"my name is \w+.{0,40}(how|calling)|let me (check|pull|look)|i can help|i'?ll (check|send|arrange)|"
    r"is there anything else)",
    re.IGNORECASE,
)


def clean_text(raw: str) -> str:
    """Conservative clean-up: drop fillers and immediate word repeats, keep the rest."""
    kept: list[str] = []
    for token in raw.split():
        bare = token.strip(".,?!;:").lower()
        if bare in FILLERS:
            continue
        if kept and kept[-1].strip(".,?!;:").lower() == bare:
            kept[-1] = token  # keep the later token so that sentence punctuation survives
            continue
        kept.append(token)
    return " ".join(kept)


def is_courtesy_only(text: str) -> bool:
    """True when a turn contains only politeness or acknowledgment words.

    Such turns ("thanks, bye") are poor evidence of how a customer actually feels,
    so they are excluded from the sentiment windows.
    """
    remainder = COURTESY_PATTERN.sub(" ", text)
    return not re.search(r"[a-zA-Z]{2,}", remainder)


def count_agent_cues(text: str) -> int:
    """Count phrases typical of an agent. Used only as a cross-check on metadata."""
    return len(AGENT_CUES.findall(text))


@dataclass
class _Run:
    """Consecutive words from one channel without a long silence."""

    channel: int
    words: list[Word] = field(default_factory=list)
    is_backchannel: bool = False

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end


def split_into_runs(words: list[Word], channel: int, gap_s: float) -> list[_Run]:
    """Split one channel's words wherever the silence exceeds `gap_s`."""
    runs: list[_Run] = []
    for word in words:
        if not runs or word.start - runs[-1].end > gap_s:
            runs.append(_Run(channel=channel))
        runs[-1].words.append(word)
    return runs


def mark_backchannels(runs: list[_Run], max_words: int) -> None:
    """Flag short interjections spoken while the other speaker is talking."""
    for run in runs:
        if len(run.words) > max_words:
            continue
        for other in runs:
            if other.channel != run.channel and len(other.words) > max_words:
                overlap = min(run.end, other.end) - max(run.start, other.start)
                if overlap >= 0.5 * max(run.end - run.start, 0.01):
                    run.is_backchannel = True
                    break


def merge_runs(runs: list[_Run], merge_gap_s: float) -> list[_Run]:
    """Join neighbouring runs of one speaker if only backchannels came between them."""
    merged: list[_Run] = []
    for run in sorted(runs, key=lambda r: r.start):
        if run.is_backchannel:
            merged.append(run)
            continue
        # The most recent run that is not a backchannel decides the merge.
        previous = next((r for r in reversed(merged) if not r.is_backchannel), None)
        if previous and previous.channel == run.channel and run.start - previous.end <= merge_gap_s:
            previous.words.extend(run.words)
        else:
            merged.append(run)
    return sorted(merged, key=lambda r: r.start)


def split_long_run(run: _Run, max_s: float) -> list[_Run]:
    """Cut very long turns at sentence ends, so that citations stay specific."""
    if run.end - run.start <= max_s:
        return [run]
    pieces: list[_Run] = []
    current = _Run(channel=run.channel, is_backchannel=run.is_backchannel)
    for word in run.words:
        current.words.append(word)
        over_half = current.end - current.start >= max_s / 2
        at_sentence_end = word.text.endswith((".", "?", "!"))
        if (over_half and at_sentence_end) or current.end - current.start >= max_s:
            pieces.append(current)
            current = _Run(channel=run.channel, is_backchannel=run.is_backchannel)
    if current.words:
        pieces.append(current)
    return pieces


def build_turns(
    call_id: str,
    words_by_channel: dict[int, list[Word]],
    speaker_labels: dict[int, str],
    roles: dict[int, str],
    settings: dict,
    asr_settings: dict | None = None,
) -> list[Turn]:
    """Turn two word streams into validated Turn objects with stable IDs."""
    runs: list[_Run] = []
    for channel, words in words_by_channel.items():
        runs.extend(split_into_runs(words, channel, settings["word_gap_s"]))
    mark_backchannels(runs, settings["backchannel_max_words"])
    merged = merge_runs(runs, settings["same_speaker_merge_s"])

    pieces: list[_Run] = []
    for run in merged:
        pieces.extend(split_long_run(run, settings["max_turn_s"]))
    pieces.sort(key=lambda r: r.start)

    threshold = (asr_settings or {}).get("low_confidence_logprob")
    share = (asr_settings or {}).get("low_confidence_turn_share", 1.0)
    turns: list[Turn] = []
    latest_end = 0.0
    for index, run in enumerate(pieces, start=1):
        raw = " ".join(word.text for word in run.words)
        cleaned = clean_text(raw)
        scored = [word.logprob for word in run.words if word.logprob is not None]
        low = bool(threshold is not None and scored and
                   sum(value < threshold for value in scored) / len(scored) >= share)
        turns.append(
            Turn(
                turn_id=f"{call_id}-T{index:04d}",
                call_id=call_id,
                speaker=speaker_labels[run.channel],
                role=roles[run.channel],
                channel=run.channel,
                start=run.start,
                end=max(run.end, run.start),
                text_raw=raw,
                text_clean=cleaned,
                is_backchannel=run.is_backchannel,
                is_courtesy_only=is_courtesy_only(cleaned),
                low_confidence=low,
                overlaps_previous=run.start < latest_end,
            )
        )
        latest_end = max(latest_end, run.end)
    return turns


def overlap_share(intervals_a: list[tuple[float, float]], intervals_b: list[tuple[float, float]]) -> float:
    """Share of the less talkative speaker's time that overlaps the other speaker.

    People rarely talk over each other for long. A high value suggests that two
    channels may be out of sync, which makes turn order unreliable.
    """
    total_a = sum(end - start for start, end in intervals_a)
    total_b = sum(end - start for start, end in intervals_b)
    if not total_a or not total_b:
        return 0.0
    overlap = sum(
        max(0.0, min(end_a, end_b) - max(start_a, start_b))
        for start_a, end_a in intervals_a
        for start_b, end_b in intervals_b
    )
    return overlap / min(total_a, total_b)


REFERENCE_MARKUP = re.compile(r"\(\(.*?\)\)|</?initial>|<lang:\w+>|</lang:\w+>|@+")


def clean_reference_text(text: str) -> str:
    """Remove annotation markup from reference text.

    Hesitations appear as "(um)", false starts end with "~", and unintelligible spans
    are "(())". This view is used only by the ASR-versus-reference experiment.
    """
    text = REFERENCE_MARKUP.sub(" ", text)
    text = re.sub(r"\(\s*\w+\s*\)", " ", text)  # hesitation tokens such as (um)
    text = re.sub(r"\b\S+~(?=\s|$)", " ", text)  # truncated words such as organizati~
    return re.sub(r"\s+", " ", text).strip()
