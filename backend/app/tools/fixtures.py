"""Recorded model responses for the synthetic cases, replayed by the stub provider."""

from pathlib import Path


def load_fixtures(data_dir: Path) -> dict[str, str]:
    """Map `<role>:<case>/<document>` to the recorded response for that document."""
    fixtures = {}
    for role in ("vision", "transcription"):
        for path in sorted(data_dir.glob(f"*/fixtures/{role}_*.json")):
            document = path.stem.removeprefix(f"{role}_")
            fixtures[f"{role}:{path.parents[1].name}/{document}"] = path.read_text()
    return fixtures
