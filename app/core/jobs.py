import asyncio
import os
import pathlib
import signal
from dataclasses import dataclass

LOG_DIR = pathlib.Path("log") / "acceptance"


@dataclass(frozen=True)
class JobSpec:
    name: str
    label: str
    argv: tuple[str, ...]
    heavy: bool = False


JOBS: list[JobSpec] = [
    JobSpec("kb-preview", "材料清单与切块预览", ("make", "kb-preview")),
    JobSpec("kb-build", "离线建库", ("make", "kb-build")),
    JobSpec("kb-mine", "对话挖知识", ("make", "kb-mine"), heavy=True),
    JobSpec("kb-vectorize", "向量化待补块", ("make", "kb-vectorize")),
    JobSpec("kb-reset", "清库重建", ("make", "kb-reset"), heavy=True),
    JobSpec("eval-rag", "RAG 评估(四策略对照)", ("make", "eval-rag"), heavy=True),
]
_BY_NAME = {j.name: j for j in JOBS}

_procs: dict[str, asyncio.subprocess.Process] = {}
_status: dict[str, str] = {}


class JobAlreadyRunning(Exception):
    pass


def list_specs() -> list[JobSpec]:
    return JOBS


def get_spec(name: str) -> JobSpec | None:
    return _BY_NAME.get(name)


async def start(name: str) -> dict:
    spec = _BY_NAME[name]
    if _status.get(name) == "running":
        raise JobAlreadyRunning(name)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / f"{name}.log"
    with open(log, "w", encoding="utf-8") as f:
        f.write(f"$ {' '.join(spec.argv)}\n")
    stdout = open(log, "a", encoding="utf-8")
    proc = await asyncio.create_subprocess_exec(
        *spec.argv,
        stdout=stdout,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )
    _procs[name] = proc
    _status[name] = "running"
    asyncio.create_task(_wait(name, proc))
    return status(name)


async def _wait(name: str, proc: asyncio.subprocess.Process) -> None:
    code = await proc.wait()
    _status[name] = "done" if code == 0 else "failed"


def status(name: str) -> dict:
    spec = _BY_NAME[name]
    return {
        "name": name,
        "label": spec.label,
        "heavy": spec.heavy,
        "status": _status.get(name, "idle"),
    }


def tail(name: str, n: int = 100) -> str:
    log = LOG_DIR / f"{name}.log"
    if not log.exists():
        return ""
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:])


async def stop(name: str) -> dict:
    proc = _procs.get(name)
    if proc is not None and _status.get(name) == "running":
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=10)
        except asyncio.TimeoutError:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        _status[name] = "stopped"
    return status(name)

