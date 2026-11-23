import pytest

from kanji_grade_language_pack.grade_kanji_pdf import appendix_words, conjugates, joyo_table, split_kun


@pytest.mark.parametrize("kanji, reading, examples, kun", [
    ("一", "ひとつ", "一つ", "ひと-つ"),
    ("生", "おう", "生い立ち，生い茂る", "お-う"),  # a conjugated form
    ("足", "たる", "舌足らず", "た-る"),
    ("初", "そめる", "書き初め，出初め式", "そ-める"),  # る dropped
    ("常", "つね", "常，常に，常々", "つね"),  # the first example has no okurigana
    ("並", "なみ", "並の品，並木，足並み", "なみ"),  # other kana after the kanji
    ("干", "ひる", "干上がる，干物，潮干狩り", "ひ-る"),  # the exception
])
def test_split_kun(kanji, reading, examples, kun):
    assert split_kun(kanji, reading, examples) == kun


def test_conjugates():
    assert conjugates("う", "い")
    assert conjugates("る", "らず")
    assert not conjugates("ね", "に")  # not the ending of a verb


def test_joyo_table_rows():
    lines = ["前書き", "亜\t（亞）\t \tア\t亜流，亜麻", "哀\t \tアイ\t哀愁", "\t \tあわれむ\t哀れむ，哀れみ\t",
             "\t \t三羽（ば），六羽（ぱ）\t注", "付 表"]
    assert joyo_table(lines) == {"亜": [("ア", "亜流，亜麻")], "哀": [("アイ", "哀愁"), ("あわれむ", "哀れむ，哀れみ")]}


def test_appendix_words():
    lines = ["付　　　表", "※以下に挙げられている語を", "あす 明日 かわせ 為替", "あずき 小豆 かわら\t 河原 川原",
             "しわす", "（「しはす」とも言う。）", "師走 はつか 二十日"]
    assert appendix_words(lines) == {"明日": "あす", "為替": "かわせ", "小豆": "あずき", "河原": "かわら",
                                     "川原": "かわら", "師走": "しわす", "二十日": "はつか"}
