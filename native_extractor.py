import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx not installed. Run: pip install python-docx")
    doc = Document(str(path))
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            lines.append("")
            continue
        style = para.style.name.lower() if para.style else ""
        if "heading" in style:
            level = 1
            for s in ("heading 1", "heading 2", "heading 3", "heading 4", "heading 5", "heading 6"):
                if s in style:
                    level = int(s.split()[-1])
                    break
            lines.append(f"{'#' * level} {text}")
        else:
            lines.append(text)

    for table in doc.tables:
        lines.append("")
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")

    return "\n".join(lines)


def extract_pptx(path: Path) -> str:
    try:
        from pptx import Presentation
    except ImportError:
        raise ImportError("python-pptx not installed. Run: pip install python-pptx")
    prs = Presentation(str(path))
    lines = []
    for slide_num, slide in enumerate(prs.slides, 1):
        lines.append(f"## Slide {slide_num}")
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        lines.append(text)
            if shape.has_table:
                table = shape.table
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def extract_html(path: Path) -> str:
    content = path.read_text(encoding="utf-8", errors="replace")
    try:
        import html2text
        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_tables = False
        return h.handle(content).strip()
    except ImportError:
        pass
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text
    except ImportError:
        pass
    import re
    clean = re.sub(r"<[^>]+>", " ", content)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


EXTRACTORS = {
    ".docx": extract_docx,
    ".pptx": extract_pptx,
    ".html": extract_html,
    ".htm": extract_html,
}


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    extractor = EXTRACTORS.get(ext)
    if not extractor:
        raise ValueError(f"Unsupported format: {ext}")
    logger.info("Extracting native text from %s file: %s", ext, path.name)
    return extractor(path)
