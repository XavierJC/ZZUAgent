"""Bounded DeepSeek HTTP adapter; no raw upstream errors or headers escape."""

from dataclasses import dataclass
import json

import httpx2

from eduagent.agent.settings import AgentSettings


class ModelError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ModelReply:
    message: dict
    prompt_tokens: int = 0
    completion_tokens: int = 0


class DeepSeekClient:
    ENDPOINT = "https://api.deepseek.com/chat/completions"

    def __init__(self, settings: AgentSettings, transport=None):
        self.settings = settings
        self.transport = transport

    def complete(self, messages: list[dict], tools: list[dict], required: bool = False) -> ModelReply:
        payload = {
            "model": self.settings.model, "messages": messages,
            "thinking": {"type": "disabled"}, "temperature": 0,
            "max_tokens": self.settings.max_tokens, "stream": False,
        }
        if tools or required:
            payload.update(tools=tools, tool_choice="required" if required else "auto")
        try:
            # Never follow redirects with credentials or inherit an arbitrary HTTP proxy.
            with httpx2.Client(timeout=self.settings.timeout, follow_redirects=False,
                               trust_env=False, transport=self.transport) as client:
                response = client.post(self.ENDPOINT, json=payload, headers={
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                })
                if response.status_code != 200:
                    code = {401: "authentication_failed", 402: "insufficient_balance",
                            429: "rate_limited"}.get(response.status_code, "upstream_error")
                    raise ModelError(code)
                body = response.json()
        except httpx2.TimeoutException:
            raise ModelError("model_timeout") from None
        except httpx2.HTTPError:
            raise ModelError("network_error") from None
        except (json.JSONDecodeError, UnicodeError):
            raise ModelError("invalid_model_response") from None
        try:
            choice = body["choices"][0]
            if choice["finish_reason"] not in ("stop", "tool_calls"):
                raise ModelError("incomplete_model_response")
            message = choice["message"]
            content = message.get("content")
            if content is not None and (not isinstance(content, str) or len(content) > 12000):
                raise ModelError("invalid_model_response")
            calls = message.get("tool_calls") or []
            if not isinstance(calls, list) or len(calls) > 4:
                raise ModelError("invalid_model_response")
            cleaned = {"role": "assistant", "content": content}
            if calls:
                for call in calls:
                    if (call.get("type") != "function" or not isinstance(call.get("id"), str)
                            or not isinstance(call.get("function"), dict)):
                        raise ModelError("invalid_model_response")
                    function = call["function"]
                    if (not isinstance(function.get("name"), str) or len(function["name"]) > 128
                            or not isinstance(function.get("arguments"), str)
                            or len(function["arguments"]) > 4000):
                        raise ModelError("invalid_model_response")
                if len({call["id"] for call in calls}) != len(calls):
                    raise ModelError("invalid_model_response")
                cleaned["tool_calls"] = [{"id": c["id"], "type": "function", "function": {
                    "name": c["function"]["name"], "arguments": c["function"]["arguments"],
                }} for c in calls]
            usage = body.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            if any(type(n) is not int or n < 0 for n in (prompt_tokens, completion_tokens)):
                raise ModelError("invalid_model_response")
            return ModelReply(cleaned, prompt_tokens, completion_tokens)
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ModelError("invalid_model_response") from None
