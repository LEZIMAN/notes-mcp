"""notes_mcp 配置:读 .env → Config dataclass → 校验。

开发规范 §4 要求:配置外置、绝不硬编码。
设计文档 §8 / 配置.md §4 定义所有变量。
"""

import os
from dataclasses import dataclass
from pathlib import Path

import dotenv

# —— 默认值(设计文档 §8 · 配置.md §4)————————————————————————
_DEFAULTS: dict[str, str] = {
    "OLLAMA_BASE_URL": "http://127.0.0.1:11434/v1",
    "OLLAMA_MODEL": "qwen3:8b",
    "OLLAMA_API_KEY": "ollama",  # ollama 不验证,但 openai SDK 要求非空
    "EMBED_MODEL": "bge-m3",
    "TOP_K": "5",
    "CHUNK_SIZE": "300",
    "OVERLAP": "50",
    "CHROMA_PATH": "./data/chroma",
    "SQLITE_PATH": "./data/index_state.db",
    "MCP_HTTP_HOST": "0.0.0.0",
    "MCP_HTTP_PORT": "8765",
    "WEB_BACKEND_HOST": "0.0.0.0",
    "WEB_BACKEND_PORT": "8000",
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "LOG_LEVEL": "INFO",
}


# —— 配置数据类 ————————————————————————————————————————————


@dataclass
class Config:
    """notes-mcp 运行时配置(只读,从 .env / 环境变量读取)。

    用法:
        config = Config.from_env()          # 读项目根 .env
        config = Config.from_env(path)      # 读指定 .env(测试用)
        config.validate()                   # 校验,有错抛 ConfigError
    """

    notes_dirs: list[Path]  # NOTES_DIR,分号 ; 分隔多目录
    ollama_base_url: str
    ollama_model: str
    ollama_api_key: str
    embed_model: str
    top_k: int
    chunk_size: int
    overlap: int
    chroma_path: Path
    sqlite_path: Path
    mcp_http_host: str
    mcp_http_port: int
    web_backend_host: str
    web_backend_port: int
    frontend_origin: str
    log_level: str

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Config":
        """从 .env 文件和环境变量构造 Config。

        优先级:环境变量(已存在) > .env 文件 > 默认值。
        env_file 为 None 时自动找项目根的 .env。
        """
        if env_file is None:
            env_file = _find_env()
        if env_file and env_file.exists():
            dotenv.load_dotenv(env_file)

        return cls(
            notes_dirs=_parse_dirs(os.getenv("NOTES_DIR", "")),
            ollama_base_url=_get("OLLAMA_BASE_URL"),
            ollama_model=_get("OLLAMA_MODEL"),
            ollama_api_key=_get("OLLAMA_API_KEY"),
            embed_model=_get("EMBED_MODEL"),
            top_k=_int("TOP_K"),
            chunk_size=_int("CHUNK_SIZE"),
            overlap=_int("OVERLAP"),
            chroma_path=Path(_get("CHROMA_PATH")),
            sqlite_path=Path(_get("SQLITE_PATH")),
            mcp_http_host=_get("MCP_HTTP_HOST"),
            mcp_http_port=_int("MCP_HTTP_PORT"),
            web_backend_host=_get("WEB_BACKEND_HOST"),
            web_backend_port=_int("WEB_BACKEND_PORT"),
            frontend_origin=_get("FRONTEND_ORIGIN"),
            log_level=_get("LOG_LEVEL"),
        )

    def validate(self) -> None:
        """校验配置(server 启动时调一次),有错抛 ConfigError。

        校验规则:
          - notes_dirs 非空且每个目录存在
          - top_k ≥ 1, chunk_size ≥ 50
          - overlap < chunk_size
        """
        errors: list[str] = []

        if not self.notes_dirs:
            errors.append("NOTES_DIR 未设或为空——至少给一个笔记目录路径")
        else:
            for d in self.notes_dirs:
                if not d.exists():
                    errors.append(f"笔记目录不存在: {d}")

        if self.top_k < 1:
            errors.append(f"TOP_K 必须 ≥ 1,实际 {self.top_k}")
        if self.chunk_size < 50:
            errors.append(f"CHUNK_SIZE 必须 ≥ 50,实际 {self.chunk_size}")
        if self.overlap >= self.chunk_size:
            errors.append(f"OVERLAP({self.overlap}) 必须 < CHUNK_SIZE({self.chunk_size})")

        if errors:
            raise ConfigError(errors)


# —— 自定义异常 ————————————————————————————————————————————


class ConfigError(Exception):
    """配置校验失败(开发规范 §4:自定义异常分层)。"""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        msg = "\n  - ".join(["配置错误:"] + errors)
        super().__init__(msg)


# —— 内部辅助 ———————————————————————————————————————————————


def _get(key: str) -> str:
    """取环境变量,未设则从 _DEFAULTS 兜底。"""
    return os.getenv(key, _DEFAULTS.get(key, ""))


def _int(key: str) -> int:
    return int(_get(key))


def _parse_dirs(raw: str) -> list[Path]:
    """解析分号分隔的笔记目录字符串 → Path 列表。排除空串/空白。"""
    if not raw or not raw.strip():
        return []
    return [Path(p.strip()) for p in raw.split(";") if p.strip()]


def _find_env() -> Path | None:
    """找项目根目录的 .env 文件(用于 from_env 的 env_file=None 时)。

    策略:从本文件位置向上找(notes_mcp/config.py → 父级的父级 → .env)。
    回退到当前工作目录的 .env。
    """
    # 包所在项目根
    candidate = Path(__file__).resolve().parent.parent / ".env"
    if candidate.exists():
        return candidate
    # 回退:当前工作目录
    cwd = Path.cwd() / ".env"
    return cwd if cwd.exists() else None
