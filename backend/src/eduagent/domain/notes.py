"""Personal note validation, independent of scoring and knowledge tracing."""

import base64
import binascii
from hashlib import sha256
from pathlib import PurePath
from uuid import UUID

COURSE_ID = "machine_learning"
MAX_NOTE_BYTES = 65536
MAX_ACTIVE_NOTES = 50
MAX_TOTAL_BYTES = 1048576
MAX_REQUEST_BYTES = 262144


class NoteNotFound(ValueError):
    pass


class NoteConflict(ValueError):
    pass


class NoteTooLarge(ValueError):
    pass


def note_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("笔记编号必须是 UUID 字符串")
    try:
        parsed = UUID(value)
    except ValueError:
        raise ValueError("笔记编号必须是规范 UUID") from None
    if str(parsed) != value:
        raise ValueError("笔记编号必须使用规范小写 UUID")
    return value


def course(value: str) -> str:
    if value != COURSE_ID:
        raise ValueError("当前只支持机器学习课程")
    return value


def revision(value: int) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("expected_revision 必须是正整数")
    return value


def title(value: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 120:
        raise ValueError("笔记标题必须为 1～120 字符")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("笔记标题不能包含控制字符")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise ValueError("笔记标题不是有效 Unicode 文本") from None
    return value.strip()


def content(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("笔记内容必须是 Markdown 字符串")
    try:
        raw = value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise ValueError("笔记内容不是有效 Unicode 文本") from None
    if len(raw) > MAX_NOTE_BYTES:
        raise NoteTooLarge("每篇笔记最多 64 KiB UTF-8 文本")
    if any((ord(char) < 32 and char not in '\n\r\t') or ord(char) == 127 for char in value):
        raise ValueError("笔记包含 NUL 或异常控制字符")
    return value


def content_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def decode_import(file_name: str, encoded: str) -> tuple[str, str, list[str]]:
    if (not isinstance(file_name, str) or not 1 <= len(file_name) <= 200 or file_name != file_name.strip()
            or any(c in '<>:"/\\|?*' or ord(c) < 32 for c in file_name)):
        raise ValueError("文件名无效；仅接受文件基础名，不能包含路径")
    if PurePath(file_name).suffix.lower() not in (".md", ".markdown", ".txt"):
        raise ValueError("只支持 UTF-8 Markdown 或 TXT 文件")
    if not isinstance(encoded, str):
        raise ValueError("导入内容必须是 base64 字符串")
    if len(encoded) > 4 * ((MAX_NOTE_BYTES + 2) // 3):
        raise NoteTooLarge("导入文件最多 64 KiB")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("导入内容的 base64 编码无效") from None
    if len(raw) > MAX_NOTE_BYTES:
        raise NoteTooLarge("导入文件最多 64 KiB")
    if raw.startswith((b'%PDF-', b'PK\x03\x04', b'\x89PNG', b'GIF87a', b'GIF89a', b'\xff\xd8', b'\x7fELF')):
        raise ValueError("文件内容不是受支持的 Markdown/TXT 文本")
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeError:
        raise ValueError("文件必须使用有效 UTF-8 编码，请转换编码后重试") from None
    warnings = []
    if raw.startswith(b'\xef\xbb\xbf'):
        warnings.append("已移除 UTF-8 BOM")
    if '\r' in text:
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        warnings.append("换行已规范为 LF")
    heading = PurePath(file_name).stem
    if len(heading) > 120:
        heading = heading[:120]
        warnings.append("文件名较长，默认标题已截取前 120 字符")
    return title(heading), content(text), warnings
