"""Pydantic schemas for transcripts and call analyses.

Schema validity only proves that an output is well formed. It does not prove the
conclusion is right, which is why src/calltrace/evaluation.py exists separately.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

Role = Literal["Customer", "Agent", "Unknown"]
SpeakerLabel = Literal["Speaker 1", "Speaker 2"]
ClaimStatus = Literal["stated", "unclear", "not_stated"]
SentimentLabel = Literal["negative", "neutral", "positive", "insufficient_evidence"]
OverallSentiment = Literal["negative", "neutral", "positive", "mixed", "insufficient_evidence"]
SentimentChange = Literal["improved", "worsened", "unchanged", "insufficient_evidence"]
Observation = Literal["yes", "no", "not_observable"]
Resolution = Literal["confirmed", "unresolved", "unclear"]


class Word(BaseModel):
    """One recognised word with its audio time in seconds."""

    text: str
    start: float
    end: float
    logprob: Optional[float] = None


class Turn(BaseModel):
    """One speaker turn: the unit that evidence references point to."""

    turn_id: str
    call_id: str
    speaker: SpeakerLabel
    role: Role
    channel: int
    start: float
    end: float
    text_raw: str              # untouched ASR (or reference) text
    text_clean: str            # fillers and immediate repeats removed
    is_backchannel: bool = False
    is_courtesy_only: bool = False
    low_confidence: bool = False
    overlaps_previous: bool = False

    @model_validator(mode="after")
    def _times_are_ordered(self) -> "Turn":
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid timestamps on {self.turn_id}: {self.start}-{self.end}")
        return self


class SpeakerInfo(BaseModel):
    """How one speaker was separated and how their role was assigned."""

    speaker: SpeakerLabel
    channel: int
    role: Role
    speaker_id: Optional[str] = None
    role_method: str
    role_uncertainty: str
    role_text_check: str


class CallTranscript(BaseModel):
    """Speaker-separated transcript of one call."""

    call_id: str
    source_id: str
    accent: str
    domain: str
    duration_s: float
    transcript_source: Literal["asr", "reference"]
    speaker_boundaries_source: str
    speakers: list[SpeakerInfo]
    turns: list[Turn]
    quality_notes: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    """A citation: the turn that supports a claim and a short verbatim quote."""

    turn_id: str
    quote: str
    speaker: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None


class Claim(BaseModel):
    """One summary statement with its evidence."""

    status: ClaimStatus
    text: str
    evidence: list[Evidence] = Field(default_factory=list)


class CallSummary(BaseModel):
    customer_issue: Claim
    agent_action: Claim
    outcome_or_next_step: Claim


class HandlingObservation(BaseModel):
    answer: str
    note: str
    evidence: list[Evidence] = Field(default_factory=list)


class CallHandling(BaseModel):
    """Call-level description only. Not a validated measure of employee performance."""

    agent_acknowledged_issue: HandlingObservation
    concrete_action_or_next_step: HandlingObservation
    resolution: HandlingObservation


class SentimentJudgment(BaseModel):
    label: str
    justification: str
    ambiguity_note: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    window_turn_ids: list[str] = Field(default_factory=list)


class CustomerSentiment(BaseModel):
    method: str
    overall: SentimentJudgment
    beginning: SentimentJudgment
    ending: SentimentJudgment
    change: SentimentChange
    change_note: str


class ValidationReport(BaseModel):
    """Result of the mechanical checks on one analysis."""

    passed: bool
    errors: list[str] = Field(default_factory=list)
    retries_used: int = 0


class CallAnalysis(BaseModel):
    """Complete structured output for one processed call."""

    call_id: str
    transcript_source: Literal["asr", "reference"]
    model_id: str
    prompt_version: str
    summary: CallSummary
    handling: CallHandling
    customer_sentiment: CustomerSentiment
    agent_sentiment: SentimentJudgment
    validation: ValidationReport
    notes_limitations: list[str] = Field(default_factory=list)
