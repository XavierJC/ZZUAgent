import json

from fastapi.testclient import TestClient
import pytest

from eduagent.agent.deepseek import ModelReply
from eduagent.agent.settings import AgentSettings
from eduagent.agent.tutor import Tutor
from eduagent.api.app import create_app
from eduagent.api.settings import APISettings
from eduagent.retrieval.evaluate import evaluate, load_dataset
from eduagent.retrieval.index import CourseIndex, informative_phrases


@pytest.fixture
def guarded(data_dir, catalog):
    return CourseIndex(data_dir / "materials", set(catalog.knowledge))


class NeverCallModel:
    def complete(self, *args, **kwargs):
        pytest.fail("Evidence rejection must not make a provider request")


def test_phrase_guard_rejects_single_character_overlap_that_baseline_accepts(guarded, data_dir, catalog):
    query = "郑州大学宿舍电费在哪里缴纳？"
    baseline = CourseIndex(data_dir / "materials", set(catalog.knowledge), phrase_gate=False)
    assert baseline.search(query)[0]["citation_id"] == "gradient:2"
    assert guarded.search(query) == []
    assert guarded.configuration["version"] == "tfidf-phrase-v2"


@pytest.mark.parametrize("query", ["如何学习？", "这个问题应该怎么解释？", "大"])
def test_generic_language_is_not_topic_evidence(guarded, query):
    assert guarded.search(query) == []


def test_phrase_terms_keep_course_symbols_and_words_but_not_generic_requests():
    phrases = informative_phrases("如何学习 sigmoid 与梯度下降 TP FP 的方法")
    assert {"sigmoid", "梯度", "下降", "tp", "fp"} <= phrases
    assert not {"如何", "学习", "方法"}.intersection(phrases)


@pytest.mark.parametrize("top_k", [True, 1.5])
def test_non_integer_search_budget_is_rejected(guarded, top_k):
    with pytest.raises(ValueError):
        guarded.search("梯度", top_k=top_k)


@pytest.mark.parametrize("dataset_name,report_name", [
    ("retrieval-dev-v1.json", "retrieval-baseline-v1.json"),
    ("retrieval-challenge-v1.json", "retrieval-challenge-baseline-v1.json"),
])
def test_original_baseline_is_still_reproducible(data_dir, catalog, dataset_name, report_name):
    index = CourseIndex(data_dir / "materials", set(catalog.knowledge), phrase_gate=False)
    dataset = load_dataset(data_dir / "evaluation" / dataset_name, index)
    saved = json.loads((data_dir.parent / "docs/evaluation" / report_name).read_text(encoding="utf-8"))
    actual = evaluate(index, dataset)
    assert actual["metrics"] == saved["metrics"]
    assert [row["retrieved_citation_ids"] for row in actual["cases"]] == [row["retrieved_citation_ids"] for row in saved["cases"]]


@pytest.mark.parametrize("question", ["郑州大学宿舍电费在哪里缴纳？", "qzzxxyyunknown"])
def test_unsupported_question_returns_rule_advice_without_cost_or_mastery_change(service, guarded, question):
    before = service.snapshot("student-a")
    result = Tutor(service, guarded, NeverCallModel(), AgentSettings(enabled=True, api_key="test-only-secret")).run("student-a", question)
    assert result["fallback_reason"] == "insufficient_evidence"
    assert result["model_calls"] == 0 and result["model"] is None
    assert result["citations"] == [] and "当前学习安排" in result["answer"]
    assert result["retrieval_policy"] == "tfidf-phrase-v2"
    assert result["next_exercise"]["action"] == "diagnose"
    assert service.snapshot("student-a") == before
    assert service.repository.tutor_run("student-a", result["run_id"]) == result


def test_model_query_rewrite_cannot_switch_to_a_different_course_topic(service, guarded):
    class DriftingModel:
        def __init__(self):
            self.calls = 0
        def complete(self, messages, tools, required=False):
            self.calls += 1
            if self.calls == 1:
                return ModelReply({"role": "assistant", "content": None, "tool_calls": [{
                    "id": "drift", "type": "function", "function": {"name": "retrieve_course_material",
                    "arguments": json.dumps({"query": "L2 正则项 lambda 梯度", "knowledge_id": "overfitting_regularization"})},
                }]})
            payload = json.loads(messages[-1]["content"])
            assert payload["matches"] == [] and payload["evidence_sufficient"] is False
            return ModelReply({"role": "assistant", "content": json.dumps({
                "answer": "不相关的正则项讲解 [regularization:2]", "citation_ids": ["regularization:2"],
            })})
    result = Tutor(service, guarded, DriftingModel(), AgentSettings(enabled=True, api_key="test-only-secret")).run("student-a", "梯度下降参数更新方向")
    assert result["fallback_reason"] == "unverified_model_answer"
    assert all(item["knowledge_id"] == "gradient_descent" for item in result["citations"])
    assert "不相关的正则项讲解" not in result["answer"]


@pytest.mark.parametrize("length", [1001, 2000])
def test_long_unsupported_http_question_falls_back_without_search_length_error(data_dir, tmp_path, monkeypatch, length):
    monkeypatch.setattr("eduagent.agent.deepseek.DeepSeekClient", lambda settings: NeverCallModel())
    settings = APISettings(data_dir, tmp_path / "long.sqlite3", AgentSettings(enabled=True, api_key="test-only-secret"))
    with TestClient(create_app(settings)) as client:
        client.post("/api/v1/students", json={"student_id": "long"})
        response = client.post("/api/v1/students/long/tutor", json={"question": "啊" * length})
        assert response.status_code == 200
        assert response.json()["fallback_reason"] == "insufficient_evidence"
        assert response.json()["model_calls"] == 0


def test_full_length_question_keeps_a_topic_at_the_end(service, guarded):
    tutor = Tutor(service, guarded, None, AgentSettings())
    topic = "梯度下降参数更新方向"
    question = " " * (2000 - len(topic)) + topic
    assert any(match["citation_id"] == "gradient:1" for match in tutor._question_matches(question))
    result = tutor.run("student-a", question)
    assert result["fallback_reason"] == "agent_disabled"
    assert result["citations"]


def test_http_wrong_answer_local_feedback_recovery_and_stop_are_consistent(data_dir, tmp_path, monkeypatch):
    monkeypatch.setattr("eduagent.agent.deepseek.DeepSeekClient", lambda settings: NeverCallModel())
    settings = APISettings(data_dir, tmp_path / "closed-loop.sqlite3", AgentSettings(enabled=True, api_key="test-only-secret"))
    with TestClient(create_app(settings)) as client:
        client.post("/api/v1/students", json={"student_id": "loop", "goals": ["gradient_descent"]})
        first = client.post("/api/v1/students/loop/next").json()
        wrong = client.post("/api/v1/students/loop/answers", json={"decision_id": first["decision_id"], "event_id": "wrong", "answer": "A"}).json()
        assert wrong["correct"] is False
        before = client.get("/api/v1/students/loop/mastery").json()
        local = client.post("/api/v1/students/loop/tutor", json={"question": "宿舍电费在哪里缴纳？"}).json()
        assert local["model_calls"] == 0 and local["next_exercise"]["action"] == "review"
        assert client.get("/api/v1/students/loop/mastery").json() == before
        second = local["next_exercise"]
        assert second["question"]["id"] == "lr_02" and "answer" not in second["question"]
        client.post("/api/v1/students/loop/answers", json={"decision_id": second["decision_id"], "event_id": "right", "answer": "A"})
        stop = client.post("/api/v1/students/loop/next").json()
        assert stop["action"] == "stopped" and stop["stop_reason"] == "insufficient_questions"
        assert client.get("/api/v1/students/loop/history").json()["revision"] == 2
    with TestClient(create_app(settings)) as restored:
        assert restored.post("/api/v1/students/loop/next").json() == stop
        assert len(restored.get("/api/v1/students/loop/history").json()["items"]) == 2
