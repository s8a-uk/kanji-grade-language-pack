"""Kanji and kana: which characters are kanji, and the school grade of each kanji."""
import json
from dataclasses import dataclass

# Characters of these blocks count as kanji: CJK Unified Ideographs, its Extension A, the Compatibility Ideographs, and the
# supplementary planes of ideographs (Extension B onwards: 𠮟 of the 常用漢字表 is U+20B9F)
_KANJI_RANGES = (("\u3400", "\u9fff"), ("\uf900", "\ufaff"), ("\U00020000", "\U0003ffff"))


def is_kanji(c: str) -> bool:
    return any(low <= c <= high for low, high in _KANJI_RANGES)


def has_kanji(text: str) -> bool:
    """Whether text holds a kanji or 々 (which repeats the kanji before it)."""
    return any(is_kanji(c) or c == "々" for c in text)


def to_hiragana(text: str) -> str:
    """Katakana ァ〜ヶ turned into hiragana; anything else unchanged."""
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


@dataclass(frozen=True)
class GradeKanji:
    """A kanji of the 学年別漢字配当表: its grade (1-6) and its readings in the 常用漢字表 (kun with the okurigana after
    a hyphen: ひと-つ)."""

    kanji: str
    grade: int
    on: tuple[str, ...]
    kun: tuple[str, ...]


NOT_TAUGHT = 99  # the grade of a kanji not taught at primary school


def load_grade_kanji(path: str) -> dict[str, GradeKanji]:
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    return {r["kanji"]: GradeKanji(r["kanji"], r["grade"], tuple(r["on"]), tuple(r["kun"])) for r in rows}


def highest_grade(text: str, grade_kanji: dict[str, GradeKanji]) -> int:
    """The highest grade among the kanji of text: 0 without kanji, NOT_TAUGHT with a kanji not taught at school."""
    return max((grade_kanji[c].grade if c in grade_kanji else NOT_TAUGHT for c in text if is_kanji(c)), default=0)
