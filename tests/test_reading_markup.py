import pytest

from kanji_grade_language_pack.reading_markup import KANA_ONLY, original, render, runs

MARKUP = "⟦鉄|てつ⟧⟦格|ごう⟧⟦子|し⟧の‸⟪欠片|かけら⟫を‸⟦作|つく⟧る"


def test_original_drops_the_markup():
    assert original(MARKUP) == "鉄格子の欠片を作る"


@pytest.mark.parametrize("grade, text", [
    (KANA_ONLY, "てつごうしの かけらを つくる"),
    (1, "てつごう子の かけらを つくる"),  # 子 is taught in grade 1, 作 in grade 2; grades 1 and 2 with spaces
    (2, "てつごう子の かけらを 作る"),
    (3, "鉄ごう子のかけらを作る"),
    (5, "鉄格子のかけらを作る"),  # 欠片 is ateji: always kana
])
def test_render(grade, text, grade_kanji):
    assert render(MARKUP, grade, grade_kanji) == text


def test_kana_only_drops_a_boundary_next_to_a_space_or_a_line_break(grade_kanji):
    assert render("⟦鉄|てつ⟧ ‸の\n‸⟦子|こ⟧", KANA_ONLY, grade_kanji) == "てつ の\nこ"


def test_runs_lists_both_kinds():
    assert runs(MARKUP) == [("鉄", "てつ"), ("格", "ごう"), ("子", "し"), ("欠片", "かけら"), ("作", "つく")]
