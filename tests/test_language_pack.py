from kanji_grade_language_pack.language_pack import LANGUAGES, build_pack, check_markup, check_text
from kanji_grade_language_pack.reading_markup import KANA_ONLY


def test_seven_languages():
    assert [language.code for language in LANGUAGES] == ["ja_kana", "ja_g1", "ja_g2", "ja_g3", "ja_g4", "ja_g5", "ja_g6"]


def test_markup_must_give_the_string_back():
    assert check_markup("k", "鉄の剣", "⟦鉄|てつ⟧の⟦剣|けん⟧") == []
    assert check_markup("k", "鉄の剣", "⟦鉄|てつ⟧の⟦刀|かたな⟧")
    assert check_markup("k", "鉄", "⟦鉄|テツ⟧")  # a reading in katakana


def test_text_checks(grade_kanji):
    assert check_text("k", "%sの鉄", "%sの鉄", 3, grade_kanji) == []
    assert check_text("k", "%sの鉄", "%sの鉄", 2, grade_kanji)  # 鉄 is taught in grade 3
    assert check_text("k", "%1$sの§a鉄", "%sのてつ", 3, grade_kanji)  # a placeholder changed
    assert check_text("k", "§a鉄", "てつ", 3, grade_kanji)  # a formatting code lost
    assert check_text("k", "鉄", "⟦鉄|てつ⟧", 3, grade_kanji)  # markup left
    assert check_text("k", "山", "山", KANA_ONLY, grade_kanji)  # no kanji in the kana-only language


def test_build_pack(grade_kanji):
    texts = {"a": "鉄の剣", "b": "%s個"}
    markup = {"a": "⟦鉄|てつ⟧の‸⟦剣|けん⟧", "b": "%s⟦個|こ⟧"}
    files, problems = build_pack(texts, markup, grade_kanji, b"png", 84, 97)
    assert problems == []
    assert set(files) == {"pack.png", "pack.mcmeta"} | {f"assets/minecraft/lang/{l.code}.json" for l in LANGUAGES}
    mcmeta = files["pack.mcmeta"]
    assert b'"ja_g3"' in mcmeta and b'"min_format": 84' in mcmeta and b'"max_format": 97' in mcmeta
