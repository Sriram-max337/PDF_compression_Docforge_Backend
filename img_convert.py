"""
Docforge — Image (PNG / JPG / JPEG) to PDF conversion using Pillow.
"""

import os

from PIL import Image

ALLOWED_IMAGE_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg"}


def image_to_pdf(src_path: str, out_dir: str) -> str:
    """
    Convert an image file to a single-page PDF.

    Parameters
    ----------
    src_path : str
        Absolute path to the source image (PNG / JPG / JPEG).
    out_dir : str
        Directory where the output PDF will be written.

    Returns
    -------
    str
        Absolute path to the generated PDF.

    Raises
    ------
    RuntimeError
        If the image cannot be opened or converted.
    """
    try:
        img = Image.open(src_path)
    except Exception as exc:
        raise RuntimeError(f"Cannot open image: {exc}") from exc

    # Convert to RGB if needed (e.g. RGBA PNGs can't be saved directly as PDF)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    base_name = os.path.splitext(os.path.basename(src_path))[0]
    pdf_path = os.path.join(out_dir, f"{base_name}.pdf")

    try:
        img.save(pdf_path, "PDF", resolution=100.0)
    except Exception as exc:
        raise RuntimeError(f"Failed to save PDF: {exc}") from exc

    if not os.path.isfile(pdf_path):
        raise RuntimeError("Image-to-PDF conversion produced no output.")

    return pdf_path
