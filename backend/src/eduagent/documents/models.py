"""Fixed limits and safe, content-free document failures."""

from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID
import re

PARSER_VERSION = 'course-documents-v1'
FORMATS = {'pdf', 'pptx', 'md', 'txt', 'png', 'jpg', 'jpeg', 'webp'}
ROLES = {'teaching_slides', 'textbook', 'framework', 'handout'}
MAX_FILE = 20 * 1024 * 1024
MAX_TEXT_FILE = 2 * 1024 * 1024
MAX_BODY = MAX_FILE + 256 * 1024
MAX_OUTPUT = 8 * 1024 * 1024
MAX_TEXT = 1_000_000
MAX_UNITS = 200
MAX_STORED_BYTES = 250 * 1024 * 1024
MAX_DERIVED_BYTES = 100 * 1024 * 1024
MAX_DOCUMENTS = 25

MESSAGES = {
    'document_not_found': '当前学习标识下没有该资料',
    'unsupported_document_type': '支持PDF、PPTX、Markdown、TXT和PNG/JPEG/WebP图片',
    'document_too_large': '文件、解析内容或保留资料超过限额',
    'invalid_document': '文件损坏或格式与内容不匹配',
    'invalid_encoding': '文本须为有效UTF-8编码',
    'encrypted_document': '首版不支持加密文档',
    'archive_limits_exceeded': '课件压缩包超过安全处理限额',
    'unsafe_document': '文档包含不支持的宏、嵌入对象或不安全XML',
    'too_many_pages': '最多处理200页或200张幻灯片',
    'parse_timeout': '本地解析超时，原件已保留，可显式重试',
    'parse_memory_limit': '解析超出内存限额，原件已保留',
    'parse_resource_limit': '解析进程达到资源限额或异常退出',
    'parse_failed': '解析失败，原件已保留，可显式重试',
    'parser_unavailable': '本地解析依赖或资源限制不可用，请检查documents依赖',
    'original_unavailable': '原件缺失或指纹不匹配，已停止解析',
    'derived_unavailable': '派生文件缺失或损坏，请显式重新本地解析',
    'revision_conflict': '资料版本已变化，请刷新后重试',
    'request_id_conflict': '请求编号已用于不同内容',
    'duplicate_document': '当前学习标识下已存在相同文件，请使用已有资料',
    'document_storage_unavailable': '资料文件暂时不可保存，请检查磁盘',
    'parse_interrupted': '解析多次中断，请显式重试',
    'vision_disabled': '页面视觉解析尚未启用；本地解析仍可使用',
    'external_consent_required': '需要本轮明确同意发送所选PDF页面或图片至DeepSeek',
    'vision_requires_pdf': '视觉解析仅支持选定PDF页面或PNG/JPEG/WebP图片',
    'execution_unconfirmed': '无法确认模型是否已执行；请查看原记录，不自动重发',
    'invalid_vision_output': '视觉解析输出不完整或不符合约定，原件及本地解析保留',
}


class DocumentError(ValueError):
    def __init__(self, code, status=422):
        self.code, self.status = code, status
        super().__init__(MESSAGES.get(code, '资料处理失败，请检查本轮状态'))


def uuid_text(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('资料和请求编号须为标准小写UUID') from None
    return value


def filename(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 180 or value != value.strip()
            or re.search(r'[\x00-\x1f\x7f/\\:]', value) or value in ('.', '..')
            or value.endswith(('.', ' '))):
        raise ValueError('文件名无效，请使用不含路径的普通文件名')
    kind = PurePosixPath(value).suffix.lower().lstrip('.')
    if kind not in FORMATS:
        raise DocumentError('unsupported_document_type', 415)
    return value, kind


@dataclass(frozen=True)
class ParseResult:
    units: list[dict]
    warnings: list[str]
    status: str

    def as_dict(self):
        return dict(units=self.units, warnings=self.warnings, status=self.status, parser_version=PARSER_VERSION)


def result(units, warnings=()):
    if len(units) > MAX_UNITS:
        raise DocumentError('too_many_pages')
    if sum(len(u['text']) + len(u.get('interpretation_md', '')) for u in units) > MAX_TEXT:
        raise DocumentError('document_too_large', 413)
    has_text = any(u['text'].strip() for u in units)
    partial = bool(warnings or any(u['warnings'] for u in units))
    return ParseResult(units, list(warnings), 'partial' if has_text and partial else 'ready' if has_text else 'empty').as_dict()


def unit(ordinal, kind, title, text, location, *, blocks=None, warnings=None, content_md=None):
    return dict(ordinal=ordinal, kind=kind, title=title[:200], text=text,
                content_md=text if content_md is None else content_md, interpretation_md='',
                location=location, blocks=blocks or [], warnings=warnings or [], origin='local_extraction')
