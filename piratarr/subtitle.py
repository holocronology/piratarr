"""SRT subtitle parser and writer.

Handles reading, parsing, translating, and writing SRT subtitle files.
"""

import os
import re
from dataclasses import dataclass, field

from piratarr.translator import translate


@dataclass
class SubtitleEntry:
    """A single subtitle entry in an SRT file."""

    index: int
    start_time: str
    end_time: str
    text: str


@dataclass
class SubtitleFile:
    """A parsed SRT subtitle file."""

    entries: list[SubtitleEntry] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.entries)


def parse_srt(content: str) -> SubtitleFile:
    """Parse an SRT file's content into a SubtitleFile.

    Args:
        content: Raw text content of an SRT file.

    Returns:
        A SubtitleFile with parsed entries.
    """
    entries = []
    # Split on blank lines to get blocks
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        try:
            index = int(lines[0].strip())
        except ValueError:
            continue

        # Parse timestamp line: "00:00:01,000 --> 00:00:04,000"
        time_match = re.match(
            r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})",
            lines[1].strip(),
        )
        if not time_match:
            continue

        start_time = time_match.group(1)
        end_time = time_match.group(2)
        text = "\n".join(lines[2:])

        entries.append(
            SubtitleEntry(
                index=index,
                start_time=start_time,
                end_time=end_time,
                text=text,
            )
        )

    return SubtitleFile(entries=entries)


def write_srt(subtitle_file: SubtitleFile) -> str:
    """Serialize a SubtitleFile back to SRT format.

    Args:
        subtitle_file: The SubtitleFile to serialize.

    Returns:
        The SRT-formatted string.
    """
    blocks = []
    for entry in subtitle_file.entries:
        block = f"{entry.index}\n{entry.start_time} --> {entry.end_time}\n{entry.text}"
        blocks.append(block)
    return "\n\n".join(blocks) + "\n"


def translate_subtitle_file(subtitle_file: SubtitleFile, seed: int | None = None) -> SubtitleFile:
    """Translate all entries in a SubtitleFile to pirate speak.

    Args:
        subtitle_file: The source SubtitleFile to translate.
        seed: Optional random seed for reproducible translations.

    Returns:
        A new SubtitleFile with pirate-speak translations.
    """
    translated_entries = []
    for entry in subtitle_file.entries:
        translated_text = translate(entry.text, seed=seed)
        translated_entries.append(
            SubtitleEntry(
                index=entry.index,
                start_time=entry.start_time,
                end_time=entry.end_time,
                text=translated_text,
            )
        )
    return SubtitleFile(entries=translated_entries)


def get_pirate_srt_path(original_path: str) -> str:
    """Get the output path for a pirate-translated SRT file.

    Preserves language codes so media players (Plex, Jellyfin) can identify
    the subtitle language.  The '.pirate' marker is inserted before the
    language/tag suffixes.

    Examples:
        'movie.en.srt'      -> 'movie.pirate.en.srt'
        'movie.eng.srt'     -> 'movie.pirate.eng.srt'
        'movie.en.hi.srt'   -> 'movie.pirate.en.hi.srt'
        'movie.en.sdh.srt'  -> 'movie.pirate.en.sdh.srt'
        'movie.srt'         -> 'movie.pirate.srt'

    Args:
        original_path: Path to the original SRT file.

    Returns:
        Path for the pirate-speak SRT output.
    """
    base, ext = os.path.splitext(original_path)
    # Match language code and optional tags (hi, sdh, forced, cc, default)
    # at the end of the base name, e.g. ".en", ".eng.hi", ".en.sdh"
    suffix_pattern = re.compile(
        r"(\.(en|eng|english))(\.(hi|sdh|forced|cc|default))?$",
        re.IGNORECASE,
    )
    m = suffix_pattern.search(base)
    if m:
        # Insert .pirate before the language suffix
        insert_pos = m.start()
        return f"{base[:insert_pos]}.pirate{base[insert_pos:]}{ext}"
    return f"{base}.pirate{ext}"


def process_srt_file(input_path: str, output_path: str | None = None, seed: int | None = None) -> str:
    """Read an SRT file, translate it to pirate speak, and write the result.

    Args:
        input_path: Path to the source SRT file.
        output_path: Path for the output file. Auto-generated if None.
        seed: Optional random seed for reproducible translations.

    Returns:
        The path of the written output file.
    """
    if output_path is None:
        output_path = get_pirate_srt_path(input_path)

    with open(input_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    subtitle_file = parse_srt(content)
    translated = translate_subtitle_file(subtitle_file, seed=seed)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(write_srt(translated))

    return output_path
