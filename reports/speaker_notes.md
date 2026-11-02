# CallTrace timed speaker notes

Total planned time: 10:00, including the live demo. Read at a normal pace, aim to finish each slide by its end time.

The numbers come from `results/evaluation/metrics.json`.

## Slide 1: CallTrace

**Time:** 0:00 to 0:20 (20 s)

Hello. This is CallTrace, my submission for the Maharah GDP assessment on call center agent performance analysis. It transcribes customer service calls, summarises them, and analyses customer sentiment. What I focused on is traceability: a reviewer can follow any claim back to the exact speaker turn and audio time.

## Slide 2: A summary is only useful if a reviewer can check it

**Time:** 0:20 to 1:05 (45 s)

The assessment asks for transcripts, summaries, and sentiment for each call, and those are all here. But a model's summary can sound confident and still be wrong. So every claim carries a turn ID and a short quote, and each turn has its audio time. In this real example from call 001, the claim points to turn T0002 at 18 seconds, and you can listen to it. I also measure sentiment change and run a small evaluation. Traceability makes checking possible. It does not make a claim correct, and I'll show a case of that.

## Slide 3: Ten sources reviewed; only two passed the eligibility gates

**Time:** 1:05 to 2:05 (60 s)

I reviewed ten data sources and seven papers, and checked each on its original page. I applied eligibility gates first, because a transcription task needs accessible audio and a clear right to use it. Most options failed here. CallCenterEN is large and real but has no audio, because of biometric privacy. Vendor sets offer only two to five open calls, and one preview shows named companies and user locations. Others are gated, have no license, or are not customer service. Two passed. SpokenWOZ is larger, but it keeps ASR noise in the customer text on purpose, so customer word error rate cannot be measured. AppTek has split channels, manual references for both speakers, and a CC BY-SA license. It scored 4.9 out of 5 against 3.2. Those scores are my judgment, and the workbook shows the reasons.

## Slide 4: The sample: 14 calls by a fixed rule, and what they cannot show

**Time:** 2:05 to 2:50 (45 s)

The sample is 14 complete calls, one per accent, about 141 minutes. A fixed seed picks them using metadata only, so I could not choose easy calls, and all 14 stayed in, including the bad one. The most important limit: this data is role-played. Speakers chose a scenario and spoke freely with fictional details. So nothing here supports claims about real customers or business impact. Two checks changed the design. In 66 of 873 calls, channel 1 is the customer, so channel order can't mean role. And one call's channels seem out of sync, which I come back to.

## Slide 5: One readable pipeline, with no paid services

**Time:** 2:50 to 3:35 (45 s)

Read this left to right. Data comes from a pinned dataset commit. Each speaker's channel goes through voice activity detection and Parakeet. The words become turns with stable IDs. A local Qwen model on my 4 gigabyte GPU writes the analysis as JSON constrained by a schema, so citations can only name turns that exist. A validator then checks quotes and roles, with at most two retries. It needs no API key. A failed call doesn't stop a run, and a re-run resumes where it stopped. The code is plain Python classes and four ordered notebooks.

## Slide 6: Speaker, role, and turn boundaries each have a stated source

**Time:** 3:35 to 4:20 (45 s)

I keep three things apart. Speakers come from the dataset's split channels: each file holds one person. Customer and agent roles come from channel metadata, cross-checked with agent phrases, and all 14 calls agree. Turn boundaries are predicted from word timestamps. I also ran a mono diarization baseline on merged audio. It has lower overall error, 7 percent against 10, partly because my spans run long. But its speaker confusion reached 35 percent on one call, against at most 1.1 percent for channels. That result doesn't transfer to mono recordings.

## Slide 7: A benchmark caught a mistake that a pilot check had missed

**Time:** 4:20 to 5:10 (50 s)

I first ran Parakeet with int8 weights for speed. The pilot looked fine at 6 percent, but the full sample gave 14.4, with one call at 39, against a published average of 9.2. So I tested explanations. A more sensitive voice detector and louder audio did not help. Whisper got 6.8 percent on a channel where I had 46, so the voice was not the problem. Full-precision weights got 5.4 on that channel. After switching, pooled WER is 9.32 percent. That's close to the published figure, though my sample is small. Customer WER is still higher than agent WER, 15.04 against 5.79 percent. And I keep the number honest: WER is word errors under one normalisation, not system accuracy.

## Slide 8: Live demo: follow a claim to the turn and the audio

**Time:** 5:10 to 7:30 (140 s)

Switch to the app now. See reports/demo_walkthrough.md for the exact clicks. (1) Select call 001. Point out the role-played notice and how the speakers were labelled. (2) Read the customer issue and click the T0002 button: the turn highlights and the audio plays from 00:18. Let it play for a few seconds. (3) Read the outcome and click T0043 at 07:15. Listen for 'should hopefully appear'. Say that the claim dropped that hedge, which the audit marks as only partly correct. (4) Show sentiment: beginning negative, ending positive, change improved. Open the ending window and show the window turns. Say this is text only, not vocal emotion. (5) Open Observed call handling. Resolution is unresolved, because the refund is pending. Say this describes one call and is not a performance score. (6) Select call 005 to show the warning at the top, and say it leads to the next slides. If the live app fails, narrate from this screenshot.

## Slide 9: Citations exist, but only 20 of 42 claims are fully covered

**Time:** 7:30 to 8:30 (60 s)

Here are the results with denominators. Transcription and speaker metrics compare with manual references. The citation checker passes 11 of 14 calls. But schema validity isn't correctness, so I audited all 42 summary claims. Only 20 are fully supported by their cited turns, and the other 22 are partly supported, usually with a detail from an uncited turn. Against the whole call, 34 are correct, 7 partly, and 1 is wrong. Be clear about the last column: that audit was by an AI assistant and not a person, and it saw the model output first. Sentiment agreement is weakest on the overall label, 8 of 14. There are no human labels yet. A blind worksheet is ready for that. In the experiment, 20 of 25 labels were the same on ASR and reference text.

## Slide 10: A valid citation can still support a wrong conclusion

**Time:** 8:30 to 9:25 (55 s)

This is call 005. The summary says the customer declined to give bank details, and it cites real turns with matching quotes, so the citation check passes. But the customer gives card digits before the agent says hello, and the manual reference shows the same order. The channel files seem to be out of sync, and 'No thank you' seems to answer something else. Traceability let me find this. It did not prevent it. So I added an overlap flag, though I chose its threshold after seeing this call, so it isn't validated. Also, overall sentiment leans on politeness: 10 of 14 calls come out positive. And in call 012, a small text change flipped a label.

## Slide 11: Reproducible today; human review next

**Time:** 9:25 to 10:00 (35 s)

To close: this reproduces from documented commands, with pinned models, a pinned data commit, and a fixed seed. The README lists the commands and limitations. Next: human labels from the blind worksheet, since that's what's missing most. Then real, consented calls, and mono audio. The main lesson is simple: let reviewers check the output, and report what fails. Thank you.
