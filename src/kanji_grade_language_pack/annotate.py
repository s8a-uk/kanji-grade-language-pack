"""The reading markup of every string of ja_jp.json, and the list of words with their readings for review."""
import re
from dataclasses import dataclass, field

from . import bunsetsu
from .kanji import has_kanji, to_hiragana
from .kanji_reading_alignment import DigitsInWord, ReadingAligner
from .reading_fixes import ReadingFixes
from .reading_markup import BOUNDARY

# The text before a word ends with a placeholder (bunsetsu.PLACEHOLDER, the one pattern of them) or a digit
PLACEHOLDER_END = re.compile(f"(?:{bunsetsu.PLACEHOLDER.pattern})$")
NUMBER_END = re.compile(r"[0-9０-９]$")


@dataclass
class WordReading:
    """A word with one reading, over all strings: for build/word_readings_for_review.tsv."""
    markup: str
    status: str
    fixed: bool
    name: bool  # Sudachi took it for a person's name (固有名詞-人名): often a misreading (当分の間村から)
    count: int = 0
    examples: list[str] = field(default_factory=list)


@dataclass
class Annotation:
    markup: dict[str, str]
    words: dict[tuple[str, str], WordReading]


def _after(text_before: str) -> str | None:
    if PLACEHOLDER_END.search(text_before):
        return "placeholder"
    if NUMBER_END.search(text_before):
        return "number"
    return None


def annotate_line(tokenizer, key: str, line: str, aligner: ReadingAligner, fixes: ReadingFixes,
                  words: dict[tuple[str, str], WordReading]) -> str:
    out = []
    line_words = bunsetsu.words(tokenizer, line)
    position = 0
    for i, word in enumerate(line_words):
        if i and bunsetsu.starts_bunsetsu(line_words, i):
            out.append(BOUNDARY)
        before = line[:position]
        position += len(word.surface)
        if not has_kanji(word.surface):
            out.append(word.surface)
            continue
        (token,) = word.tokens
        surface = word.surface
        sudachi = to_hiragana(token.reading_form())
        previous_word = line_words[i - 1].surface if i else ""
        next_word = line_words[i + 1].surface if i + 1 < len(line_words) else ""
        fixed = fixes.reading(key, surface, sudachi, previous_word, next_word, _after(before))
        reading = sudachi if fixed is None else fixed
        if surface in fixes.unsplit_words:
            fixes.mark_unsplit_word_used(surface)
        try:
            markup = aligner.markup_word(surface, reading)
        except DigitsInWord as e:
            raise DigitsInWord(f"{key}: {e}: add a word_reading rule or a string_markup") from None
        for kanji in markup.extra_readings_used:
            fixes.mark_kanji_reading_used(kanji)
        name = tuple(token.part_of_speech()[1:3]) == ("固有名詞", "人名")
        entry = words.setdefault((surface, reading), WordReading(markup.markup, markup.status, fixed is not None, name))
        entry.count += 1
        if len(entry.examples) < 3 and line not in entry.examples:
            entry.examples.append(line)
        out.append(markup.markup)
    if position != len(line):
        raise AssertionError(f"{key}: Sudachi's words do not give the line back: {line!r}")
    return "".join(out)


def annotate(texts: dict[str, str], tokenizer, aligner: ReadingAligner, fixes: ReadingFixes) -> Annotation:
    markup: dict[str, str] = {}
    words: dict[tuple[str, str], WordReading] = {}
    for key, text in texts.items():
        fixed = fixes.markup_of_string(key)
        if fixed is not None:
            markup[key] = fixed
        elif has_kanji(text) or any("ぁ" <= c <= "ヺ" for c in text):
            # Sudachi splits around line breaks oddly: one line at a time
            markup[key] = "\n".join(annotate_line(tokenizer, key, line, aligner, fixes, words)
                                    for line in text.split("\n"))
        else:
            markup[key] = text
    return Annotation(markup, words)


def word_readings_tsv(words: dict[tuple[str, str], WordReading]) -> str:
    lines = ["word\treading\tmarkup\tstatus\tcount\tfixed\texamples"]
    for (surface, reading), w in sorted(words.items(), key=lambda x: -x[1].count):
        examples = " ／ ".join(e.replace("\n", "\\n").replace("\t", " ") for e in w.examples)
        lines.append(f"{surface}\t{reading}\t{w.markup}\t{w.status}\t{w.count}\t{int(w.fixed)}\t{examples}")
    return "\n".join(lines) + "\n"
