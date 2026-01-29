# src/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = "gpt-4.1-mini"

    # Sampling
    temperature: float = 0.4

    # Strong JSON reliability for prompts that demand JSON-only output.
    # When enabled, we pass response_format to the Responses API.
    use_json_mode: bool = Field(default=True, env="USE_JSON_MODE")

    # Supported values (practically): "json_object"
    # (If in future you add json_schema, we can extend.)
    json_mode_type: str = Field(default="json_object", env="JSON_MODE_TYPE")

    # Optional: cap the output tokens to reduce truncation risk
    max_output_tokens: int = Field(default=2500, env="MAX_OUTPUT_TOKENS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()