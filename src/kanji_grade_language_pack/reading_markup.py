"""The reading markup: the strings of ja_jp.json with the reading of every kanji and the bunsetsu boundaries.

  ⟦字|よみ⟧  kanji with their reading in hiragana. A grade's language shows the kanji when every one of them is taught
             by that grade, else the reading
  ⟪字|よみ⟫  kanji read in a way neither the 常用漢字表 nor its 付表 lists (貯める た, names, ateji): always the reading
  ‸          a boundary between bunsetsu: a space in the languages with spaces (WITH_SPACES), nothing in the others
The rest is the text of ja_jp.json as it is, so removing the markup gives the original string back.
"""
import re

from .kanji import GradeKanji, highest_grade

RUN = re.compile(r"⟦([^|⟧]+)\|([^⟧]*)⟧")
KANA_ONLY_RUN = re.compile(r"⟪([^|⟫]+)\|([^⟫]*)⟫")
ANY_RUN = re.compile(r"⟦([^|⟧]+)\|([^⟧]*)⟧|⟪([^|⟫]+)\|([^⟫]*)⟫")
BOUNDARY = "‸"
MARKUP_CHARACTERS = ("⟦", "⟧", "⟪", "⟫", BOUNDARY)
KANA_ONLY = 0  # the grade of the kana-only language
# The languages written with a space between bunsetsu (分かち書き), as the textbooks of grades 1 and 2 are
WITH_SPACES = (KANA_ONLY, 1, 2)


def run(kanji: str, reading: str) -> str:
    return f"⟦{kanji}|{reading}⟧"


def kana_only_run(kanji: str, reading: str) -> str:
    return f"⟪{kanji}|{reading}⟫"


def runs(markup: str) -> list[tuple[str, str]]:
    """(kanji, reading) of every run, both kinds."""
    return [(m[1] or m[3], m[2] if m[1] else m[4]) for m in ANY_RUN.finditer(markup)]


def original(markup: str) -> str:
    """The string the markup was made from."""
    return ANY_RUN.sub(lambda m: m[1] or m[3], markup).replace(BOUNDARY, "")


def render(markup: str, grade: int, grade_kanji: dict[str, GradeKanji]) -> str:
    """The string of a language: grade 1-6, or KANA_ONLY. The languages of WITH_SPACES get a space at each bunsetsu
    boundary."""
    markup = KANA_ONLY_RUN.sub(lambda m: m[2], markup)
    if grade == KANA_ONLY:
        text = RUN.sub(lambda m: m[2], markup)
    else:
        text = RUN.sub(lambda m: m[1] if highest_grade(m[1], grade_kanji) <= grade else m[2], markup)
    if grade in WITH_SPACES:
        # A boundary next to a space or a line break is dropped; elsewhere it becomes one space
        return re.sub(r"\s*‸\s*", lambda m: " " if m[0] == BOUNDARY else m[0].replace(BOUNDARY, ""), text)
    return text.replace(BOUNDARY, "")
