from collections import Counter

import pytest

from eduagent.domain.catalog import Catalog


def test_p1_question_scope_and_pending_review(catalog):
    assert len(catalog.knowledge) == 5
    assert Counter(q.knowledge_id for q in catalog.questions.values()) == dict.fromkeys(catalog.knowledge, 2)
    assert {q.review_status for q in catalog.questions.values()} == {"pending"}


def test_deterministic_filter_exclusion_and_no_duplicates(catalog):
    questions = catalog.select("linear_regression_loss", count=10)
    assert [q.id for q in questions] == ["lr_01", "lr_02"]
    assert [q.id for q in catalog.select("linear_regression_loss", difficulty="medium")] == ["lr_02"]
    assert [q.id for q in catalog.select("linear_regression_loss", exclude={"lr_01"})] == ["lr_02"]
    assert catalog.select("linear_regression_loss", exclude={"lr_01", "lr_02"}) == []
    assert len({q.id for q in questions}) == len(questions)


def test_public_question_hides_answer_and_explanation(catalog):
    view = catalog.questions["lr_01"].public_view()
    assert "answer" not in view and "explanation" not in view
    view["options"]["B"] = "changed"
    assert catalog.questions["lr_01"].options["B"] == "2.5"


def test_grading_and_invalid_option(catalog):
    question = catalog.questions["lr_01"]
    assert question.grade(" b ") is True
    assert question.grade("A") is False
    for answer in ("E", "", "AB", None):
        with pytest.raises(ValueError):
            question.grade(answer)


def test_transitive_prerequisites_and_stable_order(catalog):
    assert catalog.expand_goals(("logistic_regression",)) == (
        "linear_regression_loss", "gradient_descent", "logistic_regression",
    )
    ordered = catalog.expand_goals(("overfitting_regularization",))
    assert ordered.index("model_evaluation") < ordered.index("overfitting_regularization")


@pytest.mark.parametrize("mutation,error", [
    ("duplicate_question", "重复题目"), ("duplicate_knowledge", "重复知识点"),
    ("unknown_knowledge", "未知知识点"), ("unknown_prerequisite", "未知知识点"),
    ("cycle", "存在环"), ("invalid_answer", "正确答案"),
    ("missing_option", "四选一"), ("invalid_difficulty", "difficulty"),
    ("missing_explanation", "解析"), ("false_review", "人工校验人"),
])
def test_invalid_catalog_rejected(raw_data, mutation, error):
    knowledge, questions = raw_data
    first = questions["questions"][0]
    if mutation == "duplicate_question":
        questions["questions"].append(dict(first))
    elif mutation == "duplicate_knowledge":
        knowledge["knowledge_points"].append(dict(knowledge["knowledge_points"][0]))
    elif mutation == "unknown_knowledge":
        first["knowledge_id"] = "missing"
    elif mutation == "unknown_prerequisite":
        knowledge["knowledge_points"][0]["prerequisites"] = ["missing"]
    elif mutation == "cycle":
        knowledge["knowledge_points"][0]["prerequisites"] = ["logistic_regression"]
    elif mutation == "invalid_answer":
        first["answer"] = "E"
    elif mutation == "missing_option":
        del first["options"]["D"]
    elif mutation == "invalid_difficulty":
        first["difficulty"] = "unknown"
    elif mutation == "missing_explanation":
        first["explanation"] = ""
    elif mutation == "false_review":
        first["review_status"] = "human_verified"
    with pytest.raises(ValueError, match=error):
        Catalog(knowledge, questions)


@pytest.mark.parametrize("kwargs", [{"count": 0}, {"count": True}, {"difficulty": "unknown"}])
def test_invalid_selection_arguments(catalog, kwargs):
    with pytest.raises(ValueError):
        catalog.select("model_evaluation", **kwargs)
