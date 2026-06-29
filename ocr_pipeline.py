import importlib.util
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

from lmstudio_client import LMStudioClient, LMStudioClientError
from pdf_utils import PDFPage, load_pdf

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"


def load_model_config(model_name: str) -> dict:
    config_path = MODELS_DIR / model_name / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config not found for model '{model_name}' at {config_path}"
        )
    return json.loads(config_path.read_text(encoding="utf-8"))


def load_model_prompts(model_name: str) -> dict:
    prompts_path = MODELS_DIR / model_name / "prompts.py"
    if not prompts_path.exists():
        raise FileNotFoundError(
            f"prompts.py not found for model '{model_name}' at {prompts_path}"
        )
    spec = importlib.util.spec_from_file_location(
        f"models.{model_name}.prompts", str(prompts_path)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PROMPTS


class PageResult:
    def __init__(
        self,
        page_num: int,
        method: str,
        processing_time: float,
        image_size: tuple[int, int],
        native_chars: int = 0,
        output_chars: int = 0,
        status: str = "ok",
    ):
        self.page_num = page_num
        self.method = method
        self.processing_time = processing_time
        self.image_size = image_size
        self.native_chars = native_chars
        self.output_chars = output_chars
        self.status = status

    def to_dict(self) -> dict:
        return {
            "page": self.page_num,
            "method": self.method,
            "processing_time_s": round(self.processing_time, 2),
            "image_size": list(self.image_size),
            "native_chars": self.native_chars,
            "output_chars": self.output_chars,
            "status": self.status,
        }


class OCRPipeline:
    def __init__(
        self,
        client: LMStudioClient,
        output_dir: Path,
        formats: list[str],
        model_name: str = "chandra-ocr-2",
        mode: str = "text-first",
        dpi: int = 200,
        resume: bool = False,
        basename: str = "documento",
    ):
        self.client = client
        self.output_dir = output_dir
        self.formats = formats
        self.model_name = model_name
        self.model_config = load_model_config(model_name)
        self.prompts = load_model_prompts(model_name)
        self._output_is_html = self.model_config.get("default_prompt_format", "html") == "html"
        self._use_system_prompt = self.model_config.get("use_system_prompt", True)
        self._use_native_ref = self.model_config.get("use_native_text_reference", True)
        self._use_image_only = self.model_config.get("use_image_only", False)
        self._use_multi_image = self.model_config.get("use_multi_image", False)
        self._batch_size = self.model_config.get("batch_size", 0)
        self._max_tokens = self.model_config.get("max_tokens", 48000)
        self.mode = mode
        self.dpi = dpi
        self.resume = resume
        self.basename = basename
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _partial_path(self, page_num: int, fmt: str) -> Path:
        return self.output_dir / f"page_{page_num:04d}.{fmt}.partial"

    EXT_MAP = {"markdown": "md", "html": "html", "json": "json"}

    def _output_path(self, fmt: str) -> Path:
        ext = self.EXT_MAP.get(fmt, fmt)
        return self.output_dir / f"{self.basename}.{ext}"

    def _metadata_path(self) -> Path:
        return self.output_dir / f"{self.basename}.metadata.json"

    def _load_partial(self, page_num: int, fmt: str) -> Optional[str]:
        path = self._partial_path(page_num, fmt)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def _save_partial(self, page_num: int, fmt: str, content: str):
        self._partial_path(page_num, fmt).write_text(content, encoding="utf-8")

    def _save_metadata(self, results: list[PageResult]):
        data = [r.to_dict() for r in results]
        self._metadata_path().write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _strip_html_attrs(html: str) -> str:
        html = re.sub(r'\sdata-[a-zA-Z_-]+="[^"]*"', '', html)
        html = re.sub(r"\sdata-[a-zA-Z_-]+='[^']*'", '', html)
        html = re.sub(r'\s(class|style|id|data)="[^"]*"', '', html)
        html = re.sub(r"\s(class|style|id|data)='[^']*'", '', html)
        return html

    @staticmethod
    def _html_to_markdown(html: str) -> str:
        html = OCRPipeline._strip_html_attrs(html)

        # Fecha tags não fechadas pelo modelo
        for tag in ('table', 'div', 'ol', 'ul', 'p', 'pre'):
            if f'<{tag}' in html and f'</{tag}>' not in html:
                html += f'</{tag}>'

        html = re.sub(r'<h([1-6])[^>]*>(.*?)</h\1>', lambda m: '#' * int(m.group(1)) + ' ' + m.group(2), html, flags=re.DOTALL)

        html = re.sub(r'<table[^>]*>(.*?)</table>', lambda m: OCRPipeline._table_to_markdown(m.group(1)), html, flags=re.DOTALL)

        html = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', html, flags=re.DOTALL)
        html = re.sub(r'</?u?[ol][^>]*>', '', html)

        html = re.sub(r'<br\s*/?>\s*<br\s*/?>', '\n\n', html)
        html = re.sub(r'<br\s*/?>', '\n', html)

        def _replace_p(m: re.Match) -> str:
            content = m.group(1)
            content = re.sub(r'\s+', ' ', content).strip()
            return content + '\n' if content else ''

        html = re.sub(r'<p[^>]*>(.*?)</p>', _replace_p, html, flags=re.DOTALL)
        html = re.sub(r'<div[^>]*>(.*?)</div>', r'\1', html, flags=re.DOTALL)
        html = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', html, flags=re.DOTALL)

        html = re.sub(r'<a[^>]*>(.*?)</a>', r'\1', html)

        html = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*/>', r'[Imagem: \1]', html)
        html = re.sub(r'<img[^>]*/>', '', html)

        html = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html, flags=re.DOTALL)
        html = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', html, flags=re.DOTALL)
        html = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html, flags=re.DOTALL)
        html = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', html, flags=re.DOTALL)
        html = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html, flags=re.DOTALL)
        html = re.sub(r'<pre[^>]*>(.*?)</pre>', r'```\n\1\n```', html, flags=re.DOTALL)
        html = re.sub(r'<pre>(.*?)</pre>', r'```\n\1\n```', html, flags=re.DOTALL)

        html = re.sub(r'<th[^>]*>(.*?)</th>', r'\1', html, flags=re.DOTALL)
        html = re.sub(r'<td[^>]*>(.*?)</td>', r'\1', html, flags=re.DOTALL)
        html = re.sub(r'</?tr[^>]*>', '\n', html)
        html = re.sub(r'</?thead[^>]*>', '', html)
        html = re.sub(r'</?tbody[^>]*>', '', html)
        html = re.sub(r'</?caption[^>]*>', '', html)

        html = re.sub(r'</?h[1-6][^>]*>', '', html)

        html = re.sub(r'<[^>]+>', '', html)
        html = re.sub(r'<![^>]+>', '', html)

        html = re.sub(r'  +', ' ', html)
        html = re.sub(r'\n{3,}', '\n\n', html)
        html = re.sub(r'\n[ \t]+\n', '\n\n', html)
        html = re.sub(r'[ \t]+\n', '\n', html)

        return html.strip()

    @staticmethod
    def _table_to_markdown(table_html: str) -> str:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, flags=re.DOTALL)
        if not rows:
            return table_html

        md_rows = []
        for row in rows:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, flags=re.DOTALL)
            cell_texts = []
            for c in cells:
                clean = re.sub(r'<[^>]+>', '', c).strip()
                cell_texts.append(clean)
            md_rows.append("| " + " | ".join(cell_texts) + " |")

        if not md_rows:
            return ""

        header_idx = None
        for i, row in enumerate(rows):
            if re.search(r'<th', row, re.IGNORECASE):
                header_idx = i
                break

        result = "\n".join(md_rows) + "\n"

        if header_idx is not None:
            header_cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', rows[header_idx], flags=re.DOTALL)
            sep = "| " + " | ".join(["---"] * len(header_cells)) + " |"
            lines = list(md_rows)
            lines.insert(header_idx + 1, sep)
            result = "\n".join(lines) + "\n"

        return result

    _REASONING_PREFIXES = (
        "the user wants", "the user asks", "the user provided",
        "the image is", "the image shows", "the document contains",
        "the screenshot", "the picture",
        "i can see", "i need to", "i will", "i think",
        "let me", "looking at", "this is a",
        "here is", "here's",
    )

    def _is_html_content(self, content: str) -> bool:
        stripped = content.strip()
        return bool(
            stripped.lower().startswith("<table")
            or stripped.lower().startswith("<html")
            or stripped.lower().startswith("<div")
            or stripped.lower().startswith("<h")
            or "<table" in stripped.lower()[:500]
        )

    def _strip_reasoning(self, content: str) -> str:
        lines = content.split("\n")
        cleaned = []
        found_content = False
        for line in lines:
            lower = line.strip().lower()
            if not found_content:
                if any(lower.startswith(p) for p in self._REASONING_PREFIXES):
                    continue
                if not line.strip():
                    continue
                found_content = True
            cleaned.append(line)
        if not cleaned:
            return content
        return "\n".join(cleaned)

    def _extract_html(self, content: str) -> str:
        start = re.search(r'<[a-zA-Z]', content)
        if not start:
            return ""
        html_part = content[start.start():]
        html_part = re.sub(r'\n\s*\[.*?(\[.*?\])\s*\]\s*$', '', html_part, flags=re.DOTALL)
        html_part = re.sub(r'\n\s*\{.*\}\s*$', '', html_part, flags=re.DOTALL)
        html_part = re.sub(r'\n\s*\[', '', html_part)
        return html_part.strip()

    def _strip_metadata_prefix(self, content: str) -> str:
        content = re.sub(
            r'^\[\s*\{[^}]*"label"[^}]*"bbox"[^}]*\}\s*(,\s*\{[^}]*"label"[^}]*"bbox"[^}]*\})*\s*\]\s*\n*',
            '', content, flags=re.DOTALL
        )
        return content

    def _strip_trailing_commentary(self, content: str) -> str:
        matches = list(re.finditer(r'</([a-zA-Z]+)>', content))
        if not matches:
            return content
        content = content[:matches[-1].end()]
        return content.strip()

    @staticmethod
    def _strip_det_format(content: str) -> str:
        content = re.sub(r'<\|det\|>[^<]*?(<\|/det\|>)?', '', content)
        content = re.sub(r'<\|/det\|>', '', content)
        content = re.sub(r'\n{3,}', '\n\n', content)
        return content.strip()

    @staticmethod
    def _strip_repetition(content: str, max_repeat: int = 5, min_ngram: int = 10) -> str:
        lines = content.split("\n")
        exact: dict[str, int] = {}
        prefix: dict[str, int] = {}
        cutoff = len(lines)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if len(stripped) < min_ngram:
                continue
            exact[stripped] = exact.get(stripped, 0) + 1
            if exact[stripped] > max_repeat:
                cutoff = i
                break
            pref = stripped[:40]
            prefix[pref] = prefix.get(pref, 0) + 1
            if prefix[pref] > max_repeat * 2:
                cutoff = i
                break
        return "\n".join(lines[:cutoff]).strip()

    def _append_saida(self, fmt: str, content: str):
        if fmt == "json":
            return
        content = self._strip_reasoning(content)
        content = self._strip_det_format(content)
        content = self._strip_metadata_prefix(content)
        content = self._strip_repetition(content)
        if fmt == "markdown" and (self._output_is_html or self._is_html_content(content)):
            if not self._use_image_only:
                content = self._strip_trailing_commentary(content)
            content = self._html_to_markdown(content)
        if fmt == "html":
            content = self._extract_html(content)
            if not content:
                logger.warning("Model returned no HTML content for format=html")
                return
        path = self._output_path(fmt)
        with path.open("a", encoding="utf-8") as f:
            if path.exists() and path.stat().st_size > 0:
                f.write("\n\n")
            f.write(content)
        logger.info("Incremental %s.%s updated (page appended)", self.basename, fmt)

    def _consolidate_json(self):
        if "json" not in self.formats:
            return
        parts = []
        for partial in sorted(self.output_dir.glob("page_*.json.partial")):
            parts.append(partial.read_text(encoding="utf-8"))
        if not parts:
            return
        combined = "[\n" + ",\n".join(parts) + "\n]"
        self._output_path("json").write_text(combined, encoding="utf-8")
        logger.info("Saved %s", self._output_path("json"))

    _STOPWORDS = frozenset({
        "a", "about", "above", "after", "again", "against", "all", "am", "an",
        "and", "any", "are", "as", "at", "be", "because", "been", "before",
        "being", "below", "between", "both", "but", "by", "can", "could",
        "did", "do", "does", "doing", "don", "down", "during", "each", "few",
        "for", "from", "further", "had", "has", "have", "having", "he", "her",
        "here", "hers", "herself", "him", "himself", "his", "how", "i", "if",
        "in", "into", "is", "it", "its", "itself", "just", "me", "more",
        "most", "my", "myself", "no", "nor", "not", "now", "of", "on", "once",
        "only", "or", "other", "our", "ours", "ourselves", "out", "over",
        "own", "per", "que", "s", "same", "she", "should", "so", "some",
        "such", "t", "than", "that", "the", "their", "them", "themselves",
        "then", "there", "these", "they", "this", "those", "through", "to",
        "too", "under", "until", "up", "us", "very", "was", "we", "were",
        "what", "when", "where", "which", "while", "who", "whom", "why",
        "will", "with", "you", "your", "yours", "yourself", "yourselves",
        "da", "das", "de", "do", "dos", "em", "na", "nas", "no", "nos",
        "num", "numa", "numas", "nuns", "o", "os", "para", "pelo", "pela",
        "pelos", "pelas", "por", "se", "suas", "um", "uma", "umas", "uns",
    })

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        words = re.findall(r"[a-zA-Z]{4,}", text.lower())
        return {w for w in words if w not in OCRPipeline._STOPWORDS}

    @staticmethod
    def _extract_numbers(text: str) -> set[str]:
        return set(re.findall(r"\b\d+(?:[.,]\d+)+\b|\b\d{2,}\b", text))

    @staticmethod
    def _extract_headings(text: str) -> list[str]:
        return re.findall(r"^#{1,6}\s.+", text, re.MULTILINE)

    def _content_overlap(self, native: str, output: str) -> dict:
        native_words = self._tokenize(native)
        output_words = self._tokenize(output)
        shared = native_words & output_words

        native_nums = self._extract_numbers(native)
        output_nums = self._extract_numbers(output)
        num_shared = native_nums & output_nums

        word_recall = (len(shared) / max(len(native_words), 1)) * 100
        num_recall = (len(num_shared) / max(len(native_nums), 1)) * 100
        out_headings = self._extract_headings(output)

        return {
            "word_recall_pct": round(word_recall, 1),
            "num_recall_pct": round(num_recall, 1),
            "native_words": len(native_words),
            "output_words": len(output_words),
            "shared_words": len(shared),
            "native_numbers": len(native_nums),
            "output_numbers": len(output_nums),
            "shared_numbers": len(num_shared),
            "output_headings": len(out_headings),
        }

    def _verify_completeness(self, pages: list[PDFPage], results: list[PageResult]):
        total_pages = len(pages)
        fmt = self.formats[0]
        path = self._output_path(fmt)
        if not path.exists() or not path.stat().st_size:
            logger.warning("No output files found")
            return

        found_pages = set()
        for partial in self.output_dir.glob(f"page_*.{fmt}.partial"):
            try:
                num = int(partial.stem.split("_")[1].split(".")[0])
                found_pages.add(num)
            except (ValueError, IndexError):
                pass
        found = len(found_pages)
        missing = sorted(set(range(1, total_pages + 1)) - found_pages)

        if missing:
            logger.warning(
                "%s: %d/%d pages. Missing pages: %s",
                path, found, total_pages, missing,
            )
        else:
            logger.info(
                "%s: all %d/%d pages present",
                path, found, total_pages,
            )

        ok_results = [r for r in results if r.status in ("ok", "resumed")]
        if not ok_results:
            return

        combined_native = "\n".join(
            pages[r.page_num - 1].native_text
            for r in ok_results
            if r.page_num - 1 < len(pages)
        )
        combined_output = path.read_text(encoding="utf-8")

        if not combined_native.strip():
            logger.info("No native text available for content comparison")
            return

        stats = self._content_overlap(combined_native, combined_output)

        scores = []
        if stats["native_words"] > 0:
            scores.append(("vocabulary recall", stats["word_recall_pct"], 80.0))
        if stats["native_numbers"] > 0:
            scores.append(("number preservation", stats["num_recall_pct"], 90.0))

        all_ok = True
        for label, value, threshold in scores:
            status = "OK" if value >= threshold else "LOW"
            if value < threshold:
                all_ok = False
            logger.info(
                "  %s: %.1f%% (%s, threshold: %.0f%%)",
                label, value, status, threshold,
            )

        logger.info(
            "  vocabulary: %d shared / %d native words",
            stats["shared_words"], stats["native_words"],
        )
        if stats["native_numbers"] > 0:
            logger.info(
                "  numbers: %d shared / %d native numbers",
                stats["shared_numbers"], stats["native_numbers"],
            )
        if stats["output_headings"] > 0:
            logger.info(
                "  headings detected in output: %d",
                stats["output_headings"],
            )

        if all_ok and not missing:
            logger.info("Fidelity: PASS (all checks OK)")
        else:
            issues = []
            if missing:
                issues.append(f"{len(missing)} missing pages")
            for label, value, threshold in scores:
                if value < threshold:
                    issues.append(f"{label} {value:.0f}% < {threshold:.0f}%")
            logger.warning("Fidelity: PARTIAL - %s", "; ".join(issues))

    def process_page(self, page: PDFPage, fmt: str) -> str:
        prompt_fmt = self.model_config.get("default_prompt_format", "html")
        actual_fmt = prompt_fmt if fmt == "markdown" else fmt
        prompt = self.prompts[actual_fmt]

        system_prompt = "" if not self._use_system_prompt else None

        if self._use_image_only:
            return self.client.ocr_image("", page.image, system_prompt="")
        elif self.mode == "text-first" and page.native_text and self._use_native_ref:
            enhanced_prompt = (
                f"{prompt}\n\n"
                f"As reference, here is the raw extracted text from this page "
                f"(may have OCR errors or wrong order - use the image as source of truth):\n"
                f"---\n{page.native_text}\n---"
            )
            return self.client.ocr_image(enhanced_prompt, page.image, system_prompt=system_prompt)
        else:
            return self.client.ocr_image(prompt, page.image, system_prompt=system_prompt)

    def _process_batch(self, pages: list[PDFPage], fmt: str) -> str:
        images = [p.image for p in pages]
        return self.client.ocr_images("", images, system_prompt="")

    def _prepare_outputs(self):
        for fmt in self.formats:
            path = self._output_path(fmt)
            if fmt == "json":
                path.write_text("[\n", encoding="utf-8")
            else:
                path.write_text("", encoding="utf-8")

    def run(self, pdf_path: Path) -> list[PageResult]:
        pages = load_pdf(pdf_path, dpi=self.dpi, mode=self.mode)
        results: list[PageResult] = []
        total = len(pages)

        logger.info(
            "Processing %d pages with mode=%s, formats=%s",
            total, self.mode, self.formats,
        )

        if not self.resume:
            self._prepare_outputs()

        for idx, page in enumerate(pages):
            page_num = page.page_num

            if self.resume:
                all_formats_done = all(
                    self._load_partial(page_num, fmt) is not None
                    for fmt in self.formats
                )
                if all_formats_done:
                    logger.info("Page %d/%d already processed, skipping", page_num, total)
                    results.append(PageResult(
                        page_num=page_num,
                        method="native_text" if page.native_text else "ocr",
                        processing_time=0.0,
                        image_size=page.image.size,
                        native_chars=len(page.native_text),
                        status="resumed",
                    ))
                    continue

            method = "native_text" if (self.mode == "text-first" and page.native_text) else "ocr"
            start = time.time()
            status = "ok"
            output_chars = 0

            try:
                for fmt in self.formats:
                    logger.info(
                        "Page %d/%d [%s] format=%s ...",
                        page_num, total, method, fmt,
                    )
                    content = self.process_page(page, fmt)
                    self._save_partial(page_num, fmt, content)
                    self._append_saida(fmt, content)
                    output_chars = len(content)

            except LMStudioClientError as e:
                logger.error("Page %d failed: %s", page_num, e)
                status = f"error: {e}"

            elapsed = time.time() - start
            results.append(PageResult(
                page_num=page_num,
                method=method,
                processing_time=elapsed,
                image_size=page.image.size,
                native_chars=len(page.native_text),
                output_chars=output_chars,
                status=status,
            ))

            logger.info("Page %d/%d done in %.1fs [%s]", page_num, total, elapsed, method)

        self._consolidate_json()
        self._save_metadata(results)
        self._verify_completeness(pages, results)

        ok_count = sum(1 for r in results if r.status in ("ok", "resumed"))
        all_ok = ok_count == total

        if all_ok:
            for partial in self.output_dir.glob("page_*.partial"):
                partial.unlink()
            metadata = self._metadata_path()
            if metadata.exists():
                metadata.unlink()
            logger.info("Arquivos temporarios limpos")

        logger.info("Pipeline finished: %d/%d pages OK", ok_count, total)

        return results
