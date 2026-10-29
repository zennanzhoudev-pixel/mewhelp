from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.actions import router as actions_router
from app.api.admin import router as admin_router
from app.api.agent import router as agent_router
from app.api.chat import router as chat_router
from app.api.extract import router as extract_router
from app.api.jobs import router as jobs_router
from app.api.kb import router as kb_router
from app.api.rageval import router as rageval_router
from app.graph import runtime

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await runtime.init_graph()
    yield
    await runtime.close_graph()


app = FastAPI(title="MewHelp", version="0.5.0", lifespan=lifespan)

app.include_router(chat_router)
app.include_router(agent_router)
app.include_router(extract_router)
app.include_router(actions_router)
app.include_router(kb_router)
app.include_router(jobs_router)
app.include_router(admin_router)
app.include_router(rageval_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/kb")
async def kb_page():
    return FileResponse(STATIC_DIR / "kb.html")


@app.get("/admin")
async def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/rag-eval")
async def rageval_page():
    return FileResponse(STATIC_DIR / "rageval.html")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

