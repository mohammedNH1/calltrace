"""Generate the ordered notebooks. Execute them with scripts/run_notebooks.py.

The notebooks explain each step and call the same src/calltrace code as the command
line. Finished work is reused from the per-call cache, so they execute quickly.
"""

from __future__ import annotations

import nbformat as nbf

from calltrace.config import PROJECT_ROOT

SETUP = """from pathlib import Path
import json
import pandas as pd
from IPython.display import Image, Markdown, display

from calltrace.config import PROJECT_ROOT, load_config
from calltrace.data import AppTekDataset

pd.set_option("display.max_colwidth", 160, "display.max_rows", 80)
config = load_config()
dataset = AppTekDataset(config)
results = config.path("results")
evaluation_dir = results / "evaluation"
"""

NOTEBOOKS = {
    "01_research_and_dataset_selection.ipynb": [
        ("md", """# 1. Research and dataset selection

**Goal:** find public customer-agent voice data, compare it, and choose with explicit criteria.
The full survey is in `reports/research_survey.xlsx`; this notebook reads it and re-runs the sampling.

**Key fact to keep in view:** the selected data is **role-played, not real customer calls**."""),
        ("code", SETUP),
        ("md", "## Dataset survey\nEvery row was checked on its source page. `Unknown` means the source does not say."),
        ("code", """survey_path = config.path("reports") / "research_survey.xlsx"
datasets = pd.read_excel(survey_path, sheet_name="Dataset comparison", header=3).dropna(subset=["Source"])
datasets = datasets[datasets["ID"].astype(str).str.startswith("D")]
datasets[["ID", "Source", "Number of calls", "Audio availability", "Transcript availability", "License / usage conditions", "Recommendation"]]"""),
        ("md", "## Eligibility, then comparison\nAudio access and permitted use are gates. Only datasets that pass all gates get a weighted score."),
        ("code", """selection = pd.read_excel(survey_path, sheet_name="Selection decision", header=None)
gate_start = selection.index[selection[0] == "Dataset"][0]
gates = selection.iloc[gate_start + 1 : gate_start + 11]
gates.columns = selection.iloc[gate_start]
gates.iloc[:, :6]"""),
        ("code", """score_start = selection.index[selection[0] == "Criterion"][0]
scores = selection.iloc[score_start + 1 : score_start + 12, :4]
scores.columns = selection.iloc[score_start, :4]
scores"""),
        ("md", "## Papers and how they shaped the work"),
        ("code", """papers = pd.read_excel(survey_path, sheet_name="Papers and articles", header=3)
papers[["ID", "Reference", "How it is used here"]]"""),
        ("md", """## Sampling
Rule: one call per accent, using a seeded shuffle, taking the first call whose domain is unused.
It reads only metadata, so no call can be chosen because it is easy. Running it again gives the same sample."""),
        ("code", """manifest = dataset.sample()
print(f"Catalogue: {manifest['catalogue_calls']} calls; eligible: {manifest['eligible_calls']}; exclusions: {len(manifest['exclusions'])}")
sample = pd.DataFrame(manifest["selected"])
sample["agent_channel"] = sample["channels"].map(lambda c: next(k for k, v in c.items() if v["role"] == "agent"))
sample[["call_id", "source_id", "accent", "domain", "duration_s", "agent_channel"]]"""),
        ("md", "## Data-quality checks on the catalogue"),
        ("code", """catalogue = dataset.build_catalogue()
channel1_customer = sum(r.channels["1"]["role"] == "customer" for r in catalogue)
print(f"{len(catalogue)} calls. All have one agent and one customer: {all({c['role'] for c in r.channels.values()} == {'agent', 'customer'} for r in catalogue)}")
print(f"Channel 1 is the customer in {channel1_customer} calls, so channel order cannot be treated as role.")
print(f"Total recording time: {sum(r.duration_s for r in catalogue) / 3600:.1f} h (the card's 128.6 h is annotated speech).")"""),
        ("code", """from calltrace.data import audio_quality

rows = []
for record in manifest["selected"]:
    # Uses files that are already downloaded; downloads only what is missing.
    paths = dataset.download_call(record)
    for channel in sorted(record["channels"]):
        row = audio_quality(paths[f"channel{channel}"])
        rows.append({"call_id": record["call_id"], "channel": channel, "role": record["channels"][channel]["role"],
                     **{k: row[k] for k in ("samplerate", "duration_s", "clipped_share", "active_share", "speech_rms")}})
quality = pd.DataFrame(rows)
quality.to_csv(config.path("manifests") / "audio_quality.csv", index=False)
print("Sample rates:", sorted(quality.samplerate.unique()))
print("Largest clipped share:", quality.clipped_share.max())
quality.head(6)"""),
        ("md", """## Decision
**AppTek Call-Center Dialogues** is the only candidate with audio open to all, split channels, manual references for
both speakers, and a license that permits sharing derived results. Its main weakness, role-played speech, limits every
conclusion: results describe these role-plays and do not support claims about real customers or business impact."""),
    ],
    "02_transcription_and_speakers.ipynb": [
        ("md", """# 2. Transcription and speaker separation

**Speaker separation** comes from the dataset's split channels: each file holds one speaker. No diarization is needed.
**Role labels** come from channel metadata, with an agent-phrase cross-check.
**Turn boundaries** are predicted from ASR word timestamps, not taken from the dataset.
Reference transcripts are kept apart and used only for evaluation."""),
        ("code", SETUP),
        ("md", "## Choosing the ASR model\nOn a pilot call that is not part of the sample. The published benchmark (P1) reports Parakeet v3 at 9.2% and Whisper Large v3 at 15.0% WER with this segmentation."),
        ("code", """pilot = pd.read_json(evaluation_dir / "asr_pilot_comparison.jsonl", lines=True)
pilot["wer_pct"] = (100 * pilot.wer).round(2)
pilot[["model", "wer_pct", "reference_words", "substitutions", "deletions", "insertions", "load_s", "inference_s", "audio_s_two_channels"]]"""),
        ("md", """One call is too small to rank models on its own. It supports the published result and shows the local scoring works.

**This pilot also hid a problem.** The first full run used int8 weights: the pilot looked fine, yet one sampled call reached 39% WER.
The next cell shows how the cause was found. Full-precision weights are now the configured default."""),
        ("code", """vad = pd.read_csv(evaluation_dir / "asr_deletion_diagnosis.csv", dtype={"call_id": str, "channel": str})
print("Hypothesis 1: VAD or low level. WER % with int8 weights:")
display(vad.pivot_table(index=["call_id", "channel"], columns="variant", values="wer_pct"))
whisper = pd.read_csv(evaluation_dir / "asr_hard_channels_whisper.csv", dtype={"call_id": str, "channel": str})
precision = pd.read_csv(evaluation_dir / "asr_parakeet_precision.csv", dtype={"call_id": str, "channel": str})
compare = vad[vad.variant == "default_vad"][["call_id", "channel", "wer_pct"]].rename(columns={"wer_pct": "parakeet_int8_wer_pct"})
print("Hypotheses 2 and 3: the voices, or the int8 weights:")
compare.merge(whisper[["call_id", "channel", "whisper_wer_pct"]], how="inner").merge(
    precision[["call_id", "channel", "parakeet_full_precision_wer_pct"]], how="inner")"""),
        ("md", "## Run transcription\nThis loads cached results. On a clean checkout it would download the audio and run ASR for each channel."),
        ("code", """from calltrace.pipeline import CallPipeline

records = dataset.load_manifest()["selected"]
pipeline = CallPipeline(config, results, use_llm=False)
run_summary = pipeline.run(records)
run_summary"""),
        ("md", "## A segmented transcript\nEach turn keeps a stable ID, timestamps, speaker, role, raw ASR, and cleaned text."),
        ("code", """from calltrace.export import load_processed_calls

processed = load_processed_calls(results / "calls")
example = processed[0][0]
print(example.speaker_boundaries_source)
pd.DataFrame([t.model_dump() for t in example.turns])[["turn_id", "start", "end", "speaker", "role", "text_raw", "is_backchannel"]].head(14)"""),
        ("md", "## Role assignment and turn statistics"),
        ("code", """rows = []
for transcript, _ in processed:
    agent = next(s for s in transcript.speakers if s.role == "Agent")
    rows.append({"call_id": transcript.call_id, "agent_channel": agent.channel, "role_method": agent.role_method,
                 "agent_phrase_check": agent.role_text_check, "turns": len(transcript.turns),
                 "backchannels": sum(t.is_backchannel for t in transcript.turns),
                 "low_confidence_turns": sum(t.low_confidence for t in transcript.turns)})
pd.DataFrame(rows)"""),
        ("md", """## Unclear audio
- Unreadable or empty audio raises an error, which is recorded per call in `failures.jsonl`; the run continues.
- Parakeet log-probabilities flag turns as `low_confidence`. This is an uncalibrated heuristic for review, not a probability of correctness.
- A silent channel or a channel with no recognised speech produces a quality note."""),
        ("code", """failure_file = results / "failures.jsonl"
print("Failures logged:", failure_file.read_text(encoding="utf-8") if failure_file.exists() else "none")
pd.DataFrame([{"call_id": t.call_id, "notes": " ".join(t.quality_notes)} for t, _ in processed])"""),
    ],
    "03_summary_and_sentiment.ipynb": [
        ("md", """# 3. Evidence-grounded summaries and sentiment

**Model:** Qwen3.5-4B (GGUF, Q4_K_M) served locally by llama.cpp. No paid API. Temperature 0, fixed seed.

**Guardrails**
- Transcripts are delimited and treated as untrusted data.
- The JSON schema restricts citations to turn IDs in the call.
- Quotes are checked against the cited turn, and failures are retried at most twice.
- Citation times are copied from the transcript, never from the model.

**Sentiment**
- From transcript text alone. No vocal emotion is claimed.
- The windows are the first and last 3 substantive customer turns (at least 4 words, no backchannels, no courtesy-only turns).
- Each window is labelled in its own request, so one label cannot anchor the other.
- The change is computed by a rule from the two labels."""),
        ("code", SETUP),
        ("md", "## Run analysis\nThis loads finished results. Missing calls need the server from `scripts/start_llm_server.py`."),
        ("code", """from calltrace.export import export_all, load_processed_calls
from calltrace.pipeline import CallPipeline

records = dataset.load_manifest()["selected"]
print(CallPipeline(config, results).run(records))
export_all(config)
processed = load_processed_calls(results / "calls")"""),
        ("md", "## One call, followed from claim to evidence"),
        ("code", """transcript, analysis = processed[0]
turns = {t.turn_id: t for t in transcript.turns}
for name, claim in (("Issue", analysis.summary.customer_issue), ("Action", analysis.summary.agent_action),
                    ("Outcome", analysis.summary.outcome_or_next_step)):
    print(f"\\n{name} ({claim.status}): {claim.text}")
    for item in claim.evidence:
        turn = turns[item.turn_id]
        print(f"   {item.turn_id} [{turn.start:.1f}-{turn.end:.1f}s] {turn.role}: \\"{item.quote}\\"")"""),
        ("code", """sentiment = analysis.customer_sentiment
print("Overall:", sentiment.overall.label, "-", sentiment.overall.justification)
print("Beginning:", sentiment.beginning.label, "| window:", sentiment.beginning.window_turn_ids)
print("Ending:", sentiment.ending.label, "| window:", sentiment.ending.window_turn_ids)
print("Change:", sentiment.change, "-", sentiment.change_note)"""),
        ("md", "## All calls"),
        ("code", """pd.read_csv(results / "summaries.csv")[["call_id", "customer_issue", "agent_action", "outcome_or_next_step", "outcome_status"]]"""),
        ("code", """pd.read_csv(results / "sentiment.csv")[["call_id", "overall", "beginning", "ending", "change", "agent_sentiment_overall", "justification"]]"""),
        ("md", "## Observed call handling\nDescribes single calls only. It is **not** an employee performance score, and agents are not ranked."),
        ("code", """pd.read_csv(results / "call_handling.csv")[["call_id", "agent_acknowledged_issue", "concrete_action_or_next_step", "resolution"]]"""),
        ("md", "## Minimum output per call\nThe assessment's table: call_id, speakers, transcript, summary, sentiment, and notes. Full text is in `results/calls.csv` and `results/calls.jsonl`."),
        ("code", """table = pd.read_csv(results / "calls.csv")
table.assign(transcript=table.transcript.str.slice(0, 80) + " ...")[["call_id", "speakers", "transcript", "summary", "sentiment", "notes_limitations"]]"""),
    ],
    "04_evaluation.ipynb": [
        ("md", """# 4. Evaluation

Schema validity is not correctness, so these checks are separate. Each has a stated sample size.

| Check | Who or what performs it |
|---|---|
| Transcription | WER against manual references |
| Speaker separation | DER against manual reference segments |
| Citations | Automatic validator |
| Grounding of claims | AI-assisted audit (**not human**) |
| Sentiment | AI second reader (**not human**); human worksheet pending |"""),
        ("code", SETUP),
        ("code", """metrics = json.loads((evaluation_dir / "metrics.json").read_text(encoding="utf-8"))
print(json.dumps({k: metrics[k] for k in ("selected_calls", "processed_calls", "human_review")}, indent=1))"""),
        ("md", "## Transcription\nProtocol: the dataset's scoring steps. Case, punctuation, and speaker labels do not count; number words and digits are normalised. WER is not overall system accuracy."),
        ("code", """print(json.dumps(metrics["transcription"], indent=1))
display(Image(config.path("reports") / "figures" / "wer_by_call.png"))
pd.read_csv(evaluation_dir / "wer_per_call.csv")"""),
        ("md", "Fourteen calls, one per accent, cannot rank accents. The published values are for all calls of that accent. The hollow markers are the first int8 run, kept for comparison."),
        ("code", """pd.read_csv(evaluation_dir / "wer_top_substitutions.csv").head(20)"""),
        ("md", "## Speaker separation"),
        ("code", """print(json.dumps(metrics["speaker_separation"], indent=1))
pd.read_csv(evaluation_dir / "speaker_separation.csv")"""),
        ("md", "### Baseline: diarization on the merged mono file\nThis is a contrast only. The main pipeline does not use it."),
        ("code", """baseline = evaluation_dir / "mono_diarization_baseline.csv"
pd.read_csv(baseline) if baseline.exists() else print("Baseline not run")"""),
        ("md", "## Citation checks\nThese show that citations exist and quotes match. They do not show that a claim is correct."),
        ("code", """print(json.dumps(metrics["output_validation"], indent=1))"""),
        ("md", "## Grounding audit\n**AI-assisted, not human.** The development assistant read each claim with its cited turns and the manual reference. Reviewers should treat it as a first pass."),
        ("code", """print(metrics["grounding_ai_audit_notice"])
print(json.dumps(metrics["grounding_ai_audit"], indent=1))
audit = json.loads((evaluation_dir / "grounding_audit_ai.json").read_text(encoding="utf-8"))
pd.DataFrame(audit["items"])[["claim_id", "cited_support", "correct_in_call", "reason"]]"""),
        ("md", "## Sentiment\nNo independent human labels exist yet. `reports/human_review_worksheet.xlsx` is ready for a person to complete. The comparison below uses an AI second reader, which is **not** independent human validation."),
        ("code", """print(json.dumps(metrics["sentiment_ai_second_reader"], indent=1))
pd.read_csv(evaluation_dir / "sentiment_second_reader_comparison.csv")"""),
        ("md", "## Experiment: does transcription error change the analysis?\nSame analysis configuration on ASR text and on the manual reference, for calls at evenly spaced WER ranks."),
        ("code", """print(json.dumps(metrics["asr_vs_reference"], indent=1))
comparison = pd.read_csv(evaluation_dir / "asr_vs_reference.csv")
comparison[comparison.field.isin(["resolution", "sentiment_overall", "sentiment_beginning", "sentiment_ending", "sentiment_change"])]"""),
        ("code", """comparison[comparison.field.isin(["issue", "action", "outcome"])]"""),
        ("md", """## Prompt change, held-out check
Prompt v1 marked 9 of 14 calls as `confirmed` even when something was only started or promised. Prompt v2 tightened that rule and left 5 of 14 on the same transcripts.
This tuning used the sample itself, so the final labels are not a clean test. The pilot call was held out as one small check."""),
        ("code", """pilot_call = json.loads((results / "pilot" / "calls" / "pilot" / "analysis.json").read_text(encoding="utf-8"))
print("Pilot resolution on prompt v2:", pilot_call["handling"]["resolution"])
print("Pilot citation check passed:", pilot_call["validation"]["passed"])"""),
        ("md", "## Error analysis\nReal successes and failures, with short excerpts and plausible causes."),
        ("code", """display(Markdown((evaluation_dir / "error_analysis.md").read_text(encoding="utf-8")))"""),
        ("md", "## Runtime"),
        ("code", """print(json.dumps(metrics["runtime"], indent=1))
pd.read_json(results / "runtime.jsonl", lines=True).query("step == 'call'")[["call_id", "audio_s", "transcription_s", "analysis_s", "turns"]]"""),
        ("md", "## Results table"),
        ("code", """display(Markdown((evaluation_dir / "results_table.md").read_text(encoding="utf-8")))"""),
    ],
}


def main() -> None:
    directory = PROJECT_ROOT / "notebooks"
    directory.mkdir(exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        notebook = nbf.v4.new_notebook()
        notebook.cells = [nbf.v4.new_markdown_cell(body) if kind == "md" else nbf.v4.new_code_cell(body) for kind, body in cells]
        notebook.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
        nbf.write(notebook, directory / name)
        print(directory / name)


if __name__ == "__main__":
    main()
