import logging
import time

from ocr_engine.base import (
    OCREngineBase,
    OCREngineError,
    EngineNotAvailableError,
    EngineResult,
)
from pdf_utils import PDFPage

logger = logging.getLogger(__name__)


class PaddleEngine(OCREngineBase):

    def __init__(self, langs: str = "por+eng"):
        self._langs = langs
        self._ocr = None
        self._available = None

    @property
    def name(self) -> str:
        return "paddle"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from paddleocr import PaddleOCR
            self._available = True
        except ImportError:
            logger.warning("PaddleOCR not available. Install paddleocr.")
            self._available = False
        return self._available

    def _get_ocr(self):
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
                lang = self._langs.split("+")[0] if "+" in self._langs else self._langs
                self._ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
            except ImportError as e:
                raise EngineNotAvailableError(f"PaddleOCR not installed: {e}") from e
        return self._ocr

    def supports(self, page: PDFPage) -> bool:
        return True

    def extract_text(self, page: PDFPage, **kwargs) -> EngineResult:
        if not self.is_available():
            raise EngineNotAvailableError("PaddleOCR is not installed")

        import numpy as np

        ocr = self._get_ocr()
        start = time.time()

        img_array = np.array(page.image.convert("RGB"))
        try:
            result = ocr.ocr(img_array, cls=True)
        except Exception as e:
            raise OCREngineError(f"PaddleOCR failed: {e}") from e

        if not result or not result[0]:
            elapsed = time.time() - start
            return EngineResult(
                text="",
                engine_name=self.name,
                confidence=0.0,
                processing_time=elapsed,
                metadata={"langs": self._langs},
            )

        lines = []
        confidences = []
        for line in result[0]:
            bbox, (text, conf) = line
            if text and text.strip():
                lines.append(text.strip())
                confidences.append(conf)

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        text = "\n".join(lines)
        elapsed = time.time() - start

        return EngineResult(
            text=text,
            engine_name=self.name,
            confidence=avg_conf,
            processing_time=elapsed,
            metadata={"langs": self._langs, "lines": len(lines), "mean_word_conf": avg_conf},
        )

    def extract_text_with_confidence(self, page: PDFPage, **kwargs) -> EngineResult:
        result = self.extract_text(page, **kwargs)
        return result
