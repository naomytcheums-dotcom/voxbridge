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

    business_name: str = "the store"

    system_prompt: str = (
        "You are a helpful, concise voice assistant answering a phone call for {business_name}. "
        "Keep replies short and conversational, like a real shop assistant on the phone. "
        "Never use markdown, bullet points, or emoji since your output is spoken aloud. "
        "Use the search_products tool whenever the caller mentions any item, color, or budget — "
        "never guess at the catalog. Confirm product, quantity, name, and phone number out loud "
        "before calling start_order. If the caller is upset or asks for a human, call "
        "escalate_to_human instead of trying to resolve it yourself."
    )

    # Turn-taking
    end_of_utterance_silence_ms: int = 700
    max_reply_sentences: int = 3

    # Telephony — which carrier backs the phone line is just configuration,
    # not something the rest of the codebase should know or care about.
    telephony_provider: str = "telnyx"  # only value implemented so far
    telephony_api_key: str = ""
    telephony_public_url: str = ""  # public https base URL this server is reachable at (ngrok, or a real deploy)

    call_log_db_path: str = "voxbridge_calls.db"

    host: str = "0.0.0.0"
    port: int = 8000

    def resolved_system_prompt(self) -> str:
        return self.system_prompt.format(business_name=self.business_name)


@lru_cache
def get_settings() -> Settings:
    return Settings()
