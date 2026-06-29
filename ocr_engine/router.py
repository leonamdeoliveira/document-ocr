import logging
from typing import Optional

from ocr_engine.base import (
    OCREngineBase,
    OCREngineError,
    EngineNotAvailableError,
    EngineResult,
    timed_extract,
)
from ocr_engine.config import HybridOCRConfig
from ocr_engine.quality import QualityScorer
from pdf_utils import PDFPage, has_meaningful_text

logger = logging.getLogger(__name__)


class OCRRouter:

    def __init__(
        self,
        engines: dict[str, OCREngineBase],
        config: HybridOCRConfig,
    ):
        self.engines = engines
        self.config = config
        self.scorer = QualityScorer()

    def select_engine(self, page: PDFPage) -> str:
        """Retorna o nome do engine que seria escolhido (sem executar)."""
        if self.config.mode in ("legacy", "ai_only"):
            return self._ai_engine_name()

        if self.config.mode == "classic_only":
            return self.config.classic_engine

        if has_meaningful_text(page.native_text, min_chars=50):
            return "native"

        return self.config.classic_engine

    def _ai_engine_name(self) -> str:
        for name in self.engines:
            if name.startswith("ai:"):
                return name
        return "ai:unknown"

    def process_with_fallback(self, page: PDFPage, **kwargs) -> EngineResult:
        mode = self.config.mode

        if mode in ("legacy", "ai_only"):
            return self._run_ai(page, **kwargs)

        if mode == "classic_only":
            return self._run_classic_only(page, **kwargs)

        return self._run_hybrid(page, **kwargs)

    def _run_ai(self, page: PDFPage, **kwargs) -> EngineResult:
        ai_engine = self._get_ai_engine()
        logger.info("Router: using AI engine (%s) for page %d", ai_engine.name, page.page_num)
        return timed_extract(ai_engine, page, **kwargs)

    def _run_classic_only(self, page: PDFPage, **kwargs) -> EngineResult:
        engine = self._get_engine(self.config.classic_engine)
        if engine is None:
            raise EngineNotAvailableError(
                f"Classic engine '{self.config.classic_engine}' not available"
            )
        if not engine.is_available():
            raise EngineNotAvailableError(
                f"Engine '{engine.name}' is not available (missing dependencies)"
            )
        logger.info("Router: using %s (classic_only) for page %d", engine.name, page.page_num)
        return timed_extract(engine, page, **kwargs)

    def _run_hybrid(self, page: PDFPage, **kwargs) -> EngineResult:
        accept = self.config.quality_threshold_accept
        retry_threshold = self.config.quality_threshold_retry

        if has_meaningful_text(page.native_text, min_chars=50):
            logger.info("Router [page %d]: native text OK, skipping OCR", page.page_num)
            return EngineResult(
                text=page.native_text,
                engine_name="native",
                confidence=1.0,
                processing_time=0.0,
                metadata={"source": "native_text", "chars": len(page.native_text)},
            )

        classic_order = ["tesseract", "paddle"]
        for engine_name in classic_order:
            engine = self._get_engine(engine_name)
            if engine is None or not engine.is_available():
                continue
            if not engine.supports(page):
                continue

            logger.info("Router [page %d]: trying %s ...", page.page_num, engine_name)
            try:
                result = timed_extract(engine, page, **kwargs)
            except OCREngineError as e:
                logger.warning("Router [page %d]: %s failed: %s", page.page_num, engine_name, e)
                continue

            report = self.scorer.score(result.text, engine_confidence=result.confidence)
            logger.info(
                "Router [page %d]: %s score=%.4f (accept>=%.2f)",
                page.page_num, engine_name, report.score, accept,
            )

            if report.acceptable(accept):
                logger.info("Router [page %d]: accepted %s result", page.page_num, engine_name)
                result.metadata["quality_score"] = report.score
                result.metadata["quality"] = report.to_dict()
                return result

            if report.retryable(retry_threshold) and self.config.enable_page_level_fallback:
                logger.info(
                    "Router [page %d]: %s score=%.4f below accept=%.2f, trying next engine",
                    page.page_num, engine_name, report.score, accept,
                )
                continue
            else:
                logger.info(
                    "Router [page %d]: %s score=%.4f below retry=%.2f, trying next engine",
                    page.page_num, engine_name, report.score, retry_threshold,
                )
                continue

        if self.config.enable_glm_fallback:
            logger.info("Router [page %d]: all classic engines failed, falling back to AI", page.page_num)
            return self._run_ai(page, **kwargs)

        raise OCREngineError(
            f"Router [page {page.page_num}]: no engine could process this page "
            f"(classic engines failed, GLM fallback disabled)"
        )

    def _get_ai_engine(self) -> OCREngineBase:
        for name, engine in self.engines.items():
            if name.startswith("ai:"):
                return engine
        raise EngineNotAvailableError("No AI engine registered")

    def _get_engine(self, name: str) -> Optional[OCREngineBase]:
        for key, engine in self.engines.items():
            if key == name or key.endswith(f":{name}"):
                return engine
        return None
