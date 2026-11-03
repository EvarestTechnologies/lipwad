import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import claims, health
from app.services import Services, build_services

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; media-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; frame-ancestors 'none'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
}


def create_app(static_dir: Path | None = None, services: Services | None = None) -> FastAPI:
    """Build the API, and serve the built PWA from the same origin when given its folder."""
    app = FastAPI(title="Lipwad")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    app.include_router(health.router, prefix="/api")
    if services is not None:
        app.include_router(claims.router(services), prefix="/api")
    if static_dir is not None:
        _serve_frontend(app, static_dir)
    return app


def _serve_frontend(app: FastAPI, static_dir: Path) -> None:
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
    index = static_dir / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def app_shell(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)


_static = os.environ.get("STATIC_DIR")
app = create_app(
    Path(_static) if _static else None,
    build_services() if os.environ.get("LIPWAD_SERVE_API") == "1" else None,
)
