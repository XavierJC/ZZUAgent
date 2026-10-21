import json

import httpx2
import pytest

from eduagent.agent.deepseek import DeepSeekClient, ModelError
from eduagent.agent.settings import AgentSettings
from eduagent.config import local_configuration


def settings(**kwargs):
    return AgentSettings(enabled=True, api_key="test-only-secret", **kwargs)


def test_request_is_bounded_and_only_uses_official_endpoint():
    def handler(request):
        assert str(request.url) == DeepSeekClient.ENDPOINT
        assert request.headers["Authorization"] == "Bearer test-only-secret"
        payload = json.loads(request.content)
        assert payload["thinking"] == {"type": "disabled"}
        assert payload["tool_choice"] == "required"
        assert payload["max_tokens"] == 700
        assert "test-only-secret" not in json.dumps(payload)
        return httpx2.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": "answer", "reasoning_content": "must not expose",
        }}], "usage": {"prompt_tokens": 5, "completion_tokens": 3}})
    reply = DeepSeekClient(settings(), httpx2.MockTransport(handler)).complete([], [], required=True)
    assert reply.message == {"role": "assistant", "content": "answer"}
    assert reply.prompt_tokens == 5 and reply.completion_tokens == 3


def test_question_only_request_omits_empty_tools_and_keeps_json_message():
    def handler(request):
        payload = json.loads(request.content)
        assert 'tools' not in payload and 'tool_choice' not in payload
        assert payload['messages'] == [{'role': 'user', 'content': 'hi deepseek'}]
        return httpx2.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'role': 'assistant', 'content': '{"answer":"你好","citation_ids":[]}'}}]})
    result = DeepSeekClient(settings(), httpx2.MockTransport(handler)).complete([{'role': 'user', 'content': 'hi deepseek'}], [])
    assert json.loads(result.message['content'])['citation_ids'] == []


def test_json_mode_is_opt_in_and_uses_explicit_output_budget():
    def handler(request):
        payload = json.loads(request.content)
        assert payload['response_format'] == {'type': 'json_object'} and payload['max_tokens'] == 1500
        return httpx2.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'role': 'assistant', 'content': '{"answer":"解释","citation_ids":[]}'}}]})
    DeepSeekClient(settings(max_tokens=1500), httpx2.MockTransport(handler), json_output=True).complete([], [])


@pytest.mark.parametrize('finish,code', [('length', 'model_output_truncated'), ('content_filter', 'model_content_filtered'),
    ('insufficient_system_resource', 'model_resource_exhausted'), ('aborted', 'model_aborted'), ('new_unknown_reason', 'incomplete_model_response')])
def test_incomplete_responses_preserve_sanitized_cause_and_usage_without_partial_text(finish, code):
    response = {'choices': [{'finish_reason': finish, 'message': {'content': 'private cut-off answer'}}],
                'usage': {'prompt_tokens': 123, 'completion_tokens': 1500}}
    transport = httpx2.MockTransport(lambda _: httpx2.Response(200, json=response))
    with pytest.raises(ModelError) as caught:
        DeepSeekClient(settings(), transport).complete([], [])
    assert caught.value.code == code and caught.value.prompt_tokens == 123 and caught.value.completion_tokens == 1500
    assert caught.value.finish_reason == (None if finish == 'new_unknown_reason' else finish)
    assert 'private cut-off answer' not in str(caught.value) and 'private cut-off answer' not in repr(vars(caught.value))


def test_chat_output_budget_is_independent_of_legacy_tutor_budget():
    configured = AgentSettings.from_mapping({'EDUAGENT_MODEL_MAX_TOKENS': '700', 'EDUAGENT_WORKBENCH_MAX_TOKENS': '1200'})
    assert configured.max_tokens == 700 and configured.workbench_max_tokens == 1200
    assert AgentSettings().workbench_max_tokens == 1500


@pytest.mark.parametrize('limit', [99, 1501, True])
def test_chat_output_budget_stays_bounded(limit):
    with pytest.raises(ValueError):
        AgentSettings(workbench_max_tokens=limit)


@pytest.mark.parametrize("status,code", [(401, "authentication_failed"), (402, "insufficient_balance"),
                                        (429, "rate_limited"), (500, "upstream_error"), (302, "upstream_error")])
def test_http_errors_are_sanitized_without_body_or_key(status, code):
    transport = httpx2.MockTransport(lambda request: httpx2.Response(status, text="test-only-secret upstream detail"))
    with pytest.raises(ModelError) as caught:
        DeepSeekClient(settings(), transport).complete([], [])
    assert str(caught.value) == code
    assert "secret" not in str(caught.value)


def test_timeouts_are_sanitized():
    def handler(request):
        raise httpx2.ReadTimeout("sensitive upstream details", request=request)
    with pytest.raises(ModelError, match="model_timeout"):
        DeepSeekClient(settings(), httpx2.MockTransport(handler)).complete([], [])


@pytest.mark.parametrize("body", [
    {}, {"choices": []}, {"choices": [{"finish_reason": "length", "message": {"content": "cut"}}]},
    {"choices": [{"finish_reason": "stop", "message": {"content": 123}}]},
])
def test_invalid_upstream_response_is_not_executed(body):
    transport = httpx2.MockTransport(lambda request: httpx2.Response(200, json=body))
    with pytest.raises(ModelError):
        DeepSeekClient(settings(), transport).complete([], [])


def test_settings_repr_never_contains_key():
    assert "test-only-secret" not in repr(settings())


def test_config_environment_precedence_and_no_shell_expansion(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DEEPSEEK_API_KEY='test-only-secret'\nDEEPSEEK_MODEL=local\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_MODEL", "environment")
    result = local_configuration(env)
    assert result["DEEPSEEK_MODEL"] == "environment"
    assert result["DEEPSEEK_API_KEY"] == "test-only-secret"
    env.write_text("DEEPSEEK_API_KEY='test-only-secret\n", encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        local_configuration(env)
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("values", [
    {"EDUAGENT_AGENT_ENABLED": "maybe"}, {"EDUAGENT_AGENT_ENABLED": "true"},
    {"EDUAGENT_MODEL_MAX_CALLS": "9"}, {"EDUAGENT_MODEL_TIMEOUT": "nan"},
    {"EDUAGENT_AGENT_ENABLED": "true", "DEEPSEEK_API_KEY": "invalid\nheader"},
])
def test_invalid_agent_settings_rejected(values):
    with pytest.raises(ValueError):
        AgentSettings.from_mapping(values)
