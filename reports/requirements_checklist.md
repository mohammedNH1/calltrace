# Requirement-to-artifact checklist

Status terms: **Done** means the artifact exists and was checked. **You** means it still needs you.

## Plan as executed

1. Read the assessment and inspected hardware, Python, and available tools.
2. Researched sources, then chose data and models from what was verified.
3. Ran one call end to end early, then the full sample.
4. Evaluated, diagnosed the failures found, and re-ran the final configuration.
5. Built reports and ran a clean-copy check limited to one call, on the same Windows machine, with downloaded weights reused.

## Required tasks

| # | Requirement | Artifact | Status |
|---|---|---|---|
| 1 | Research datasets and papers | `reports/research_survey.xlsx`: 10 sources, 7 papers | Done |
| 2 | Excel survey with all required columns | `Dataset comparison` sheet; `Source references` sheet with access dates | Done |
| 3 | Select the best dataset, with criteria and reasons | `Selection decision` sheet; `notebooks/01_...` | Done |
| 4 | Transcribe and segment; separate Speaker 1 and 2; label roles and explain how | `results/calls/*/transcript.json`, `results/turns.csv`; README, Method | Done |
| 5 | Summarise each call: issue, action, outcome | `results/summaries.csv`, `results/calls/*/analysis.json` | Done. Processing completed for 14 of 14. Separately, 3 calls (006, 009, 014) failed citation validation and stay marked as failed |
| 6 | Customer sentiment: label, reason, beginning and end | `results/sentiment.csv` | Done |
| 7 | Record a 10-minute presentation | Slides, notes, and demo are ready | **You: record** |

**Minimum output per call** (`results/calls.csv`): `call_id`, `speakers`, `transcript`, `summary`, `sentiment`, `notes_limitations`. Done.

## Deliverables

| # | Deliverable | Artifact | Status |
|---|---|---|---|
| 01 | Research survey | `reports/research_survey.xlsx` | Done |
| 02 | Ordered, executed notebooks | `notebooks/01` to `04` | Done |
| 03 | README | `README.md` | Done |
| 04 | Slides plus recording | `reports/calltrace_presentation.pptx` (9 slides) | Slides done. **You: recording** |
| 05 | Results in a reusable format | `results/` (JSON, JSONL, CSV) | Done |
| - | Validation | `results/evaluation/`: measured comparisons, automatic validation, and AI audit | Done. No human evaluation |
| - | Human review worksheet | `reports/human_review_worksheet.xlsx` | Created but blank, 0 labels. **You: optional review** |
| - | Timed speaker notes | `reports/speaker_notes.md` | Done. Slide notes differ; see the end of this file |
| - | Demo walkthrough | `reports/demo_walkthrough.md` | Done |

## Optional bonus

| Item | Artifact | Status |
|---|---|---|
| Python classes | `AppTekDataset`, `Transcriber`, `CallAnalyzer`, `CallPipeline`, and others in `src/calltrace/` | Done |
| Simple interface | `app/streamlit_app.py` | Done. A headless browser confirmed the highlight and player position. Audible playback is unverified |
| Architecture diagram | `reports/figures/architecture.png` | Done |
| Sequence diagram | `reports/figures/sequence.png` | Done |

## Submission rules

| Rule | How it is met | Status |
|---|---|---|
| Useful comments, clean modular code | `src/calltrace/`, `scripts/` | Done |
| Dependency file | `requirements.txt`, pinned | Done |
| No keys or credentials | Scan in the final check; no key is needed | Done |
| No private or restricted data | Role-played, CC BY-SA 4.0, fictional details; rejected sources are explained in the survey | Done |
| Document redistribution limits | README, Data source; `Selection decision` sheet | Done |
| State if data is synthetic, translated, pre-transcribed, or incomplete | Role-played is stated in the README, slides, and app. Not translated. ASR is generated here; references are separate | Done |
| Reproducible with README instructions | README, How to run. Clean-copy check on one call only, same Windows machine, downloaded weights reused. All 14 calls were not re-run from clean | Done, within that scope |

## Evaluation rubric

| Area | Points | Where reviewers should look | Known weakness |
|---|---|---|---|
| Research survey | 15 | `reports/research_survey.xlsx` | Vendor sizes are advertised, not verified, and marked as such |
| Dataset selection | 10 | `Selection decision` sheet | Role-played data; scores are judgment |
| Transcription and speakers | 15 | `wer_per_call.csv`, `speaker_separation.csv`, `error_analysis.md` | Customer WER is 15.04%; word ends run long |
| Call summaries | 10 | `summaries.csv`, `grounding_audit_ai.json` | Only 20 of 42 fully covered by citations |
| Sentiment | 10 | `sentiment.csv`, comparison CSV | Overall leans positive; no human labels yet |
| Implementation quality | 15 | `src/`, `notebooks/`, `tests/` | Parakeet and Silero revisions are not pinned in code |
| Validation and analysis | 10 | `metrics.json`, `results_table.md`, `error_analysis.md` | **Manual checks by a human are not done yet.** The citation check is automatic, and the audit is by AI |
| README and reproducibility | 5 | `README.md` | Windows is the only tested platform |
| Presentation | 10 | Deck, notes, demo | **Needs your recording** |

## Your remaining tasks

1. **Review (recommended):** complete `reports/human_review_worksheet.xlsx`, then run `python -m calltrace evaluate`. The rubric asks for manual checks, and today only an AI audit exists.
2. **Update results if you review:** the slides and README say no human labels exist. Change slide 7 and the README's table if that stops being true.
3. **Record** the 10-minute presentation using `reports/speaker_notes.md` and `reports/demo_walkthrough.md`.
4. **Include the recording link** in the submission email.
5. **GitHub:** commit and push these documentation corrections.
6. **Submit** through the channel in your invitation by 8 November 2026.

## Known remaining inconsistencies

These files were left unchanged, so they still carry older wording. The README and `error_analysis.md` take precedence.

- `reports/calltrace_presentation.pptx`, slide 1: "Every claim links to the moment in the call that supports it." Three calls failed citation validation.
- Same deck, slide 7: "Transcription is close to the published figure". The published figure is context only.
- Same deck, embedded notes: slide 2 says "none failed", slide 7 defines WER loosely, and slide 8 says the change "fixed it". Use `reports/speaker_notes.md`.
- `reports/figures/wer_by_call.png`: the title says quantized weights "caused" the worst errors.
- `notebooks/04_evaluation.ipynb`: its saved output shows the older `error_analysis.md`, and `notebooks/02_...` calls the int8 check finding "the cause".
