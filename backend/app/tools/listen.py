"""Listen tool: turn a staff voice note into cited fields with Muse Voice Transcribe.

Values come only from what was said: each field cites the audio upload, the seconds
it was spoken between and the words themselves. A note with no speech produces a
request to record it again, never a guessed value.
"""

import re
from datetime import date

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
ISO = re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})\b")
ARRIVAL = re.compile(r"\b(admit\w*|admission|came|arrived|brought|presented)\b", re.I)
SENTENCE = re.compile(r"(?<=[.!?])\s+")


class NoteInput(BaseModel):
    upload: Upload
    case_id: str


class NoteResult(BaseModel):
    upload_id: str
    fields: list[Field]
    retake_reasons: list[str]
    model: str


def spoken_date(text: str) -> str | None:
    """The first real calendar date said in the text, as YYYY-MM-DD."""
    found = []
    for match in ISO.finditer(text):
        found.append((match.start(), int(match["year"]), int(match["month"]), int(match["day"])))
    lowered = re.sub(r"[-\s]+", " ", text.lower()).replace(" ,", ",")
    for pattern in (DAY_FIRST, MONTH_FIRST):
        for match in pattern.finditer(lowered):
            day, year = match["day"], match["year"]
            day_number = int(re.sub(r"\D", "", day)) if day[0].isdigit() else ORDINALS[day]
            year_number = int(year) if year.isdigit() else SPOKEN_YEARS[year]
            found.append((match.start(), year_number, MONTHS[match["month"]], day_number))
    for _, year, month, day in sorted(found):
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            continue
    return None


def arrival_date(text: str) -> str | None:
    """The date in the first sentence that talks about the patient arriving or being admitted."""
    for sentence in SENTENCE.split(text):
        if ARRIVAL.search(sentence) and (found := spoken_date(sentence)):
            return found
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
        admitted = arrival_date(segment.text)
        if admitted:
            citation = Citation(
                kind="audio",
                source_id=note.upload.id,
                t_start=segment.t_start,
                t_end=segment.t_end,
                quote=segment.text,
            )
            fields.append(
                Field(
                    name="voice_admission_date",
                    value=admitted,
                    confidence=1.0,
                    citations=[citation],
                )
            )
            break
    return NoteResult(
        upload_id=note.upload.id, fields=fields, retake_reasons=[], model=transcript.model_id
    )
