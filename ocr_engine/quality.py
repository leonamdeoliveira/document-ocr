import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class QualityReport:
    score: float
    char_count: int
    alphanumeric_ratio: float
    symbol_ratio: float
    avg_line_length: float
    empty_line_ratio: float
    has_repeated_chars: bool
    engine_confidence: Optional[float]

    def acceptable(self, threshold: float = 0.7) -> bool:
        return self.score >= threshold

    def retryable(self, threshold: float = 0.4) -> bool:
        return self.score >= threshold

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 4),
            "char_count": self.char_count,
            "alphanumeric_ratio": round(self.alphanumeric_ratio, 4),
            "symbol_ratio": round(self.symbol_ratio, 4),
            "avg_line_length": round(self.avg_line_length, 2),
            "empty_line_ratio": round(self.empty_line_ratio, 4),
            "has_repeated_chars": self.has_repeated_chars,
            "engine_confidence": self.engine_confidence,
        }


_CHAR_REPEAT_PATTERN = re.compile(r"(.)\1{7,}")


class QualityScorer:

    WEIGHTS = {
        "alphanumeric_ratio": 0.35,
        "symbol_ratio": 0.20,
        "avg_line_length": 0.15,
        "empty_line_ratio": 0.10,
        "repeated_chars": 0.10,
        "engine_confidence": 0.10,
    }

    MIN_CHARS = 20
    IDEAL_LINE_LENGTH = 60
    MAX_SYMBOL_RATIO = 0.10
    MAX_EMPTY_LINE_RATIO = 0.50

    def score(self, text: str, engine_confidence: Optional[float] = None) -> QualityReport:
        if not text or len(text.strip()) < self.MIN_CHARS:
            return QualityReport(
                score=0.0,
                char_count=len(text),
                alphanumeric_ratio=0.0,
                symbol_ratio=1.0,
                avg_line_length=0.0,
                empty_line_ratio=1.0,
                has_repeated_chars=False,
                engine_confidence=engine_confidence,
            )

        lines = text.split("\n")
        non_empty = [l for l in lines if l.strip()]

        char_count = len(text)
        total_chars = max(len(text), 1)
        letter_digit_chars = sum(1 for c in text if c.isalnum() or c.isspace())
        alphanumeric_ratio = letter_digit_chars / total_chars

        symbol_chars = sum(1 for c in text if c in "|\\/<>{}[]~`^_=+@#$%&*!")
        symbol_ratio = symbol_chars / total_chars
        symbol_score = max(0.0, 1.0 - (symbol_ratio / self.MAX_SYMBOL_RATIO))

        line_lengths = [len(l) for l in non_empty] if non_empty else [0]
        avg_line_length = sum(line_lengths) / len(line_lengths)
        length_score = min(1.0, avg_line_length / self.IDEAL_LINE_LENGTH)

        empty_line_ratio = (len(lines) - len(non_empty)) / max(len(lines), 1)
        empty_score = max(0.0, 1.0 - (empty_line_ratio / self.MAX_EMPTY_LINE_RATIO))

        has_repeated = bool(_CHAR_REPEAT_PATTERN.search(text))
        repeat_score = 0.0 if has_repeated else 1.0

        conf_score = engine_confidence if engine_confidence is not None else 1.0

        score = (
            self.WEIGHTS["alphanumeric_ratio"] * alphanumeric_ratio
            + self.WEIGHTS["symbol_ratio"] * symbol_score
            + self.WEIGHTS["avg_line_length"] * length_score
            + self.WEIGHTS["empty_line_ratio"] * empty_score
            + self.WEIGHTS["repeated_chars"] * repeat_score
            + self.WEIGHTS["engine_confidence"] * conf_score
        )

        return QualityReport(
            score=score,
            char_count=char_count,
            alphanumeric_ratio=alphanumeric_ratio,
            symbol_ratio=symbol_ratio,
            avg_line_length=avg_line_length,
            empty_line_ratio=empty_line_ratio,
            has_repeated_chars=has_repeated,
            engine_confidence=engine_confidence,
        )
