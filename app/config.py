from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mcp_agent_token: str = "dev-mcp-agent-token"
    cors_origins: str = "*"
    exercisedb_api_key: str = ""
    exercisedb_api_host: str = "edb-with-videos-and-images-by-ascendapi.p.rapidapi.com"
    exercisedb_base_url: str = ""
    exercisedb_timeout_seconds: float = 15.0
    notion_token: str = ""
    notion_database_id: str = ""
    notion_lifts_database_id: str = ""
    notion_logs_database_id: str = ""
    notion_goals_database_id: str = ""
    notion_locations_database_id: str = ""
    notion_stats_database_id: str = ""
    notion_data_source_id: str = ""
    notion_template_id: str = ""
    notion_version: str = ""
    notion_timeout_seconds: float = 20.0

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
