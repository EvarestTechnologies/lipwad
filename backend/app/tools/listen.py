"""Listen tool: turn a staff voice note into cited fields with Muse Voice Transcribe.

Values come only from what was said: each field cites the audio upload, the seconds
it was spoken between and the words themselves. A note with no speech produces a
request to record it again, never a guessed value.
"""

import re

from pydantic import BaseModel

from app.db.schemas import Citation, Field, Upload
from app.models.transcribe import Transcriber

MONTH_NAMES = (
    "january february march april may june july august september october november december"
)
ORDINAL_WORDS = (
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth "
    "thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth"
)
MONTHS = {name: number for number, name in enumerate(MONTH_NAMES.split(), start=1)}
ORDINALS = {word: number for number, word in enumerate(ORDINAL_WORDS.split(), start=1)}
ORDINALS |= {f"twenty {word}": 20 + n for word, n in list(ORDINALS.items())[:9]}
ORDINALS |= {"thirtieth": 30, "thirty first": 31}
UNITS = "one two three four five six seven eight nine".split()
SPOKEN_YEARS = {f"twenty twenty {word}": 2020 + n for n, word in enumerate(UNITS, start=1)}
SPOKEN_YEARS |= {
    f"two thousand and twenty {word}": 2020 + n for n, word in enumerate(UNITS, start=1)
}

_DAY = r"(\d{1,2})(?:st|nd|rd|th)?|" + "|".join(sorted(ORDINALS, key=len, reverse=True))
_MONTH = "|".join(MONTHS)
_YEAR = r"\d{4}|" + "|".join(sorted(SPOKEN_YEARS, key=len, reverse=True))
DAY_FIRST = re.compile(
    rf"\b(?P<day>{_DAY})\s+(?:of\s+)?(?P<month>{_MONTH}),?\s+(?P<year>{_YEAR})\b"
)
MONTH_FIRST = re.compile(rf"\b(?P<month>{_MONTH})\s+(?P<day>{_DAY}),?\s+(?P<year>{_YEAR})\b")
ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


class NoteInput(BaseModel):
    upload: Upload
    case_id: str


class NoteResult(BaseModel):
    upload_id: str
    fields: list[Field]
    retake_reasons: list[str]
    model: str


def spoken_date(text: str) -> str | None:
    """The first calendar date said in the text, as YYYY-MM-DD."""
    lowered = re.sub(r"[-\s]+", " ", text.lower()).replace(" ,", ",")
    if match := ISO.search(text):
        return match.group(0)
    for pattern in (DAY_FIRST, MONTH_FIRST):
        if match := pattern.search(lowered):
            day, year = match.group("day"), match.group("year")
            day_number = int(re.sub(r"\D", "", day)) if day[0].isdigit() else ORDINALS[day]
            year_number = int(year) if year.isdigit() else SPOKEN_YEARS[year]
            return f"{year_number:04d}-{MONTHS[match.group('month')]:02d}-{day_number:02d}"
    return None


def transcribe_note(note: NoteInput, transcriber: Transcriber) -> NoteResult:
    """Hear one voice note and return the admission date it states, cited to the moment."""
    transcript = transcriber.transcribe(note.upload.path, note.case_id)
    if not transcript.segments:
        return NoteResult(
            upload_id=note.upload.id,
            fields=[],
            retake_reasons=["voice note could not be heard"],
            model=transcript.model_id,
        )
    fields = []
    for segment in transcript.segments:
        date = spoken_date(segment.text)
        if date:
            citation = Citation(
                kind="audio",
                source_id=note.upload.id,
                t_start=segment.t_start,
                t_end=segment.t_end,
                quote=segment.text,
            )
            fields.append(
                Field(name="voice_admission_date", value=date, confidence=1.0, citations=[citation])
            )
            break
    return NoteResult(
        upload_id=note.upload.id, fields=fields, retake_reasons=[], model=transcript.model_id
    )
