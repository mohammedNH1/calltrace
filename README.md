# CallTrace: Evidence-Based Call Review

Maharah GDP Trainee Assessment: Call Center Agent Performance Analysis.

CallTrace transcribes customer-service calls, separates speakers, summarises each call, and analyses customer sentiment. Claims cite speaker turns with audio times, so a reviewer can check them, and an automatic check reports where citations fail.

> **The data is role-played, not real customer calls.** It is spontaneous, unscripted human speech with fictional details. Nothing here supports claims about real customers, production readiness, or business impact.

## Results at a glance

Sample: 14 calls, one per accent, about 141 minutes. All metrics below come from executed runs (`results/evaluation/metrics.json`). Processing and citation validation are different statuses: all 14 calls completed processing, and 3 of those 14 (006, 009, 014) failed citation validation.

| Check | Result | Sample | Type of evidence |
|---|---|---|---|
| Calls completing processing | 14 of 14 | 0 processing failures | Run record |
| Pooled WER | 9.32% | 19,248 reference words, 28 channels, 14 calls | Measured against manual reference |
| Median call WER (range) | 6.81% (3.28-22.77%) | 14 calls | Measured against manual reference |
| Agent / customer pooled WER | 5.79% / 15.04% | 28 channels | Measured against manual reference |
| Median DER, split channels | 10.23% | 14 calls, 0.25 s collar | Measured against manual segments |
| Median / max speaker confusion, split channels | 0.14% / 1.1% | 14 calls | Measured against manual segments |
| Mono diarization baseline: median DER; median / max confusion | 6.97%; 1.1% / 35.23% | 14 calls; clusters mapped using the reference | Measured against manual segments |
| Calls passing all citation checks | 11 of 14 | 275 citations | Automatic validation (rules, not correctness) |
| Claims fully supported by cited turns | 20 of 42 | partial 22, unsupported 0 | **AI audit, not human** |
| Claims correct against the whole call | 34 of 42 | partly 7, wrong 1 | **AI audit, not human** |
| Sentiment agreement: overall / beginning / ending | 8 / 13 / 12 of 14 | reader saw model labels first | **AI second reader, not human** |
| Sentiment agreement with human labels | Not available | 0 labels completed | Human evaluation not done; worksheet is blank |
| ASR vs reference: labels unchanged | 20 of 25 | 5 calls, 5 labels each | Measured comparison of model output, same analysis settings |

**How to read this**
- WER is (substitutions + deletions + insertions) / reference words, after one stated normalisation. Lower is better, and it can exceed 100%. It is not system accuracy, and 1 - WER is not reported.
- The published 9.2% for this model (all 873 calls, averaged over accents) is context, not a directly comparable benchmark. Sample, averaging, and scorer implementation differ, and it is unverified whether the paper used the same ONNX weights.
- Passing a citation check shows that the turn exists and the quote matches. It does not show that the claim is right. Call 005 passes, and the AI audit judged its outcome wrong.
- No human evaluation has been done. `reports/human_review_worksheet.xlsx` is blank, with 0 labels completed, and is ready for a person to fill in.
- Fourteen calls cannot support claims about particular accents or domains.

## Setup

Tested only on Windows 11 with Python 3.11.9; other platforms are unverified. Needs about 7 GB of disk for models and audio. A 4 GB GPU is enough for the LLM, which also runs slowly on CPU. No API key or paid service is needed.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## How to run

**1. Start the local LLM** in its own terminal. The first run downloads llama.cpp and the model (2.7 GB).

```powershell
python scripts/start_llm_server.py
# With two GPUs, choose one. List them with: models\llama-cpp\llama-server.exe --list-devices
python scripts/start_llm_server.py --device Vulkan1
```

On Linux or macOS (not tested), install llama.cpp yourself and add `--binary /path/to/llama-server`. Any OpenAI-compatible server works if you change `llm.base_url` in `configs/config.yaml`.

**2. Run the pipeline.**

```powershell
python -m calltrace run --smoke --fresh   # one call end to end, into results/smoke
python -m calltrace run --full            # all 14 calls, into results/
python -m calltrace export                # CSV and JSONL outputs
python -m calltrace evaluate              # metrics, grounding sheet, human worksheet
```

The smoke run takes 1 to 3 minutes after models are downloaded. On a machine like the one below, the full run took about 30 minutes. A re-run skips finished calls, and caches are kept per channel and per LLM request. Transcripts alone need no LLM: add `--asr-only`.

**3. Open the outputs.**

```powershell
python scripts/run_notebooks.py           # execute notebooks 01 to 04 in order
pytest                                    # focused tests
streamlit run app/streamlit_app.py        # evidence review interface
```

Result files, notebooks, and reports can all be read without the app.

**What has been checked.** In a clean copy with a new environment from `requirements.txt`, the tests passed, the redrawn sample manifest was identical, and a smoke run on one call produced transcript and analysis files byte-identical to the main run. Scope: one call, on the same Windows machine, reusing already downloaded model weights. All 14 calls have not been re-run from a clean copy, no saved log of this check exists, and no other platform was tested.

## Data source

[AppTek Call-Center Dialogues](https://huggingface.co/datasets/apptek-com/apptek_callcenter_dialogues) (Beck et al., 2026, [arXiv:2604.27543](https://arxiv.org/abs/2604.27543)), pinned to commit `b98967d9946f7f59f58d08624a2a00fe98fe0219`. It has 873 role-played agent-customer calls in 14 English accents and 16 service domains, with one audio file per speaker and manual transcripts.

**Why this dataset.** Real public customer calls with usable audio were not found: real corpora withhold audio, sell it, or lack a clear license. This was the only candidate with open audio, split channels, manual references for both speakers, and a license that allows sharing derived results. The comparison of 10 sources is in `reports/research_survey.xlsx`.

**License and redistribution.** The dataset is CC BY-SA 4.0, so the derived transcripts and summaries in `results/` are shared under the same license, with attribution to AppTek.ai. Audio is not in this repository, only to keep it small; the commands above download it. The dataset card excludes training, and this project trains nothing. Reference transcripts are kept apart from ASR output and used only in evaluation.

**Data status.** Role-played human speech, not synthetic speech and not translated. The dataset comes pre-transcribed by hand, but the transcripts analysed here are generated by ASR; the manual ones are used only for scoring. This is a sample of 14 of 873 calls. Some recordings end abruptly: call 011 stops mid-question, and call 013 ends with unanswered "Hello?" turns.

**Sampling.** Seed 20261108. For each accent, shuffle its calls and take the first whose domain is unused. The rule reads metadata only. 0 of 873 calls were excluded (rules: two channels, one agent and one customer, at least 180 s, reference segments present), and no sampled call was replaced. See `data/manifests/sample_manifest.json`.

## Method

**Speaker separation.** Each file holds one speaker, so identity comes from the dataset's channels, not from diarization. Channel 1 is the customer in 66 of 873 calls, so channel order is never treated as role.

**Roles.** Customer and Agent come from channel metadata. A phrase check on agent wording agrees on 14 of 14 calls. Speaker 1 and Speaker 2 are kept alongside the roles.

**Turns.** Turn boundaries are predicted from ASR word timestamps and are not from the dataset. Short interjections over the other speaker are flagged as backchannels, and turns over 30 s split at a sentence end. Each turn has a stable ID, timestamps, raw ASR text, and cleaned text.

**Unclear audio.** Unreadable or empty audio stops that call and is logged in `failures.jsonl`, and the run continues. Silent channels produce a quality note. Low-confidence turns are flagged by an uncalibrated log-probability rule. Calls whose speakers overlap on over 30% of the quieter speaker's time are flagged as possibly out of sync. This is a heuristic and may produce false alarms. It fires on calls 005 (61%), 004 (45%), and 010 (31%), but overlap in the manual reference is high only on 005 (54.2%, against 22.9% and 14.6%).

**Summaries and handling.** The local LLM returns JSON constrained by a schema, so citations can only name turns from that call. Quotes are checked against the cited turn, with at most 2 retries; calls that still fail stay marked as failed. A failed citation check is separate from processing, which completed for all 14 calls. Citation times are copied from the transcript. `not stated` and `unclear` are allowed, and thanks are not treated as resolution. Handling notes describe single calls. They are not a performance score, and agents are not ranked.

**Sentiment.** From transcript text only, so nothing is claimed about vocal emotion.
- Labels: negative, neutral, positive, insufficient_evidence (plus mixed for overall).
- Windows: the first and last 3 substantive customer turns: at least 4 words, no backchannels, no courtesy-only turns.
- Each window is judged in a separate request, so one label cannot anchor the other. Agent sentiment is judged separately.
- Change is computed by a rule from the two labels. No confidence percentages are produced.

**Safety.** Transcript text is delimited and treated as untrusted data. Model names, ASR precision, and prompt versions are recorded in the outputs; pinned revisions are listed below.

### Tools and models

| Purpose | Tool | Version or revision | License |
|---|---|---|---|
| ASR | NVIDIA Parakeet TDT 0.6B v3, [ONNX export](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx), full precision, via `onnx-asr` | `onnx-asr` 0.12.0. Revision not pinned in code; the local cache used holds `8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce` | CC BY 4.0 |
| Segmentation | Silero VAD, settings from the dataset card | via `onnx-asr`. Revision not pinned in code; the local cache used holds `b3e3ee3cce4c11ceb63b1a0b229d916069c1ddf6` | MIT |
| Analysis | [Qwen3.5-4B Q4_K_M GGUF](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF) | `e87f176479d0855a907a41277aca2f8ee7a09523`, SHA-256 `00fe7986...ef11a4` | Apache-2.0 |
| LLM server | llama.cpp `llama-server`, Vulkan build | release `b12034` | MIT |
| Comparison only | faster-whisper large-v3; sherpa-onnx with pyannote segmentation and 3D-Speaker embeddings | `requirements.txt`, `scripts/` | See model pages |

Settings are in `configs/config.yaml`. Python dependencies are pinned in `requirements.txt`. Parakeet and Silero download from each repository's default branch, so a later upstream change could alter results.

### Runtime

AMD Ryzen 7 6800H (8 cores), 15 GB RAM, RTX 3050 Ti 4 GB. ASR on CPU: median 7.5 s per minute of audio, about 5 s to load cached weights. Analysis on GPU: median 46 s per call, maximum 70 s, with some requests served from cache. The machine was in normal use during timing.

## What the evaluation found

The full account with excerpts is in `results/evaluation/error_analysis.md`.

1. **The tested int8 weights scored worse than the tested full-precision weights.** Measured: the int8 run gave 14.39% pooled WER, with one call at 38.98%, and the full-precision run gave 9.32%, with 10 calls better, 3 slightly worse, and 1 unchanged. Whisper reached 6.83% on a channel where int8 Parakeet had 45.78%, and full-precision Parakeet reached 5.38%. The pilot call had looked fine at 6.02%. A more sensitive VAD and normalised audio gave no consistent fix: some channels improved (largest gain 43.36% to 37.34%) and others got worse. This is an observation about these configurations of one third-party export on this sample, not proof that quantization generally reduces accuracy. The mechanism was not tested.
2. **A valid citation can support a wrong conclusion.** Measured: on call 005 the customer gives card digits before the agent's greeting, and the manual reference shows the same order, with 54.2% overlap. Unverified explanation: the channels are suspected to be out of sync, and "No thank you" may answer another question. No person has listened to confirm this. AI audit: the outcome claim, that the customer declined to pay, is wrong.
3. **Sentiment is weakest overall.** The overall label is positive for 10 of 14 calls and often leans on polite closings. The AI second reader agrees on 8 of 14. Treat this label as weak until human labels exist.
4. **Summaries are mostly correct but under-cited.** 34 of 42 claims are correct against the whole call, but only 20 of 42 are fully covered by their own citations, often because a detail came from an uncited turn. These are AI-audit figures.
5. **Word errors changed few labels in this small test, but labels are unstable.** 20 of 25 labels matched between ASR and reference text. Two of the five differences are on call 005, and two on call 012, which has the lowest WER (3.28%). So model instability, rather than word errors, may explain some flips, but this is an unverified explanation. Reference turns also have different segmentation, so the comparison is not purely about words.
6. **Channels beat a mono baseline on attribution, not on overall DER.** The baseline has lower DER (6.97% vs 10.23%), but confusion reached 35.23% on one call against at most 1.1%, and it needed the reference to map clusters to speakers.

## Assumptions and limitations

- **Role-played data.** Sentiment may be milder or staged, and speakers may not know the domain. Results do not transfer to real customers.
- **Split-channel audio.** Separation here depends on clean channels. Mono telephone calls would be harder, and results would differ.
- **Small sample.** 14 calls give examples and rough rates, not precise estimates, and no accent or domain comparison is justified.
- **Tuned on the sample.** Prompt v2 (which moved `confirmed` from 9 to 5 of 14 calls on int8 transcripts), full-precision weights, and the 30% overlap threshold were all chosen after seeing sample results. The pilot call was the only held-out check of the prompt. Earlier outputs are kept in `results/evaluation/prompt_v1/` and `results/evaluation/parakeet_int8/`.
- **No human evaluation.** The AI audit and second reader saw the model's output first. They are a first pass, not validation.
- **WER reimplementation.** The dataset's scoring steps were re-implemented with the `whisper_normalizer` package in place of the `openai-whisper` normaliser, and may differ slightly. Published figures are context only, not a directly comparable benchmark.
- **Word end times are estimates.** They come from the next token's start, so spans can run long, and DER false alarm is inflated. Citation times use turn starts.
- **Local LLM.** A small quantized model on one seed. Output can change if the text changes slightly. Answers were generated with context sizes of 8,192 and 16,384 tokens; the larger one is the default because long reference transcripts overflowed the smaller.
- **Recorded failures.** Calls 006, 009, and 014 completed processing but still fail citation validation after retries. They remain in the results, marked as failed.

## Repository structure

```text
app/streamlit_app.py     Evidence review interface
configs/config.yaml      Models, sampling, and processing settings
data/manifests/          Seeded sample manifest and audio quality table (audio is downloaded)
notebooks/               01 research, 02 transcription, 03 analysis, 04 evaluation (executed)
reports/                 Research workbook, slides, speaker notes, demo, checklist, worksheet, figures
results/calls/<id>/      Per-call ASR words, transcript, analysis, audio quality
results/*.csv, calls.jsonl  Turns, summaries, sentiment, handling, and the per-call table
results/evaluation/      Metrics, audits, experiments, error analysis, earlier runs
scripts/                 Server start, comparisons, baselines, and report builders
src/calltrace/           data, asr, turns, llm, analysis, validation, evaluation, pipeline, export
tests/                   Timestamps, evidence, schemas, empty input, failures, and resume
```

**Main per-call output** (`results/calls.csv`, `results/calls.jsonl`): `call_id`, `speakers`, `transcript`, `summary`, `sentiment`, `notes_limitations`, plus evidence and timestamps.

**Diagrams:** `reports/figures/architecture.png` and `reports/figures/sequence.png`.

## Presentation

Slides: `reports/calltrace_presentation.pptx`. Speaker notes: `reports/speaker_notes.md`. Demo: `reports/demo_walkthrough.md`.

## References

- Beck et al. (2026). AppTek Call-Center Dialogues. arXiv:2604.27543.
- Si et al. (2023). SpokenWOZ. NeurIPS. arXiv:2305.13040.
- Jia & SungChu (2020). A Deep Learning System for Sentiment Analysis of Service Calls. arXiv:2004.10320.
- Gao et al. (2023). Enabling Large Language Models to Generate Text with Citations. EMNLP. arXiv:2305.14627.
- Feigenblat et al. (2021). TWEETSUMM. Findings of EMNLP. arXiv:2111.11894.
- Ghosh et al. (2025). ASR-Synchronized Speaker-Role Diarization. arXiv:2507.17765.
- An empirical analysis of word error rate and keyword error rate. INTERSPEECH 2008, IBM Research.
