"""Sentences of our own through Sudachi: the readings and the bunsetsu boundaries of the kana-only language."""
import pytest
from sudachipy import Dictionary, SplitMode

from kanji_grade_language_pack.annotate import annotate
from kanji_grade_language_pack.reading_fixes import load_reading_fixes
from kanji_grade_language_pack.reading_markup import KANA_ONLY, render


@pytest.fixture(scope="module")
def tokenizer():
    return Dictionary(dict="full").tokenizer(SplitMode.C)


@pytest.mark.parametrize("text, kana", [
    ("鉄のツルハシを作る", "てつの ツルハシを つくる"),
    ("馬に乗りこなす", "うまに のりこなす"),  # a compound verb stays together
    ("この石は大きすぎる", "この いしは おおきすぎる"),
    ("設定を有効化する", "せっていを ゆうこうかする"),
    ("敵がスポーンする", "てきが スポーンする"),
    ("このまま進む", "この まま すすむ"),
    ("薄灰色の石", "うすはいいろの いし"),
    ("%sの石を%1$s個置く", "%sの いしを %1$sこ おく"),  # a placeholder is one word
    ("バケツが空になる", "バケツが からに なる"),  # a word_reading rule of data/reading_fixes.toml
    ("何かが来る", "なにかが くる"),
    ("あと%s日です", "あと %sにちです"),
    ("木の吊り看板を作る", "きの つりかんばんを つくる"),  # a verb in 連用形 and a noun: one word
    ("雨により中止", "あめに より ちゅうし"),  # but により stays apart
    ("その他の本", "そのたの ほん"),
    ("まもなく始まります", "まもなく はじまります"),  # Sudachi splits it ま|も|なく
    ("石を3個追加しました", "いしを 3こ ついかしました"),  # a counter, then a verbal noun
    ("クラフト可能な石", "クラフトかのうな いし"),  # a noun and a 形状詞
])
def test_kana_only_language(tokenizer, aligner, grade_kanji, text, kana):
    fixes = load_reading_fixes("data/reading_fixes.toml")
    markup = annotate({"key": text}, tokenizer, aligner, fixes).markup["key"]
    assert render(markup, KANA_ONLY, grade_kanji) == kana


@pytest.mark.parametrize("text, languages", [
    # The table of README.md: ja_kana, ja_g1 ... ja_g6
    ("鉄格子", ["てつごうし", "てつごう子", "てつごう子", "鉄ごう子", "鉄ごう子", "鉄格子", "鉄格子"]),
    ("作業台", ["さぎょうだい", "さぎょうだい", "作ぎょう台", "作業台", "作業台", "作業台", "作業台"]),
    ("言語設定…", ["げんごせってい…", "げんごせってい…", "言語せってい…", "言語せっ定…", "言語せっ定…", "言語設定…", "言語設定…"]),
])
def test_the_table_of_the_readme(tokenizer, aligner, grade_kanji, text, languages):
    fixes = load_reading_fixes("data/reading_fixes.toml")
    markup = annotate({"key": text}, tokenizer, aligner, fixes).markup["key"]
    assert [render(markup, grade, grade_kanji) for grade in (KANA_ONLY, 1, 2, 3, 4, 5, 6)] == languages
