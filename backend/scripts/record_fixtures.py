"""Record real Muse Spark vision responses for each synthetic document.

The tests replay these through the stub provider, so CI never calls a paid model.
Run by hand after changing a prompt or a document: `uv run python scripts/record_fixtures.py`.
"""

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.models import ChatMessage, ChatRequest, Role, create_client
from app.tools.intake import DOCUMENT_PROMPTS

DATA_DIR = Path(__file__).parents[2] / "data" / "synthetic"


def record(image: Path) -> str:
    kind = "invoice" if image.stem == "invoice" else "claim_form"
    encoded = base64.b64encode(image.read_bytes()).decode()
    request = ChatRequest(
        json_output=True,
        messages=[
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": DOCUMENT_PROMPTS[kind]},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
                ],
            )
        ],
    )
    content = create_client(Role.VISION).complete(request).content
    target = image.parent / "fixtures" / f"vision_{image.stem}.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(json.loads(content), indent=2) + "\n")
    return f"{image.parent.name}/{image.name}"


def main() -> None:
    images = sorted(DATA_DIR.glob("*/*.png"))
    with ThreadPoolExecutor(max_workers=6) as pool:
        for done in pool.map(record, images):
            print("recorded", done)


if __name__ == "__main__":
    main()
