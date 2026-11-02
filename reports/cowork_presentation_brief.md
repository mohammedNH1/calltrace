# CallTrace presentation brief for Claude Cowork

**Purpose:** source text for a 10-minute screen-recorded presentation of the Maharah GDP Trainee Assessment, "Call Center Agent Performance Analysis".

**How this was verified:** every fact below was read on 2 November 2026 from the assessment PDF and the project's saved code, configuration, research workbook, results, and evaluation files. Nothing was re-run to prepare this brief. Paths are relative to the project folder.

**Status words**
- **Measured:** computed by code against the dataset's manual reference.
- **Automatic check:** a rule run by code. It shows that something is well formed, not that it is correct.
- **AI review:** judgment by Claude Opus 5.5, the assistant that also built the project. It is **not** human review.
- **Unverified:** could not be confirmed from saved files. Section 11 says what is missing.

**Human review of our outputs: none has taken place.** The human review worksheet has 0 labels completed. The dataset's reference transcripts were written by the dataset's own annotators. They are not a review of our outputs.

---

## 1. Project overview

**What it does.** CallTrace processes recorded customer-service calls and shows the result for review. Three AI tasks do the main work:
1. **Speech-to-text:** turns each speaker's audio into words with timestamps.
2. **Summarization:** writes the customer issue, agent action, and outcome or next step.
3. **Customer sentiment analysis:** labels the customer's sentiment overall, at the beginning, and at the end of the call.

**The problem it addresses.** A generated summary can sound confident and still be wrong. A reviewer needs a quick way to check it. In CallTrace, each claim cites a speaker turn with a short quote, and each turn has its audio time.

**Scope**
- 14 role-played calls, in English.
- Everything runs locally, with pretrained models and no paid service.
- It describes individual calls. It does **not** score employees or rank agents, despite the assessment's title. Its "observed call handling" fields describe one call only.
- It is an assessment project, not a production system.

---

## 2. Assessment requirements

Source: the assessment PDF. Deadline: 8 November 2026. Submission: GitHub repository plus a 10-minute screen recording.

| Maharah asked for | How it is addressed | Status |
|---|---|---|
| Research public customer-agent voice datasets and papers | 10 sources and 7 papers in `reports/research_survey.xlsx` | Done |
| Excel survey with required comparison columns | `Dataset comparison` sheet, with links and access dates | Done |
| Select the best dataset, and explain why | `Selection decision` sheet: gates, then a weighted comparison | Done |
| Transcribe and segment; separate Speaker 1 and 2; label roles if possible | `results/turns.csv`, `results/calls/<id>/transcript.json` | Done |
| Summarize each call: issue, action, outcome or next step | `results/summaries.csv` | Done |
| Customer sentiment: label and justification; optional beginning versus end | `results/sentiment.csv` | Done |
| 10-minute recorded presentation | Slides from this brief | **Recording not done** |
| Results in a reusable format | JSON, JSONL, and CSV in `results/` | Done |
| README, dependency file, comments, no credentials | `README.md`, `requirements.txt` | Done |
| Optional bonus: classes, interface, architecture and sequence diagrams | `src/calltrace/`, `app/streamlit_app.py`, `reports/figures/` | Done |

The rubric totals 100 points: research survey 15, dataset selection 10, transcription and segmentation 15, summaries 10, sentiment 10, implementation 15, validation 10, README 5, presentation 10. The rubric's validation row mentions "manual checks", and **no human has done those yet**.

---

## 3. Dataset research and selection

**Method.** Audio access and permitted use were treated as gates. Only sources passing every gate received a weighted score. Gates: audio accessible without purchase or sign-up gate; clear permitted use; at least 10 customer-agent calls; responsible use.

| Source | Result | Deciding reason |
|---|---|---|
| AppTek Call-Center Dialogues | **Selected** | Split channels, manual references for both speakers, CC BY-SA 4.0 |
| SpokenWOZ | Eligible, runner-up | Customer text keeps speech-recognition noise on purpose, so customer error rate cannot be measured. 8 kHz. CC BY-NC 4.0 |
| CallCenterEN (AIxBlock) | Rejected | Real calls, but no audio released, for biometric privacy reasons |
| AxonData samples | Rejected | Only 2 open English calls; the full set is paid |
| UniData preview | Rejected | 5 calls; no-derivatives license; preview names companies and user locations |
| InfoBayAI Arabic dual channel | Rejected | Gated; about 3 sample calls; terms not read |
| Nakulbh/call-center-dataset | Rejected | No license or provenance |
| AIxBlock Japanese | Rejected | Human-to-machine, not a human agent |
| Arabic call benchmark paper | Rejected | No public download located |
| Switchboard and CALLHOME (LDC) | Rejected | Licensed; not service calls |

**Weighted score (author's judgment, out of 5):** AppTek 4.90, SpokenWOZ 3.20. AppTek also leads with equal weights (4.71 vs 3.14) and without the reference criterion (4.88 vs 3.50). These are judgments against stated reasons, not measurements.

**AppTek facts**
- 873 calls, 1,746 channel files, 14 English accents, 16 service domains.
- 151.1 hours of total recording time, of which 128.6 hours is annotated speech, according to the dataset paper.
- 16 kHz audio, one speaker per file, with a merged file per call.
- Manual transcripts with timed segments, role labels, and pseudonymous speaker IDs.
- Dataset revision pinned: `b98967d9946f7f59f58d08624a2a00fe98fe0219`.

**License.** CC BY-SA 4.0. Derived transcripts and summaries are shared under the same license, with attribution. The dataset card excludes training use; this project trains nothing. Audio is downloaded by script and is not stored in the repository, to keep it small.

**THE CALLS ARE ROLE-PLAYED, NOT REAL CUSTOMER CALLS.** Speakers chose a scenario and spoke freely, without a script, using fictional names and details. No real public customer calls with usable open audio and clear permitted use were found among the sources reviewed.

**Limitations of this choice**
- Sentiment may be milder or staged.
- Speakers may not know the domain, as the dataset paper notes.
- Audio came through VoIP with separate channels. Mono phone recordings would be harder.
- Nothing here supports claims about real customers or business impact.

**The 14-call sample**
- Rule: seed 20261108. Visit each accent in a fixed order, shuffle its calls, and take the first call whose domain has not been used.
- The rule reads only metadata, so calls could not be chosen for being easy.
- Eligibility rules excluded 0 of 873 calls. No sampled call was replaced.
- Result: 14 calls, 14 accents, 14 distinct domains.
- **Total audio duration: 8,466.5 seconds, about 141 minutes.** Calls range from 358.7 s to 902.9 s.
- One separate pilot call, `en_US_General_Travel_1586358`, is outside the sample. It was used for engine comparison and one prompt check.

---

## 4. Actual processing workflow

| Step | What happens | Source |
|---|---|---|
| 1. Audio input | Downloads two per-speaker WAV files at the pinned revision; records basic audio checks and SHA-256 hashes | **Dataset** |
| 2. Speech detection | Silero VAD (voice activity detection) finds speech chunks of up to 30 s, using settings from the dataset card. It only prepares chunks for transcription | **Predicted** |
| 3. Transcription | Parakeet turns each chunk into words with timestamps and log-probabilities, for each channel separately | **Predicted** |
| 4. Speaker separation | Each file holds one speaker, so Speaker 1 and Speaker 2 come from the channel. No diarization model is used in the pipeline | **Dataset** |
| 5. Role assignment | Customer or Agent comes from channel metadata. A simple agent-phrase check is a cross-check only | **Dataset**, plus a rule |
| 6. Turn construction | Words from both channels are merged by time into turns with stable IDs. Rules: a 1.2 s gap ends a speech run; runs merge within 2 s; interjections of up to 3 words over the other speaker are flagged as backchannels; turns over 30 s split at a sentence end | **Rules on predicted words** |
| 7. Summarization | Local LLM writes issue, action, outcome, and handling observations as JSON. The schema allows citations only to turns in that call | **Predicted** |
| 8. Customer sentiment | Separate requests for the beginning window, ending window, and overall. Windows are the first and last 3 customer turns that have at least 4 words and are not backchannels or courtesy-only | **Predicted label; windows by rule** |
| 9. Change | improved, worsened, unchanged, or insufficient evidence, computed by a rule from the two window labels | **Rule** |
| 10. Evidence validation | Checks that cited turns exist, quotes match the turn, customer sentiment cites customer turns, and claims have citations. At most 2 retries. Failures stay marked as failed | **Automatic check** |
| 11. Display | Results export to CSV and JSONL, and the Streamlit app shows them with the dataset's merged audio | Exported results and dataset audio |

**Keep these distinctions on the slide**
- **Supplied by the dataset:** audio, one-speaker-per-file channels, Customer and Agent roles, speaker IDs, and manual reference transcripts. References are used only for evaluation. They are never given to the main analysis.
- **Predicted by models:** speech chunks, words, word timestamps, summaries, and sentiment labels.
- **Computed by rules:** turn boundaries from predicted words, sentiment windows, sentiment change, and quality flags.

**Also worth saying**
- Sentiment uses transcript text only. It claims nothing about tone of voice.
- Agent sentiment is judged in its own request and is reported separately.
- Transcript text is treated as untrusted data in prompts.
- Citation times are copied from the transcript, never taken from the model.

**Visual:** `reports/figures/architecture.png` and `reports/figures/sequence.png`. A native workflow graphic built from this table, color-coded by "dataset", "model", and "rule", would show the distinctions better.

---

## 5. Models and implementation

**All models are pretrained. Nothing was trained or fine-tuned.**

| Task | Model | Quantization | Tool | Hardware | Why chosen |
|---|---|---|---|---|---|
| Transcription | NVIDIA Parakeet TDT 0.6B v3, ONNX export `istupakov/parakeet-tdt-0.6b-v3-onnx` (CC BY 4.0) | **None: full-precision weights** | `onnx-asr` 0.12.0, `onnxruntime` 1.31.1 | CPU | The dataset paper reports it at 9.2% average WER with Silero segmentation, against 15.0% for Whisper Large v3. It also scored lowest in our pilot-call comparison |
| Speech detection | Silero VAD, ONNX export `istupakov/silero-vad-onnx` | Not applicable | `onnx-asr` | CPU | Recommended on the dataset card |
| Summary and sentiment | Qwen3.5-4B, `unsloth/Qwen3.5-4B-GGUF`, file `Qwen3.5-4B-Q4_K_M.gguf` (Apache-2.0) | **Q4_K_M** | `llama.cpp` server, release b12034, Vulkan build | RTX 3050 Ti 4 GB GPU | It runs locally with no API key and fits a 4 GB GPU. **No other LLM was compared** |

**Comparison only, not in the main pipeline**
- `faster-whisper` large-v3 (CPU, int8).
- A mono diarization baseline: `sherpa-onnx` with pyannote segmentation 3.0 and a 3D-Speaker embedding model.

**LLM settings:** temperature 0, seed 20261108, at most 2 repair retries, prompt version v2.

**Machine:** AMD Ryzen 7 6800H (8 cores), 15 GB RAM, Windows 11, Python 3.11.9.

**Implementation**
- Python package `src/calltrace/` with classes such as `AppTekDataset`, `ParakeetTranscriber`, `CallAnalyzer`, and `CallPipeline`.
- Settings in `configs/config.yaml`; JSON schemas with Pydantic; per-call caching and resume.
- No agents, databases, or orchestration frameworks.

---

## 6. What makes the project distinctive

Only demonstrated functionality is listed. Claims of uniqueness should be avoided: other submissions were not seen.

**Timestamped evidence references.** Every summary and sentiment statement can cite turn IDs with quotes and times. 275 citations were checked automatically across 14 calls.

**Clickable citation-to-audio navigation.** In the Streamlit app, clicking a citation button highlights that turn in the transcript, scrolls to it, and starts the audio from its time. A real browser test confirmed the highlight and the player position: the player showed 7:17 after clicking a 07:15 citation (`reports/figures/app_evidence_outcome.png`).
- **Be precise:** the clickable items are the **citation buttons**. Transcript turns themselves are not clickable.

**Beginning versus ending customer sentiment.** Windows are chosen by code. Each is labelled in a separate request, so one label cannot anchor the other, and the change comes from a fixed rule. Results: 11 improved, 3 unchanged, 0 worsened. That pattern could partly reflect the role-play, or a positive lean in the model, so it is not evidence about real service quality.

**Reproducibility**
- Pinned dataset revision, LLM revision, llama.cpp release, Python dependencies, and sampling seed.
- Re-drawing the sample in a clean copy produced an identical manifest file.
- A clean-copy smoke run on one call produced transcript and analysis files identical to the main run.
- Parakeet's revision is **not** pinned in code. See section 11.

**Honest failure reporting.** The evaluation keeps failed outputs and earlier runs, including a run that went wrong.

---

## 7. One real worked example: call 001

**Why this call.** It is a complete story with a clear issue, a visible sentiment change, passing citation checks, and an instructive partial error. **It is an easier call than most:** WER 3.90%, against a median of 6.81%. Call 005 is the failure example in section 9.

**Facts:** call 001, source `en_AU_Banking_1590914`, banking domain, en-AU accent, 633.2 s, 59 turns. Speaker 1 = Agent, Speaker 2 = Customer. Names are fictional, as the dataset requires. Citation check: passed, with 1 retry.

**Transcript excerpts (unedited ASR output)**

| Turn | Time | Speaker | Text |
|---|---|---|---|
| 001-T0001 | 00:13 | Agent | "Hi, thanks for calling A and Z. You are speaking with Tom. How can I help you today?" |
| 001-T0002 | 00:18 | Customer | "...I had to make a transaction and when I've gone to transfer something, I've realized I've sent it to the wrong place." |
| 001-T0003 | 00:37 | Customer | "So I've sent all this money and I'm really worried because obviously I didn't want to go to the wrong place and yeah..." |
| 001-T0023 | 03:40 | Agent | "We can't always guarantee that we will get it back, but we will certainly try our best..." |
| 001-T0043 | 07:15 | Agent | "...Uh the amount uh should hopefully appear as a pending refund uh within your account, uh, but will take uh 24 to 48 hours for the money to actually clear..." |
| 001-T0050 | 08:58 | Customer | "Okay, brilliant. Oh this is giving me a little bit of relief. I was freaking out." |
| 001-T0056 | 09:57 | Customer | "No, that's all. You've been such a big help. I really appreciate it. Five stars. Tell your boss to give you a raise." |

**Transcription errors visible here, shown as generated:** "A and Z" is "ANZ" in the reference; "Osco" is "Osko".

**Model's summary, exactly as generated**
- **Issue:** "The customer accidentally transferred money to the wrong person via the banking app." Cites T0002 (00:18), T0003 (00:37).
- **Action:** "The agent verified customer details, located the transaction, and guided the customer through the recall process." Cites T0004 (00:51), T0022 (03:24), T0033 (05:22).
- **Outcome:** "The agent confirmed the recall was initiated and the refund would appear as pending within 24 to 48 hours." Cites T0043 (07:15), T0048 (08:40).

**Model's customer sentiment, exactly as generated**
- **Beginning: negative.** "The customer expresses worry and anxiety about sending money to the wrong place." Window: T0002, T0003, T0005. Cites T0002, T0003.
- **Ending: positive.** "The customer expresses relief, gratitude, and offers a five-star rating with a request for a raise." Window: T0050, T0053, T0056. Cites T0050, T0056.
- **Change: improved** (by the rule).
- **Overall: positive.** "The customer expresses relief and gratitude after successfully recalling the payment and receiving a summary for their real estate agent."

**Observed handling, exactly as generated:** acknowledged issue: yes; concrete next step: yes; resolution: **unresolved**, "The refund is pending and will take 24 to 48 hours to clear; the money has not yet returned."

**AI review of this call (not human)**
- Issue: fully supported, and correct.
- Action: partly supported. Locating the transaction is in an uncited turn. Correct against the call.
- Outcome: partly supported, and only partly correct. The summary drops the agent's hedge, "should hopefully appear".
- Overall sentiment: the AI reader would say "mixed", not "positive". Beginning and ending agree.

**Teaching point:** the outcome claim sounds more certain than the agent did. The citation lets a reviewer hear that within seconds.

---

## 8. Results by type of evidence

**Terms**
- **WER (word error rate):** (substitutions + deletions + insertions) divided by the number of reference words. Lower is better, and it can exceed 100%. It is computed after normalising case, punctuation, and numbers, following the dataset's scoring steps. It is not overall system accuracy.
- **DER (diarization error rate):** the share of speech time attributed wrongly: speech missed, speech falsely added, or assigned to the wrong speaker ("confusion").

| Type | Metric | Result | Sample | Compared against |
|---|---|---|---|---|
| Measured | Pooled WER | **9.32%** | 19,248 reference words, 28 channels, 14 calls | Dataset's manual transcript |
| Measured | WER per call, median (range) | 6.81% (3.28% to 22.77%) | 14 calls | Same |
| Measured | Agent / customer WER | 5.79% / 15.04% | 28 channels | Same |
| Measured | DER, split channels, median | 10.23% | 14 calls, 0.25 s tolerance | Dataset's manual segments |
| Measured | Speaker confusion, split channels, median / max | 0.14% / 1.1% | 14 calls | Same |
| Measured | Mono baseline: median DER; median / max confusion | 6.97%; 1.1% / 35.23% | 14 calls; clusters mapped to speakers using the reference | Same |
| Measured | Labels unchanged, ASR vs reference text | 20 of 25 | 5 calls, 5 labels each, same settings | Same analysis on manual transcript |
| Automatic check | Calls passing all citation checks | 11 of 14 | 275 citations | Validation rules |
| Automatic check | Agent-phrase check agrees with role metadata | 14 of 14 | Weak evidence: 1 vs 0 cues on two calls | Phrase rule |
| AI review | Claims fully supported by cited turns | 20 of 42 | 22 partly, 0 unsupported | **AI, not human** |
| AI review | Claims correct against the whole call | 34 of 42 | 7 partly, 1 wrong | **AI, not human** |
| AI review | Sentiment agreement: overall / beginning / ending | 8 / 13 / 12 of 14 | Reader saw model labels first | **AI, not human** |
| AI review | Resolution label agreement | 12 of 14 | Reader saw model labels first | **AI, not human** |
| Human | Agreement with human labels | **Not available** | 0 labels completed | Worksheet pending |

**Reading notes**
- **Published comparison:** the dataset paper reports 9.2% for Parakeet v3 as an average over accents, on all 873 calls. Our 9.32% is pooled by words. Our average over the 14 calls is 8.56%. The published figure is context, not a directly comparable benchmark or a replication.
- **DER:** the mono baseline wins on overall DER, but split channels win clearly on attributing speech to the right person. Split-channel error is mostly false alarm (speech added). Word end times are estimated and can run long, which is a likely contributor.
- **Confusion:** with split channels, confusion measures timing overlap, not a speaker-identification decision.
- **5 label differences are 3 underlying differences:** two are sentiment-change labels that follow from another differing label.
- **AI review independence:** the reviewer is the assistant that built the pipeline. It is a different model from the one that wrote the summaries, but it is not independent, and it saw outputs first.

**Runtime (one timed run, machine in normal use, some LLM answers cached)**
- Transcription: median 7.5 s per audio minute, on CPU.
- Analysis: median 45.5 s per call, maximum 70.4 s, on GPU.
- Logged total for 14 calls: about 29 minutes.

---

## 9. Challenges and limitations

**A. Transcription configuration: int8 weights**

*Verified*
- First full run with int8 weights: 14.39% pooled WER, with one call at 38.98%.
- Final run with full precision, otherwise the same setup: 9.32%, maximum 22.77%. 10 calls improved, 3 got slightly worse (at most 0.96 points), and 1 was unchanged.
- The pilot call did not reveal this: int8 scored 6.02%, full precision 4.83%, Whisper 7.71%.
- More sensitive VAD and louder audio gave no consistent fix: most test channels stayed about the same or got worse. The largest improvement was one channel, from 43.36% to 37.34%.
- On one channel: int8 Parakeet 45.78%, Whisper large-v3 6.83%, full-precision Parakeet 5.38%.

*Limit of this finding:* it is an observation about these configurations of a third-party ONNX export on this sample, not proof that quantization generally reduces accuracy. The mechanism was not tested.

**B. Remaining transcription errors**

*Verified:* customer WER is well above agent WER, and call 010's customer channel is the worst, at 35.65%. Whisper is about the same there, at 36.59%.

*Hypothesis:* dialect, audio, or speaking style on that channel. Not tested.

**C. A valid citation can support a wrong conclusion: call 005**

*Verified:* the customer gives card digits at 00:01 and a sort code at 00:26, while the agent greets at 00:14 and repeats that sort code at 05:40. The manual reference shows the same order, with 54.2% overlap. Every citation check passes on this call.

*Hypothesis, strongly suggested but not confirmed:* the two channel files are out of sync, and "No thank you" answers a different question. No person has listened to confirm it.

*AI review:* the outcome claim is wrong, because the reference has the customer supplying bank details.

*Note:* the model did mark this outcome `unclear`.

**D. The overlap flag is unvalidated**

*Verified:* this heuristic flags 3 calls: call 005 at 61%, call 004 at 45%, and call 010 at 31%.
- Reference overlap on 004 and 010 is only 22.9% and 14.6%. So these two flags may be false alarms, partly because estimated word times run long.
- The 30% threshold was chosen after seeing call 005.

**E. Citation weaknesses**

*Verified*
- Calls 006, 009, and 014 still fail after retries, and remain marked as failed.
- Call 006 gives three handling answers with no citation.
- Calls 009 and 014 contain quotes not found in the cited turn.

*AI review:* 22 of 42 claims are only partly supported, most often because a detail comes from an uncited turn. Action claims are weakest: 3 of 14 fully supported.

**F. Sentiment errors**

*Verified:* overall is positive in 10 of 14 calls.

*AI review:* overall agreement is lowest, 8 of 14. Calls 002, 005, and 006 use polite closings as evidence.

*Verified:* the courtesy filter misses some turns. "Thank you, bye for now." passed the filter, because "now" is not in its word list.

*Verified:* on call 012, which has the lowest WER (3.28%), the beginning label is positive on ASR text and neutral on the reference. Segmentation also differs between the two, so the cause is not isolated.

**G. Resolution over-claiming, and tuning on the sample**

*Verified:* on the earlier int8 transcripts, prompt v1 marked `confirmed` on 9 of 14 calls, and prompt v2 on 5 of 14. The final run gives 6 of 14.

*Limitation:* the prompt, weights, and flag were all chosen after seeing sample results, so final figures are not a clean test. Only the pilot call was held out for the prompt, and one call is a very small check.

**H. ASR errors reach summaries**

*Verified:* in call 003, ASR heard "prescription review" where the reference says "refill", and the summary repeats it. The quote check passes, because it compares against ASR text, not against what was said.

**I. The limits of the sample**

14 role-played calls, one per accent, with no claims about any accent, domain, real customer, or business impact. Split-channel results do not transfer to mono recordings.

---

## 10. Deliverables and reproducibility

| Item | Location | Notes |
|---|---|---|
| Research workbook | `reports/research_survey.xlsx` | 4 sheets: datasets, papers, selection, sources |
| Notebooks | `notebooks/01` to `04` | Research, transcription, analysis, evaluation. All executed, 0 errors |
| Modules | `src/calltrace/` | data, asr, turns, llm, analysis, validation, evaluation, pipeline, export |
| Tests | `tests/test_core.py` | 36 tests pass: timestamps, evidence, schemas, windows, metrics, empty input, failures, resume |
| App | `app/streamlit_app.py` | Reads saved results; needs no LLM |
| Results | `results/` | `calls.csv`, `calls.jsonl`, `turns.csv` (839 turns), `summaries.csv`, `sentiment.csv`, `call_handling.csv`, per-call JSON |
| Evaluation | `results/evaluation/` | Metrics, AI audit, experiments, error analysis, earlier runs |
| Human worksheet | `reports/human_review_worksheet.xlsx` | Blank, and hides model labels. One marked example row |
| Diagrams | `reports/figures/` | Architecture, sequence, WER chart, app screenshots |
| Setup and commands | `README.md`, `requirements.txt` | Python 3.11, Windows tested |

**Run failures:** 0 of 14 calls failed in processing. `results/failures.jsonl` does not exist.

**Reproducibility checks observed in the build session**
- A clean copy with a new environment installed from `requirements.txt`, passed 36 tests, and redrew an identical sample manifest.
- A smoke run took 1 minute 41 seconds, and its transcript and analysis matched the main run byte for byte.
- Scope: one call only, on the same machine, and it reused downloaded model weights. No full 14-call clean run was done. See section 11.

**Not yet done:** recording, pushing the documentation corrections, and submission. The recording link goes in the submission email.

---

## 11. Unverified items

| Item | Status | What is missing |
|---|---|---|
| Audible playback in the app | **Unverified** | The browser test confirmed highlight and player position, in a headless browser. Nobody has confirmed hearing the sound. Check this before recording |
| Number of LLM layers on the GPU | **Unverified** | The server was started with `--n-gpu-layers 99`, and 3,037 of 4,096 MiB GPU memory was seen in use in one reading. The load log was overwritten, so full offload cannot be shown |
| Parakeet and Silero revisions | **Not pinned in code** | The local cache holds `8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce` and `b3e3ee3cce4c11ceb63b1a0b229d916069c1ddf6`, but the code downloads each default branch. A later change upstream could alter results |
| Exact Silero VAD release | **Unverified** | Cached as `istupakov/silero-vad-onnx` revision `b3e3ee3c...`. It is not confirmed to be the `silero-vad==5.1.2` named on the dataset card |
| Exact match to the dataset's scorer | **Unverified** | The scoring steps were re-implemented with `whisper_normalizer`, and the official script was not run for comparison |
| Whether published figures used the same weights | **Unverified** | The paper names the model, not this ONNX export |
| Clean-copy check log | **No saved file** | Observed in the build session and not written to disk. It can be re-run with the README commands |
| Vendor dataset sizes | **Unverified** | Advertised on vendor pages, and marked as such in the workbook |
| Other platforms | **Unverified** | Only Windows 11 was tested |
| Human agreement figures | **Not available** | No labels exist |

**Known corrections to older project files.** The README, `error_analysis.md`, requirements checklist, demo walkthrough, and `reports/speaker_notes.md` have been corrected. These older items were left unchanged and are superseded by this brief:
- `reports/calltrace_presentation.pptx`, the final 9-slide deck, says "close to the published figure" on slide 7, and its embedded notes on slides 2, 7, and 8 use older wording.
- `reports/figures/wer_by_call.png` says quantized weights "caused" the worst errors.
- `notebooks/04_evaluation.ipynb` shows the older `error_analysis.md` in its saved output.

---

## 12. Authorship disclosure

Suggested slide text: **"Built with AI assistance: Claude Code helped with implementation, experiments, evaluation, and documentation."**

Presenter guidance: I set the goal, requirements, and project direction. Claude Code wrote most of the code and documentation and ran the experiments under that direction. "We" in the notes below means me working with Claude Code. Do not claim personal listening, labelling, or review unless it actually happens before recording.

---

## 13. Proposed slides: 10 slides, 10:00 total

This was the proposal given to Cowork. The final deck has 9 slides, with proposed slides 6 and 7 combined into one demo slide. `reports/speaker_notes.md` follows the final deck.

### Slide 1: CallTrace: checking what an AI says about a call (0:40)

**Takeaway:** CallTrace transcribes, summarizes, and analyses sentiment, and lets a reviewer check the claims against the call.

**Content**
- Three AI tasks: speech-to-text, summarization, customer sentiment
- Each claim links to a speaker turn and an audio time
- 14 role-played calls, run locally with pretrained models
- Describes single calls; does not score employees

**Visual:** simple flow: Claim → Speaker turn → Audio time, using call 001 from section 7.

**Speaker notes:** "This is CallTrace, my project for the Maharah GDP assessment. It does three AI tasks on customer-service calls: it turns speech into text, summarizes each call, and analyses the customer's sentiment. The problem I wanted to focus on is trust. An AI summary can sound confident and still be wrong. So each claim points to the exact turn and audio time behind it. One disclosure up front: I built this with Claude Code, which helped with implementation, experiments, and documentation. When I say 'we', that's what I mean."

### Slide 2: What the assessment asked for (0:40)

**Takeaway:** every required item has a matching output, except the recording, which is this presentation.

**Content**
- Dataset research and an Excel survey
- Transcripts with Speaker 1 and 2, labelled Customer and Agent
- A summary for every call: issue, action, outcome
- Customer sentiment with reasons, beginning and end
- Notebooks, README, reusable results, plus optional app and diagrams

**Visual:** compact requirement-to-output table from section 2.

**Speaker notes:** "Maharah asked for data research, transcripts with separated speakers, a summary and customer sentiment for each call, and a presentation, all reproducible from a GitHub repository. All 14 sampled calls completed processing, and three of them later failed the citation check, which is a separate status. We also added the optional review app, Python classes, and diagrams. The title says agent performance, but I want to be clear about scope: this describes individual calls. It doesn't score employees or rank agents."

### Slide 3: Choosing the data (1:05)

**Takeaway:** only two of ten sources passed the eligibility gates, and the chosen calls are role-played.

**Content**
- 10 sources and 7 papers compared in the workbook
- Gates: open audio, clear permission, at least 10 calls, responsible use
- Selected: AppTek, 873 calls, CC BY-SA 4.0, separate speaker channels, manual transcripts
- **Role-played, not real customer calls**
- Sample: 14 calls, one per accent, about 141 minutes, by a seeded metadata-only rule

**Visual:** eligibility table from section 3, with a prominent "role-played" callout.

**Speaker notes:** "We compared ten sources. Audio access and permission to use it were gates, because you can't test transcription without audio. Most options failed there. One large real dataset has no audio, for privacy reasons. Vendor samples offered only a few open calls, and one source had no license at all. Two passed. SpokenWOZ is larger, but its customer text deliberately keeps recognition errors, so we couldn't measure customer accuracy. AppTek has a separate audio file for each speaker, manual transcripts for both, and a license that lets us share derived results. The most important limit is that these calls are role-played. Speakers improvised with fictional details, so nothing here tells us about real customers. We drew 14 calls, one per accent, about 141 minutes, using a fixed seed and metadata only, so easy calls couldn't be picked."

### Slide 4: From audio to reviewable results (1:15)

**Takeaway:** each step has a known source: the dataset, a model, or a rule.

**Content**
- Dataset supplies: audio, one speaker per file, Customer and Agent roles
- Models predict: speech chunks, words and times, summaries, sentiment labels
- Rules compute: turns, sentiment windows, sentiment change
- Automatic checks: cited turns exist, quotes match
- Manual reference transcripts are used only for evaluation

**Visual:** native workflow graphic from section 4, color-coded by source. Alternative: `reports/figures/architecture.png`.

**Speaker notes:** "This is the workflow, and the colors show where each piece of information comes from. The dataset gives us separate audio for each speaker and says who is the customer and who is the agent. So speaker separation here isn't predicted, which makes this easier than a normal phone recording. Then models take over. One detects speech, and another turns it into words with timestamps. Simple rules merge those words into turns, each with a stable ID. A language model then writes the summary and the sentiment labels. It can only cite turns that exist in that call. Sentiment is judged from text only, so it says nothing about tone of voice. The beginning and ending are judged separately, and a rule computes the change. Finally, code checks that each quote really appears in the cited turn. The dataset's manual transcripts are never given to the analysis. We only use them for scoring."

### Slide 5: Models used (0:45)

**Takeaway:** we used small pretrained models on a laptop, and trained nothing.

**Content**
- Speech-to-text: Parakeet TDT 0.6B v3, full precision, on CPU
- Speech detection: Silero VAD, on CPU
- Summary and sentiment: Qwen3.5-4B, Q4_K_M, through llama.cpp, on a 4 GB GPU
- No training, no fine-tuning, no paid API
- About 7.5 s of transcription per audio minute; about 46 s of analysis per call

**Visual:** three-row model table from section 5.

**Speaker notes:** "All the models are pretrained. We didn't train or fine-tune anything. For speech-to-text we used NVIDIA's Parakeet, because the dataset's own paper reported it well ahead of Whisper Large v3 on this data, and it also scored lowest in our one pilot comparison. It runs on the laptop's CPU. For summaries and sentiment we used Qwen 3.5, a small 4B model in a compressed format, Q4 K M, running on a 4 gigabyte GPU. I should say we chose that for fit and license. We didn't compare other language models. Everything runs locally, without an API key."

### Slide 6: One real call, end to end (1:00)

**Takeaway:** in call 001, the evidence shows that the summary is slightly more certain than the agent was.

**Content**
- Issue: money sent to the wrong person (T0002, 00:18)
- Outcome: refund "would appear as pending" (T0043, 07:15)
- But the agent said "should hopefully appear"
- Sentiment: negative at the start, positive at the end, "improved"
- Resolution: unresolved, since the refund is still pending

**Visual:** generated claim next to the T0043 transcript excerpt, from section 7. Label it "call 001, role-played; an easier call than most".

**Speaker notes:** "Here's a real example, call 001. It's an easier call than most, with only about 4 percent word errors. The customer accidentally sent money to the wrong person, and the summary cites that at 18 seconds. Sentiment starts negative: 'I'm really worried'. It ends positive: 'You've been such a big help.' Now look at the outcome. The summary says the refund would appear as pending. But in the cited turn, the agent says it 'should hopefully appear', and earlier said it couldn't be guaranteed. So the claim is a little too certain. The AI review marks it as only partly correct. That's exactly why the link matters: you can check this in seconds."

### Slide 7: Demo: from a claim to the audio (1:30)

**Takeaway:** a citation button takes a reviewer straight to the turn and audio time.

**Content**
- Select a call
- Click a citation button
- Turn highlights; audio starts from that time
- Inspect sentiment windows and limitations

**Visual:** `reports/figures/app_evidence_outcome.png`, the real capture with T0043 selected. Use it as a fallback if the live demo fails. Steps are in `reports/demo_walkthrough.md`.

**Speaker notes (demo):** "Here's the review app. I'll select call 001. You can see the notice that this is role-played, and how speakers were labelled. I'll click this citation for the customer's issue. The turn highlights, and the audio starts from that point. [Play briefly.] Now the outcome: I'll click T0043, at seven minutes fifteen. [Listen for 'should hopefully appear'.] In the sentiment section, you can see the beginning and ending labels, and these are the turns each one used. And here's the resolution, marked unresolved. Finally, I'll switch to call 005. This warning says the channels may be out of sync. I'll come back to that shortly."

### Slide 8: What we measured, and who judged it (1:15)

**Takeaway:** transcription is measured against manual references, while citations are checked by rules and claims only by AI, so human checking is still needed.

**Content**
- Word error rate (WER): 9.32%, on 19,248 words. Agent 5.79%, customer 15.04%
- Automatic check: 11 of 14 calls pass citation checks
- AI review: 34 of 42 claims correct; only 20 of 42 fully covered by citations
- AI review: sentiment agreement overall 8, beginning 13, ending 12, of 14
- **Human labels: none yet**

**Visual:** results table from section 8, grouped by Measured, Automatic check, AI review, and Human, with AI rows clearly marked.

**Speaker notes:** "Let me separate who judged what. Word error rate is substitutions plus deletions plus insertions, divided by the number of words in the dataset's manual transcripts. Ours is 9.3 percent over about 19,000 words. The paper reports 9.2 percent for this model, but that's context, not a directly comparable benchmark. Customers have much higher error than agents. All 14 calls completed processing. Automatic checks show 11 of the 14 pass, but that only proves the citations are real. Whether claims are right is a harder question. An AI review found 34 of 42 claims correct, but only 20 fully covered by their own citations. Please note: that review was by Claude, not a person, and it saw the outputs first. No human review has happened yet. A worksheet with the model's labels hidden is ready for that."

### Slide 9: What went wrong, and what we learned (1:10)

**Takeaway:** the most useful findings came from failures, and some causes remain unconfirmed.

**Content**
- Tested configurations: int8 weights 14.39% WER; full precision 9.32%. A pilot check missed the gap
- Call 005: citations pass, but AI review judged the conclusion wrong; channels suspected out of sync (not confirmed)
- Overlap flag fires on 3 calls, with possible false alarms on 2
- Overall sentiment leans positive, often on polite closings
- Settings were tuned on this sample, so results aren't a clean test

**Visual:** `reports/figures/wer_by_call.png`, with `reports/figures/app_flagged_call.png` beside it.

**Speaker notes:** "First, a configuration mistake. We started with compressed int8 weights for speed. A pilot call looked fine, but the full sample was at 14 percent, with one call at 39. The published figure, as context, prompted a closer look. A more sensitive VAD and louder audio gave no consistent fix. The full-precision run gave 9.3 percent. That's an observation about these configurations, not proof that quantization generally reduces accuracy, and we don't know the mechanism. Second, call 005. Every citation check passes, yet the customer gives card details before the agent says hello. The manual transcript shows the same order. We suspect the channels are out of sync, but no one has listened to confirm it. So traceability helped us find the problem, but didn't prevent it. We added a heuristic flag, which fires on three calls, and two of those may be false alarms. Also, overall sentiment leans positive, often because of polite closings. And we tuned settings on this same sample, so these results aren't a clean test."

### Slide 10: Reproducibility and next steps (0:40)

**Takeaway:** the work can be re-run from documented commands, and human review comes next.

**Content**
- 4 executed notebooks, 36 passing tests, reusable CSV and JSON results
- Fixed seed; pinned dataset and LLM versions; one-call clean-copy smoke run matched
- Next: human labels, real consented calls, mono audio
- Built with AI assistance: Claude Code helped with implementation, experiments, evaluation, and documentation

**Visual:** simple two-column layout: "Available now" and "Next". No code-heavy content.

**Speaker notes:** "To close, the README has the setup and commands, and there are four executed notebooks and 36 passing tests. In a clean copy on the same machine, a one-call smoke test matched the main run exactly. I haven't run all 14 calls from a clean copy, and only Windows was tested. The next step is human review, because that's the biggest gap. After that, I'd test on real, consented calls and on mono recordings. The main thing I learned is to make AI output easy to check, and to report what fails. Thank you."

**Timing check:** 0:40 + 0:40 + 1:05 + 1:15 + 0:45 + 1:00 + 1:30 + 1:15 + 1:10 + 0:40 = 10:00.

---

## 14. Instructions to Cowork

Create a professional PowerPoint from this verified brief for a 10-minute presentation. Use clear workflow visuals, actual project examples, readable results, and restrained text. Preserve all limitations and distinctions between measured results and AI review. Do not invent facts, metrics, screenshots, or Maharah branding. Put detailed explanations in speaker notes.
