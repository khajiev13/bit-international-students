from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


APP_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "BIT Professor Agent"
    cors_origins: str = Field(
        default="http://localhost:8081,http://127.0.0.1:8081",
        validation_alias="LAB4_ALLOWED_ORIGINS",
    )
    allowed_hosts: str = Field(
        default="localhost,127.0.0.1,testserver,lab4_professor_caddy",
        validation_alias="LAB4_ALLOWED_HOSTS",
    )
    corpus_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "corpus")
    qa_log_db_path: Path = Field(
        default_factory=lambda: BACKEND_ROOT / "analytics" / "question_answer_log.sqlite3",
        validation_alias="LAB4_QA_LOG_DB_PATH",
    )
    llm_api_key: SecretStr | None = Field(default=None, validation_alias="BIT_PROF_LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.silra.cn/v1/", validation_alias="BIT_PROF_LLM_BASE_URL")
    llm_model: str = Field(default="deepseek-v4-flash", validation_alias="BIT_PROF_LLM_MODEL")
    max_prompt_chars: int = Field(default=2000, ge=1, le=10000, validation_alias="LAB4_MAX_PROMPT_CHARS")
    max_history_messages: int = Field(default=12, ge=0, le=100, validation_alias="LAB4_MAX_HISTORY_MESSAGES")
    max_history_chars: int = Field(default=24000, ge=0, le=200000, validation_alias="LAB4_MAX_HISTORY_CHARS")
    agent_recursion_limit: int = Field(default=80, ge=25, le=200, validation_alias="LAB4_AGENT_RECURSION_LIMIT")
    admin_username: str | None = Field(default=None, validation_alias="LAB4_ADMIN_USERNAME")
    admin_password: SecretStr | None = Field(default=None, validation_alias="LAB4_ADMIN_PASSWORD")
    context_hub_enabled: bool = Field(default=False, validation_alias="LAB4_CONTEXT_HUB_ENABLED")
    context_hub_identifier: str = Field(default="-/bit-professor-agent", validation_alias="LAB4_CONTEXT_HUB_IDENTIFIER")
    langsmith_tracing: bool = Field(default=True, validation_alias="LANGSMITH_TRACING")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com", validation_alias="LANGSMITH_ENDPOINT")
    langsmith_api_key: SecretStr | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="bit_agent_app", validation_alias="LANGSMITH_PROJECT")
    deployment_env: str = Field(default="production", validation_alias="LAB4_DEPLOYMENT_ENV")

    model_config = SettingsConfigDict(
        env_file=(APP_ROOT / ".env", BACKEND_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def model_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_api_key.get_secret_value().strip())

    @property
    def admin_configured(self) -> bool:
        return bool(
            self.admin_username
            and self.admin_username.strip()
            and self.admin_password
            and self.admin_password.get_secret_value().strip()
        )

    @property
    def context_hub_configured(self) -> bool:
        return bool(
            self.context_hub_enabled
            and self.context_hub_identifier.strip()
            and self.langsmith_api_key
            and self.langsmith_api_key.get_secret_value().strip()
        )

    @property
    def langsmith_tracing_configured(self) -> bool:
        return bool(
            self.langsmith_tracing
            and self.langsmith_api_key
            and self.langsmith_api_key.get_secret_value().strip()
        )

    @property
    def resolved_cors_origins(self) -> list[str]:
        return _split_csv(self.cors_origins)

    @property
    def resolved_allowed_hosts(self) -> list[str]:
        return _split_csv(self.allowed_hosts)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
