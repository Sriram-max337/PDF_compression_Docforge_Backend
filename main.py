import os
import platform
import subprocess
import tempfile
from enum import Enum

from fastapi import FastAPI, File, Query, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

app = FastAPI(title="Docforge — PDF Compression API")

# ---------------------------------------------------------------------------
# CORS — allow any frontend origin during development
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Compression helpers
# ---------------------------------------------------------------------------
GS_BIN = (
    r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe"
    if platform.system() == "Windows"
    else "gs"
)


class CompressionLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


LEVEL_TO_SETTING = {
    CompressionLevel.low: "/prepress",
    CompressionLevel.medium: "/ebook",
    CompressionLevel.high: "/screen",
}

# Order used when iterating toward a target file size
LEVELS_ASCENDING = [CompressionLevel.low, CompressionLevel.medium, CompressionLevel.high]


def _compress_pdf(src: str, dst: str, level: CompressionLevel) -> None:
    """Run Ghostscript to compress *src* into *dst*."""
    setting = LEVEL_TO_SETTING[level]
    cmd = [
        GS_BIN,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={setting}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={dst}",
        src,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "Ghostscript failed")


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@app.post("/compress-pdf")
async def compress_pdf(
    file: UploadFile = File(...),
    compression_level: CompressionLevel = Query(
        CompressionLevel.medium,
        description="low (best quality), medium (balanced), high (smallest size)",
    ),
    target_size_mb: float | None = Query(
        None,
        description="Optional target file size in MB. If set, the API will try "
        "increasingly aggressive compression to meet it.",
    ),
):
    """Accept a PDF upload, compress it with Ghostscript, and return the result."""

    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF.")

    # Save upload to a temp file
    tmp_dir = tempfile.mkdtemp()
    input_path = os.path.join(tmp_dir, "input.pdf")
    output_path = os.path.join(tmp_dir, "compressed.pdf")

    try:
        with open(input_path, "wb") as f:
            f.write(await file.read())

        if target_size_mb is not None:
            # Iterate through compression levels until size target is met
            target_bytes = target_size_mb * 1024 * 1024
            for level in LEVELS_ASCENDING:
                _compress_pdf(input_path, output_path, level)
                if os.path.getsize(output_path) <= target_bytes:
                    break
        else:
            _compress_pdf(input_path, output_path, compression_level)

        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="Compression produced no output.")

        original = os.path.getsize(input_path)
        compressed = os.path.getsize(output_path)

        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=f"compressed_{file.filename}",
            headers={
                "X-Original-Size": str(original),
                "X-Compressed-Size": str(compressed),
            },
        )

    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
