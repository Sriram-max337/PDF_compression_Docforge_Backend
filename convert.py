"""
Docforge — File-to-PDF conversion via LibreOffice headless.

Supported input formats: doc, docx, ppt, pptx, xls, xlsx, txt.
"""

import glob
import os
import platform
import shutil
import subprocess

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS: set[str] = {
    ".doc", ".docx",
    ".ppt", ".pptx",
    ".xls", ".xlsx",
    ".txt",
}

# Locate LibreOffice binary based on platform
if platform.system() == "Windows":
    _candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    LIBREOFFICE_BIN = next((p for p in _candidates if os.path.isfile(p)), "soffice")
else:
    LIBREOFFICE_BIN = "soffice"


# ---------------------------------------------------------------------------
# Conversion helper
# ---------------------------------------------------------------------------
def convert_to_pdf(src_path: str, out_dir: str) -> str:
    """
    Convert *src_path* to PDF using LibreOffice headless mode.

    To avoid issues with spaces / special characters in filenames,
    the source file is copied to a safe name (``inputfile.<ext>``)
    inside *out_dir* before conversion.  After conversion the
    output directory is scanned for **any** ``.pdf`` file rather
    than assuming a specific filename.

    Returns the absolute path of the resulting PDF file.

    Raises
    ------
    RuntimeError
        If LibreOffice exits with a non-zero code or no PDF is produced.
    """
    # --- Rename to a safe filename to avoid LibreOffice quirks ----------------
    ext = os.path.splitext(os.path.basename(src_path))[1].lower()
    safe_name = f"inputfile{ext}"
    safe_path = os.path.join(out_dir, safe_name)

    if os.path.abspath(src_path) != os.path.abspath(safe_path):
        shutil.copy2(src_path, safe_path)

    # --- Run LibreOffice ------------------------------------------------------
    cmd = [
        LIBREOFFICE_BIN,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", out_dir,
        safe_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        raise RuntimeError(
            f"LibreOffice conversion failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip() or 'unknown error'}"
        )

    # --- Find generated PDF (don't assume exact name) -------------------------
    pdf_files = glob.glob(os.path.join(out_dir, "*.pdf"))
    if not pdf_files:
        raise RuntimeError(
            "LibreOffice did not produce any PDF output. "
            f"Contents of output dir: {os.listdir(out_dir)}"
        )

    # Return the first (and usually only) PDF found
    return pdf_files[0]
