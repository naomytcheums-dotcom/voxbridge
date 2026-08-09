"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Speech-to-text
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-2"

    # Text-to-speech
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # default public demo voice

    # LLM
    llm_provider: str = "openai"  # "openai" | "anthropic"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = ""

    system_prompt: str = (
        "You are a helpful, concise voice assistant answering a phone call. "
        "Keep replies short and conversational, like a real receptionist. "
        "Never use markdown, bullet points, or emoji since your output is spoken aloud."
    )

    # Turn-taking
    end_of_utterance_silence_ms: int = 700
    max_reply_sentences: int = 3

    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
