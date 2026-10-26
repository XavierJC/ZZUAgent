"""Source locations, protected content and document preflight failures."""

import json
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from eduagent.documents.models import DocumentError
from eduagent.documents.parsers import parse
from eduagent.documents.preflight import pptx_package, signature
from eduagent.documents.limits import run_worker
from document_fixtures import pdf_bytes, pptx_bytes


def write(tmp_path, raw, kind):
    path = tmp_path / ('file.' + kind); path.write_bytes(raw); return path


def test_pdf_chinese_text_physical_pages_and_images_are_preserved(tmp_path):
    payload = parse(write(tmp_path, pdf_bytes(('主成分分析 PCA', '梯度下降 学习率'), image=True), 'pdf'), 'pdf')
    assert [u['location']['page_number'] for u in payload['units']] == [1, 2]
    assert '主成分分析' in payload['units'][0]['text'] and '梯度下降' in payload['units'][1]['text']
    assert payload['status'] == 'partial'
    assert all('image_content_not_extracted' in u['warnings'] for u in payload['units'])


def test_image_only_pdf_has_an_explicit_marker_not_fabricated_text(tmp_path):
    payload = parse(write(tmp_path, pdf_bytes(('',), image=True), 'pdf'), 'pdf')
    assert payload['status'] == 'empty'
    assert 'possible_scan_or_image_content' in payload['units'][0]['warnings']


def fake_pdf(monkeypatch, texts, labels=None):
    import pypdf
    class Page(dict):
        def __init__(self, text): super().__init__(); self.text = text
        def get_contents(self): return None
        def extract_text(self):
            if isinstance(self.text, Exception): raise self.text
            return self.text
    class Reader:
        is_encrypted = False
        pages = [Page(text) for text in texts]
        @property
        def page_labels(self):
            if isinstance(labels, Exception): raise labels
            return labels if labels is not None else [str(i + 1) for i in range(len(texts))]
    monkeypatch.setattr(pypdf, 'PdfReader', lambda path: Reader())
    return Reader


def test_pdf_skips_only_failed_page_and_preserves_later_physical_pages(tmp_path, monkeypatch):
    fake_pdf(monkeypatch, ['第一页中文与可读数学 x+y', ValueError('synthetic page error'), '第三页仍可阅读'])
    data = parse(write(tmp_path, b'%PDF-1.7\n', 'pdf'), 'pdf')
    assert data['status'] == 'partial'
    assert [u['location']['page_number'] for u in data['units']] == [1, 2, 3]
    assert data['units'][1]['text'] == data['units'][1]['content_md'] == ''
    assert 'pdf_page_text_extraction_failed' in data['units'][1]['warnings']
    assert data['units'][0]['text'].startswith('第一页') and data['units'][2]['text'] == '第三页仍可阅读'
    json.dumps(data, ensure_ascii=False).encode('utf-8')


def test_pdf_repairs_math_pairs_marks_isolated_characters_and_keeps_good_text(tmp_path, monkeypatch):
    fake_pdf(monkeypatch, ['中文 \ud835\udc65 + \ud835 残缺\udc65，正文继续\x00'], labels=['\ud835\udc65'])
    data = parse(write(tmp_path, b'%PDF-1.7\n', 'pdf'), 'pdf')
    item = data['units'][0]
    assert item['text'] == '中文 𝑥 + � 残缺�，正文继续�'
    assert item['location'] == dict(page_number=1, page_label='𝑥')
    assert {'pdf_text_encoding_repaired', 'text_encoding_needs_review'} <= set(item['warnings'])
    assert json.loads(json.dumps(data, ensure_ascii=False).encode('utf-8')) == data


def test_pdf_bad_image_metadata_does_not_discard_readable_text(tmp_path, monkeypatch):
    from eduagent.documents.parsers import pdf
    fake_pdf(monkeypatch, ['可读正文与公式 x+y'])
    def bad_metadata(page): raise ValueError('synthetic image dictionary error')
    monkeypatch.setattr(pdf, 'image_objects', bad_metadata)
    data = parse(write(tmp_path, b'%PDF-1.7\n', 'pdf'), 'pdf')
    assert data['units'][0]['text'] == '可读正文与公式 x+y'
    assert 'pdf_image_inspection_failed' in data['units'][0]['warnings']


def test_pdf_bad_labels_fall_back_to_physical_page_numbers(tmp_path, monkeypatch):
    fake_pdf(monkeypatch, ['第一页', '第二页'], labels=ValueError('synthetic label error'))
    data = parse(write(tmp_path, b'%PDF-1.7\n', 'pdf'), 'pdf')
    assert [u['location'] for u in data['units']] == [dict(page_number=1, page_label='1'), dict(page_number=2, page_label='2')]
    assert all('pdf_page_labels_unavailable' in u['warnings'] for u in data['units'])


def test_all_failed_pdf_pages_remain_empty_not_ready(tmp_path, monkeypatch):
    fake_pdf(monkeypatch, [ValueError('synthetic'), ValueError('synthetic')])
    data = parse(write(tmp_path, b'%PDF-1.7\n', 'pdf'), 'pdf')
    assert data['status'] == 'empty' and all(not u['text'] for u in data['units'])


@pytest.mark.parametrize('failure', [MemoryError(), DocumentError('document_too_large', 413)])
def test_pdf_page_tolerance_does_not_swallow_resource_limits(tmp_path, monkeypatch, failure):
    fake_pdf(monkeypatch, ['good page', failure, 'later page'])
    with pytest.raises(type(failure)):
        parse(write(tmp_path, b'%PDF-1.7\n', 'pdf'), 'pdf')


def test_real_pdf_worker_saves_malformed_cmap_math_with_other_text(tmp_path):
    original = write(tmp_path, pdf_bytes(('合成数学 \ud835\udc65 + 1，损坏\ud835，正文继续', '第二页保留。')), 'pdf')
    manifest, output = tmp_path/'math-input.json', tmp_path/'math-output.json'
    manifest.write_text(json.dumps(dict(path=str(original), kind='pdf', mode='local')), encoding='utf-8')
    data = run_worker(manifest, output)
    assert data['status'] == 'partial' and len(data['units']) == 2
    assert '𝑥 + 1' in data['units'][0]['text'] and '�' in data['units'][0]['text']
    assert '第二页保留' in data['units'][1]['text']
    assert 'pdf_text_encoding_repaired' in data['units'][0]['warnings']
    assert json.loads(output.read_text(encoding='utf-8')) == data


@pytest.mark.parametrize('raw,code', [(b'not a pdf', 'invalid_document'), (pdf_bytes(encrypted=True), 'encrypted_document'),
                                      (pdf_bytes(('',) * 201), 'too_many_pages')], ids=['invalid', 'encrypted', 'page-limit'])
def test_bad_encrypted_or_too_many_pdf_pages_reject(tmp_path, raw, code):
    with pytest.raises(DocumentError, match='.') as caught:
        parse(write(tmp_path, raw, 'pdf'), 'pdf')
    assert caught.value.code == code


def test_pptx_preserves_real_slide_order_groups_tables_and_math(tmp_path):
    data = parse(write(tmp_path, pptx_bytes(), 'pptx'), 'pptx')
    assert [u['location']['slide_number'] for u in data['units']] == [1, 2]
    first = data['units'][0]
    assert '主成分分析' in first['title'] and '主要变化方向' in first['text']
    table = next(b for b in first['blocks'] if b['kind'] == 'table')
    assert len(table['cells']) == 3 and table['cells'][0]['colspan'] == 2
    equation = next(b for b in first['blocks'] if b['kind'] == 'formula_omml')
    assert 'oMath' in equation['xml'] and 'equation_needs_review' in first['warnings']
    assert data['units'][1]['location']['hidden']


def test_markdown_original_formula_code_offsets_and_bom(tmp_path):
    text = '# 梯度下降\n\n$$\nw := w - \\eta g\n$$\n\n```python\nprint("<script>")\n```\n'
    data = parse(write(tmp_path, b'\xef\xbb\xbf' + text.encode(), 'md'), 'md')
    value = data['units'][0]
    assert value['text'] == text and value['content_md'] == text
    for block in value['blocks']:
        assert text[block['start_offset']:block['end_offset']]
    assert len([b for b in value['blocks'] if b['kind'] == 'protected']) == 2


@pytest.mark.parametrize('raw', [b'\xff\xfe', b'x\x00y'])
def test_abnormal_text_encoding_rejects_without_replacement(tmp_path, raw):
    with pytest.raises(DocumentError) as caught:
        parse(write(tmp_path, raw, 'txt'), 'txt')
    assert caught.value.code == 'invalid_encoding'


@pytest.mark.parametrize('name,content', [('../escape.xml', b'x'), ('ppt/vbaProject.bin', b'x'),
    ('ppt/embeddings/object.bin', b'x'), ('bad.xml', b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///secret">]><x>&x;</x>'),
    ('bomb.xml', b'x' * 100000)], ids=['traversal', 'macro', 'ole', 'xxe', 'zip-bomb'])
def test_zip_preflight_rejects_unsafe_entries_without_extracting(tmp_path, name, content):
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr(name, content)
    with pytest.raises(DocumentError):
        pptx_package(write(tmp_path, output.getvalue(), 'pptx'))
    assert not (tmp_path.parent / 'escape.xml').exists()


def test_native_worker_applies_limits_and_keeps_unicode(tmp_path):
    original = write(tmp_path, '# 合成资料\n\n学习率控制步长。'.encode(), 'md')
    manifest, output = tmp_path / 'input.json', tmp_path / 'output.json'
    manifest.write_text(json.dumps(dict(path=str(original), kind='md', mode='local')), encoding='utf8')
    data = run_worker(manifest, output)
    assert data['status'] == 'ready' and '学习率' in data['units'][0]['text']


def test_visual_renderer_is_local_and_bounded(tmp_path):
    original = write(tmp_path, pdf_bytes(), 'pdf')
    manifest, output = tmp_path / 'input.json', tmp_path / 'output.json'
    manifest.write_text(json.dumps(dict(path=str(original), kind='pdf', mode='render', pages=[1])), encoding='utf8')
    data = run_worker(manifest, output)
    assert data['images'][0]['page_number'] == 1
    assert data['images'][0]['image_base64'].startswith('iVBOR')
