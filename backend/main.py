import os
import re
import uuid
import json
import base64
from io import BytesIO
from pathlib import Path

import httpx
import fitz
from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import aiofiles

BASE_DIR = Path(__file__).parent
FRONTEND_DIR = (BASE_DIR / ".." / "frontend").resolve()
UPLOAD_DIR = (BASE_DIR / ".." / "temp_uploads").resolve()
UPLOAD_DIR.mkdir(exist_ok=True)

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "glm-ocr:latest")

def _candidate_hosts() -> list[str]:
    if h := os.getenv("OLLAMA_HOST"):
        return [h]
    hosts = ["http://localhost:11434"]
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                m = re.match(r"^nameserver\s+(\S+)", line)
                if m:
                    hosts.append(f"http://{m.group(1)}:11434")
    except FileNotFoundError:
        pass
    return hosts

OLLAMA_HOSTS = _candidate_hosts()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "glm-ocr:latest")
print(f"[CONFIG] Ollama hosts: {OLLAMA_HOSTS}, model: {OLLAMA_MODEL}")

app = FastAPI(title="GLM OCR Web App Bis")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MIME_MAP = {".css": "text/css", ".js": "application/javascript", ".html": "text/html", ".png": "image/png"}


def _page_path(file_id: str, page: int) -> Path:
    return UPLOAD_DIR / file_id / f"page_{page:04d}.png"


def _meta_path(file_id: str) -> Path:
    return UPLOAD_DIR / file_id / "meta.json"


def _ocr_path(file_id: str, page: int) -> Path:
    return UPLOAD_DIR / file_id / f"ocr_{page:04d}.md"


# ── API routes ──────────────────────────────────────────────

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    file_id = uuid.uuid4().hex[:12]
    file_dir = UPLOAD_DIR / file_id
    file_dir.mkdir(exist_ok=True)

    raw_bytes = await file.read()
    ext = Path(file.filename).suffix.lower()

    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"):
        img = Image.open(BytesIO(raw_bytes)).convert("RGB")
        img.save(file_dir / "page_0001.png", "PNG")
        total_pages = 1
    elif ext == ".pdf":
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        total_pages = len(doc)
        for i in range(total_pages):
            pix = doc[i].get_pixmap(dpi=15)
            async with aiofiles.open(_page_path(file_id, i + 1), "wb") as f:
                await f.write(pix.tobytes("png"))
        doc.close()
    else:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    meta = {"filename": file.filename, "total_pages": total_pages}
    async with aiofiles.open(_meta_path(file_id), "w") as f:
        await f.write(json.dumps(meta))
    return {"file_id": file_id, "filename": file.filename, "total_pages": total_pages}


@app.get("/api/pages/{file_id}/{page}")
async def get_page(file_id: str, page: int):
    path = _page_path(file_id, page)
    if not path.exists():
        raise HTTPException(404, "Page not found")
    return FileResponse(str(path), media_type="image/png")


@app.get("/api/meta/{file_id}")
async def get_meta(file_id: str):
    path = _meta_path(file_id)
    if not path.exists():
        raise HTTPException(404, "File not found")
    async with aiofiles.open(path) as f:
        return json.loads(await f.read())


async def _call_ollama(img_path: Path) -> str:
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "Please recognize all text, tables, and content in this image. Return the result in clean Markdown format, preserving the original structure including tables, headers, lists, and code blocks.",
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0},
    }
    last_err = None
    for host in OLLAMA_HOSTS:
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                resp = await client.post(f"{host}/api/generate", json=payload)
                resp.raise_for_status()
                return resp.json().get("response", "")
        except httpx.TimeoutException as e:
            last_err = e
            continue
        except httpx.RequestError as e:
            last_err = e
            continue
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"Ollama error at {host}: {e.response.status_code} {e.response.text}")
    err_type = type(last_err).__name__ if last_err else "sconosciuto"
    msg = (
        f"Ollama non risponde dopo il tentativo di tutti gli host. "
        f"Host provati: {OLLAMA_HOSTS}. "
        f"Ultimo errore: {err_type}. "
        f"Se Ollama gira su Windows (non in WSL), esegui in Windows: "
        f"set OLLAMA_HOST=0.0.0.0 && ollama serve. "
        f"Se sei su CPU, il modello potrebbe essere troppo lento: "
        f"riduci la risoluzione (dpi) o usa una GPU."
    )
    raise HTTPException(502, msg)


@app.post("/api/ocr/{file_id}/{page}")
async def run_ocr(file_id: str, page: int):
    img_path = _page_path(file_id, page)
    if not img_path.exists():
        raise HTTPException(404, "Page not found")

    ocr_out = _ocr_path(file_id, page)
    if ocr_out.exists():
        async with aiofiles.open(ocr_out) as f:
            return {"file_id": file_id, "page": page, "markdown": await f.read()}

    markdown = await _call_ollama(img_path)
    async with aiofiles.open(ocr_out, "w") as f:
        await f.write(markdown)
    return {"file_id": file_id, "page": page, "markdown": markdown}


@app.get("/api/ocr/{file_id}/{page}")
async def get_ocr(file_id: str, page: int):
    ocr_out = _ocr_path(file_id, page)
    if not ocr_out.exists():
        raise HTTPException(404, "OCR not run yet for this page")
    async with aiofiles.open(ocr_out) as f:
        return {"file_id": file_id, "page": page, "markdown": await f.read()}


@app.post("/api/ocr-all/{file_id}")
async def ocr_all(file_id: str):
    meta_path = _meta_path(file_id)
    if not meta_path.exists():
        raise HTTPException(404, "File not found")
    async with aiofiles.open(meta_path) as f:
        meta = json.loads(await f.read())
    total = meta["total_pages"]

    results = {}
    for p in range(1, total + 1):
        ocr_out = _ocr_path(file_id, p)
        if ocr_out.exists():
            async with aiofiles.open(ocr_out) as f:
                results[p] = {"markdown": await f.read()}
        else:
            try:
                markdown = await _call_ollama(_page_path(file_id, p))
                async with aiofiles.open(ocr_out, "w") as f:
                    await f.write(markdown)
                results[p] = {"markdown": markdown}
            except Exception as e:
                results[p] = {"error": str(e)}
    return {"file_id": file_id, "results": results}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── Frontend SPA catch-all ─────────────────────────────────

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    target = FRONTEND_DIR / (full_path or "index.html")
    if not target.exists() or not target.is_file():
        target = FRONTEND_DIR / "index.html"
    suffix = target.suffix
    media_type = MIME_MAP.get(suffix, "text/html")
    return HTMLResponse(target.read_bytes(), media_type=media_type)
