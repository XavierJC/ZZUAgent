"""Bounded, line-aware Markdown chunking. Never renders or executes content.

This is a block recognizer, not a complete CommonMark parser. Fenced code and
display math remain atomic. Offsets are Python Unicode character offsets;
raw_md always equals the original document[start_offset:end_offset].
"""

from dataclasses import dataclass
from hashlib import sha256
import re

from eduagent.retrieval.lexical import terms

INDEXER_VERSION = "md-blocks-tfidf-v1-800-100"
TARGET_CHARS, OVERLAP_CHARS = 800, 100
MAX_BLOCK_CHARS, MAX_NOTE_CHUNKS = 8192, 256


class ChunkingError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Block:
    start: int
    end: int
    section: str
    protected: bool = False


def blocks(text: str) -> list[Block]:
    lines = text.splitlines(keepends=True)
    offsets, position = [], 0
    for line in lines:
        offsets.append(position)
        position += len(line)
    headings, result, i = [], [], 0
    while i < len(lines):
        start = i
        line = lines[i].rstrip('\r\n')
        heading = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            level = len(heading[1])
            headings = [(depth, value) for depth, value in headings if depth < level]
            headings.append((level, heading[2]))
        section = " / ".join(value for _, value in headings)
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        math = line.strip() in ('$$', r'\[')
        if fence:
            marker = fence[1]
            i += 1
            while i < len(lines):
                close = re.fullmatch(r" {0,3}" + re.escape(marker[0]) + '{' + str(len(marker)) + r",}\s*", lines[i].rstrip('\r\n'))
                i += 1
                if close:
                    break
        elif math:
            close_marker = '$$' if line.strip() == '$$' else r'\]'
            i += 1
            while i < len(lines):
                closing = lines[i].strip() == close_marker
                i += 1
                if closing:
                    break
        elif heading or not line.strip():
            i += 1
        else:
            i += 1
            while i < len(lines):
                following = lines[i].rstrip('\r\n')
                if (not following.strip() or re.match(r"^ {0,3}(#{1,6})\s|^ {0,3}(`{3,}|~{3,})", following)
                        or following.strip() in ('$$', r'\[')):
                    break
                i += 1
        end = offsets[i] if i < len(lines) else len(text)
        if fence or math:
            if end - offsets[start] > MAX_BLOCK_CHARS:
                raise ChunkingError('protected_block_too_large')
        result.append(Block(offsets[start], end, section, bool(fence or math)))
    return result


def split_paragraph(text: str, block: Block) -> list[Block]:
    """Split long prose; keep common inline math and backtick spans intact."""
    if block.protected or block.end - block.start <= TARGET_CHARS:
        return [block]
    raw = text[block.start:block.end]
    spans = [(block.start + m.start(), block.start + m.end()) for m in re.finditer(
        r"(?<!\\)\$[^$\n]+?(?<!\\)\$|`[^`\n]+`", raw)]
    result, start = [], block.start
    while start < block.end:
        end = min(start + TARGET_CHARS, block.end)
        for left, right in spans:
            if left < end < right:
                end = right
        if end - start > MAX_BLOCK_CHARS:
            raise ChunkingError('inline_block_too_large')
        result.append(Block(start, end, block.section))
        if end == block.end:
            break
        following = max(start + 1, end - OVERLAP_CHARS)
        for left, right in spans:
            if left < following < right:
                following = left if left > start else right
        start = following
    return result


def chunk_markdown(note: dict) -> list[dict]:
    text = note['content_md']
    pieces = [part for block in blocks(text) for part in split_paragraph(text, block)]
    groups, active = [], None
    for block in pieces:
        if (active and block.section == active.section and block.start >= active.end
                and block.end - active.start <= TARGET_CHARS):
            active = Block(active.start, block.end, active.section)
        else:
            if active:
                groups.append(active)
            # Small whole paragraphs provide overlap without breaking code/math.
            previous = groups[-1] if groups else None
            start = block.start
            if previous and previous.section == block.section and previous.end == start and not block.protected:
                tail = text[previous.start:previous.end].splitlines(keepends=True)
                overlap = 0
                for line in reversed(tail):
                    if overlap + len(line) > OVERLAP_CHARS:
                        break
                    overlap += len(line)
                # Never duplicate a partial fenced/math block as overlap.
                candidate = text[start - overlap:start]
                if not re.search(r'```|~~~|\$\$|\\\[|\\\]', candidate):
                    start -= overlap
            active = Block(start, block.end, block.section)
    if active:
        groups.append(active)
    result = []
    for block in groups:
        raw = text[block.start:block.end]
        plain = re.sub(r'^ {0,3}(?:#{1,6}\s+|`{3,}[^\n]*|~{3,}[^\n]*)', '', raw, flags=re.M).strip()
        if not terms(plain):
            continue
        ordinal = len(result)
        digest = sha256(raw.encode('utf-8')).hexdigest()
        chunk_id = sha256(f"{note['id']}:{note['revision']}:{ordinal}:{digest}:{INDEXER_VERSION}".encode()).hexdigest()
        result.append(dict(note_id=note['id'], student_id=note['student_id'], course_id=note['course_id'],
            revision=note['revision'], content_hash=note['content_hash'], chunk_id=chunk_id, ordinal=ordinal,
            title=note['title'], section=block.section or note['title'], start_offset=block.start, end_offset=block.end,
            start_line=text.count('\n', 0, block.start) + 1,
            end_line=text.count('\n', 0, max(block.start, block.end - 1)) + 1,
            raw_md=raw, content_text=plain, chunk_hash=digest, indexer_version=INDEXER_VERSION))
    if len(result) > MAX_NOTE_CHUNKS:
        raise ChunkingError('too_many_chunks')
    return result
