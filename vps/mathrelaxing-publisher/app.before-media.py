import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
root = Path(os.environ["STATE_DIRECTORY"])
key = (Path(os.environ["CREDENTIALS_DIRECTORY"]) / "api-key").read_text().strip()
LIMIT = 256 * 1024 * 1024


@app.middleware("http")
async def authenticate(request: Request, call_next):
    if request.url.path != "/health":
        supplied = request.headers.get("authorization", "")
        if not secrets.compare_digest(supplied, "Bearer " + key):
            from starlette.responses import JSONResponse
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


class Draft(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    facebook_caption: str = Field(default="", max_length=10000)
    instagram_caption: str = Field(default="", max_length=2200)


def folder(job: UUID):
    path = root / str(job)
    if not (path / "draft.json").exists():
        raise HTTPException(404, "Draft not found")
    return path


@app.get("/health")
def health():
    return {"service": "mathrelaxing-publisher", "publishing_enabled": False}


@app.post("/drafts", status_code=201)
def create_draft(draft: Draft):
    job = uuid4()
    path = root / str(job)
    path.mkdir(mode=0o700)
    (path / "draft.json").write_text(
        json.dumps(draft.model_dump(), ensure_ascii=False)
    )
    return {"id": str(job), "status": "awaiting_video"}


@app.get("/drafts/{job}")
def status(job: UUID):
    path = folder(job)
    return {
        "id": str(job),
        "status": "ready" if (path / "video.mp4").exists() else "awaiting_video",
        "draft": json.loads((path / "draft.json").read_text()),
    }


@app.put("/drafts/{job}/video")
async def upload(job: UUID, request: Request):
    path = folder(job)
    if (path / "video.mp4").exists():
        raise HTTPException(409, "Video already exists")
    lock = path / ".uploading"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    except FileExistsError:
        raise HTTPException(409, "Upload in progress")

    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(dir=path, suffix=".mp4")
        total = 0
        with os.fdopen(fd, "wb") as stream:
            async for chunk in request.stream():
                total += len(chunk)
                if total > LIMIT:
                    raise HTTPException(413, "Maximum size: 256 MiB")
                stream.write(chunk)
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_streams",
                 "-show_format", "-of", "json", temporary],
                capture_output=True, text=True, timeout=30, check=True,
            )
            info = json.loads(result.stdout)
            video = next(s for s in info["streams"]
                         if s.get("codec_type") == "video")
            duration = float(info["format"]["duration"])
            if not (1 <= duration <= 180):
                raise ValueError()
            if video["width"] * 16 != video["height"] * 9:
                raise ValueError()
            if video.get("codec_name") != "h264":
                raise ValueError()
            if not any(s.get("codec_type") == "audio" for s in info["streams"]):
                raise ValueError()
        except (subprocess.SubprocessError, ValueError, KeyError, StopIteration):
            raise HTTPException(422, "Expected H.264, 9:16, audio, 1–180 seconds")
        os.replace(temporary, path / "video.mp4")
        return {"id": str(job), "status": "ready", "bytes": total}
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
