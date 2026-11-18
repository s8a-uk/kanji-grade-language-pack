"""Sudachi's words, and where a bunsetsu starts (the kana-only language puts a space there)."""
import re
from collections.abc import Iterator
from dataclasses import dataclass

from sudachipy import SplitMode

# Parts of speech that start a bunsetsu (自立語), unless a rule below joins them to the word before
CONTENT = {"名詞", "代名詞", "動詞", "形容詞", "形状詞", "副詞", "連体詞", "接続詞", "感動詞", "接頭辞"}
BRACKETS = "（）()「」『』［］[]"


def tokens(tokenizer, text: str) -> Iterator:
    """Sudachi's words, with words that swallowed brackets (時間（ティック）) split again piece by piece. Their surfaces
    put together give text back."""
    for token in tokenizer.tokenize(text):
        surface = token.surface()
        if token.part_of_speech()[1] == "固有名詞" and len(surface) > 3 and any(c in "のにが" for c in surface[1:-1]):
            # A name Sudachi reads as one word with particles inside (灰色の花模様): its short units, for the spaces
            yield from tokenizer.tokenize(surface, SplitMode.A)
        elif len(surface) > 1 and any(c in BRACKETS for c in surface):
            piece = ""
            for c in surface + "\0":
                if c in BRACKETS or c == "\0":
                    if piece:
                        yield from tokens(tokenizer, piece)
                    if c != "\0":
                        yield from tokenizer.tokenize(c)
                    piece = ""
                else:
                    piece += c
        else:
            yield token


PLACEHOLDER = re.compile(r"%(?:\d+\$)?[a-zA-Z%]")
PLACEHOLDER_PART_OF_SPEECH = ("名詞", "普通名詞", "一般", "*", "*", "*")
# Words Sudachi splits into pieces that are one word for the bunsetsu (まもなく: ま|も|なく), with their part of speech
JOINED_WORDS = {"まもなく": ("副詞", "*", "*", "*", "*", "*")}
# Words that stay with a counter after a number (%s個以上, 5分前, 2日目)
AFTER_COUNTER = {"以上", "以下", "以内", "未満", "分", "前", "後", "目", "毎", "毎秒", "間", "ごと"}


@dataclass
class Word:
    """A word of a line: one of Sudachi's tokens, or a placeholder (%s, %1$s) or a word of JOINED_WORDS that Sudachi
    splits into pieces."""
    surface: str
    part_of_speech: tuple[str, ...]
    dictionary_form: str
    tokens: list  # Sudachi's tokens
    placeholder: bool = False


def words(tokenizer, line: str) -> list[Word]:
    """The words of a line; their surfaces put together give the line back."""
    spans = [m.span() for m in PLACEHOLDER.finditer(line)]
    out: list[Word] = []
    position = 0
    for token in tokens(tokenizer, line):
        start, end = position, position + len(token.surface())
        position = end
        span = next((s for s in spans if s[0] <= start < s[1]), None)
        if span is not None and end <= span[1]:
            if out and out[-1].placeholder and span[0] < start:  # the rest of a placeholder
                out[-1].surface += token.surface()
                out[-1].tokens.append(token)
                continue
            if start == span[0]:
                out.append(Word(token.surface(), PLACEHOLDER_PART_OF_SPEECH, token.surface(), [token], True))
                continue
        out.append(Word(token.surface(), tuple(token.part_of_speech()), token.dictionary_form(), [token]))
    return _join(out)


def _join(line_words: list[Word]) -> list[Word]:
    """Words of JOINED_WORDS put back together."""
    out: list[Word] = []
    i = 0
    while i < len(line_words):
        for n in (3, 2):
            pieces = line_words[i:i + n]
            surface = "".join(w.surface for w in pieces)
            if len(pieces) == n and surface in JOINED_WORDS and not any(w.placeholder for w in pieces):
                out.append(Word(surface, JOINED_WORDS[surface], surface, [t for w in pieces for t in w.tokens]))
                i += n
                break
        else:
            out.append(line_words[i])
            i += 1
    return out


def _number(word: Word) -> bool:
    return word.placeholder or word.part_of_speech[1] == "数詞" or word.surface.isdigit()


def starts_bunsetsu(line_words: list[Word], i: int) -> bool:
    """Whether a bunsetsu starts at the word i (i >= 1) of a line."""
    previous, word = line_words[i - 1], line_words[i]
    before = line_words[i - 2] if i >= 2 else None
    p, t = previous.part_of_speech, word.part_of_speech
    if t[0] not in CONTENT or p[0] in ("補助記号", "空白", "接頭辞") or word.surface.isspace():
        return False
    if previous.surface == "その" and word.surface == "他":
        return False  # その他
    if previous.surface == "他" and t[0] == "名詞":
        return before is not None and before.surface == "その"  # 他プレイヤー; その他 %s項目
    if before is not None and _number(before) and t[0] in ("名詞", "形状詞") \
            and (p[2] in ("助数詞", "助数詞可能") or p[0] == "接尾辞" or (p[0] == "名詞" and len(previous.surface) <= 2)) \
            and word.surface not in AFTER_COUNTER and (t[0] == "形状詞" or t[2] in ("サ変可能", "形状詞可能", "サ変形状詞可能")):
        return True  # %1$s個 禁止しました, 30日間 無料で, 1つ 必要です
    if t[0] == "名詞" and p[0] == "名詞" and p[2] == "副詞可能" and t[2] != "助数詞可能" and word.surface != "時":
        return True  # この まま ワールドに (通常時 stays together)
    if t[0] == "名詞" and p[0] in ("名詞", "接尾辞", "形状詞"):
        return False  # compound nouns
    if t[0] == "形状詞" and p[0] == "名詞" and p[2] != "副詞可能":
        return False  # クラフト可能な, 建築高度
    if t[0] == "名詞" and p[0] == "形容詞" and p[5].startswith("語幹"):
        return False  # 薄灰色
    if t[0] == "名詞" and p[0] == "動詞" and p[5] == "連用形-一般" \
            and previous.dictionary_form not in ("よる", "因る", "対する", "引き続く", "する", "為る", "れる", "せる"):
        return False  # 吊り看板, 空き容量, 読み込み画面 (により チャットが stays apart)
    if t[0] == "動詞" and word.dictionary_form in ("入る",) and word.surface == "入り" and p[0] == "名詞":
        return False  # ヒトミソウ入り
    if t[0] in ("動詞", "形容詞") and p[0] == "動詞" and p[5].startswith("連用形"):
        return False  # compound verbs: 乗りこなす, 読みにくい
    if t[0] == "動詞" and word.dictionary_form in ("すぎる", "過ぎる"):
        return False  # 長すぎる, 大きすぎる
    if t[0] == "動詞" and word.dictionary_form in ("する", "できる", "出来る") and p[0] in ("名詞", "形状詞", "接尾辞", "副詞"):
        return False  # 移動する, 有効化する, スポーンする (Sudachi reads スポーン as an adverb)
    return True
