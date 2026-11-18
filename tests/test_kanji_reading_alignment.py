import pytest

from kanji_grade_language_pack.kanji_reading_alignment import DigitsInWord, appendix_runs, kun_forms, variants


@pytest.mark.parametrize("word, reading, markup", [
    ("鉄格子", "てつごうし", "⟦鉄|てつ⟧⟦格|ごう⟧⟦子|し⟧"),  # rendaku: こう → ごう
    ("学校", "がっこう", "⟦学|がっ⟧⟦校|こう⟧"),  # sokuon: がく → がっ
    ("一本", "いっぽん", "⟦一|いっ⟧⟦本|ぽん⟧"),  # handakuten: ほん → ぽん
    ("人々", "ひとびと", "⟦人々|ひとびと⟧"),  # 々 repeats the kanji, voiced
    ("入り口", "いりぐち", "⟦入|い⟧り⟦口|ぐち⟧"),
    ("気持ち", "きもち", "⟦気|き⟧⟦持|も⟧ち"),
    ("ヶ月", "かげつ", "⟦ヶ月|かげつ⟧"),  # ヶ goes with the kanji after it
    ("今日", "きょう", "⟦今日|きょう⟧"),  # 付表: read as a whole
    ("友達", "ともだち", "⟦友|とも⟧⟦達|だち⟧"),  # each kanji takes a reading: no need of the 付表 run
    ("手伝い", "てつだい", "⟦手伝|てつだ⟧い"),  # 付表 手伝う
    ("避雷針", "ひらいしん", "⟦避雷|ひらい⟧⟦針|しん⟧"),  # kanji not taught at school go together
    ("貯める", "ためる", "⟪貯|た⟫める"),  # た is not a reading of 貯 in the 常用漢字表: always kana
    ("欠片", "かけら", "⟪欠片|かけら⟫"),  # unsplit_words
])
def test_markup_word(aligner, word, reading, markup):
    assert aligner.markup_word(word, reading).markup == markup


def test_digits_with_kanji_need_a_fix(aligner):
    with pytest.raises(DigitsInWord):
        aligner.markup_word("3匹", "さんびき")


def test_an_empty_reading_is_an_error(aligner):
    with pytest.raises(ValueError):
        aligner.markup_word("漢字", "")


def test_variants():
    assert variants("ほん") == {"ほん", "ぼん", "ぽん"}
    assert variants("てつ") == {"てつ", "でつ", "てっ", "でっ"}
    with pytest.raises(ValueError):
        variants("")


def test_kun_forms():
    assert kun_forms("ひ-く") == {"ひ", "ひく", "ひき"}
    assert kun_forms("やま") == {"やま"}


def test_appendix_runs():
    assert appendix_runs("今日", "きょう") == [("今日", "きょう")]
    assert appendix_runs("お巡りさん", "おまわりさん") == [("巡", "まわ")]
    assert appendix_runs("差し支える", "さしつかえる") == [("差", "さ"), ("支", "つか")]
