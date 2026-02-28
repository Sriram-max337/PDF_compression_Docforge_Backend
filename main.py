import os
import platform
import shutil
import subprocess
import tempfile
from enum import Enum

from fastapi import FastAPI, File, Query, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from convert import convert_to_pdf, ALLOWED_EXTENSIONS

app = FastAPI(title="Docforge — PDF Toolkit API")

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


# ---------------------------------------------------------------------------
# File → PDF conversion endpoint
# ---------------------------------------------------------------------------
@app.post("/convert-to-pdf")
async def convert_file_to_pdf(
    file: UploadFile = File(...),
):
    """Accept an office document upload, convert it to PDF via LibreOffice,
    and return the PDF for download."""

    # --- Validate extension ---------------------------------------------------
    original_name = file.filename or "upload"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Accepted types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    # --- Save upload to a temp directory --------------------------------------
    tmp_dir = tempfile.mkdtemp()
    input_path = os.path.join(tmp_dir, original_name)

    try:
        with open(input_path, "wb") as f:
            f.write(await file.read())

        pdf_path = convert_to_pdf(input_path, tmp_dir)

        pdf_download_name = os.path.splitext(original_name)[0] + ".pdf"

        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=pdf_download_name,
            # Clean up the temp directory after the response is sent
            background=BackgroundTask(shutil.rmtree, tmp_dir, ignore_errors=True),
        )

    except RuntimeError as exc:
        # Clean up on error
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during conversion: {exc}",
        )
