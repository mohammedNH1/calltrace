"""Write reusable outputs (JSON, JSONL, CSV) from the per-call files.

The per-call table matches the assessment's minimum output: call_id, speakers,
transcript, summary, sentiment, and notes/limitations, plus evidence and timestamps.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .config import Config
from .schemas import CallAnalysis, CallTranscript, Evidence


def format_evidence(evidence: list[Evidence]) -> str:
    """Readable citation list: turn ID, time span, and quote."""
    return " | ".join(
        f"{item.turn_id} [{item.start:.1f}-{item.end:.1f}s] \"{item.quote}\"" for item in evidence
    )


def load_processed_calls(calls_dir: Path) -> list[tuple[CallTranscript, CallAnalysis | None]]:
    """Read all finished calls in call_id order."""
    loaded = []
    for directory in sorted(path for path in calls_dir.iterdir() if path.is_dir()):
        transcript_file = directory / "transcript.json"
        if not transcript_file.exists():
            continue
        transcript = CallTranscript.model_validate_json(transcript_file.read_text(encoding="utf-8"))
        analysis_file = directory / "analysis.json"
        analysis = (
            CallAnalysis.model_validate_json(analysis_file.read_text(encoding="utf-8"))
            if analysis_file.exists()
            else None
        )
        loaded.append((transcript, analysis))
    return loaded


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    # utf-8-sig lets Excel open the file with the correct encoding.
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def export_all(config: Config, results_dir: Path | None = None) -> dict:
    """Write turns, summaries, sentiment, and the combined per-call table."""
    results = results_dir or config.path("results")
    processed = load_processed_calls(results / "calls")
    if not processed:
        raise SystemExit(f"No processed calls under {results / 'calls'}")

    turn_rows, summary_rows, sentiment_rows, handling_rows, call_rows = [], [], [], [], []
    for transcript, analysis in processed:
        for turn in transcript.turns:
            turn_rows.append(turn.model_dump())
        speakers = " / ".join(f"{s.speaker}={s.role}" for s in transcript.speakers)
        readable = "\n".join(
            f"[{t.turn_id} {t.start:.1f}-{t.end:.1f}s] {t.role}: {t.text_raw}" for t in transcript.turns
        )
        row = {
            "call_id": transcript.call_id,
            "source_id": transcript.source_id,
            "accent": transcript.accent,
            "domain": transcript.domain,
            "duration_s": transcript.duration_s,
            "speakers": speakers,
            "n_turns": len(transcript.turns),
            "transcript": readable,
        }
        if analysis is None:
            call_rows.append(row)
            continue

        summary = analysis.summary
        sentiment = analysis.customer_sentiment
        handling = analysis.handling
        summary_rows.append(
            {
                "call_id": analysis.call_id,
                "customer_issue": summary.customer_issue.text,
                "issue_status": summary.customer_issue.status,
                "issue_evidence": format_evidence(summary.customer_issue.evidence),
                "agent_action": summary.agent_action.text,
                "action_status": summary.agent_action.status,
                "action_evidence": format_evidence(summary.agent_action.evidence),
                "outcome_or_next_step": summary.outcome_or_next_step.text,
                "outcome_status": summary.outcome_or_next_step.status,
                "outcome_evidence": format_evidence(summary.outcome_or_next_step.evidence),
            }
        )
        sentiment_rows.append(
            {
                "call_id": analysis.call_id,
                "overall": sentiment.overall.label,
                "justification": sentiment.overall.justification,
                "overall_evidence": format_evidence(sentiment.overall.evidence),
                "beginning": sentiment.beginning.label,
                "beginning_evidence": format_evidence(sentiment.beginning.evidence),
                "ending": sentiment.ending.label,
                "ending_evidence": format_evidence(sentiment.ending.evidence),
                "change": sentiment.change,
                "ambiguity_notes": " / ".join(
                    note
                    for note in (
                        sentiment.overall.ambiguity_note,
                        sentiment.beginning.ambiguity_note,
                        sentiment.ending.ambiguity_note,
                    )
                    if note and note.lower() != "none"
                ),
                "agent_sentiment_overall": analysis.agent_sentiment.label,
                "method": sentiment.method,
            }
        )
        handling_rows.append(
            {
                "call_id": analysis.call_id,
                "agent_acknowledged_issue": handling.agent_acknowledged_issue.answer,
                "acknowledged_evidence": format_evidence(handling.agent_acknowledged_issue.evidence),
                "concrete_action_or_next_step": handling.concrete_action_or_next_step.answer,
                "action_evidence": format_evidence(handling.concrete_action_or_next_step.evidence),
                "resolution": handling.resolution.answer,
                "resolution_evidence": format_evidence(handling.resolution.evidence),
            }
        )
        row.update(
            {
                "summary": (
                    f"Issue: {summary.customer_issue.text} Action: {summary.agent_action.text} "
                    f"Outcome: {summary.outcome_or_next_step.text}"
                ),
                "sentiment": f"{sentiment.overall.label}: {sentiment.overall.justification}",
                "sentiment_change": f"{sentiment.beginning.label} -> {sentiment.ending.label} ({sentiment.change})",
                "validation_passed": analysis.validation.passed,
                "notes_limitations": " ".join(analysis.notes_limitations),
            }
        )
        call_rows.append(row)

    _write_csv(results / "turns.csv", turn_rows)
    _write_csv(results / "summaries.csv", summary_rows)
    _write_csv(results / "sentiment.csv", sentiment_rows)
    _write_csv(results / "call_handling.csv", handling_rows)
    _write_csv(results / "calls.csv", call_rows)

    # Combined JSONL: one object per call, holding everything needed to reuse the results.
    with open(results / "calls.jsonl", "w", encoding="utf-8") as handle:
        for transcript, analysis in processed:
            record = {"transcript": transcript.model_dump(),
                      "analysis": analysis.model_dump() if analysis else None}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Exported {len(processed)} calls and {len(turn_rows)} turns.")
    return {"calls": len(processed), "turns": len(turn_rows)}
