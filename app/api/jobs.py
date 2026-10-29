from fastapi import APIRouter, HTTPException

from app.core import jobs

router = APIRouter()


@router.get("/api/jobs")
async def list_jobs():
    return [jobs.status(s.name) for s in jobs.list_specs()]


@router.post("/api/jobs/{name}")
async def start_job(name: str):
    if jobs.get_spec(name) is None:
        raise HTTPException(status_code=404, detail=f"未知作业 {name}")
    try:
        return await jobs.start(name)
    except jobs.JobAlreadyRunning:
        raise HTTPException(status_code=409, detail="同名作业仍在运行")


@router.get("/api/jobs/{name}")
async def get_job(name: str):
    if jobs.get_spec(name) is None:
        raise HTTPException(status_code=404, detail=f"未知作业 {name}")
    return {**jobs.status(name), "tail": jobs.tail(name)}


@router.post("/api/jobs/{name}/stop")
async def stop_job(name: str):
    if jobs.get_spec(name) is None:
        raise HTTPException(status_code=404, detail=f"未知作业 {name}")
    return await jobs.stop(name)

