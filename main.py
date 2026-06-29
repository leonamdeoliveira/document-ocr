#!/usr/bin/env python3
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from PIL import Image

from lmstudio_client import LMStudioClient, LMStudioClientError
from native_extractor import extract_text, EXTRACTORS as NATIVE_FORMATS
from ocr_pipeline import OCRPipeline, PageResult
from model_loader import load_model_config
from pdf_utils import PDFPage
from ocr_engine import (
    HybridOCRConfig,
    OCRRouter,
    OCREngineBase,
    OCREngineError,
    AIEngine,
    TesseractEngine,
    PaddleEngine,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _list_available_models() -> list[str]:
    models_dir = Path(__file__).parent / "models"
    return sorted(
        d.name for d in models_dir.iterdir()
        if d.is_dir() and (d / "config.json").exists() and d.name != "template"
    )


def _pick_model() -> str:
    models = _list_available_models()
    if not models:
        logger.error("No models found in models/ directory")
        sys.exit(1)
    print("\nModelos de OCR disponiveis:")
    for i, m in enumerate(models, 1):
        cfg = load_model_config(m)
        print(f"  {i}. {cfg.get('label', m)} - {cfg.get('description', '')}")
    while True:
        try:
            choice = input(f"\nEscolha o modelo (1-{len(models)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
        except (ValueError, IndexError):
            pass
        print(f"Opcao invalida. Escolha entre 1 e {len(models)}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Document OCR pipeline via LM Studio local API"
    )
    parser.add_argument("input", type=str, help="Path to input PDF or image file")
    parser.add_argument(
        "--out", type=str, default=None,
        help="Output directory (default: DIR_DO_INPUT/saida_ocr)",
    )
    parser.add_argument(
        "--output-name", type=str, default="",
        help="Output filename (without extension). Default: same as input file name.",
    )
    parser.add_argument(
        "--format",
        nargs="+",
        choices=["markdown", "html", "json"],
        default=["markdown"],
        help="Output format(s) (default: markdown)",
    )
    parser.add_argument(
        "--mode",
        choices=["text-first", "ocr-only"],
        default="text-first",
        help="Processing mode (default: text-first)",
    )
    parser.add_argument(
        "--model", type=str, default="",
        help="OCR model to use (default: prompted interactively). Choices: " + ", ".join(_list_available_models()),
    )
    parser.add_argument(
        "--dpi", type=int, default=None, help="DPI for PDF rasterization (default: model config)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume partial processing if partial files exist",
    )
    parser.add_argument(
        "--lmstudio-url", type=str, default="",
        help="LM Studio base URL (overrides env LMSTUDIO_BASE_URL)",
    )
    parser.add_argument(
        "--lmstudio-model", type=str, default="",
        help="Model name in LM Studio (overrides env LMSTUDIO_MODEL)",
    )
    parser.add_argument(
        "--lmstudio-api-key", type=str, default="",
        help="API key if required (overrides env LMSTUDIO_API_KEY)",
    )
    parser.add_argument(
        "--timeout", type=int, default=None,
        help="Request timeout in seconds (default: model config)",
    )
    parser.add_argument(
        "--retries", type=int, default=3,
        help="Max retries per request (default: 3)",
    )
    parser.add_argument(
        "--ocr-mode", type=str, default="",
        choices=["", "legacy", "hybrid", "classic_only", "ai_only"],
        help="OCR mode: legacy (default), hybrid, classic_only, ai_only",
    )
    parser.add_argument(
        "--classic-engine", type=str, default="",
        choices=["", "tesseract", "paddle"],
        help="Classic OCR engine for hybrid/classic_only modes",
    )
    parser.add_argument(
        "--ocr-langs", type=str, default="",
        help="Languages for classic OCR (e.g. por+eng)",
    )
    parser.add_argument(
        "--quality-threshold", type=float, default=None,
        help="Quality score threshold to accept classic OCR (0-1, default: 0.70)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    ext = input_path.suffix.lower()
    basename = args.output_name or input_path.stem
    if args.out:
        output_dir = Path(args.out)
    else:
        output_dir = input_path.parent / "saida_ocr"

    if ext in NATIVE_FORMATS:
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Extracting native text from %s file: %s", ext, input_path.name)
        text = extract_text(input_path)
        ext_map = {"markdown": "md", "html": "html", "json": "json"}
        for fmt in args.format:
            if fmt == "json":
                content = json.dumps({"filename": input_path.name, "content": text}, ensure_ascii=False, indent=2)
            else:
                content = text
            out_path = output_dir / f"{basename}.{ext_map.get(fmt, fmt)}"
            out_path.write_text(content, encoding="utf-8")
            logger.info("Saved: %s", out_path)
        logger.info("Done!")
        return

    model_name = args.model or _pick_model()
    model_config = load_model_config(model_name)

    base_url = args.lmstudio_url or os.environ.get("LMSTUDIO_BASE_URL") or "http://localhost:1234/v1"
    lmstudio_model = args.lmstudio_model or os.environ.get("LMSTUDIO_MODEL") or model_config["lmstudio_model"]
    api_key = args.lmstudio_api_key or os.environ.get("LMSTUDIO_API_KEY") or ""

    dpi = args.dpi if args.dpi is not None else model_config.get("default_dpi", 200)
    timeout = args.timeout if args.timeout is not None else model_config.get("default_timeout", 300)
    max_tokens = model_config.get("max_tokens", 48000)

    extra_params = {}
    ngram_size = model_config.get("no_repeat_ngram_size")
    ngram_window = model_config.get("ngram_window")
    if ngram_size:
        extra_params["custom_logit_processor"] = f"DeepseekOCRNoRepeatNGram(size={ngram_size},window={ngram_window or 128})"
        extra_params["custom_params"] = {
            "ngram_size": ngram_size,
            "window_size": ngram_window or 128,
        }

    logger.info("Model: %s (%s)", model_name, model_config.get("label", model_name))
    logger.info("LM Studio URL: %s", base_url)
    logger.info("LM Studio Model: %s", lmstudio_model)
    logger.info("Input: %s", input_path)
    logger.info("Output: %s / %s.{md,html,json}", output_dir, basename)
    logger.info("Formats: %s", args.format)
    logger.info("Mode: %s", args.mode)
    logger.info("DPI: %d", dpi)
    logger.info("Max tokens: %d", max_tokens)

    client = LMStudioClient(
        base_url=base_url,
        model=lmstudio_model,
        api_key=api_key,
        timeout=timeout,
        max_retries=args.retries,
        max_tokens=max_tokens,
        extra_params=extra_params,
    )

    hybrid_config = None
    router = None
    ocr_mode = args.ocr_mode or os.environ.get("OCR_MODE", "legacy")
    if ocr_mode != "legacy":
        hybrid_config = HybridOCRConfig(
            mode=ocr_mode,
            classic_engine=args.classic_engine or os.environ.get("CLASSIC_OCR_ENGINE", "tesseract"),
            langs=args.ocr_langs or os.environ.get("OCR_LANGS", "por+eng"),
            quality_threshold_accept=(
                args.quality_threshold if args.quality_threshold is not None
                else float(os.environ.get("QUALITY_THRESHOLD_ACCEPT", "0.70"))
            ),
            enable_glm_fallback=os.environ.get("ENABLE_GLM_FALLBACK", "true").lower() == "true",
            enable_paddle=os.environ.get("ENABLE_PADDLE_FALLBACK", "false").lower() == "true",
            ocr_timeout=timeout,
        )
        logger.info("OCR Mode: %s (classic=%s, langs=%s, accept=%.2f)",
                     hybrid_config.mode, hybrid_config.classic_engine,
                     hybrid_config.langs, hybrid_config.quality_threshold_accept)

    if ocr_mode in ("hybrid", "classic_only"):
        ai_engine = AIEngine(client=client, model_name=model_name, mode=args.mode)
        engines: dict[str, OCREngineBase] = {ai_engine.name: ai_engine}

        tesseract = TesseractEngine(langs=hybrid_config.langs, timeout=hybrid_config.ocr_timeout)
        engines[tesseract.name] = tesseract
        logger.info("Tesseract available: %s", tesseract.is_available())

        if hybrid_config.enable_paddle or hybrid_config.classic_engine == "paddle":
            paddle = PaddleEngine(langs=hybrid_config.langs)
            engines[paddle.name] = paddle
            logger.info("PaddleOCR available: %s", paddle.is_available())

        router = OCRRouter(engines=engines, config=hybrid_config)

    pipeline = OCRPipeline(
        client=client,
        output_dir=output_dir,
        formats=args.format,
        model_name=model_name,
        mode=args.mode,
        dpi=dpi,
        resume=args.resume,
        basename=basename,
        hybrid_config=hybrid_config,
        router=router,
    )

    if ext == ".pdf":
        use_multi = model_config.get("use_multi_image", False)
        if use_multi and not args.resume:
            from pdf_utils import load_pdf
            pages = load_pdf(path=input_path, dpi=dpi, mode=args.mode)
            bs = model_config.get("batch_size", 0) or len(pages)
            batches = [pages[i:i+bs] for i in range(0, len(pages), bs)]
            logger.info("Batch processing %d pages in %d batch(es) of %d", len(pages), len(batches), bs)
            pipeline._prepare_outputs()
            results = []
            for batch_idx, batch in enumerate(batches):
                batch_start = time.time()
                try:
                    for fmt in args.format:
                        logger.info("Batch %d/%d: %d pages [%s] ...", batch_idx + 1, len(batches), len(batch), fmt)
                        content = pipeline._process_batch(batch, fmt)
                        pipeline._append_saida(fmt, content)
                    status = "ok"
                except LMStudioClientError as e:
                    logger.error("Batch %d failed: %s", batch_idx + 1, e)
                    status = f"error: {e}"
                    content = ""
                elapsed = time.time() - batch_start
                for page in batch:
                    results.append(PageResult(
                        page_num=page.page_num,
                        method="ocr",
                        processing_time=elapsed,
                        image_size=page.image.size,
                        native_chars=len(page.native_text),
                        output_chars=len(content) if status == "ok" else 0,
                        status=status,
                    ))
            pipeline._consolidate_json()
            pipeline._save_metadata(results)
            ok_count = sum(1 for r in results if r.status == "ok")
            if ok_count == len(pages):
                for partial in pipeline.output_dir.glob("page_*.partial"):
                    partial.unlink()
            logger.info("Pipeline finished: %d/%d pages OK", ok_count, len(pages))
        else:
            results = pipeline.run(input_path)
    elif ext in (".png", ".jpg", ".jpeg"):
        output_dir.mkdir(parents=True, exist_ok=True)
        image = Image.open(input_path).convert("RGB")
        page = PDFPage(page_num=1, image=image)
        start = time.time()

        logger.info("Processing single image...")
        error = None
        last_content = ""
        for fmt in args.format:
            try:
                content = pipeline.process_page(page, fmt)
                pipeline._save_partial(1, fmt, content)
                pipeline._append_saida(fmt, content)
                last_content = content
            except (LMStudioClientError, OCREngineError) as e:
                error = str(e)
                logger.error("Image processing failed: %s", e)
                break

        elapsed = time.time() - start
        results = [PageResult(
            page_num=1,
            method="ocr",
            processing_time=elapsed,
            image_size=image.size,
            native_chars=0,
            output_chars=len(last_content),
            status="error" if error else "ok",
        )]
        pipeline._save_metadata(results)
        pipeline._consolidate_json()
        if not error:
            for partial in output_dir.glob("page_*.partial"):
                partial.unlink()
            metadata = output_dir / f"{basename}.metadata.json"
            if metadata.exists():
                metadata.unlink()
        logger.info("Done!")
    else:
        logger.error("Unsupported file type: %s (use .pdf, .png, .jpg, .jpeg, .docx, .pptx, .html)", ext)
        sys.exit(1)

    ok = sum(1 for r in results if r.status in ("ok", "resumed"))
    logger.info("Processing complete: %d/%d pages OK", ok, len(results))


if __name__ == "__main__":
    main()
