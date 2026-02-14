"""Tests for the SRT subtitle parser and writer."""

from piratarr.subtitle import (
    SubtitleEntry,
    SubtitleFile,
    get_pirate_srt_path,
    parse_srt,
    translate_subtitle_file,
    write_srt,
)

SAMPLE_SRT = """1
00:00:01,000 --> 00:00:04,000
Hello my friend.

2
00:00:05,000 --> 00:00:08,000
How are you doing today?

3
00:00:09,000 --> 00:00:12,000
I am looking for the treasure.
"""


def test_parse_srt_entry_count():
    result = parse_srt(SAMPLE_SRT)
    assert result.count == 3


def test_parse_srt_first_entry():
    result = parse_srt(SAMPLE_SRT)
    entry = result.entries[0]
    assert entry.index == 1
    assert entry.start_time == "00:00:01,000"
    assert entry.end_time == "00:00:04,000"
    assert entry.text == "Hello my friend."


def test_parse_srt_second_entry():
    result = parse_srt(SAMPLE_SRT)
    entry = result.entries[1]
    assert entry.index == 2
    assert "How are you" in entry.text


def test_write_srt_roundtrip():
    parsed = parse_srt(SAMPLE_SRT)
    output = write_srt(parsed)
    reparsed = parse_srt(output)
    assert reparsed.count == parsed.count
    for orig, new in zip(parsed.entries, reparsed.entries):
        assert orig.index == new.index
        assert orig.start_time == new.start_time
        assert orig.end_time == new.end_time
        assert orig.text == new.text


def test_translate_subtitle_file():
    parsed = parse_srt(SAMPLE_SRT)
    translated = translate_subtitle_file(parsed, seed=42)
    assert translated.count == parsed.count
    # Timestamps should be preserved
    for orig, trans in zip(parsed.entries, translated.entries):
        assert orig.start_time == trans.start_time
        assert orig.end_time == trans.end_time
    # Text should be different (translated)
    assert translated.entries[0].text != parsed.entries[0].text


def test_get_pirate_srt_path():
    assert get_pirate_srt_path("/movies/Movie/Movie.srt") == "/movies/Movie/Movie.pirate.srt"


def test_get_pirate_srt_path_preserves_lang():
    # Language code should be kept at the end so media players detect the language
    assert get_pirate_srt_path("/movies/Movie/Movie.en.srt") == "/movies/Movie/Movie.pirate.en.srt"
    assert get_pirate_srt_path("/movies/Movie/Movie.eng.srt") == "/movies/Movie/Movie.pirate.eng.srt"


def test_get_pirate_srt_path_preserves_lang_with_tags():
    assert get_pirate_srt_path("/tv/Show/S01E01.en.hi.srt") == "/tv/Show/S01E01.pirate.en.hi.srt"
    assert get_pirate_srt_path("/tv/Show/S01E01.en.sdh.srt") == "/tv/Show/S01E01.pirate.en.sdh.srt"
    assert get_pirate_srt_path("/tv/Show/S01E01.eng.forced.srt") == "/tv/Show/S01E01.pirate.eng.forced.srt"


def test_get_pirate_srt_path_preserves_extension():
    path = get_pirate_srt_path("/tv/Show/S01E01.srt")
    assert path.endswith(".srt")
    assert ".pirate." in path


def test_parse_empty_content():
    result = parse_srt("")
    assert result.count == 0


def test_parse_malformed_srt():
    malformed = "not a real srt file\njust some text"
    result = parse_srt(malformed)
    assert result.count == 0
