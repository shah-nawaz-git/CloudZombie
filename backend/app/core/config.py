from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import Mode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    cloudzombie_mode: Mode = Field(default=Mode.DEMO, validation_alias="CLOUDZOMBIE_MODE")
    database_url: str = Field(default="sqlite:///./cloudzombie.db", validation_alias="DATABASE_URL")
    aws_profile: str | None = Field(default=None, validation_alias="AWS_PROFILE")
    aws_region_selection: str | None = Field(default=None, validation_alias="AWS_REGION_SELECTION")
    pricing_cache_ttl: int = Field(default=86400, validation_alias="PRICING_CACHE_TTL")
    cloudzombie_cors_origins: str = Field(
        default="http://localhost:3000", validation_alias="CLOUDZOMBIE_CORS_ORIGINS"
    )
    cloudzombie_demo_seed: bool = Field(default=True, validation_alias="CLOUDZOMBIE_DEMO_SEED")
    demo_fixture_path: str | None = Field(default=None, validation_alias="CLOUDZOMBIE_DEMO_FIXTURE")
    cloudzombie_log_level: str = Field(default="INFO", validation_alias="CLOUDZOMBIE_LOG_LEVEL")

    @field_validator("aws_profile", "aws_region_selection", mode="before")
    @classmethod
    def empty_aws_setting_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def region_selection(self) -> list[str] | None:
        if not self.aws_region_selection:
            return None
        values = [item.strip() for item in self.aws_region_selection.split(",") if item.strip()]
        return values or None

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cloudzombie_cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
