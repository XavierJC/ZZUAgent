"""Small .env reader: explicit allowlist, no interpolation or shell execution."""

import os
from pathlib import Path

CONFIG_KEYS = {
    "EDUAGENT_DATA_DIR", "EDUAGENT_DB_PATH", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL",
    "EDUAGENT_AGENT_ENABLED", "EDUAGENT_MODEL_TIMEOUT", "EDUAGENT_MODEL_MAX_CALLS",
    "EDUAGENT_MODEL_MAX_TOKENS",
    "EDUAGENT_RETRIEVAL_ENABLED",
}


def local_configuration(path: Path | None = None) -> dict[str, str]:
    """Never log this mapping; it may include an API key."""
    values: dict[str, str] = {}
    path = path if path is not None else Path(".env")
    if path.is_file():
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            name, value = name.strip(), value.strip()
            if not separator or name not in CONFIG_KEYS:
                raise ValueError(f"本地配置第 {number} 行格式或字段不受支持")
            if value.startswith(("'", '"')):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError(f"本地配置第 {number} 行引号未闭合")
                value = value[1:-1]
            values[name] = value
    values.update({key: os.environ[key] for key in CONFIG_KEYS if key in os.environ})
    return values
