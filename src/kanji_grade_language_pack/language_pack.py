"""The seven languages, their checks, and the resource pack zip."""
import json
import re
import zipfile
from dataclasses import dataclass

from .kanji import GradeKanji, is_kanji
from .reading_markup import KANA_ONLY, MARKUP_CHARACTERS, WITH_SPACES, original, render, runs


@dataclass(frozen=True)
class Language:
    code: str
    name_markup: str  # rendered in the language itself: 日本ご（1年生）
    grade: int  # 1-6, or KANA_ONLY


LANGUAGES = (
    Language("ja_kana", "にほんご（ひらがな・カタカナ）", KANA_ONLY),
    *(Language(f"ja_g{g}", f"⟦日|に⟧⟦本|ほん⟧⟦語|ご⟧（{g}⟦年|ねん⟧⟦生|せい⟧）", g) for g in range(1, 7)),
)
REGION_MARKUP = "⟦日|に⟧⟦本|ほん⟧"
# Shown in the resource pack list whatever the language, so in kana
DESCRIPTION = "がくねんべつ かんじの にほんご（ひらがな・1〜6ねんせい）"
# A fixed time for the zip entries, so the same contents give the same zip
ZIP_TIME = (2026, 1, 1, 0, 0, 0)

FORMAT_CODES = re.compile(r"%(?:\d+\$)?[a-zA-Z%]|§.")
READING = re.compile(r"[ぁ-ゖー]+")


def check_markup(key: str, source: str, markup: str) -> list[str]:
    """Problems of the markup of one string."""
    problems = []
    if original(markup) != source:
        problems.append(f"{key}: the markup does not give the string back: {markup!r}")
    for kanji, reading in runs(markup):
        if not READING.fullmatch(reading):
            problems.append(f"{key}: the reading of {kanji} is not hiragana: {reading!r}")
    return problems


def check_text(key: str, source: str, text: str, grade: int, grade_kanji: dict[str, GradeKanji]) -> list[str]:
    """Problems of one string of one language."""
    problems = []
    if FORMAT_CODES.findall(source) != FORMAT_CODES.findall(text):
        problems.append(f"{key}: placeholders or formatting codes changed: {source!r} → {text!r}")
    if any(c in text for c in MARKUP_CHARACTERS):
        problems.append(f"{key}: markup left: {text!r}")
    above = [c for c in text if is_kanji(c) and (grade == KANA_ONLY or c not in grade_kanji
                                                 or grade_kanji[c].grade > grade)]
    if above:
        problems.append(f"{key}: kanji above grade {grade}: {''.join(above)} in {text!r}")
    if grade == KANA_ONLY and "々" in text:
        problems.append(f"{key}: 々 left in the kana-only language: {text!r}")
    if grade in WITH_SPACES:
        problems += [f"{key}: {problem}: {text!r}" for problem in _space_problems(source, text)]
    return problems


# Where a bunsetsu space must not go: at the start or end of a line, twice in a row, before closing punctuation, after
# opening punctuation
_BAD_SPACES = (
    ("a space at the start of a line", re.compile(r"(?m)^ ")),
    ("a space at the end of a line", re.compile(r"(?m) $")),
    ("two spaces in a row", re.compile(r"  ")),
    ("a space before punctuation", re.compile(r" [、。，．！？!?…）」』］】〉》,.)\]]")),
    ("a space after an opening bracket", re.compile(r"[（「『［【〈《(\[] ")),
)


def _space_problems(source: str, text: str) -> list[str]:
    """Spaces the languages with spaces added where they must not be (unless the original string had them there)."""
    return [name for name, pattern in _BAD_SPACES if len(pattern.findall(text)) > len(pattern.findall(source))]


def language_strings(texts: dict[str, str], markup: dict[str, str], grade: int,
                     grade_kanji: dict[str, GradeKanji]) -> dict[str, str]:
    return {key: render(markup[key], grade, grade_kanji) for key in texts}


def build_pack(texts: dict[str, str], markup: dict[str, str], grade_kanji: dict[str, GradeKanji],
               icon: bytes, min_format: int, max_format: int) -> tuple[dict[str, bytes], list[str]]:
    """The files of the pack for the resource pack formats min_format to max_format, and the problems found (the
    pack must not be written when there are any)."""
    problems = []
    if set(markup) != set(texts):
        problems.append(f"the markup has other keys than ja_jp.json: {sorted(set(markup) ^ set(texts))[:10]}")
        return {}, problems
    for key, source in texts.items():
        problems += check_markup(key, source, markup[key])
    files: dict[str, bytes] = {}
    languages = {}
    for language in LANGUAGES:
        strings = language_strings(texts, markup, language.grade, grade_kanji)
        for key, source in texts.items():
            problems += check_text(key, source, strings[key], language.grade, grade_kanji)
        languages[language.code] = {
            "region": render(REGION_MARKUP, language.grade, grade_kanji),
            "name": render(language.name_markup, language.grade, grade_kanji),
            "bidirectional": False,
        }
        files[language_file(language.code)] = _json(strings)
    mcmeta = {
        "pack": {"description": DESCRIPTION, "min_format": min_format, "max_format": max_format},
        "language": languages,
    }
    return {"pack.png": icon, "pack.mcmeta": _json(mcmeta), **files}, problems


def language_file(code: str) -> str:
    """The path of a language's file in the pack (where the game reads the strings of a language from)."""
    return f"assets/minecraft/lang/{code}.json"


def write_zip(path: str, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)


def _json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
