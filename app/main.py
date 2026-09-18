import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.services.worker import run_startup_recovery, run_worker_forever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot sequence: crash recovery, then the background worker loop."""
    # 1) Startup recovery — reset any in-flight rows left by a previous
    #    process crash back to QUEUED so the worker re-picks them up.
    await asyncio.to_thread(run_startup_recovery)

    # 2) Background worker (Task 8) — a lightweight polling loop; skipped when
    #    WORKER_ENABLED=false (e.g. under tests).
    worker_task = None
    if settings.WORKER_ENABLED:
        worker_task = asyncio.create_task(run_worker_forever())
        logger.info("Background worker started")
    try:
        yield
    finally:
        if worker_task:
            worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker_task


app = FastAPI(title="Resume Interview Q&A Generator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=True)