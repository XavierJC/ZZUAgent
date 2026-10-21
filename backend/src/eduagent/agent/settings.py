from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSettings:
    enabled: bool = False
    api_key: str = field(default="", repr=False)
    model: str = "deepseek-flash"
    timeout: float = 25
    max_calls: int = 3
    max_tokens: int = 700

    def __post_init__(self) -> None:
        object.__setattr__(self, "api_key", self.api_key.strip())
        if not self.model or len(self.model) > 100:
            raise ValueError("模型名称无效")
        if not 1 <= self.timeout <= 60:
            raise ValueError("模型超时需在 1～60 秒内")
        if not 1 <= self.max_calls <= 4 or not 100 <= self.max_tokens <= 1500:
            raise ValueError("模型调用轮数或输出上限超出允许范围")
        if self.enabled and not self.api_key.strip():
            raise ValueError("启用 Agent 前需在本机配置 DEEPSEEK_API_KEY")
        if self.enabled and (len(self.api_key) > 256 or any(ord(c) < 33 or ord(c) > 126 for c in self.api_key)):
            raise ValueError("密钥格式无效")

    @classmethod
    def from_mapping(cls, values: dict[str, str]) -> "AgentSettings":
        enabled = values.get("EDUAGENT_AGENT_ENABLED", "false").lower()
        if enabled not in ("true", "false", "1", "0"):
            raise ValueError("EDUAGENT_AGENT_ENABLED 需为 true/false")
        try:
            return cls(
                enabled=enabled in ("true", "1"), api_key=values.get("DEEPSEEK_API_KEY", ""),
                model=values.get("DEEPSEEK_MODEL", "deepseek-flash"),
                timeout=float(values.get("EDUAGENT_MODEL_TIMEOUT", "25")),
                max_calls=int(values.get("EDUAGENT_MODEL_MAX_CALLS", "3")),
                max_tokens=int(values.get("EDUAGENT_MODEL_MAX_TOKENS", "700")),
            )
        except (TypeError, ValueError):
            # Do not embed configuration values, which can contain credentials.
            raise ValueError("Agent 配置无效，请检查启用项、密钥、模型与调用限制") from None
