from app.config import Settings


def test_resolved_system_prompt_interpolates_business_name():
    settings = Settings(business_name="Aurora Boutique")
    assert "Aurora Boutique" in settings.resolved_system_prompt()


def test_resolved_system_prompt_instructs_bilingual_reply():
    settings = Settings()
    prompt = settings.resolved_system_prompt().lower()
    assert "french" in prompt
    assert "english" in prompt
    assert "never mix" in prompt


def test_default_deepgram_language_supports_code_switching():
    assert Settings().deepgram_language == "multi"


def test_default_elevenlabs_model_is_multilingual():
    assert "multilingual" in Settings().elevenlabs_model_id or "v2_5" in Settings().elevenlabs_model_id
