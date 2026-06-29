import os
from dataclasses import dataclass


@dataclass
class HybridOCRConfig:
    mode: str = "legacy"
    classic_engine: str = "tesseract"
    enable_paddle: bool = False
    enable_glm_fallback: bool = True
    langs: str = "por+eng"
    quality_threshold_accept: float = 0.70
    quality_threshold_retry: float = 0.40
    max_parallel_pages: int = 2
    ocr_timeout: int = 120
    keep_intermediate_files: bool = False
    enable_page_level_fallback: bool = True

    VALID_MODES = {"legacy", "hybrid", "classic_only", "ai_only"}

    def __post_init__(self):
        if self.mode not in self.VALID_MODES:
            raise ValueError(f"Invalid mode '{self.mode}'. Must be one of: {self.VALID_MODES}")
        self.quality_threshold_accept = max(0.0, min(1.0, self.quality_threshold_accept))
        self.quality_threshold_retry = max(0.0, min(1.0, self.quality_threshold_retry))

    @classmethod
    def from_env(cls) -> "HybridOCRConfig":
        return cls(
            mode=os.environ.get("OCR_MODE", "legacy"),
            classic_engine=os.environ.get("CLASSIC_OCR_ENGINE", "tesseract"),
            enable_paddle=os.environ.get("ENABLE_PADDLE_FALLBACK", "false").lower() == "true",
            enable_glm_fallback=os.environ.get("ENABLE_GLM_FALLBACK", "true").lower() == "true",
            langs=os.environ.get("OCR_LANGS", "por+eng"),
            quality_threshold_accept=float(os.environ.get("QUALITY_THRESHOLD_ACCEPT", "0.70")),
            quality_threshold_retry=float(os.environ.get("QUALITY_THRESHOLD_RETRY", "0.40")),
            max_parallel_pages=int(os.environ.get("MAX_PARALLEL_PAGES", "2")),
            ocr_timeout=int(os.environ.get("OCR_TIMEOUT_SECONDS", "120")),
            keep_intermediate_files=os.environ.get("KEEP_INTERMEDIATE_FILES", "false").lower() == "true",
            enable_page_level_fallback=os.environ.get("ENABLE_PAGE_LEVEL_FALLBACK", "true").lower() == "true",
        )
