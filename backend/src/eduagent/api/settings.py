"""Explicit file paths for a local API process, with no secret handling."""

from dataclasses import dataclass, field
from pathlib import Path

from eduagent.agent.settings import AgentSettings
from eduagent.config import local_configuration


@dataclass(frozen=True)
class APISettings:
    data_dir: Path = Path("data")
    db_path: Path = Path("data/local/eduagent.sqlite3")
    agent: AgentSettings = field(default_factory=AgentSettings, repr=False)
    frontend_dir: Path = Path("frontend/dist")
    retrieval_enabled: bool = True
    document_dir: Path | None = None
    document_vision_enabled: bool = False

    def __post_init__(self) -> None:
        if type(self.retrieval_enabled) is not bool:
            raise ValueError('retrieval_enabled 必须为布尔值')
        if str(self.db_path) == ":memory:":
            raise ValueError("HTTP 请求使用独立连接，必须使用文件数据库，不能使用 :memory:")
        object.__setattr__(self, "data_dir", Path(self.data_dir).resolve())
        object.__setattr__(self, "db_path", Path(self.db_path).resolve())
        object.__setattr__(self, "frontend_dir", Path(self.frontend_dir).resolve())
        object.__setattr__(self, 'document_dir', Path(self.document_dir).resolve() if self.document_dir is not None else self.db_path.with_suffix('.documents'))
        if type(self.document_vision_enabled) is not bool:
            raise ValueError('document_vision_enabled必须为布尔值')

    @classmethod
    def from_environment(cls) -> "APISettings":
        values = local_configuration()
        data_dir = values.get("EDUAGENT_DATA_DIR", "data")
        db_path = values.get("EDUAGENT_DB_PATH", "data/local/eduagent.sqlite3")
        if not data_dir.strip() or not db_path.strip():
            raise ValueError("EDUAGENT_DATA_DIR 和 EDUAGENT_DB_PATH 不能为空")
        enabled = values.get('EDUAGENT_RETRIEVAL_ENABLED', 'true').lower()
        if enabled not in ('true', 'false'):
            raise ValueError('EDUAGENT_RETRIEVAL_ENABLED 必须为 true 或 false')
        vision = values.get('EDUAGENT_DOCUMENT_VISION_ENABLED', 'false').lower()
        if vision not in ('true', 'false'):
            raise ValueError('EDUAGENT_DOCUMENT_VISION_ENABLED必须为true或false')
        return cls(data_dir=Path(data_dir), db_path=Path(db_path), agent=AgentSettings.from_mapping(values),
                   retrieval_enabled=enabled == 'true', document_dir=Path(values['EDUAGENT_DOCUMENT_DIR']) if values.get('EDUAGENT_DOCUMENT_DIR') else None,
                   document_vision_enabled=vision == 'true')
