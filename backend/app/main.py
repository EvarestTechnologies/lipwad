from fastapi import FastAPI

from app.api import health

app = FastAPI(title="Lipwad")
app.include_router(health.router, prefix="/api")
