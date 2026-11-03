"""Recorded model responses for the synthetic cases, replayed by the stub provider."""

from pathlib import Path


def load_fixtures(data_dir: Path) -> dict[str, str]:
    """Map `vision:<case>/<document>` to the recorded response for that document."""
    fixtures = {}
    for path in sorted(data_dir.glob("*/fixtures/vision_*.json")):
        document = path.stem.removeprefix("vision_")
        fixtures[f"vision:{path.parents[1].name}/{document}"] = path.read_text()
    return fixtures
