# Error analysis

Representative successes, failures, and ambiguous cases from the final run (Parakeet full precision, prompt v2).
Judgments here come from the AI-assisted audit and **are not human annotations**. Figures compared with the dataset's references are measured. Causes are unverified explanations unless stated otherwise. Short excerpts are from the
role-played dataset. "Reference" is the dataset's manual transcript.

## Successes

**Call 001, banking: evidence that holds up.** The summary says the customer sent money to the wrong person.
It cites `001-T0002` at 18.4 s: "I've realized I've sent it to the wrong place." The ASR text matches the reference
closely here, and WER on this call is 3.90%.

**Call 001, resolution after the prompt fix.** Prompt v1 said resolution was `confirmed`. Prompt v2 says `unresolved`.
That fits the evidence: the agent said the amount "should hopefully appear as a pending refund".

**Call 014, sentiment change.** The customer opens with "I'm upset and angry." (`014-T0004`), later turns are calm,
and the change is `improved`. The label comes from a fixed rule, not from the model's impression of the call.

## Failures

**Call 005, aviation: a real citation supports a wrong conclusion.**
The summary says the customer declined to give payment details, and it cites `005-T0026` and `005-T0027`.
Those turns exist and the quotes match, so every mechanical check passes.
But the customer gives card digits at 1.5 s and a sort code at 26.7 s, while the agent's greeting is at 14.7 s and the
agent only repeats that sort code at 340.9 s. The reference has the same order, with 54.2% overlap, so the pattern is not caused by ASR.
The AI audit judged the outcome claim wrong.
*Suspected cause, not confirmed:* the two channels are out of sync, and "No thank you" answers a different question. No person has listened to check this.
*What the project now does:* flags calls whose speakers overlap on over 30% of the quieter speaker's time.
This is a heuristic, and its threshold was chosen after seeing this call. It fires on 3 calls:

| Call | Overlap on ASR turns (flag) | Overlap in manual reference |
|---|---|---|
| 005 | 61% | 54.2% |
| 004 | 45% | 22.9% |
| 010 | 31% | 14.6% |

The flags on 004 and 010 may be false alarms, partly because estimated word end times can run long. The flag has not been validated.
*Lesson:* traceability lets a reviewer find this error, but it does not prevent it.

**Call 003, ASR error reaches the summary.** ASR heard "prescription review"; the reference says "prescription refill".
The summary repeats "review". *Measured:* the recognition error on a key word. The quote check passes, because it compares
with the ASR text and not with what was really said.

**Calls 006, 009, and 014, failed citation checks.** All three completed processing; citation validation is a separate status. Call 006 answers three handling questions with no citation.
Call 014 cites "two four two seven one zero." in `014-T0048`, which does not contain it (the digits are in another turn).
Call 009 quotes a sentence that is not in the turn it cites. The validator catches all three, the retries do not fix
them, and the outputs stay marked as failed instead of being dropped.

**Customer sentiment leans on politeness.** The overall label is `positive` for 10 of 14 calls. The AI second reader
agrees with the overall label on only 8 of 14 calls, against 13 of 14 for the beginning label and 12 of 14 for the ending label.
In call 002 the evidence includes "Thank you very much."; in call 006, "Thank you, bye for now." The courtesy filter also missed
that second turn, because "now" is not in its word list.
*Possible cause, unverified:* the rule against treating thanks as sentiment is only an instruction for the overall label, and the code filter is imperfect.
*Status:* not fixed. Treat overall sentiment as weak until human labels exist.

**Call 012, sentiment label flips on nearly identical text.** The beginning label is `positive` on ASR text and `neutral`
on the reference, though this call has the lowest WER (3.28%). The justification treats "It's actually a special occasion
for us." as enthusiasm. *Possible cause, unverified:* model instability on a borderline turn. The reference's segmentation also differs, so the cause is not isolated.

## Ambiguous cases

**Call 010, telecom: the hardest audio.** Customer-channel WER is 35.65%, against 4.26% for the agent, on the same call.
Parakeet and Whisper both struggle (35.65% and 36.59%), which suggests the model is not the main cause, though this was not tested further. The summary still gets the
main points right, but evidence is weak: the ASR has "And then the other day, uh fix everything" where the reference has
"installers just now just came, and then they already (uh) fix everything".

**Call 011, finance: the recording ends mid-question.** The outcome is marked `unclear`, which is right, but no one can tell
from the data whether the role-play was stopped early or the file was cut.

**Call 013, retail: the ending.** The last customer turns are repeated "Hello?" with no reply. The ending window correctly
ignores them as non-substantive, so the label reflects the turns before them. Whether the call dropped cannot be known from the transcript.

## Diagnosing the transcription errors

The first full run used int8 weights and gave 14.39% pooled WER, with one call at 38.98%. Deletions dominated.

1. **Hypothesis: the VAD or low level loses speech.** No consistent fix on 7 test channels. Some improved (call 009 customer, 43.36% to 37.34% with a more sensitive VAD; call 008 customer, 36.18% to 33.59% with both changes). Others got worse (call 003 customer, 28.48% to 39.24% with both changes) or barely moved (call 003 agent, 45.78% to 46.08% with a more sensitive VAD).
2. **Hypothesis: the voices are simply hard.** Not the whole explanation. On the 3 channels tested, Whisper large-v3 beat int8 Parakeet: 6.83% vs 45.78%, 17.54% vs 43.36%, and 36.59% vs 52.06%. The last channel stayed hard for both.
3. **Hypothesis: the int8 weights.** Supported for the tested configurations. Full-precision Parakeet scored lower on all 4 channels tested, with the same VAD and audio: 5.38% vs 45.78%, 18.30% vs 43.36%, 35.65% vs 52.06%, and 3.57% vs 3.87%.

The final run uses full precision: 9.32% pooled WER. Against the int8 run, 10 calls improved, 3 got slightly worse, and 1 was unchanged.
This is an observation about these configurations of one third-party ONNX export on this sample. It does not prove that quantization generally reduces accuracy, and the mechanism was not tested.
The 9.2% published for this model prompted the check, but it is context, not a directly comparable benchmark: it averages accents over all 873 calls, and the weights used are unverified.
The pilot call hid this problem, scoring 6.02% with int8. A small easy check can pass while a harder sample fails.

## Speaker separation: what the numbers do and do not show

Channel-based separation has median DER 10.23%; the mono baseline, 6.97%. So the baseline wins on overall DER.
Most of the channel-based error is false alarm. Word ends are estimated from the next token's start, so spans can run past
the actual speech. Using word spans instead of turn spans barely changes it (10.16%), so pauses inside turns are not the main cause.

Speaker confusion is what matters for attributing a claim to the right person, and there the channels win: at most 1.1%,
against up to 35.23% on call 004 for the baseline. The baseline also needed the reference to map its clusters to speakers,
which a real deployment could not do. Channels are not always available: this result does not apply to mono recordings.
