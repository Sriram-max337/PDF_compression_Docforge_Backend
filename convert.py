"""
Docforge — File-to-PDF conversion via LibreOffice headless.

Supported input formats: doc, docx, ppt, pptx, xls, xlsx, txt.
"""

import os
import platform
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
    # Common default install paths on Windows
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

    The generated PDF is written into *out_dir*.
    Returns the absolute path of the resulting PDF file.

    Raises
    ------
    RuntimeError
        If LibreOffice exits with a non-zero code or no PDF is produced.
    """
    cmd = [
        LIBREOFFICE_BIN,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", out_dir,
        src_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        raise RuntimeError(
            f"LibreOffice conversion failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip() or 'unknown error'}"
        )

    # LibreOffice writes <original_stem>.pdf into out_dir
    base_name = os.path.splitext(os.path.basename(src_path))[0]
    pdf_path = os.path.join(out_dir, f"{base_name}.pdf")

    if not os.path.isfile(pdf_path):
        raise RuntimeError(
            "LibreOffice did not produce the expected PDF output. "
            f"Looked for: {pdf_path}"
        )

    return pdf_path
