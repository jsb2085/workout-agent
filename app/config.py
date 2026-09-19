from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://workout:workout@localhost:5432/workout"
    jwt_secret: str = "dev-jwt-secret-change-me-please-use-32+"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 30
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "physique-photos"
    minio_secure: bool = False
    mcp_agent_token: str = "dev-mcp-agent-token"
    cors_origins: str = "*"
    # ExerciseDB: RapidAPI key enables V2 MP4 videos. Without a key, the free
    # hosted V1 API is used and demonstration media is an animated GIF.
    exercisedb_api_key: str = ""
    exercisedb_api_host: str = "edb-with-videos-and-images-by-ascendapi.p.rapidapi.com"
    exercisedb_base_url: str = ""
    exercisedb_timeout_seconds: float = 15.0
    notion_token: str = ""
    notion_database_id: str = ""
    notion_data_source_id: str = ""
    notion_template_id: str = ""
    notion_version: str = ""
    notion_timeout_seconds: float = 20.0

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
