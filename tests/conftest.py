import functools
import json

import pytest

from kanji_grade_language_pack.kanji import load_grade_kanji
from kanji_grade_language_pack.kanji_reading_alignment import ReadingAligner
from kanji_grade_language_pack.reading_fixes import load_reading_fixes

DATA = "data"


@functools.cache
def _grade_kanji():
    return load_grade_kanji(f"{DATA}/grade_kanji_readings.json")


@functools.cache
def _appendix():
    with open(f"{DATA}/joyo_appendix_words.json", encoding="utf-8") as f:
        return {row["word"]: row["reading"] for row in json.load(f)}


@pytest.fixture
def grade_kanji():
    return _grade_kanji()


@pytest.fixture
def appendix():
    return _appendix()


@pytest.fixture
def aligner(grade_kanji, appendix):
    """The aligner of the build: the real tables and the extra readings and unsplit words of data/reading_fixes.toml."""
    fixes = load_reading_fixes(f"{DATA}/reading_fixes.toml")
    return ReadingAligner(grade_kanji, fixes.extra_kanji_readings, fixes.unsplit_words, appendix)
