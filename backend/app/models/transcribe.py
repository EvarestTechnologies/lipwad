"""Speech to text with Muse Voice Transcribe.

The Meta Model API serves Muse Voice Transcribe only as a realtime WebSocket stream,
not through the Chat Completions format the other roles use, so it has its own small
client. Each detected utterance becomes a `Segment` timed from the server's
`audioProcessedMs` counter, which is what audio citations point at.
"""

import json
import os
import time
import wave
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from app.models.base import MissingAPIKeyError, ModelAPIError, StubFixtureMissingError

MODEL_ID = "muse-voice-transcribe-1.0"
REALTIME_URL = "wss://api.meta.ai/v1/asr/realtime"
PACKET_MS = 80
TRAILING_SILENCE_S = 2
ENCODINGS = {16000: "PCM_16KHZ", 24000: "PCM_24KHZ"}


class Segment(BaseModel):
    t_start: float
    t_end: float
    text: str


class Transcript(BaseModel):
    segments: list[Segment]
    model_id: str


class Transcriber(Protocol):
    def transcribe(self, audio_path: str, case_id: str) -> Transcript: ...


def segments_from_events(events: Iterable[Mapping[str, Any]]) -> list[Segment]:
    """Turn the server's turn events into timed segments, in speaking order."""
    starts: dict[Any, float] = {}
    segments = []
    for event in events:
        kind, turn = event.get("type"), event.get("turnId")
        if kind == "speechStart":
            starts[turn] = event["audioProcessedMs"] / 1000
        elif kind == "speechComplete" and event.get("transcript", "").strip():
            segments.append(
                Segment(
                    t_start=starts.get(turn, 0.0),
                    t_end=event["audioProcessedMs"] / 1000,
                    text=event["transcript"].strip(),
                )
            )
    return sorted(segments, key=lambda segment: segment.t_start)


class MetaTranscriber:
    """Streams a mono PCM16 WAV file to Muse Voice Transcribe at real-time pace."""

    def __init__(self, api_key: str, url: str = REALTIME_URL, timeout_s: float = 30) -> None:
        self._api_key = api_key
        self._url = url
        self._timeout_s = timeout_s

    def transcribe(self, audio_path: str, case_id: str) -> Transcript:
        from websockets.exceptions import ConnectionClosed, WebSocketException
        from websockets.sync.client import connect

        with wave.open(audio_path) as audio:
            rate, channels = audio.getframerate(), audio.getnchannels()
            pcm = audio.readframes(audio.getnframes())
        if rate not in ENCODINGS or channels != 1 or len(pcm) % 2:
            raise ModelAPIError(f"{audio_path} must be mono PCM16 at 16 or 24 kHz")
        pcm += b"\0" * (rate * 2 * TRAILING_SILENCE_S)
        packet = rate * 2 * PACKET_MS // 1000
        events: list[dict[str, Any]] = []
        try:
            with connect(self._url, open_timeout=self._timeout_s) as socket:
                socket.send(json.dumps(self._handshake(rate)))
                for offset in range(0, len(pcm), packet):
                    socket.send(pcm[offset : offset + packet])
                    time.sleep(PACKET_MS / 1000)
                    events += _drain(socket)
                socket.send(json.dumps({"type": "endStream"}))
                deadline = time.monotonic() + self._timeout_s
                while time.monotonic() < deadline:
                    try:
                        events.append(json.loads(socket.recv(timeout=self._timeout_s)))
                    except (ConnectionClosed, TimeoutError):
                        break
        except (OSError, WebSocketException) as error:
            raise ModelAPIError(f"Muse Voice Transcribe failed: {error}") from error
        errors = [event for event in events if event.get("type") == "error"]
        if errors:
            raise ModelAPIError(f"Muse Voice Transcribe failed: {errors[0].get('message')}")
        return Transcript(segments=segments_from_events(events), model_id=MODEL_ID)

    def _handshake(self, rate: int) -> dict[str, Any]:
        return {
            "authorization": {"accessToken": self._api_key},
            "audioEncoding": ENCODINGS[rate],
            "model": MODEL_ID,
            "mode": "ENDPOINTING",
            "partialMode": "CUMULATIVE",
            "emitAudioProgress": True,
            "languageBias": ["English"],
        }


def _drain(socket) -> list[dict[str, Any]]:
    events = []
    while True:
        try:
            events.append(json.loads(socket.recv(timeout=0)))
        except TimeoutError:
            return events


class FixtureTranscriber:
    """Replays recorded transcripts keyed `transcription:<case>/<file stem>`; no network."""

    def __init__(self, fixtures: Mapping[str, str]) -> None:
        self._fixtures = dict(fixtures)

    def transcribe(self, audio_path: str, case_id: str) -> Transcript:
        key = f"transcription:{case_id}/{Path(audio_path).stem}"
        if key not in self._fixtures:
            raise StubFixtureMissingError(f"no recorded transcript for {key}")
        return Transcript.model_validate_json(self._fixtures[key])


def create_transcriber(
    env: Mapping[str, str] | None = None, fixtures: Mapping[str, str] | None = None
) -> Transcriber:
    settings = dict(os.environ) if env is None else dict(env)
    mode = (settings.get("MODEL_PROVIDER_MODE") or "live").strip().lower()
    if mode == "stub":
        return FixtureTranscriber(fixtures or {})
    key = (settings.get("META_MODEL_API_KEY") or "").strip()
    if not key:
        raise MissingAPIKeyError("META_MODEL_API_KEY is required for Muse Voice Transcribe")
    return MetaTranscriber(key)
