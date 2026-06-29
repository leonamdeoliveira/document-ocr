import logging
from pathlib import Path

import fitz
from PIL import Image

logger = logging.getLogger(__name__)


class PDFPage:
    def __init__(self, page_num: int, image: Image.Image, native_text: str = ""):
        self.page_num = page_num
        self.image = image
        self.native_text = native_text.strip()


def render_page(page: fitz.Page, dpi: int = 200) -> Image.Image:
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def extract_native_text(page: fitz.Page) -> str:
    return page.get_text("text", sort=True)


def has_meaningful_text(text: str, min_chars: int = 50) -> bool:
    stripped = text.strip()
    return len(stripped) >= min_chars


def load_pdf(
    path: Path, dpi: int = 200, mode: str = "text-first"
) -> list[PDFPage]:
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(str(path))
    try:
        pages: list[PDFPage] = []
        logger.info("PDF has %d pages", len(doc))

        for i in range(len(doc)):
            page = doc[i]
            page_num = i + 1

            native_text = extract_native_text(page)
            image = render_page(page, dpi=dpi)

            if mode == "text-first" and has_meaningful_text(native_text):
                logger.info("Page %d: using native text", page_num)
            else:
                logger.info("Page %d: will use OCR", page_num)

            pages.append(PDFPage(page_num=page_num, image=image, native_text=native_text))

        return pages
    finally:
        doc.close()
