import json

import pytest

from eduagent.retrieval.index import CourseIndex, terms


@pytest.fixture
def course_index(data_dir, catalog):
    return CourseIndex(data_dir / "materials", set(catalog.knowledge))


@pytest.mark.parametrize("query,knowledge_id,expected", [
    ("MSE 均方误差定义", "linear_regression_loss", "linear:2"),
    ("学习率过大会造成振荡或发散", "gradient_descent", "gradient:2"),
    ("sigmoid 正类概率", "logistic_regression", "logistic:1"),
    ("L2 正则项 lambda 梯度", "overfitting_regularization", "regularization:2"),
    ("精确率召回率 TP FP FN", "model_evaluation", "evaluation:2"),
])
def test_reference_queries_retrieve_expected_sections(course_index, query, knowledge_id, expected):
    matches = course_index.search(query, knowledge_id)
    assert matches[0]["citation_id"] == expected
    assert all(item["knowledge_id"] == knowledge_id for item in matches)
    assert matches[0]["source"].startswith("materials/")
    assert matches[0]["review_status"] == "pending"


def test_no_in_vocabulary_evidence_returns_empty(course_index):
    assert course_index.search("qzzzxxyywwwunrelated") == []


@pytest.mark.parametrize("query,knowledge_id,top_k", [
    ("", None, 3), ("x" * 1001, None, 3), ("梯度", "unknown", 3), ("梯度", None, 0),
])
def test_retrieval_input_validation(course_index, query, knowledge_id, top_k):
    with pytest.raises(ValueError):
        course_index.search(query, knowledge_id, top_k)


def test_retrieval_is_reproducible_and_chinese_tokenization(course_index):
    assert "梯度" in terms("梯度下降 Gradient")
    assert "gradient" in terms("梯度下降 Gradient")
    assert course_index.search("梯度下降") == course_index.search("梯度下降")


def test_manifest_cannot_escape_material_directory(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"documents": [{
        "id": "unsafe", "knowledge_id": "test", "file": "../outside.md",
        "title": "Unsafe", "review_status": "pending", "license": "test",
    }]}), encoding="utf-8")
    with pytest.raises(ValueError, match="路径"):
        CourseIndex(tmp_path, {"test"})
