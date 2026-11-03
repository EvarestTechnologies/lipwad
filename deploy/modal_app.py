"""Modal deployment: the FastAPI app and the built PWA behind one URL.

SQLite, uploads and the mock HIE state live on a Volume. A single container serves
requests because SQLite allows one writer. Provider keys come from the `lipwad-env`
secret; nothing secret is baked into the image.

Deploy from the repo root with `make deploy`.
"""

import os
from pathlib import Path

import modal

DATA = "/data"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_sync(uv_project_dir="backend")
    .env(
        {
            "PYTHONPATH": "/root/backend",
            "DATABASE_URL": f"sqlite:///{DATA}/lipwad.db",
            "HIE_STATE_PATH": f"{DATA}/hie_state.json",
            "UPLOAD_DIR": f"{DATA}/uploads",
            "HIE_MODE": "mock",
            "STATIC_DIR": "/root/frontend/dist",
        }
    )
    .add_local_dir("backend/app", "/root/backend/app")
    .add_local_dir("data/synthetic", "/root/data/synthetic")
    .add_local_dir("frontend/dist", "/root/frontend/dist")
)

app = modal.App("lipwad", image=image)
volume = modal.Volume.from_name("lipwad-data", create_if_missing=True)


@app.function(
    volumes={DATA: volume},
    secrets=[modal.Secret.from_name("lipwad-env")],
    max_containers=1,
    timeout=600,
)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def web():
    from app.db.seed import seed_database
    from app.main import app as fastapi_app

    if not Path(DATA, "lipwad.db").exists():
        seed_database(os.environ["DATABASE_URL"], Path(os.environ["HIE_STATE_PATH"]))
        volume.commit()
    return fastapi_app
