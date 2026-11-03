import json
from pathlib import Path

import pytest

from app.db.schemas import Upload
from app.models import StubFixtureMissingError
from app.models.transcribe import (
    FixtureTranscriber,
    Segment,
    Transcript,
    create_transcriber,
    segments_from_events,
)
from app.tools.listen import NoteInput, spoken_date, transcribe_note

NOTE = Upload(
    id="F06-voice_note", claim_id="F06", kind="audio", filename="voice_note.wav", path="x"
)


class Fixed:
    def __init__(self, *segments: Segment) -> None:
        self.segments = list(segments)

    def transcribe(self, audio_path: str, case_id: str) -> Transcript:
        return Transcript(segments=self.segments, model_id="fake-asr")


def test_segments_are_timed_from_audio_progress() -> None:
    events = [
        {"type": "speechStart", "audioProcessedMs": 0, "turnId": 0},
        {"type": "transcript", "transcript": "partial", "final": False, "turnId": 0},
        {"type": "speechComplete", "audioProcessedMs": 4200, "turnId": 0, "transcript": "One."},
        {"type": "speechStart", "audioProcessedMs": 5600, "turnId": 1},
        {"type": "speechComplete", "audioProcessedMs": 9800, "turnId": 1, "transcript": "Two."},
        {"type": "transcript", "transcript": "", "final": True, "audioProcessedMs": 11000},
    ]

    assert segments_from_events(events) == [
        Segment(t_start=0.0, t_end=4.2, text="One."),
        Segment(t_start=5.6, t_end=9.8, text="Two."),
    ]


def test_fixture_transcriber_replays_by_case_and_file() -> None:
    recorded = {"segments": [{"t_start": 0, "t_end": 2, "text": "Hello."}], "model_id": "m"}
    transcriber = FixtureTranscriber({"transcription:F06/voice_note": json.dumps(recorded)})

    assert transcriber.transcribe("data/F06/voice_note.wav", "F06").segments[0].text == "Hello."
    with pytest.raises(StubFixtureMissingError):
        transcriber.transcribe("data/F01/voice_note.wav", "F01")


def test_stub_mode_never_builds_a_network_transcriber() -> None:
    assert isinstance(create_transcriber({"MODEL_PROVIDER_MODE": "stub"}), FixtureTranscriber)


@pytest.mark.parametrize(
    "text",
    [
        "He came on the 11th of October 2026 with fever.",
        "Admitted October 11, 2026.",
        "Date of visit 2026-10-11.",
        "came on the eleventh of October, twenty twenty six",
    ],
)
def test_spoken_dates_are_read(text: str) -> None:
    assert spoken_date(text) == "2026-10-11"


def test_no_date_means_none() -> None:
    assert spoken_date("The malaria test was negative.") is None


def test_spoken_admission_date_cites_the_audio_moment() -> None:
    transcriber = Fixed(
        Segment(t_start=0, t_end=4.1, text="Voice note for Musa Kariuki."),
        Segment(t_start=5.6, t_end=10.3, text="He came to the clinic on the 11th of October 2026."),
    )
    result = transcribe_note(NoteInput(upload=NOTE, case_id="F06"), transcriber)
    field = next(f for f in result.fields if f.name == "voice_admission_date")
    citation = field.citations[0]

    assert field.value == "2026-10-11"
    assert (citation.kind, citation.source_id) == ("audio", "F06-voice_note")
    assert (citation.t_start, citation.t_end) == (5.6, 10.3)
    assert "11th of October" in citation.quote
    assert result.model == "fake-asr"


def test_silent_note_asks_for_a_new_recording() -> None:
    result = transcribe_note(NoteInput(upload=NOTE, case_id="F06"), Fixed())

    assert result.fields == []
    assert result.retake_reasons == ["voice note could not be heard"]


def test_recorded_f06_fixture_exists() -> None:
    path = Path(__file__).parents[2] / "data/synthetic/F06/fixtures/transcription_voice_note.json"
    recorded = Transcript.model_validate_json(path.read_text())

    assert any(spoken_date(s.text) == "2026-10-11" for s in recorded.segments)


def test_segments_without_a_start_or_with_no_length_are_dropped() -> None:
    events = [
        {"type": "speechComplete", "audioProcessedMs": 900, "turnId": 0, "transcript": "Orphan."},
        {"type": "speechStart", "audioProcessedMs": 1000, "turnId": 1},
        {"type": "speechComplete", "audioProcessedMs": 1000, "turnId": 1, "transcript": "Empty."},
    ]

    assert segments_from_events(events) == []


def test_non_pcm16_audio_is_refused_as_a_model_error(tmp_path: Path) -> None:
    import wave

    from app.models import ModelAPIError
    from app.models.transcribe import MetaTranscriber

    wide = tmp_path / "wide.wav"
    with wave.open(str(wide), "wb") as out:
        out.setnchannels(1), out.setsampwidth(4), out.setframerate(16000)
        out.writeframes(b"\0" * 32000)
    broken = tmp_path / "broken.wav"
    broken.write_bytes(b"not audio")
    transcriber = MetaTranscriber("key", url="ws://127.0.0.1:9")

    for path in (wide, broken):
        with pytest.raises(ModelAPIError):
            transcriber.transcribe(str(path), "X")


def test_transcripts_are_cached_per_file(tmp_path: Path) -> None:
    from app.models.transcribe import CachedTranscriber

    calls = []

    class Counting:
        def transcribe(self, audio_path: str, case_id: str) -> Transcript:
            calls.append(audio_path)
            return Transcript(segments=[], model_id="m")

    note = tmp_path / "voice_note.wav"
    note.write_bytes(b"x")
    cached = CachedTranscriber(Counting())
    cached.transcribe(str(note), "F06")
    cached.transcribe(str(note), "F06")

    assert calls == [str(note)]


def test_earliest_date_wins_and_impossible_dates_are_ignored() -> None:
    assert spoken_date("Admitted 11th October 2026, follow-up 2026-10-20.") == "2026-10-11"
    assert spoken_date("on the thirty first of February 2026") is None


def test_only_a_date_said_about_arrival_is_the_admission_date() -> None:
    transcriber = Fixed(
        Segment(t_start=0, t_end=3, text="Born on the 3rd of March 1990."),
        Segment(
            t_start=4,
            t_end=8,
            text="Lab results due 2026-10-20. He was admitted 12th October 2026.",
        ),
    )
    result = transcribe_note(NoteInput(upload=NOTE, case_id="F06"), transcriber)

    assert [f.value for f in result.fields] == ["2026-10-12"]


def test_a_note_without_an_arrival_date_gives_no_admission_field() -> None:
    transcriber = Fixed(Segment(t_start=0, t_end=3, text="Born on the 3rd of March 1990."))

    assert transcribe_note(NoteInput(upload=NOTE, case_id="F06"), transcriber).fields == []
