import time
import logging
import base64
from io import BytesIO
from typing import Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)


class LMStudioClientError(Exception):
    pass


class LMStudioClient:
    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        model: str = "chandra-ocr-2",
        api_key: str = "",
        timeout: int = 120,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        max_tokens: int = 48000,
        extra_params: Optional[dict] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_tokens = max_tokens
        self.extra_params = extra_params or {}

    def _encode_image(self, image: Image.Image) -> tuple[str, str]:
        buffer = BytesIO()
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGB")
        image.save(buffer, format="JPEG", quality=95, optimize=True)
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return "image/jpeg", b64

    _SYSTEM_PROMPT = (
        "You are a precise OCR engine. Your ONLY task is to extract ALL text "
        "exactly as it appears in the provided document image. "
        "CRITICAL RULES:\n"
        "- Extract text VERBATIM. Do NOT change, rephrase, summarize, or improve any text.\n"
        "- Do NOT add any information that is not present in the image.\n"
        "- Do NOT change arXiv IDs, titles, author names, dates, numbers, or any other content.\n"
        "- Do NOT translate. Preserve the original language exactly.\n"
        "- If text is unclear, use [unclear] - do NOT guess or invent.\n"
        "- Preserve natural reading order."
    )

    def _build_multimodal_payload(
        self, prompt: str, images: list[Image.Image] | Image.Image | None = None,
        system_prompt: Optional[str] = None,
    ) -> dict:
        if system_prompt is None:
            system_prompt = self._SYSTEM_PROMPT
        messages = (
            [{"role": "system", "content": system_prompt}]
            if system_prompt else []
        )

        content = []

        if images is not None:
            image_list = images if isinstance(images, list) else [images]
            for img in image_list:
                mime, b64 = self._encode_image(img)
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64}"
                        },
                    }
                )

        if prompt:
            content.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": content})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.0,
        }
        payload.update(self.extra_params)
        return payload

    def _request(self, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/chat/completions"

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    url, headers=headers, json=payload, timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    raise LMStudioClientError(f"Model error: {data['error']}")
                return data
            except requests.exceptions.RequestException as e:
                logger.warning(
                    "Attempt %d/%d failed: %s", attempt, self.max_retries, e
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)
                else:
                    raise LMStudioClientError(
                        f"Request failed after {self.max_retries} attempts: {e}"
                    ) from e

    def _extract_content(self, data: dict) -> str:
        try:
            msg = data["choices"][0]["message"]
            content = msg.get("content", "") or ""
            if not content:
                content = msg.get("reasoning_content", "") or ""
            finish_reason = data["choices"][0].get("finish_reason", "")
            if finish_reason == "length":
                logger.warning("Response truncated: hit max_tokens limit (%d chars)", len(content))
            if not content:
                logger.warning("Model returned empty content. finish_reason=%s",
                               finish_reason)
            return content
        except (KeyError, IndexError) as e:
            logger.error("Unexpected API response: %s", data)
            raise LMStudioClientError(f"Unexpected API response format: {e}") from e

    def ocr_image(self, prompt: str, image: Image.Image, system_prompt: Optional[str] = None) -> str:
        payload = self._build_multimodal_payload(prompt, image, system_prompt=system_prompt)
        data = self._request(payload)
        return self._extract_content(data)

    def ocr_images(self, prompt: str, images: list[Image.Image], system_prompt: Optional[str] = None) -> str:
        payload = self._build_multimodal_payload(prompt, images, system_prompt=system_prompt)
        data = self._request(payload)
        return self._extract_content(data)


