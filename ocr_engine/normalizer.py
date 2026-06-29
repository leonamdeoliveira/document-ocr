import re


_HYPHENATION = re.compile(r"(\w)-\n(\w)")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_OCR_LINE_ARTIFACTS = re.compile(r"[|\\/]{4,}")
_TRAILING_SPACE = re.compile(r"[ \t]+\n")
_LEADING_SPACE = re.compile(r"\n[ \t]+")


class OutputNormalizer:

    def normalize(self, text: str) -> str:
        if not text:
            return ""

        text = _CONTROL_CHARS.sub("", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = _HYPHENATION.sub(r"\1\2", text)
        text = _OCR_LINE_ARTIFACTS.sub("", text)
        text = _TRAILING_SPACE.sub("\n", text)
        text = _LEADING_SPACE.sub("\n", text)
        text = _MULTI_NEWLINE.sub("\n\n", text)
        return text.strip()

    def normalize_to_markdown(self, text: str, preserve_paragraphs: bool = True) -> str:
        text = self.normalize(text)
        if not text:
            return ""

        lines = text.split("\n")
        result = []
        buffer = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if buffer:
                    result.append(" ".join(buffer))
                    buffer = []
                if preserve_paragraphs:
                    result.append("")
                continue
            buffer.append(stripped)

        if buffer:
            result.append(" ".join(buffer))

        cleaned = "\n".join(result)
        cleaned = _MULTI_NEWLINE.sub("\n\n", cleaned)
        return cleaned.strip()
