"""CallTrace review interface: follow a claim back to the exact turn and audio time.

Run with: streamlit run app/streamlit_app.py
The app only reads exported results, so it needs neither ASR nor the LLM server.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import streamlit as st

from calltrace.config import PROJECT_ROOT, load_config
from calltrace.schemas import CallAnalysis, CallTranscript, Evidence

TEAL = "#0F766E"
CHARCOAL = "#1F2937"
SENTIMENT_COLOURS = {"negative": "#B45309", "positive": TEAL, "neutral": "#4B5563", "mixed": "#6D28D9",
                     "insufficient_evidence": "#9CA3AF"}

st.set_page_config(page_title="CallTrace: Evidence-Based Call Review", layout="wide")
st.markdown(
    f"""
    <style>
      .stApp {{ background-color: #FBFAF7; color: {CHARCOAL}; }}
      h1, h2, h3 {{ color: {CHARCOAL}; font-weight: 600; }}
      .card {{ background: #FFFFFF; border: 1px solid #E5E7EB; border-left: 4px solid {TEAL};
               border-radius: 6px; padding: 0.7rem 0.9rem; margin-bottom: 0.3rem; }}
      .card-label {{ color: {TEAL}; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.04em;
                     text-transform: uppercase; }}
      .pill {{ color: white; border-radius: 10px; padding: 0.1rem 0.55rem; font-size: 0.8rem; }}
      .notice {{ background: #FEF3C7; border-radius: 6px; padding: 0.5rem 0.8rem; font-size: 0.88rem; }}
      div[data-testid="stButton"] button {{ border: 1px solid {TEAL}; color: {TEAL}; background: #FFFFFF;
                                            padding: 0.1rem 0.5rem; font-size: 0.8rem; min-height: 0; }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_calls() -> dict[str, dict]:
    """Load every finished call as plain dictionaries, keyed by call ID."""
    config = load_config()
    calls_dir = config.path("results") / "calls"
    manifest_path = config.path("manifests") / "sample_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    merged_files = {record["call_id"]: record["merged_file"] for record in manifest["selected"]}
    calls = {}
    for directory in sorted(calls_dir.iterdir() if calls_dir.exists() else []):
        transcript_file, analysis_file = directory / "transcript.json", directory / "analysis.json"
        if transcript_file.exists() and analysis_file.exists():
            calls[directory.name] = {
                "transcript": json.loads(transcript_file.read_text(encoding="utf-8")),
                "analysis": json.loads(analysis_file.read_text(encoding="utf-8")),
                "audio": str(config.path("raw_audio") / merged_files.get(directory.name, "missing")),
            }
    return calls


def format_time(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def transcript_html(transcript: CallTranscript, selected: str | None) -> str:
    """Scrollable transcript. The selected turn is highlighted and scrolled into view."""
    rows = []
    for turn in transcript.turns:
        colour = TEAL if turn.role == "Agent" else "#92400E"
        selected_style = "background:#CCFBF1;outline:2px solid #0F766E;" if turn.turn_id == selected else ""
        minor = "opacity:0.6;" if turn.is_backchannel else ""
        flag = " <span title='Low ASR confidence (uncalibrated)'>&#9888;</span>" if turn.low_confidence else ""
        rows.append(
            f"<div id='{turn.turn_id}' style='padding:6px 8px;margin:2px 0;border-radius:4px;{selected_style}{minor}'>"
            f"<span style='color:#6B7280;font-size:12px'>{turn.turn_id} &middot; {format_time(turn.start)}</span> "
            f"<b style='color:{colour}'>{turn.role}</b> <span style='color:#6B7280;font-size:12px'>"
            f"({turn.speaker})</span>{flag}<br>{html.escape(turn.text_raw)}</div>"
        )
    scroll = ""
    if selected:
        scroll = f"<script>document.getElementById('{selected}').scrollIntoView({{block:'center'}});</script>"
    return (
        "<div style=\"font-family:'Segoe UI',Arial,sans-serif;font-size:14px;color:#1F2937;"
        f"line-height:1.45;background:#FFFFFF\">{''.join(rows)}</div>{scroll}"
    )


def select_evidence(item: Evidence) -> None:
    """Highlight the cited turn and start the audio from its timestamp."""
    st.session_state.update(selected_turn=item.turn_id, seek=int(item.start or 0), autoplay=True)


def shorten(quote: str, limit: int = 170) -> str:
    """Keep long citations readable. The full text stays visible in the transcript."""
    return quote if len(quote) <= limit else quote[: limit - 3].rsplit(" ", 1)[0] + " ..."


def evidence_buttons(evidence: list[Evidence], key: str) -> None:
    """One button per citation. A click selects the turn and seeks the audio."""
    if not evidence:
        st.caption("No citation (nothing to cite for this statement).")
        return
    for index, item in enumerate(evidence):
        columns = st.columns([1, 3])
        with columns[0]:
            label = f"{item.turn_id.split('-')[-1]} · {format_time(item.start or 0)}"
            # A callback runs before the page reruns, so the transcript above sees the new turn.
            st.button(label, key=f"{key}-{index}", on_click=select_evidence, args=(item,))
        with columns[1]:
            st.caption(f"“{shorten(item.quote)}”")


def claim_card(label: str, status: str, text: str, evidence: list[Evidence], key: str) -> None:
    badge = "" if status in ("stated", "yes") else f" <i style='color:#6B7280'>({status})</i>"
    st.markdown(
        f"<div class='card'><div class='card-label'>{label}{badge}</div>{html.escape(text)}</div>",
        unsafe_allow_html=True,
    )
    evidence_buttons(evidence, key)


def pill(label: str) -> str:
    colour = SENTIMENT_COLOURS.get(label, "#4B5563")
    return f"<span class='pill' style='background:{colour}'>{label.replace('_', ' ')}</span>"


calls = load_calls()
st.title("CallTrace: Evidence-Based Call Review")
if not calls:
    st.error("No processed calls were found. Run `python -m calltrace run --full` first.")
    st.stop()

with st.sidebar:
    st.header("Select a call")
    call_id = st.selectbox(
        "Call",
        list(calls),
        format_func=lambda cid: f"{cid} · {calls[cid]['transcript']['domain']} · {calls[cid]['transcript']['accent']}",
    )
    if st.session_state.get("active_call") != call_id:
        st.session_state.update(active_call=call_id, selected_turn=None, seek=0, autoplay=False)

    transcript = CallTranscript.model_validate(calls[call_id]["transcript"])
    analysis = CallAnalysis.model_validate(calls[call_id]["analysis"])

    st.caption(f"Source: {transcript.source_id} | {transcript.duration_s / 60:.1f} min")
    st.markdown(
        "<div class='notice'><b>Role-played data.</b> These are spontaneous role-plays, not real customers. "
        "Sentiment is judged from transcript text only, not from voice. Observations describe one call and are "
        "not a performance score.</div>",
        unsafe_allow_html=True,
    )
    st.subheader("How speakers were labelled")
    for speaker in transcript.speakers:
        st.markdown(f"**{speaker.speaker} = {speaker.role}** (channel {speaker.channel})")
    st.caption(transcript.speakers[0].role_method + ".")
    st.caption(transcript.speaker_boundaries_source)
    if analysis.validation.passed:
        st.success("Citation check passed: cited turns exist and quotes match. That does not prove a claim is correct.")
    else:
        st.warning("Citation check found problems.")
        for error in analysis.validation.errors:
            st.caption(error)

# A quality problem that undermines the whole call belongs at the top of the page.
for note in transcript.quality_notes:
    if "out of sync" in note:
        st.warning(f"Check this call first. {note}")

left, right = st.columns([5, 4], gap="large")

with left:
    st.subheader("Audio and transcript")
    audio_path = Path(calls[call_id]["audio"])
    if audio_path.exists():
        st.audio(str(audio_path), start_time=st.session_state.get("seek", 0),
                 autoplay=st.session_state.get("autoplay", False))
    else:
        st.info("Audio not found locally. Run `python -m calltrace run --full` to download it from the dataset.")
    selected_turn = st.session_state.get("selected_turn")
    if selected_turn:
        st.caption(f"Selected evidence: {selected_turn}, audio starts at {format_time(st.session_state['seek'])}")
    # Turn text is escaped in transcript_html, so nothing from the transcript runs as HTML.
    st.iframe(transcript_html(transcript, selected_turn), height=640)

with right:
    summary = analysis.summary
    st.subheader("Summary with evidence")
    claim_card("Customer issue", summary.customer_issue.status, summary.customer_issue.text,
               summary.customer_issue.evidence, "issue")
    claim_card("Agent action", summary.agent_action.status, summary.agent_action.text,
               summary.agent_action.evidence, "action")
    claim_card("Outcome or next step", summary.outcome_or_next_step.status, summary.outcome_or_next_step.text,
               summary.outcome_or_next_step.evidence, "outcome")

    sentiment = analysis.customer_sentiment
    st.subheader("Customer sentiment (text only)")
    st.markdown(
        f"Overall {pill(sentiment.overall.label)} &nbsp; Beginning {pill(sentiment.beginning.label)} "
        f"&rarr; Ending {pill(sentiment.ending.label)} &nbsp; <b>{sentiment.change.replace('_', ' ')}</b>",
        unsafe_allow_html=True,
    )
    st.write(sentiment.overall.justification)
    with st.expander("Overall evidence", expanded=True):
        evidence_buttons(sentiment.overall.evidence, "overall")
    with st.expander("Beginning window"):
        st.write(sentiment.beginning.justification)
        st.caption("Window turns: " + ", ".join(sentiment.beginning.window_turn_ids))
        evidence_buttons(sentiment.beginning.evidence, "beginning")
    with st.expander("Ending window"):
        st.write(sentiment.ending.justification)
        st.caption("Window turns: " + ", ".join(sentiment.ending.window_turn_ids))
        evidence_buttons(sentiment.ending.evidence, "ending")
    notes = [n.ambiguity_note for n in (sentiment.overall, sentiment.beginning, sentiment.ending)
             if n.ambiguity_note and n.ambiguity_note.lower() != "none"]
    if notes:
        st.caption("Ambiguity: " + " ".join(notes))

    handling = analysis.handling
    st.subheader("Observed call handling")
    st.caption("Describes this call only. It is not an employee performance score.")
    for label, observation, key in (
        ("Agent acknowledged the issue", handling.agent_acknowledged_issue, "ack"),
        ("Concrete action or next step", handling.concrete_action_or_next_step, "step"),
        ("Resolution", handling.resolution, "res"),
    ):
        with st.expander(f"{label}: {observation.answer.replace('_', ' ')}"):
            st.write(observation.note)
            evidence_buttons(observation.evidence, key)

    with st.expander("Notes and limitations for this call"):
        for note in analysis.notes_limitations:
            st.write(f"- {note}")
        st.caption(f"Model: {analysis.model_id}. Prompt version: {analysis.prompt_version}.")
        st.caption(f"Project root: {PROJECT_ROOT.name}. See README for overall validation results.")
