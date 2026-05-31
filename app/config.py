from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Supabase
    supabase_url: str
    supabase_service_key: str
    owner_user_id: str = ""

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str
    my_whatsapp_number: str

    # LLM
    llm_api_key: str
    llm_model: str = "gpt-4o-mini"

    # App
    log_level: str = "INFO"


settings = Settings()
