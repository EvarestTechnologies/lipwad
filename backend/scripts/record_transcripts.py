"""Record real Muse Voice Transcribe transcripts for each synthetic voice note.

The tests replay these through `FixtureTranscriber`, so CI never calls a paid model.
Run by hand after changing a voice note: `uv run python scripts/record_transcripts.py`.
"""

from pathlib import Path

from app.models.transcribe import create_transcriber

DATA_DIR = Path(__file__).parents[2] / "data" / "synthetic"


def main() -> None:
    transcriber = create_transcriber()
    for note in sorted(DATA_DIR.glob("*/voice_note.wav")):
        transcript = transcriber.transcribe(str(note), note.parent.name)
        target = note.parent / "fixtures" / f"transcription_{note.stem}.json"
        target.write_text(transcript.model_dump_json(indent=2) + "\n")
        print("recorded", f"{note.parent.name}/{note.name}", len(transcript.segments), "segments")


if __name__ == "__main__":
    main()
