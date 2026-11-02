"""Focused checks: timestamps, evidence references, schemas, empty input, and resume."""

import json

import numpy as np
import pytest
import soundfile as sf
from pydantic import ValidationError

from calltrace.analysis import compute_change, select_windows, substantive_customer_turns
from calltrace.asr import tokens_to_words
from calltrace.config import load_config
from calltrace.data import audio_quality
from calltrace.evaluation import WerScorer, best_speaker_mapping, diarization_error
from calltrace.pipeline import CallPipeline
from calltrace.schemas import (
    CallAnalysis,
    CallHandling,
    CallSummary,
    CallTranscript,
    Claim,
    CustomerSentiment,
    Evidence,
    HandlingObservation,
    SentimentJudgment,
    Turn,
    ValidationReport,
    Word,
)
from calltrace.turns import build_turns, clean_reference_text, clean_text, is_courtesy_only, overlap_share
from calltrace.validation import check_evidence, quote_in_turn, validate_analysis

TURN_SETTINGS = {"word_gap_s": 1.2, "same_speaker_merge_s": 2.0, "backchannel_max_words": 3, "max_turn_s": 30}
LABELS = {1: "Speaker 1", 2: "Speaker 2"}
ROLES = {1: "Agent", 2: "Customer"}


def make_turn(index, role="Customer", text="my internet has been down for two days", **extra):
    channel = 1 if role == "Agent" else 2
    return Turn(
        turn_id=f"001-T{index:04d}", call_id="001", speaker=LABELS[channel], role=role, channel=channel,
        start=float(index), end=float(index) + 0.9, text_raw=text, text_clean=text, **extra,
    )


def words_from(text, start, step=0.3):
    return [Word(text=w, start=start + i * step, end=start + (i + 1) * step) for i, w in enumerate(text.split())]


def make_analysis(evidence):
    judgment = SentimentJudgment(label="neutral", justification="x", evidence=evidence)
    observation = HandlingObservation(answer="not_observable", note="x")
    return CallAnalysis(
        call_id="001", transcript_source="asr", model_id="m", prompt_version="v1",
        summary=CallSummary(
            customer_issue=Claim(status="stated", text="x", evidence=evidence),
            agent_action=Claim(status="not_stated", text="not stated"),
            outcome_or_next_step=Claim(status="not_stated", text="not stated"),
        ),
        handling=CallHandling(
            agent_acknowledged_issue=observation, concrete_action_or_next_step=observation, resolution=observation,
        ),
        customer_sentiment=CustomerSentiment(
            method="text", overall=judgment,
            beginning=SentimentJudgment(label="insufficient_evidence", justification="x"),
            ending=SentimentJudgment(label="insufficient_evidence", justification="x"),
            change="insufficient_evidence", change_note="x",
        ),
        agent_sentiment=SentimentJudgment(label="insufficient_evidence", justification="x"),
        validation=ValidationReport(passed=True),
    )


# -- Timestamps ---------------------------------------------------------------------

def test_turn_rejects_end_before_start():
    with pytest.raises(ValidationError):
        Turn(turn_id="x", call_id="001", speaker="Speaker 1", role="Agent", channel=1,
             start=5.0, end=4.0, text_raw="a", text_clean="a")


def test_turn_rejects_negative_start():
    with pytest.raises(ValidationError):
        Turn(turn_id="x", call_id="001", speaker="Speaker 1", role="Agent", channel=1,
             start=-1.0, end=4.0, text_raw="a", text_clean="a")


def test_token_grouping_applies_chunk_offset_and_merges_subwords():
    words = tokens_to_words(100.0, [" hel", "lo", " there"], [0.0, 0.2, 0.5], [-0.1, -0.1, -0.2])
    assert [w.text for w in words] == ["hello", "there"]
    assert words[0].start == 100.0 and words[0].end == 100.5
    assert words[1].start == 100.5


# -- Turn building ------------------------------------------------------------------

def test_turns_are_time_ordered_with_stable_ids_and_correct_speakers():
    words = {
        1: words_from("hello how can I help you today", 0.0),
        2: words_from("my internet is not working at all", 3.0),
    }
    turns = build_turns("001", words, LABELS, ROLES, TURN_SETTINGS)
    assert [t.turn_id for t in turns] == ["001-T0001", "001-T0002"]
    assert [t.role for t in turns] == ["Agent", "Customer"]
    assert turns[0].start <= turns[1].start
    assert build_turns("001", words, LABELS, ROLES, TURN_SETTINGS)[1].text_raw == turns[1].text_raw


def test_backchannel_does_not_split_the_main_turn():
    words = {
        1: words_from("so the first thing we need to do is restart the router now", 0.0),
        2: words_from("mm-hm", 1.0),
    }
    turns = build_turns("001", words, LABELS, ROLES, TURN_SETTINGS)
    main = [t for t in turns if t.role == "Agent"]
    interjection = [t for t in turns if t.role == "Customer"]
    assert len(main) == 1 and len(interjection) == 1
    assert interjection[0].is_backchannel and interjection[0].overlaps_previous


def test_long_turn_is_split_at_a_sentence_end():
    text = " ".join(["word"] * 30 + ["stop."] + ["word"] * 40)
    turns = build_turns("001", {1: words_from(text, 0.0, step=0.6), 2: []}, LABELS, ROLES, TURN_SETTINGS)
    assert len(turns) >= 2
    assert all(t.end - t.start <= TURN_SETTINGS["max_turn_s"] + 0.7 for t in turns)


def test_clean_text_keeps_raw_meaning_and_removes_only_fillers_and_repeats():
    assert clean_text("I I um want to uh cancel, cancel.") == "I want to cancel."


def test_reference_markup_is_removed():
    cleaned = clean_reference_text("many (um) organizati~ organic (()) farmers <initial>USA</initial>")
    assert cleaned == "many organic farmers USA"


@pytest.mark.parametrize(
    "text,expected",
    [("thanks so much, bye", True), ("okay great thank you", True), ("you have a good day", True),
     ("I am still really upset about the bill", False), ("thank you, but the refund never came", False)],
)
def test_courtesy_detection(text, expected):
    assert is_courtesy_only(text) is expected


# -- Evidence ----------------------------------------------------------------------

def test_quote_matching_ignores_case_and_punctuation_but_not_words():
    turn = make_turn(1, text="My internet has been down, for two days!")
    assert quote_in_turn("internet has been down for two days", turn)
    assert not quote_in_turn("internet has been down for three days", turn)
    assert not quote_in_turn("   ", turn)


def test_missing_turn_and_wrong_quote_are_reported():
    turn = make_turn(1)
    problems = check_evidence(
        [Evidence(turn_id="001-T9999", quote="x"), Evidence(turn_id=turn.turn_id, quote="made up words")],
        {turn.turn_id: turn}, "claim",
    )
    assert len(problems) == 2


def test_customer_sentiment_cannot_cite_agent_turns():
    agent = make_turn(1, role="Agent", text="I understand this is frustrating")
    analysis = make_analysis([Evidence(turn_id=agent.turn_id, quote="this is frustrating")])
    problems = validate_analysis(analysis, [agent])
    assert any("expected Customer" in problem for problem in problems)


def test_stated_claim_without_evidence_fails():
    analysis = make_analysis([])
    problems = validate_analysis(analysis, [make_turn(1)])
    assert any("marked stated but cites no turn" in problem for problem in problems)


def test_valid_analysis_passes():
    turn = make_turn(1)
    analysis = make_analysis([Evidence(turn_id=turn.turn_id, quote="down for two days")])
    assert validate_analysis(analysis, [turn]) == []


def test_schema_rejects_unknown_status():
    with pytest.raises(ValidationError):
        Claim(status="probably", text="x")


# -- Sentiment windows and change ---------------------------------------------------

def test_windows_skip_courtesy_and_backchannel_and_do_not_overlap():
    settings = {"sentiment_window_turns": 3, "substantive_min_words": 4}
    turns = [
        make_turn(1, text="hello"),
        make_turn(2, text="I have been waiting two weeks for this"),
        make_turn(3, text="the delivery still has not arrived here"),
        make_turn(4, text="what are you going to do"),
        make_turn(5, text="okay so you will refund me then"),
        make_turn(6, text="mm-hm right yes sure", is_backchannel=True),
        make_turn(7, text="thanks so much, bye", is_courtesy_only=True),
    ]
    beginning, ending = select_windows(turns, settings)
    begin_ids = {t.turn_id for t in beginning}
    end_ids = {t.turn_id for t in ending}
    assert not begin_ids & end_ids
    assert "001-T0007" not in end_ids and "001-T0006" not in end_ids
    assert len(substantive_customer_turns(turns, 4)) == 4


def test_windows_are_empty_when_turns_are_too_few():
    assert select_windows([make_turn(1)], {"sentiment_window_turns": 3, "substantive_min_words": 4}) == ([], [])


@pytest.mark.parametrize(
    "begin,end,expected",
    [("negative", "positive", "improved"), ("positive", "neutral", "worsened"), ("neutral", "neutral", "unchanged"),
     ("insufficient_evidence", "positive", "insufficient_evidence")],
)
def test_change_rule(begin, end, expected):
    assert compute_change(begin, end)[0] == expected


# -- Metrics ------------------------------------------------------------------------

def test_wer_ignores_case_punctuation_and_counts_a_real_error():
    scorer = WerScorer()
    assert scorer.score(["Hello, World!"], ["hello world"])["wer"] == 0
    assert scorer.score(["the cat sat here"], ["the cat sat there"])["wer"] == 0.25
    # Number words and digits are the same after normalisation, as in the dataset's scorer.
    assert scorer.score(["call me at nine"], ["call me at 9"])["wer"] == 0


def test_der_is_zero_for_identical_input_and_counts_swapped_speakers():
    reference = {"Agent": [(0.0, 5.0)], "Customer": [(6.0, 10.0)]}
    assert diarization_error(reference, reference, 10.0)["der"] == 0
    swapped = {"Agent": reference["Customer"], "Customer": reference["Agent"]}
    assert diarization_error(reference, swapped, 10.0)["confusion"] > 0.9


def test_anonymous_clusters_map_to_reference_speakers():
    reference = {"Agent": [(0.0, 5.0)], "Customer": [(6.0, 10.0)]}
    mapping = best_speaker_mapping(reference, {"A": [(6.0, 10.0)], "B": [(0.0, 5.0)]}, 10.0)
    assert mapping == {"A": "Customer", "B": "Agent"}


# -- Empty and corrupt input, failures, and resume -----------------------------------

@pytest.fixture
def pipeline(tmp_path):
    return CallPipeline(load_config(), output_dir=tmp_path, use_llm=False)


@pytest.fixture
def record():
    return {
        "call_id": "901", "source_id": "fake", "accent": "en-XX", "domain": "test", "duration_s": 1.0,
        "channels": {"1": {"role": "agent", "speaker_id": "a", "file": "a"},
                     "2": {"role": "customer", "speaker_id": "b", "file": "b"}},
        "merged_file": "m",
    }


def test_empty_audio_raises(tmp_path):
    path = tmp_path / "empty.wav"
    sf.write(path, np.zeros(0, dtype=np.float32), 16000)
    with pytest.raises(ValueError, match="empty audio"):
        audio_quality(path)


def test_corrupt_audio_raises(tmp_path):
    path = tmp_path / "corrupt.wav"
    path.write_bytes(b"this is not audio")
    with pytest.raises(Exception):
        audio_quality(path)


def test_failure_is_recorded_and_does_not_stop_the_run(pipeline, record, tmp_path, monkeypatch):
    good = dict(record, call_id="902")
    processed = []

    def fake_transcribe(call):
        if call["call_id"] == "901":
            raise ValueError("no speech recognised on either channel")
        processed.append(call["call_id"])
        return CallTranscript(
            call_id=call["call_id"], source_id="s", accent="a", domain="d", duration_s=1, transcript_source="asr",
            speaker_boundaries_source="x", speakers=[], turns=[],
        )

    monkeypatch.setattr(pipeline, "transcribe_call", fake_transcribe)
    summary = pipeline.run([record, good])
    assert summary["failed"] == ["901"] and summary["processed"] == ["902"]
    failure = json.loads((tmp_path / "failures.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert failure["call_id"] == "901" and "no speech" in failure["error"]


def test_resume_skips_finished_calls(pipeline, record, monkeypatch):
    done = pipeline.calls_dir / "901"
    done.mkdir(parents=True)
    (done / "transcript.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(pipeline, "transcribe_call", lambda call: pytest.fail("should not transcribe again"))
    assert pipeline.run([record])["resumed"] == ["901"]


def test_cached_asr_words_are_reused_without_loading_a_model(pipeline, record, monkeypatch):
    cache = pipeline.calls_dir / "901" / "asr_channel1.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(
        json.dumps({"model_id": pipeline.config["asr"]["model_id"],
                    "quantization": pipeline.config["asr"]["quantization"],
                    "words": [{"text": "hi", "start": 0.0, "end": 0.2, "logprob": None}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(pipeline, "_get_transcriber", lambda: pytest.fail("model must not be loaded"))
    assert pipeline._channel_words(record, "1", None)[0].text == "hi"


def test_cache_from_other_weights_is_not_reused(pipeline, record, monkeypatch):
    cache = pipeline.calls_dir / "901" / "asr_channel1.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(
        json.dumps({"model_id": pipeline.config["asr"]["model_id"], "quantization": "int8", "words": []}),
        encoding="utf-8",
    )

    class Fake:
        def transcribe(self, path):
            return words_from("hello there", 0.0)

    monkeypatch.setattr(pipeline, "_get_transcriber", lambda: Fake())
    assert [w.text for w in pipeline._channel_words(record, "1", None)] == ["hello", "there"]


def test_overlap_share_detects_talking_over_each_other():
    assert overlap_share([(0.0, 10.0)], [(20.0, 30.0)]) == 0
    assert overlap_share([(0.0, 10.0)], [(0.0, 10.0), (20.0, 40.0)]) == 1
    assert overlap_share([], [(0.0, 1.0)]) == 0


def test_channel_order_is_not_assumed_to_mean_role(pipeline, record, tmp_path, monkeypatch):
    # In 66 dataset calls channel 1 is the customer. Roles must follow the metadata.
    flipped = dict(record, channels={"1": {"role": "customer", "speaker_id": "b", "file": "b"},
                                     "2": {"role": "agent", "speaker_id": "a", "file": "a"}})
    wav = tmp_path / "tone.wav"
    sf.write(wav, 0.1 * np.sin(np.linspace(0, 2000, 16000)).astype(np.float32), 16000)
    monkeypatch.setattr(pipeline.dataset, "download_call",
                        lambda call: {"channel1": wav, "channel2": wav, "merged": wav})
    spoken = {"1": "my bill is wrong this month", "2": "thank you for calling how can I help"}
    monkeypatch.setattr(pipeline, "_channel_words",
                        lambda call, channel, path: words_from(spoken[channel], 0.0 if channel == "2" else 5.0))
    transcript = pipeline.transcribe_call(flipped)
    roles = {t.channel: t.role for t in transcript.turns}
    assert roles == {1: "Customer", 2: "Agent"}
    assert transcript.turns[0].role == "Agent"
