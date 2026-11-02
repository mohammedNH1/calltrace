# CallTrace demo walkthrough

**Planned time:** 2 minutes 20 seconds, within the 10-minute talk (slide 8).

## Before you record

Audio must be on disk, which `python -m calltrace run --full` downloads. No LLM server is needed for the app.

```powershell
.venv\Scripts\activate
streamlit run app/streamlit_app.py
```

1. Open http://localhost:8501 and zoom the browser to 90% if the page feels cramped.
2. Click once on the page and play a few seconds of audio, so the browser allows autoplay. Check that your recording tool captures system audio.
3. Reload the page, so that call 001 starts with nothing selected.

## Steps

| Time | Action | What to say |
|---|---|---|
| 0:00 | Call **001 · banking · en-AU** is selected. Point to the yellow notice and "How speakers were labelled". | "This is a role-played call. Speakers come from split channels, and roles from dataset metadata." |
| 0:20 | Read the customer issue. Click **T0002 · 00:18**. | "Here is the claim. I click its citation." The turn highlights, and audio plays from 00:18. Let it play about 5 seconds. |
| 0:45 | Scroll to the outcome. Read it. Click **T0043 · 07:15**. | Listen for "should hopefully appear". "The agent hedged, but the summary dropped that. This is why a reviewer needs the evidence." |
| 1:15 | Scroll to **Customer sentiment**. Show negative, then positive, then improved. Open **Ending window**. | "These are the last substantive customer turns. Courtesy-only turns are left out. It is text only, so it says nothing about voice." |
| 1:40 | Open **Resolution** under Observed call handling. | "Unresolved, because the refund is still pending. This describes one call. It is not a performance score, and I don't rank agents." |
| 2:00 | Select call **005 · aviation · en-GB_SCT** in the sidebar. | "Here the citation check passes, but this warning says the channels look out of sync. I'll come back to that." Return to the slides. |

## If something goes wrong

- **The app won't start:** run `pip install -r requirements.txt` and `pip install -e .`, then try again.
- **No sound or no audio player:** the app shows a note if the audio file is missing. Run `python -m calltrace run --full --asr-only` to download audio, or carry on, since the transcript and highlight still work.
- **Audio does not start on click:** press play by hand. It is positioned at the citation's time.
- **Anything else during recording:** stay on slide 8 and narrate from its screenshot, which is a real capture of this same step.

## Do not say

- That the citation check proves the claim is correct. It proves only that the turn exists and the quote matches.
- That a person reviewed the results. No human review has been done yet, unless you complete the worksheet first.
- That the sentiment detects vocal emotion, or that results apply to real customers.
