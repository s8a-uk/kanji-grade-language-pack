"""The kanji of each school grade with their readings, and the words of the 付表, from two PDFs of the Japanese
government (each checked against a fixed SHA-256).

  grades    MEXT「音訓の小・中・高等学校段階別割り振り表」(2017-03): next to every 常用漢字, its grade in the 学年別漢字配当表
            of the 小学校学習指導要領 (2017 notice, in force from 2020). The 配当表 itself (the 別表 of the 学習指導要領) is
            in the PDFs as images, so it cannot be read as text
  readings  文化庁「常用漢字表」(2010 cabinet notice): every reading of the 本表, the special ones (indented) included; the
            okurigana of a kun reading (ひと-つ) comes from the first example word of the table (一つ)
  付表       the words of the same table read as a whole (今日 きょう, 小豆 あずき)
The 配当表 and the 常用漢字表 are public notices, out of copyright (著作権法 13 条). pypdf gives a row of a table as one
line with its cells separated by tabs.
"""
import io
import re

from pypdf import PdfReader

from .download import download

WARIFURI_PDF = ("https://www.mext.go.jp/a_menu/shotou/new-cs/__icsFiles/afieldfile/2017/05/15/1385768.pdf",
                "0bc189982a50122f1e35dd6a751bfdff0ec5a0ad67e99eda916d012f859a5ae4")
JOYO_PDF = ("https://www.bunka.go.jp/kokugo_nihongo/sisaku/joho/joho/kijun/naikaku/pdf/joyokanjihyo_20101130.pdf",
            "d9f28aeb4ce8250dbde07de20ac66cca71805ba09d94e4942c752dffa84d8d42")
GRADE_COUNTS = (80, 160, 200, 202, 193, 191)  # 学年別漢字配当表 (2017)
JOYO_COUNT = 2136
APPENDIX_COUNT = 116  # readings in the 付表; some have two spellings (かわら 河原 川原)

KANJI = r"[㐀-鿿豈-﫿\U00020000-\U0003ffff]"  # 𠮟 is outside the BMP
ON = re.compile(r"[ァ-ヶー]+")
READING = re.compile(r"[ァ-ヶー]+|[ぁ-ゖ]+")
HIRAGANA = re.compile(r"[ぁ-ゖー]+")
# Kun readings whose okurigana the examples of the table cannot show: ひる is a verb (干る), its examples are compounds
OKURIGANA_EXCEPTIONS = {"干": {"ひる": "ひ-る"}}
# The kana rows of the gojūon table, to match the ending of a verb to its conjugated form (生う → 生い立ち)
ROWS = ("あいうえお", "かきくけこ", "がぎぐげご", "さしすせそ", "ざじずぜぞ", "たちつてと", "だぢづでど", "なにぬねの",
        "はひふへほ", "ばびぶべぼ", "ぱぴぷぺぽ", "まみむめも", "らりるれろ", "わゐうゑを")


class TableError(Exception):
    pass


def pdf_lines(data: bytes) -> list[str]:
    return [line for page in PdfReader(io.BytesIO(data)).pages for line in page.extract_text().splitlines()]


def grades(lines: list[str]) -> dict[str, int]:
    """{kanji: grade} from the 割り振り表: a kanji followed by its grade (委 3 イ ○)."""
    out: dict[str, int] = {}
    for line in lines:
        for m in re.finditer(rf"(?:^|\s)({KANJI})\s+([1-6])\s", line):
            out.setdefault(m[1], int(m[2]))
    return out


def joyo_table(lines: list[str]) -> dict[str, list[tuple[str, str]]]:
    """{kanji: [(reading, examples), ...]} from the 本表 of the 常用漢字表, in its order. A row is
    <kanji> <other forms>? <reading> <examples> <note>? for the first reading of a kanji, <reading> <examples> <note>?
    for the others; a special reading is indented with a full-width space."""
    table: dict[str, list[tuple[str, str]]] = {}
    current, started = None, False
    for line in lines:
        if "\t" not in line:  # page heads (ア－イ), footers, the text before and after the table
            if started and line.strip().startswith("付"):  # 付表
                break
            continue
        cells = [c.strip(" 　") for c in line.split("\t")]
        cells = [c for c in cells if c]
        # The reading; the cells before it are the kanji and its other forms (亜（亞）, 遜［遜］, 弁 辨). A row without
        # one is the rest of the row above: other forms (瓣, 辯), examples or a note (三羽（ば），六羽（ぱ）)
        i = next((i for i, c in enumerate(cells) if READING.fullmatch(c)), None)
        if i is None:
            continue
        if i and re.fullmatch(KANJI, cells[0]):
            current = cells[0]
            started = started or current == "亜"
            if started and current in table:
                raise TableError(f"常用漢字表: {current} twice")
            table[current] = []
        if started:
            table[current].append((cells[i], cells[i + 1] if i + 1 < len(cells) else ""))
    return table


def appendix_words(lines: list[str]) -> dict[str, str]:
    """{spelling: reading} of the 付表: lines of "<reading> <spelling> <spelling>? <reading> <spelling> ...", after the
    line 付表 and its two notes."""
    start = next(i for i, line in enumerate(lines) if re.fullmatch(r"付\s*表", line.strip()))
    out: dict[str, str] = {}
    reading = None
    for line in lines[start + 1:]:
        if ".indd" in line or line.strip().isdigit() or "例「" in line or line.strip().startswith(("※", "用い", "（", "「")):
            continue
        for token in line.replace("\t", " ").split():
            if HIRAGANA.fullmatch(token):
                reading = token
            elif reading is not None:
                out[token] = reading
    return out


def conjugates(ending: str, kana: str) -> bool:
    """Whether kana (after the kanji in an example word) is a conjugated form of the okurigana ending of a verb: the
    last kana in another column of its row (生う → 生い立ち, 足る → 足らず), or る dropped (初める → 書き初め)."""
    if ending[-1] == "る" and len(ending) > 1 and kana.startswith(ending[:-1]):
        return True
    if ending[-1] not in "うくぐすつぬぶむる" or len(kana) < len(ending) or not kana.startswith(ending[:-1]):
        return False
    return any(ending[-1] in row and kana[len(ending) - 1] in row for row in ROWS)


def split_kun(kanji: str, reading: str, examples: str) -> str:
    """The kun reading with its okurigana marked (ひと-つ). The first example word gives it: the kana after the kanji are
    the end of the reading (一つ) or a conjugated form of it (生い立ち); none (常) or other kana (並の品) mean none."""
    if reading in OKURIGANA_EXCEPTIONS.get(kanji, {}):
        return OKURIGANA_EXCEPTIONS[kanji][reading]
    for word in examples.split("，"):
        m = re.search(rf"{kanji}([ぁ-ゖ]*)", word)
        if not m:
            continue
        for i in range(1, len(reading)):
            if m[1].startswith(reading[i:]) or conjugates(reading[i:], m[1]):
                return f"{reading[:i]}-{reading[i:]}"
        return reading
    return reading


def build_grade_kanji(warifuri_lines: list[str], joyo_lines: list[str]) -> list[dict]:
    grade = grades(warifuri_lines)
    counts = tuple(sum(1 for g in grade.values() if g == n) for n in range(1, 7))
    if counts != GRADE_COUNTS:
        raise TableError(f"割り振り表: {counts} kanji per grade, expected {GRADE_COUNTS}")
    table = joyo_table(joyo_lines)
    if len(table) != JOYO_COUNT:
        raise TableError(f"常用漢字表: {len(table)} kanji, expected {JOYO_COUNT}")
    missing = [c for c in grade if c not in table]
    if missing:
        raise TableError(f"kanji of the 割り振り表 not in the 常用漢字表: {''.join(missing)}")
    out = []
    for g in range(1, 7):
        for c in (c for c in table if grade.get(c) == g):  # in the order of the 常用漢字表
            on = [r for r, _ in table[c] if ON.fullmatch(r)]
            kun = [split_kun(c, r, ex) for r, ex in table[c] if not ON.fullmatch(r)]
            if not on and not kun:
                raise TableError(f"{c}: no reading")
            if len(set(on)) != len(on) or len(set(kun)) != len(kun):
                raise TableError(f"{c}: a reading twice: {on} {kun}")
            out.append({"kanji": c, "grade": g, "on": on, "kun": kun})
    if len(out) != sum(GRADE_COUNTS):
        raise TableError(f"{len(out)} kanji, expected {sum(GRADE_COUNTS)}")
    return out


def build_appendix(joyo_lines: list[str]) -> list[dict]:
    words = appendix_words(joyo_lines)
    if len(set(words.values())) != APPENDIX_COUNT:
        raise TableError(f"付表: {len(set(words.values()))} readings, expected {APPENDIX_COUNT}")
    return [{"word": w, "reading": r} for w, r in words.items()]


def fetch_and_build() -> tuple[list[dict], list[dict]]:
    warifuri = pdf_lines(download(WARIFURI_PDF[0], "sha256", WARIFURI_PDF[1]))
    joyo = pdf_lines(download(JOYO_PDF[0], "sha256", JOYO_PDF[1]))
    return build_grade_kanji(warifuri, joyo), build_appendix(joyo)
