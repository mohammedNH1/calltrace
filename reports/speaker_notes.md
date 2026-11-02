# CallTrace timed speaker notes

Total planned time: 10:00, including the live demo. These times are a plan, not a measured rehearsal.

These notes follow the 9 slides of the final deck. The numbers come from `results/evaluation/metrics.json`. "We" means the presenter working with Claude Code. Only say you listened to, labelled, or reviewed something if you actually did.

The notes embedded in the deck differ on slides 1, 2, 7, 8, and 9. This file has the corrected wording.

## Slide 1: CallTrace: checking what an AI says about a call

**Time:** 0:00 to 0:40 (40 s)

Hello. This is CallTrace, my project for the Maharah GDP assessment. It runs three AI tasks on customer-service calls: it turns speech into text, summarizes each call, and labels the customer's sentiment. The problem I focused on is trust. An AI summary can sound confident and still be wrong. So in CallTrace, claims cite the evidence behind them. On the right is a real example: a claim from a summary, the speaker turn it cites, and the exact time in the audio. I built this with help from Claude Code, so when I say 'we', that's what I mean.

## Slide 2: What the assessment asked for

**Time:** 0:40 to 1:20 (40 s)

Maharah asked for dataset research, transcripts with the two speakers separated, a summary and customer sentiment for each call, and clean, reproducible code. Each of these has a matching output in the repository. We also did the optional extras: Python classes, a review app, and diagrams. All 14 sampled calls completed processing. Three of them later failed the citation check, which is a separate status, and they stay marked as failed. One point on scope: the assessment title mentions agent performance, but this project describes individual calls. It doesn't score employees or rank agents.

## Slide 3: Choosing the data

**Time:** 1:20 to 2:25 (65 s)

We compared ten sources. Open audio and clear permission to use it were hard requirements, because you can't test transcription without audio. Most sources failed there. One large dataset of real calls released no audio, for privacy reasons. Vendor samples had only a handful of open calls, and one source had no license at all. Two sources passed, and we chose AppTek's call-center dataset. It has 873 calls, a separate audio file for each speaker, manual transcripts for both speakers, and an open license that lets us share our results. The most important limit is that these calls are role-played. Speakers improvised with fictional details, so nothing here tells us about real customers. We drew 14 calls, one per accent, about 141 minutes in total. The draw used a fixed random seed and metadata only, so we couldn't pick easy calls.

## Slide 4: From audio to reviewable results

**Time:** 2:25 to 3:40 (75 s)

Here's how a call flows through the system. The colours show where each piece of information comes from. The dataset gives us the audio already split into one file per speaker, and tells us who is the customer and who is the agent. So speaker separation isn't predicted here, which makes this easier than a normal phone recording. A speech model turns each channel into words with timestamps. Simple rules merge those words into turns, and each turn gets a stable ID. Then a language model writes the summary and the sentiment labels, and it can only cite turns that exist in that call. The beginning and the end of the call are judged separately, and a fixed rule decides whether sentiment improved. Two things to note at the bottom: the dataset's manual transcripts are never given to the analysis, we only use them for scoring. And sentiment is judged from text only, so it says nothing about tone of voice.

## Slide 5: Models used

**Time:** 3:40 to 4:25 (45 s)

All the models are pretrained. We didn't train or fine-tune anything. For speech-to-text we used NVIDIA's Parakeet. The dataset's own paper reported it well ahead of Whisper Large v3, and it was also best in our pilot test. Silero detects where speech is. For summaries and sentiment we used Qwen 3.5, a small four-billion-parameter model, compressed to fit a four-gigabyte laptop GPU. We chose it because it fits and runs locally without an API key. We didn't compare other language models. On this laptop, transcription takes about seven and a half seconds per minute of audio, and analysis about 45 seconds per call.

## Slide 6: Demo

**Time:** 4:25 to 6:55 (150 s)

Exact clicks are in `reports/demo_walkthrough.md`. Before recording, check that the audio is audible in the app, because this has not been verified.

[Switch to the app.] Now let me show the review app, using call 001. It's a role-played banking call, and an easier one than most, with only about 4 percent word errors. At the top you can see the notice that the call is role-played. Here's the summary. The issue: the customer sent money to the wrong person by mistake. [Click the issue's citation button.] When I click a citation button, the turn it cites is highlighted in the transcript, and the audio starts from that moment. [Let it play for a few seconds.] Now the outcome. The summary says the refund would appear as pending within 24 to 48 hours. It cites turn T0043, at seven minutes fifteen. [Click T0043 and let it play until 'should hopefully appear'.] The agent actually said the money 'should hopefully appear', and earlier said they couldn't guarantee it. So the summary is a little more certain than the agent was, and our AI review marked this claim as only partly correct. That's exactly why the link matters: a reviewer can check it in seconds. Note that it's the citation buttons you click; the transcript turns themselves aren't clickable. [Scroll to the sentiment section.] Here the customer starts negative, 'I'm really worried', and ends positive, 'You've been such a big help', so the change is marked improved. You can see exactly which customer turns each label was based on. And the resolution is marked unresolved, because the refund is still pending. Last, I'll switch to call 005. [Select call 005 and point to the warning.] This warning says the two audio channels may be out of sync. That's suspected, not confirmed, and I'll come back to it shortly. [Switch back to the slides.]

## Slide 7: What we measured, and who judged it

**Time:** 6:55 to 8:10 (75 s)

Now the results, and who judged what. First, a measured result. WER, or word error rate, is substitutions plus deletions plus insertions, divided by the number of words in the dataset's manual transcripts. Ours is 9.3 percent over about 19,000 words. The dataset paper reports 9.2 percent for this model, but that's context, not a directly comparable benchmark. Customers have much higher error than agents: about 15 percent, against under 6. Second, an automatic check. All 14 calls completed processing, and 11 of them pass the citation check. That only shows the citations are real. Third, an AI review. It judged 34 of 42 claims correct, but only 20 were fully covered by their own citations. That review was done by Claude, not by a person, and it saw the model's outputs first. No person has reviewed these results yet, which is why human review is the first next step.

## Slide 8: What went wrong, and what we learned

**Time:** 8:10 to 9:20 (70 s)

Some of the most useful findings came from failures. First, transcription. We started with compressed int8 weights for the speech model, to make it faster. One pilot call looked fine, but on the full sample the WER was over 14 percent, with one call near 39. A more sensitive voice detector and louder audio gave no consistent fix. The full-precision run gave 9.3 percent. Most calls improved, though a few got very slightly worse. That's what we observed for these configurations, not proof that quantization generally reduces accuracy, and we don't know the mechanism. Second, call 005. Every citation check passes, yet the customer gives card details before the agent even says hello. We suspect the two channels are out of sync, but nobody has listened to confirm it. So citations helped us find the problem, but didn't prevent it. We added a heuristic warning flag; it fires on three calls, and two of those may be false alarms. Third, overall sentiment leans positive, often because customers end the call politely. And because we tuned settings on this same sample, these results aren't a clean test.

## Slide 9: Reproducibility and next steps

**Time:** 9:20 to 10:00 (40 s)

To close. The repository has setup steps in the README, four executed notebooks, 36 passing tests, and results in CSV and JSON. In a clean copy on the same machine, a one-call test matched the main run exactly. All 14 calls haven't been rerun from scratch, and only Windows was tested. The most important next step is human review. After that, I'd test on real, consented calls. The main thing I learned is to make AI output easy to check, and to be open about what fails. Thank you.
