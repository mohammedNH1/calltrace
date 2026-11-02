"""Mechanical checks on model output: cited turns exist, times agree, quotes match.

Passing these checks shows that a citation is real, not that the claim is correct.
Whether cited turns support a claim is audited separately (see results/evaluation).
"""

from __future__ import annotations

import re

from .schemas import CallAnalysis, Evidence, Turn


def normalise_for_match(text: str) -> str:
    """Compare quotes without regard to case, punctuation, or spacing."""
    return re.sub(r"[^a-z0-9 ]+", "", re.sub(r"\s+", " ", text.lower())).strip()


def quote_in_turn(quote: str, turn: Turn) -> bool:
    """A quote must appear verbatim (after normalisation) in the raw or clean text."""
    needle = normalise_for_match(quote)
    if not needle:
        return False
    return needle in normalise_for_match(turn.text_raw) or needle in normalise_for_match(turn.text_clean)


def check_evidence(
    evidence: list[Evidence],
    turns_by_id: dict[str, Turn],
    label: str,
    required_role: str | None = None,
    allowed_ids: set[str] | None = None,
) -> list[str]:
    """Return human-readable problems with a list of citations."""
    problems: list[str] = []
    for item in evidence:
        turn = turns_by_id.get(item.turn_id)
        if turn is None:
            problems.append(f"{label}: turn {item.turn_id} does not exist")
            continue
        if not quote_in_turn(item.quote, turn):
            problems.append(f"{label}: quote not found in {item.turn_id}: {item.quote!r}")
        if required_role and turn.role != required_role:
            problems.append(f"{label}: {item.turn_id} is {turn.role}, expected {required_role}")
        if allowed_ids is not None and item.turn_id not in allowed_ids:
            problems.append(f"{label}: {item.turn_id} is outside the allowed window")
        if item.start is not None and (item.start != turn.start or item.end != turn.end):
            problems.append(f"{label}: timestamps on {item.turn_id} do not match the turn")
    return problems


def attach_turn_details(evidence: list[Evidence], turns_by_id: dict[str, Turn]) -> None:
    """Copy speaker and times from the transcript, never from the model."""
    for item in evidence:
        turn = turns_by_id.get(item.turn_id)
        if turn is not None:
            item.speaker = turn.role if turn.role != "Unknown" else turn.speaker
            item.start = turn.start
            item.end = turn.end


def validate_analysis(analysis: CallAnalysis, turns: list[Turn]) -> list[str]:
    """Run every check on a complete analysis and collect all problems."""
    turns_by_id = {turn.turn_id: turn for turn in turns}
    problems: list[str] = []

    # Summary: a stated claim needs evidence; a missing one must not pretend to have it.
    summary = analysis.summary
    for name, claim in (
        ("customer_issue", summary.customer_issue),
        ("agent_action", summary.agent_action),
        ("outcome_or_next_step", summary.outcome_or_next_step),
    ):
        problems += check_evidence(claim.evidence, turns_by_id, name)
        if claim.status == "stated" and not claim.evidence:
            problems.append(f"{name}: marked stated but cites no turn")

    # Handling observations.
    handling = analysis.handling
    for name, observation in (
        ("agent_acknowledged_issue", handling.agent_acknowledged_issue),
        ("concrete_action_or_next_step", handling.concrete_action_or_next_step),
        ("resolution", handling.resolution),
    ):
        problems += check_evidence(observation.evidence, turns_by_id, name)
        unsupported = observation.answer not in ("not_observable", "unclear")
        if unsupported and not observation.evidence:
            problems.append(f"{name}: answer {observation.answer!r} cites no turn")

    # Customer sentiment may cite customer turns only, within the window when one is set.
    sentiment = analysis.customer_sentiment
    for name, judgment in (
        ("overall", sentiment.overall),
        ("beginning", sentiment.beginning),
        ("ending", sentiment.ending),
    ):
        allowed = set(judgment.window_turn_ids) or None
        problems += check_evidence(judgment.evidence, turns_by_id, f"sentiment.{name}", "Customer", allowed)
        if judgment.label != "insufficient_evidence" and not judgment.evidence:
            problems.append(f"sentiment.{name}: label {judgment.label!r} cites no turn")

    problems += check_evidence(
        analysis.agent_sentiment.evidence, turns_by_id, "agent_sentiment", "Agent"
    )

    # Turn timestamps are checked here too, in case a transcript file was edited.
    for turn in turns:
        if turn.end < turn.start or turn.start < 0:
            problems.append(f"{turn.turn_id}: invalid timestamps")
    return problems
