"""Splitting the reading of a word over its kanji (鉄格子 てつごうし → 鉄 てつ, 格 ごう, 子 し).

A grade's language keeps each kanji the children have learnt, so the reading Sudachi gives for a whole word is split
over its kanji, using the readings of the 常用漢字表 as they may sound inside a word, and the words of its 付表 read as
a whole (今日 きょう). A kanji read in a way neither lists is always written in kana: the children learn the kanji with
its listed readings only.
"""
import functools
import re
from dataclasses import dataclass

from .kanji import GradeKanji, is_kanji, to_hiragana
from .reading_markup import kana_only_run, run

DAKUTEN = dict(zip("かきくけこさしすせそたちつてとはひふへほ", "がぎぐげござじずぜぞだぢづでどばびぶべぼ"))
HANDAKUTEN = dict(zip("はひふへほ", "ぱぴぷぺぽ"))
SOKUON_END = set("くつちき")
RENYOU = dict(zip("うくぐすつぬぶむる", "いきぎしちにびみり"))


def variants(reading: str) -> set[str]:
    """A reading as it may sound inside a word: rendaku on the first kana, sokuon on the last."""
    if not reading:
        raise ValueError("empty reading")
    first = reading[0]
    heads = {first, DAKUTEN.get(first, first), HANDAKUTEN.get(first, first)}
    if first == "ち":
        heads.add("ぢ")
    out = {h + reading[1:] for h in heads}
    if len(reading) >= 2 and reading[-1] in SOKUON_END:
        out |= {v[:-1] + "っ" for v in out}
    return out


def kun_forms(kun: str) -> set[str]:
    """A kun reading (ひ-く) as it is written into words: the stem, with the okurigana, its 連用形 and the okurigana but
    its last kana (場合 あ-う → あい, 引数 ひ-く → ひき, 見積 つ-もる → つもり, 書き初め そ-める → そめ)."""
    stem, _, okurigana = kun.partition("-")
    forms = {stem}
    if okurigana:
        forms |= {stem + okurigana, stem + okurigana[:-1] + RENYOU.get(okurigana[-1], ""), stem + okurigana[:-1]}
    return forms


@dataclass(frozen=True)
class Part:
    text: str
    reading: str | None  # None for kana and other characters
    start: int  # where its sound starts in the word's reading
    guessed: bool = False  # a taught kanji given a reading not among its candidates
    whole_run: bool = False  # several kanji of a 付表 word read as a whole (今日 きょう)


def appendix_runs(spelling: str, reading: str) -> list[tuple[str, str]]:
    """The kanji runs of a 付表 word with their readings: お巡りさん おまわりさん → [(巡, まわ)], 今日 きょう → [(今日, きょう)]."""
    pieces = re.findall(r"[^ぁ-ゖ]+|[ぁ-ゖ]+", spelling)
    pattern = "".join("(.+)" if not re.fullmatch(r"[ぁ-ゖ]+", p) else re.escape(p) for p in pieces)
    m = re.fullmatch(pattern, reading)
    if m is None:
        raise ValueError(f"付表 {spelling} {reading}: the kana do not match")
    kanji_pieces = [p for p in pieces if not re.fullmatch(r"[ぁ-ゖ]+", p)]
    return list(zip(kanji_pieces, m.groups()))


@dataclass(frozen=True)
class WordMarkup:
    markup: str
    # "ok"; "kana only" (a kanji read in a way the tables do not list: that part always in kana); "unsplit" (a word
    # of unsplit_words, always in kana)
    status: str
    extra_readings_used: frozenset[str]  # kanji that took a reading from extra_kanji_readings


class DigitsInWord(ValueError):
    """Sudachi read digits and kanji as one word (3匹 さんびき): the digits stay digits, so the reading cannot be split
    right. A word_reading rule or a string_markup has to give it."""


class ReadingAligner:
    def __init__(self, grade_kanji: dict[str, GradeKanji], extra_kanji_readings: dict[str, tuple[str, ...]],
                 unsplit_words: frozenset[str], appendix_words: dict[str, str]):
        self.grade_kanji = grade_kanji
        self.extra_kanji_readings = extra_kanji_readings
        self.unsplit_words = unsplit_words
        # Runs of the 付表 words: several kanji read as a whole (今日 きょう) are tried as one piece; one kanji (退 の of
        # 立ち退く) gets the reading as a candidate
        self.whole_runs: dict[str, set[str]] = {}
        self.appendix_kanji_readings: dict[str, set[str]] = {}
        for spelling, reading in appendix_words.items():
            for kanji, kanji_reading in appendix_runs(spelling, reading):
                if len(kanji) > 1:
                    self.whole_runs.setdefault(kanji, set()).add(kanji_reading)
                else:
                    self.appendix_kanji_readings.setdefault(kanji, set()).add(kanji_reading)

    @functools.cache
    def table_candidates(self, kanji: str) -> frozenset[str]:
        k = self.grade_kanji[kanji]
        base = {to_hiragana(o) for o in k.on} | self.appendix_kanji_readings.get(kanji, set())
        for kun in k.kun:
            base |= kun_forms(kun)
        return frozenset(v for r in base for v in variants(r))

    @functools.cache
    def candidates(self, kanji: str) -> frozenset[str]:
        extra = {v for r in self.extra_kanji_readings.get(kanji, ()) for v in variants(r)}
        return self.table_candidates(kanji) | extra

    def units(self, surface: str) -> list[tuple[str, str]]:
        """A word as units: ("kanji", chars) for one taught kanji (with a following 々), ("wild", chars) for a run of
        other kanji, ("kana", c), ("other", c)."""
        out: list[tuple[str, str]] = []
        for c in surface:
            if c == "々" and out and out[-1][0] in ("kanji", "wild"):
                out[-1] = (out[-1][0], out[-1][1] + c)
            elif is_kanji(c) and c not in self.grade_kanji:
                if out and out[-1][0] == "wild":
                    out[-1] = ("wild", out[-1][1] + c)
                else:
                    out.append(("wild", c))
            elif is_kanji(c):
                out.append(("kanji", c))
            elif "ぁ" <= c <= "ゖ" or "ァ" <= c <= "ヺ" or c == "ー":
                out.append(("kana", c))
            else:
                out.append(("other", c))
        return out

    def align(self, surface: str, reading: str) -> tuple[list[Part], int] | None:
        """The reading split over the units of the word, and how many taught kanji got a reading not among their
        candidates; None when it cannot be split."""
        units = self.units(surface)
        starts = [0]
        for _, chars in units:
            starts.append(starts[-1] + len(chars))

        @functools.cache
        def go(i: int, j: int) -> tuple[list[Part], int] | None:
            if i == len(units):
                return ([], 0) if j == len(reading) else None
            kind, chars = units[i]
            rest = len(reading) - j
            tries: list[tuple[int, int]] = []  # (length of the reading, cost)
            if kind == "kana":
                if rest and _kana_match(chars, reading[j]):
                    tries = [(1, 0)]
            elif kind == "kanji":
                candidates = self.candidates(chars[0])
                if len(chars) > 1:  # 々: the same reading again, maybe voiced
                    candidates = frozenset(a + b for a in candidates for b in variants(a))
                known = sorted({len(r) for r in candidates if reading.startswith(r, j)}, reverse=True)
                tries = [(n, 0) for n in known] + [(n, 1) for n in range(1, min(rest, 4 * len(chars)) + 1)]
            elif kind == "wild":
                tries = [(n, 0) for n in range(1, min(rest, 4 * len(chars)) + 1)]
            else:
                tries = [(n, 0) for n in range(0, min(rest, 4) + 1)]
            best = None
            for n, cost in tries:
                tail = go(i + 1, j + n)
                if tail is not None and (best is None or tail[1] + cost < best[1]):
                    part = Part(chars, None if kind in ("kana", "other") else reading[j:j + n], j, cost > 0)
                    best = ([part] + tail[0], tail[1] + cost)
                    if best[1] == 0:
                        break
            if best is not None and best[1] == 0:
                return best
            # A 付表 run of several kanji starting here, read as a whole (今日 きょう, 手伝う てつだう): only when the
            # kanji cannot each take one of their readings (友達 stays 友 とも + 達 だち)
            for whole, whole_readings in self.whole_runs.items():
                end = starts[i] + len(whole)
                if surface.startswith(whole, starts[i]) and end in starts:
                    for whole_reading in whole_readings:
                        if reading.startswith(whole_reading, j):
                            tail = go(starts.index(end), j + len(whole_reading))
                            if tail is not None and (best is None or tail[1] < best[1]):
                                best = ([Part(whole, whole_reading, j, whole_run=True)] + tail[0], tail[1])
            return best

        return go(0, 0)

    def markup_word(self, surface: str, reading: str) -> WordMarkup:
        if not reading:
            raise ValueError(f"empty reading for {surface}")
        if surface in self.unsplit_words:
            return WordMarkup(kana_only_run(surface, reading), "unsplit", frozenset())
        if any(kind == "other" and re.fullmatch(r"[0-9０-９]", chars) for kind, chars in self.units(surface)):
            raise DigitsInWord(f"{surface} {reading}")
        result = self.align(surface, reading)
        if result is None or result[1] > 1:
            return WordMarkup(kana_only_run(surface, reading), "kana only", frozenset())
        parts, guesses = result
        # ヶ and ヵ (ヶ月 かげつ) go with the kanji after them, so the kana-only language reads them
        merged: list[Part] = []
        for p in parts:
            if merged and merged[-1].reading is None and merged[-1].text in ("ヶ", "ヵ") and p.reading is not None \
                    and not p.guessed:
                small = merged.pop()
                p = Part(small.text + p.text, reading[p.start - 1] + p.reading, p.start - 1)
            merged.append(p)
        parts = merged
        extra = frozenset(p.text[0] for p in parts
                          if p.reading is not None and not p.whole_run and p.text[0] in self.extra_kanji_readings
                          and p.text[0] in self.grade_kanji and not self._table_reading(p))
        markup = "".join(p.text if p.reading is None
                         else kana_only_run(p.text, p.reading) if p.guessed
                         else run(p.text, p.reading) for p in parts)
        return WordMarkup(markup, "kana only" if guesses else "ok", extra)

    def _table_reading(self, part: Part) -> bool:
        table = self.table_candidates(part.text[0])
        if len(part.text) > 1:
            table = frozenset(a + b for a in table for b in variants(a))
        return part.reading in table


def _kana_match(c: str, r: str) -> bool:
    """Whether the kana c of a word sounds r in its reading: ヶ and ヵ (ヶ月, 一ヵ所) sound か, が or こ; ー any."""
    if c in "ヶヵ":
        return r in "かがこ"
    return to_hiragana(c) == r or c == "ー"
