"""Compute every reported metric from finished calls and write the review worksheets.

Nothing here invents labels. Human columns stay empty until a person fills them, and
any AI-assisted audit is read from a file that is marked as AI-produced.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import jiwer
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .analysis import substantive_customer_turns
from .config import Config
from .data import AppTekDataset
from .evaluation import WerScorer, diarization_error, load_word_mappings
from .export import _write_csv, load_processed_calls
from .llm import LLMError
from .pipeline import CallPipeline
from .schemas import CallTranscript
from .turns import overlap_share

# Parakeet v3 WER (%) by accent with Silero segmentation: Beck et al. 2026, Table 3.
PUBLISHED_PARAKEET_V3 = {
    "en-AU": 5.2, "en-CA": 7.6, "en-CN": 12.9, "en-GB": 10.3, "en-GB_SCT": 12.1, "en-GB_WLS": 10.7, "en-IE": 7.3,
    "en-IN": 9.7, "en-MX": 10.9, "en-SG": 12.4, "en-US_Aave": 8.1, "en-US_General": 5.5, "en-US_Southern": 7.1,
    "en-ZA": 9.6,
}
AI_AUDIT_NOTICE = (
    "AI-assisted audit by the development assistant (Claude Opus 5.5), a different model from the one that "
    "wrote the summaries. It is NOT a human annotation and NOT independent human validation."
)


def _turn_intervals(transcript: CallTranscript) -> dict[str, list[tuple[float, float]]]:
    intervals: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for turn in transcript.turns:
        intervals[turn.role].append((turn.start, turn.end))
    return intervals


def evaluate_transcription(dataset, records, processed, out_dir: Path) -> dict:
    """WER per call, role, and accent, plus the most frequent word confusions."""
    scorer = WerScorer(load_word_mappings(dataset._fetch("word_mappings.py")))
    rows, role_refs, role_preds = [], defaultdict(list), defaultdict(list)
    transcripts = {t.call_id: t for t, _ in processed}
    substitutions: Counter = Counter()
    all_refs, all_preds = [], []

    for record in records:
        transcript = transcripts.get(record["call_id"])
        if transcript is None:
            continue
        references = dataset.reference_channel_text(record)
        channels = sorted(references)
        predictions = {
            c: " ".join(t.text_raw for t in sorted(transcript.turns, key=lambda t: t.start) if t.channel == int(c))
            for c in channels
        }
        score = scorer.score([references[c] for c in channels], [predictions[c] for c in channels])
        role_scores = {}
        for c in channels:
            role = record["channels"][c]["role"]
            role_refs[role].append(references[c])
            role_preds[role].append(predictions[c])
            role_scores[role] = scorer.score([references[c]], [predictions[c]])["wer"]
            all_refs.append(references[c])
            all_preds.append(predictions[c])
        rows.append(
            {
                "call_id": record["call_id"],
                "accent": record["accent"],
                "domain": record["domain"],
                "reference_words": score["reference_words"],
                "wer_pct": round(100 * score["wer"], 2),
                "substitutions": score["substitutions"],
                "deletions": score["deletions"],
                "insertions": score["insertions"],
                "agent_wer_pct": round(100 * role_scores["agent"], 2),
                "customer_wer_pct": round(100 * role_scores["customer"], 2),
                "published_accent_wer_pct": PUBLISHED_PARAKEET_V3.get(record["accent"]),
            }
        )

    # Most frequent word confusions, computed after the same normalisation.
    pairs = [scorer.normalise_pair(r, p) for r, p in zip(all_refs, all_preds)]
    measures = jiwer.process_words(
        [p[0] for p in pairs], [p[1] for p in pairs],
        reference_transform=scorer._transform, hypothesis_transform=scorer._transform,
    )
    for chunks, ref_words, hyp_words in zip(measures.alignments, measures.references, measures.hypotheses):
        for chunk in chunks:
            if chunk.type == "substitute":
                ref_span = " ".join(ref_words[chunk.ref_start_idx : chunk.ref_end_idx])
                hyp_span = " ".join(hyp_words[chunk.hyp_start_idx : chunk.hyp_end_idx])
                substitutions[f"{ref_span} -> {hyp_span}"] += 1

    _write_csv(out_dir / "wer_per_call.csv", rows)
    _write_csv(out_dir / "wer_top_substitutions.csv",
               [{"reference -> asr": key, "count": count} for key, count in substitutions.most_common(40)])
    pooled = scorer.score(all_refs, all_preds)
    per_call = [row["wer_pct"] for row in rows]
    return {
        "calls": len(rows),
        "channels": len(all_refs),
        "reference_words": pooled["reference_words"],
        "pooled_wer_pct": round(100 * pooled["wer"], 2),
        "median_call_wer_pct": round(statistics.median(per_call), 2),
        "min_call_wer_pct": min(per_call),
        "max_call_wer_pct": max(per_call),
        "agent_pooled_wer_pct": round(100 * scorer.score(role_refs["agent"], role_preds["agent"])["wer"], 2),
        "customer_pooled_wer_pct": round(100 * scorer.score(role_refs["customer"], role_preds["customer"])["wer"], 2),
        "normalisation": "dataset score.py protocol, re-implemented; whisper_normalizer package in place of "
                         "openai-whisper's identical normaliser class",
    }


def _word_intervals(call_dir: Path, record: dict, gap_s: float = 0.3) -> dict[str, list[tuple[float, float]]]:
    """Speech spans per role from ASR words. Unlike turn spans, these leave out short pauses."""
    intervals: dict[str, list[tuple[float, float]]] = {}
    for channel, info in record["channels"].items():
        words = json.loads((call_dir / f"asr_channel{channel}.json").read_text(encoding="utf-8"))["words"]
        spans: list[list[float]] = []
        for word in words:
            if spans and word["start"] - spans[-1][1] <= gap_s:
                spans[-1][1] = word["end"]
            else:
                spans.append([word["start"], word["end"]])
        intervals[info["role"].capitalize()] = [(start, end) for start, end in spans]
    return intervals


def evaluate_speaker_separation(dataset, records, processed, config, out_dir: Path) -> dict:
    """Compare channel-derived turns with manual reference segments on one timeline."""
    settings = config["evaluation"]
    transcripts = {t.call_id: t for t, _ in processed}
    rows = []
    for record in records:
        transcript = transcripts.get(record["call_id"])
        if transcript is None:
            continue
        reference: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for segment in dataset.reference_segments(record):
            reference[segment["role"].capitalize()].append((segment["start"], segment["end"]))
        metrics = diarization_error(reference, _turn_intervals(transcript), record["duration_s"],
                                    settings["frame_s"], settings["collar_s"])
        word_level = diarization_error(
            reference, _word_intervals(out_dir.parent / "calls" / record["call_id"], record), record["duration_s"],
            settings["frame_s"], settings["collar_s"],
        )
        agent = next(s for s in transcript.speakers if s.role == "Agent")
        # Overlap in the manual reference is independent of any ASR or turn-building error.
        reference_overlap = overlap_share(reference["Agent"], reference["Customer"])
        first_agent = min(start for start, _ in reference["Agent"])
        first_customer = min(start for start, _ in reference["Customer"])
        rows.append(
            {
                "call_id": record["call_id"],
                "speakers": " / ".join(f"{s.speaker}={s.role}" for s in transcript.speakers),
                "agent_channel": agent.channel,
                "role_text_check": agent.role_text_check,
                "der_pct": round(100 * metrics["der"], 2),
                "missed_pct": round(100 * metrics["missed"], 2),
                "false_alarm_pct": round(100 * metrics["false_alarm"], 2),
                "confusion_pct": round(100 * metrics["confusion"], 2),
                "scored_speech_s": round(metrics["scored_speech_s"], 1),
                "word_level_der_pct": round(100 * word_level["der"], 2),
                "word_level_missed_pct": round(100 * word_level["missed"], 2),
                "word_level_false_alarm_pct": round(100 * word_level["false_alarm"], 2),
                "word_level_confusion_pct": round(100 * word_level["confusion"], 2),
                "n_turns": len(transcript.turns),
                "backchannel_turns": sum(t.is_backchannel for t in transcript.turns),
                "overlapping_turns": sum(t.overlaps_previous for t in transcript.turns),
                "reference_overlap_pct": round(100 * reference_overlap, 1),
                "customer_speaks_first_s_before_agent": round(max(first_agent - first_customer, 0), 1),
            }
        )
    _write_csv(out_dir / "speaker_separation.csv", rows)
    checks = Counter(row["role_text_check"].split(" ")[0] for row in rows)
    return {
        "calls": len(rows),
        "median_der_pct": round(statistics.median(r["der_pct"] for r in rows), 2),
        "max_der_pct": max(r["der_pct"] for r in rows),
        "median_confusion_pct": round(statistics.median(r["confusion_pct"] for r in rows), 2),
        "max_confusion_pct": max(r["confusion_pct"] for r in rows),
        "collar_s": settings["collar_s"],
        "role_phrase_check": dict(checks),
        "median_word_level_der_pct": round(statistics.median(r["word_level_der_pct"] for r in rows), 2),
        "median_word_level_confusion_pct": round(statistics.median(r["word_level_confusion_pct"] for r in rows), 2),
        "max_word_level_confusion_pct": max(r["word_level_confusion_pct"] for r in rows),
        "mono_baseline": _summarise_mono_baseline(out_dir),
        "median_reference_overlap_pct": round(statistics.median(r["reference_overlap_pct"] for r in rows), 1),
        "max_reference_overlap_pct": max(r["reference_overlap_pct"] for r in rows),
        "note": "Speaker identity comes from split channels, so confusion here measures timing overlap, "
                "not a clustering decision.",
    }


def _summarise_mono_baseline(out_dir: Path) -> dict | None:
    """Summary of the contrast run on merged audio, if it has been executed."""
    path = out_dir / "mono_diarization_baseline.csv"
    if not path.exists():
        return None
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    der = [float(row["der_pct"]) for row in rows]
    confusion = [float(row["confusion_pct"]) for row in rows]
    return {
        "calls": len(rows),
        "median_der_pct": round(statistics.median(der), 2),
        "max_der_pct": max(der),
        "median_confusion_pct": round(statistics.median(confusion), 2),
        "max_confusion_pct": max(confusion),
        "median_inference_s": round(statistics.median(float(row["inference_s"]) for row in rows), 1),
    }


def summarise_mechanical_checks(processed) -> dict:
    """Count citations and validation outcomes. These checks say nothing about correctness."""
    analyses = [a for _, a in processed if a is not None]
    counts = Counter()
    for analysis in analyses:
        summary, handling, sentiment = analysis.summary, analysis.handling, analysis.customer_sentiment
        for claim in (summary.customer_issue, summary.agent_action, summary.outcome_or_next_step):
            counts[f"claim_{claim.status}"] += 1
            counts["citations"] += len(claim.evidence)
        for observation in (handling.agent_acknowledged_issue, handling.concrete_action_or_next_step,
                            handling.resolution):
            counts["citations"] += len(observation.evidence)
        for judgment in (sentiment.overall, sentiment.beginning, sentiment.ending, analysis.agent_sentiment):
            counts["citations"] += len(judgment.evidence)
        counts["retries"] += analysis.validation.retries_used
    return {
        "calls": len(analyses),
        "calls_passing_validation": sum(a.validation.passed for a in analyses),
        "citations_checked": counts["citations"],
        "repair_retries": counts["retries"],
        "claims_stated": counts["claim_stated"],
        "claims_unclear": counts["claim_unclear"],
        "claims_not_stated": counts["claim_not_stated"],
        "failing_errors": [e for a in analyses for e in a.validation.errors],
    }


def write_grounding_sheet(processed, dataset, records, out_dir: Path) -> None:
    """One row per summary claim, with cited ASR turns and the overlapping reference text."""
    rows = []
    record_by_id = {r["call_id"]: r for r in records}
    for transcript, analysis in processed:
        if analysis is None:
            continue
        turns = {t.turn_id: t for t in transcript.turns}
        reference = dataset.reference_segments(record_by_id[transcript.call_id])
        summary = analysis.summary
        for name, claim in (("issue", summary.customer_issue), ("action", summary.agent_action),
                            ("outcome", summary.outcome_or_next_step)):
            cited = [turns[e.turn_id] for e in claim.evidence if e.turn_id in turns]
            overlap = [
                s["text"] for t in cited for s in reference
                if s["start"] < t.end and s["end"] > t.start
            ]
            rows.append(
                {
                    "claim_id": f"{transcript.call_id}-{name}",
                    "call_id": transcript.call_id,
                    "claim_type": name,
                    "status": claim.status,
                    "claim_text": claim.text,
                    "cited_turn_ids": " ".join(t.turn_id for t in cited),
                    "cited_asr_text": " || ".join(f"{t.role}: {t.text_raw}" for t in cited),
                    "reference_text_same_time": " || ".join(dict.fromkeys(overlap)),
                }
            )
    _write_csv(out_dir / "grounding_claims.csv", rows)


def summarise_grounding_audit(out_dir: Path) -> dict | None:
    """Tally verdicts from the AI-assisted audit file, if that audit has been done."""
    path = out_dir / "grounding_audit_ai.json"
    if not path.exists():
        return None
    audit = json.loads(path.read_text(encoding="utf-8"))
    by_type: dict[str, Counter] = defaultdict(Counter)
    for item in audit["items"]:
        by_type[item["claim_id"].split("-")[1]][item["cited_support"]] += 1
    return {
        "auditor": audit["auditor"],
        "claims": len(audit["items"]),
        "cited_support": dict(Counter(item["cited_support"] for item in audit["items"])),
        "correct_in_call": dict(Counter(item["correct_in_call"] for item in audit["items"])),
        "cited_support_by_type": {key: dict(value) for key, value in by_type.items()},
    }


def write_human_worksheet(processed, config, path: Path) -> None:
    """Workbook for the human reviewer. Model labels are deliberately left out to avoid bias."""
    settings = config["analysis"]
    workbook = Workbook()
    header_fill = PatternFill("solid", fgColor="0F766E")
    header_font = Font(bold=True, color="FFFFFF")
    wrap = Alignment(wrap_text=True, vertical="top")

    guide = workbook.active
    guide.title = "READ ME"
    lines = [
        "CallTrace human review worksheet: TO BE COMPLETED BY A PERSON",
        "Status: not reviewed. All label columns are empty on purpose. No human labels exist until you fill them in.",
        "Why model labels are absent: seeing them first would bias your judgment, so they are not shown here.",
        "",
        "Sheet 'Sentiment': read every customer turn of a call, then fill the yellow cells on that call's LABEL row.",
        "Edit only the yellow cells and the notes column. The first row marked EXAMPLE only shows the format; it is not data.",
        "Allowed labels for overall: negative, neutral, positive, mixed, insufficient_evidence.",
        "Allowed labels for beginning and ending: negative, neutral, positive, insufficient_evidence.",
        "Beginning and ending mean the turns marked B and E in the Window column.",
        "A routine thank-you alone is courtesy, not positive sentiment.",
        "",
        "Sheet 'Summary claims': open results/summaries.csv and mark each claim supported, partially, or unsupported.",
        "Then run: python -m calltrace evaluate. It computes agreement from whatever you have completed.",
    ]
    for index, line in enumerate(lines, start=1):
        guide.cell(index, 1, line).alignment = Alignment(wrap_text=True)
    guide.column_dimensions["A"].width = 110
    guide["A1"].font = Font(bold=True, size=13)

    sheet = workbook.create_sheet("Sentiment")
    headers = ["call_id", "row_type", "turn_id", "time_s", "window", "customer_text", "overall_label",
               "beginning_label", "ending_label", "reviewer_notes"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.fill, cell.font = header_fill, header_font
    yellow = PatternFill("solid", fgColor="FEF3C7")
    # An invented row that shows the format. The scorer skips it because its ID is not a call.
    sheet.append(["EXAMPLE", "LABEL", "", "", "", "(format example only, not a real label)", "negative",
                  "negative", "neutral", "Complains at first; calm by the end."])
    for transcript, analysis in processed:
        beginning = set(analysis.customer_sentiment.beginning.window_turn_ids) if analysis else set()
        ending = set(analysis.customer_sentiment.ending.window_turn_ids) if analysis else set()
        usable = {t.turn_id for t in substantive_customer_turns(transcript.turns, settings["substantive_min_words"])}
        for turn in transcript.turns:
            if turn.role == "Customer" and turn.turn_id in usable:
                window = "B" if turn.turn_id in beginning else "E" if turn.turn_id in ending else ""
                sheet.append([transcript.call_id, "turn", turn.turn_id, round(turn.start, 1), window, turn.text_raw])
        sheet.append([transcript.call_id, "LABEL"])
        for column in (7, 8, 9):
            sheet.cell(sheet.max_row, column).fill = yellow
    for column, width in zip("ABCDEFGHIJ", (8, 9, 13, 8, 8, 90, 14, 14, 14, 30)):
        sheet.column_dimensions[column].width = width
    for row in sheet.iter_rows(min_row=2):
        row[5].alignment = wrap
    sheet.freeze_panes = "A2"

    claims = workbook.create_sheet("Summary claims")
    claims.append(["call_id", "issue_verdict", "action_verdict", "outcome_verdict", "reviewer_notes"])
    for cell in claims[1]:
        cell.fill, cell.font = header_fill, header_font
    claims.append(["EXAMPLE", "supported", "partially", "unsupported", "Format example only, not a real verdict."])
    for transcript, _ in processed:
        claims.append([transcript.call_id])
        for column in (2, 3, 4):
            claims.cell(claims.max_row, column).fill = yellow
    claims.column_dimensions["E"].width = 50
    for column in "BCD":
        claims.column_dimensions[column].width = 16
    workbook.save(path)


def score_human_worksheet(path: Path, processed) -> dict:
    """Compute agreement from a completed worksheet. Reports zero when it is still empty."""
    if not path.exists():
        return {"status": "worksheet missing", "labels_completed": 0}
    sheet = load_workbook(path)["Sentiment"]
    analyses = {a.call_id: a for _, a in processed if a}
    agreement = Counter()
    completed = 0
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[1] != "LABEL" or str(row[0]).zfill(3) not in analyses:
            continue
        sentiment = analyses[str(row[0]).zfill(3)].customer_sentiment
        for name, value, model in (("overall", row[6], sentiment.overall.label),
                                   ("beginning", row[7], sentiment.beginning.label),
                                   ("ending", row[8], sentiment.ending.label)):
            if value:
                completed += 1
                agreement[f"{name}_n"] += 1
                agreement[f"{name}_agree"] += str(value).strip().lower() == model
    if not completed:
        return {"status": "not reviewed: no human labels yet", "labels_completed": 0}
    return {"status": "human labels present", "labels_completed": completed, **agreement}


def compare_second_reader(processed, out_dir: Path) -> dict | None:
    """Agreement with the AI second reader. Clearly not independent human validation."""
    path = out_dir / "sentiment_second_reader_ai.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    analyses = {a.call_id: a for _, a in processed if a}
    rows, agree = [], Counter()
    for item in data["items"]:
        analysis = analyses[item["call_id"]]
        sentiment = analysis.customer_sentiment
        row = {"call_id": item["call_id"]}
        for name, model in (("overall", sentiment.overall.label), ("beginning", sentiment.beginning.label),
                            ("ending", sentiment.ending.label), ("resolution", analysis.handling.resolution.answer)):
            row[f"{name}_pipeline"], row[f"{name}_second_reader"] = model, item[name]
            agree[name] += model == item[name]
        row["second_reader_note"] = item.get("note", "")
        rows.append(row)
    _write_csv(out_dir / "sentiment_second_reader_comparison.csv", rows)
    return {"reader": data["reader"], "calls": len(rows), "agreements": dict(agree)}


def _experiment_calls(records, wer_rows_path: Path, count: int) -> list[dict]:
    """Pick calls at evenly spaced WER ranks, so that both easy and hard calls are tested."""
    with open(wer_rows_path, encoding="utf-8-sig") as handle:
        rows = sorted(csv.DictReader(handle), key=lambda row: float(row["wer_pct"]))
    step = (len(rows) - 1) / max(count - 1, 1)
    chosen = {rows[round(i * step)]["call_id"] for i in range(count)}
    return [r for r in records if r["call_id"] in chosen]


def run_reference_experiment(config: Config, records, processed, out_dir: Path) -> dict | None:
    """Same analysis configuration on reference text and ASR text. Only for a subset."""
    pipeline = CallPipeline(config, config.path("results"))
    subset = _experiment_calls(records, out_dir / "wer_per_call.csv", config["evaluation"]["reference_experiment_calls"])
    asr_analyses = {t.call_id: a for t, a in processed}
    rows, skipped = [], []
    for record in subset:
        call_id = record["call_id"]
        target = pipeline.calls_dir / call_id / "analysis_reference.json"
        if not target.exists() and not pipeline.client.is_available():
            print("LLM server is not running, so missing reference-experiment calls are skipped.")
            continue
        reference_transcript = pipeline.reference_transcript(record)
        try:
            reference = pipeline.analyse_call(reference_transcript, "analysis_reference.json")
        except LLMError as error:
            # Reported in the output, so a skipped call cannot be mistaken for a compared one.
            skipped.append({"call_id": call_id, "error": str(error)})
            continue
        asr = asr_analyses[call_id]
        for name, on_asr, on_ref in (
            ("issue", asr.summary.customer_issue.text, reference.summary.customer_issue.text),
            ("action", asr.summary.agent_action.text, reference.summary.agent_action.text),
            ("outcome", asr.summary.outcome_or_next_step.text, reference.summary.outcome_or_next_step.text),
            ("resolution", asr.handling.resolution.answer, reference.handling.resolution.answer),
            ("sentiment_overall", asr.customer_sentiment.overall.label, reference.customer_sentiment.overall.label),
            ("sentiment_beginning", asr.customer_sentiment.beginning.label, reference.customer_sentiment.beginning.label),
            ("sentiment_ending", asr.customer_sentiment.ending.label, reference.customer_sentiment.ending.label),
            ("sentiment_change", asr.customer_sentiment.change, reference.customer_sentiment.change),
        ):
            rows.append({"call_id": call_id, "field": name, "on_asr": on_asr, "on_reference": on_ref,
                         "exact_match": on_asr == on_ref})
    if not rows:
        return None
    _write_csv(out_dir / "asr_vs_reference.csv", rows)
    labelled = [row for row in rows if row["field"] not in ("issue", "action", "outcome")]
    return {
        "calls": sorted({row["call_id"] for row in rows}),
        "label_fields_compared": len(labelled),
        "label_fields_matching": sum(row["exact_match"] for row in labelled),
        "text_fields_for_manual_comparison": len(rows) - len(labelled),
        "skipped_calls": skipped,
    }


def summarise_runtime(results: Path) -> dict:
    """Separate model loading from per-call time, using logged timings."""
    path = results / "runtime.jsonl"
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    calls = [row for row in rows if row["step"] == "call"]
    per_audio = [row["transcription_s"] / row["audio_s"] for row in calls]
    analysis = [row["analysis_s"] for row in calls if row["analysis_s"] > 1]
    loads = [row["seconds"] for row in rows if row["step"] == "asr_model_load"]
    return {
        "hardware": "AMD Ryzen 7 6800H (8 cores), 15 GB RAM; ASR on CPU; LLM on RTX 3050 Ti 4 GB via Vulkan",
        "asr_model_load_s_cached_weights": loads[-1] if loads else None,
        "calls_timed": len(calls),
        "median_transcription_s_per_audio_minute": round(60 * statistics.median(per_audio), 1) if per_audio else None,
        "median_analysis_s_per_call": round(statistics.median(analysis), 1) if analysis else None,
        "max_analysis_s_per_call": round(max(analysis), 1) if analysis else None,
        "note": "Timed during normal use of the machine. Some LLM answers came from the cache.",
    }


def write_results_table(metrics: dict, out_dir: Path) -> None:
    """Concise results table with sample sizes and denominators."""
    asr = metrics["transcription"]
    speakers = metrics["speaker_separation"]
    checks = metrics["output_validation"]
    audit = metrics["grounding_ai_audit"] or {}
    reader = metrics["sentiment_ai_second_reader"] or {}
    experiment = metrics["asr_vs_reference"] or {}
    mono = speakers.get("mono_baseline") or {}
    support, correct = audit.get("cited_support", {}), audit.get("correct_in_call", {})
    agreements = reader.get("agreements", {})
    n_reader = reader.get("calls", 0)
    rows = [
        ("Transcription: pooled WER", f"{asr['pooled_wer_pct']}%", f"{asr['reference_words']:,} reference words, {asr['channels']} channels, {asr['calls']} calls", "Manual reference"),
        ("Transcription: median call WER (range)", f"{asr['median_call_wer_pct']}% ({asr['min_call_wer_pct']}-{asr['max_call_wer_pct']}%)", f"{asr['calls']} calls", "Manual reference"),
        ("Transcription: agent / customer pooled WER", f"{asr['agent_pooled_wer_pct']}% / {asr['customer_pooled_wer_pct']}%", f"{asr['channels']} channels", "Manual reference"),
        ("Speakers: median DER (channel-based)", f"{speakers['median_der_pct']}%", f"{speakers['calls']} calls, {speakers['collar_s']} s collar", "Manual segments"),
        ("Speakers: median DER, word-level spans (channel-based)", f"{speakers['median_word_level_der_pct']}%", f"{speakers['calls']} calls, pauses excluded", "Manual segments"),
        ("Speakers: median / max confusion (channel-based, turn spans)", f"{speakers['median_confusion_pct']}% / {speakers['max_confusion_pct']}%", f"{speakers['calls']} calls", "Manual segments"),
        ("Speakers: mono diarization baseline, median DER; median / max confusion", f"{mono.get('median_der_pct')}%; {mono.get('median_confusion_pct')}% / {mono.get('max_confusion_pct')}%", f"{mono.get('calls')} calls, clusters mapped with the reference", "Manual segments"),
        ("Citations: calls passing all mechanical checks", f"{checks['calls_passing_validation']} of {checks['calls']}", f"{checks['citations_checked']} citations", "Automatic validator"),
        ("Grounding: claims fully supported by cited turns", f"{support.get('supported', 0)} of {audit.get('claims', 0)}", f"partial {support.get('partially', 0)}, unsupported {support.get('unsupported', 0)}", "AI-assisted audit, not human"),
        ("Grounding: claims correct against the whole call", f"{correct.get('yes', 0)} of {audit.get('claims', 0)}", f"partly {correct.get('partly', 0)}, wrong {correct.get('no', 0)}", "AI-assisted audit, not human"),
        ("Sentiment: overall / beginning / ending agreement", f"{agreements.get('overall', 0)} / {agreements.get('beginning', 0)} / {agreements.get('ending', 0)} of {n_reader}", "second reader saw model labels first", "AI second reader, not human"),
        ("Sentiment: agreement with human labels", "Not available", f"{metrics['human_review']['labels_completed']} labels completed", "Human worksheet pending"),
        ("ASR vs reference: labels unchanged", f"{experiment.get('label_fields_matching', 0)} of {experiment.get('label_fields_compared', 0)}", f"{len(experiment.get('calls', []))} calls, 5 label fields per call", "Same analysis settings"),
    ]
    lines = ["| Check | Result | Sample | Compared against |", "|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    (out_dir / "results_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_evaluation(config: Config) -> dict:
    results = config.path("results")
    out_dir = results / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    dataset = AppTekDataset(config)
    records = dataset.load_manifest()["selected"]
    processed = load_processed_calls(results / "calls")

    metrics: dict = {"selected_calls": len(records), "processed_calls": len(processed)}
    metrics["transcription"] = evaluate_transcription(dataset, records, processed, out_dir)
    metrics["speaker_separation"] = evaluate_speaker_separation(dataset, records, processed, config, out_dir)
    metrics["output_validation"] = summarise_mechanical_checks(processed)
    write_grounding_sheet(processed, dataset, records, out_dir)
    metrics["grounding_ai_audit"] = summarise_grounding_audit(out_dir)
    metrics["grounding_ai_audit_notice"] = AI_AUDIT_NOTICE

    worksheet = config.path("reports") / "human_review_worksheet.xlsx"
    if not worksheet.exists():
        write_human_worksheet(processed, config, worksheet)
    metrics["human_review"] = score_human_worksheet(worksheet, processed)
    metrics["sentiment_ai_second_reader"] = compare_second_reader(processed, out_dir)
    metrics["asr_vs_reference"] = run_reference_experiment(config, records, processed, out_dir)
    metrics["runtime"] = summarise_runtime(results)

    with open(out_dir / "metrics.json", "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2, ensure_ascii=False)
    write_results_table(metrics, out_dir)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return metrics
