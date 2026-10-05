from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import config, migrate
from .db import Base, engine
from .routes import cron, food, plan, progress_api, web, workout


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate.run(engine)          # เติมคอลัมน์ใหม่ให้ฐานข้อมูลเดิม
    Base.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    same_site="lax",
    https_only=config.BASE_URL.startswith("https"),
    max_age=60 * 60 * 24 * 30,
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

for r in (web.router, food.router, workout.router, plan.router, progress_api.router, cron.router):
    app.include_router(r)


@app.get("/healthz")
def healthz():
    return {"ok": True}
