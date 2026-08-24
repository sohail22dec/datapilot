from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load and override .env variables into os.environ for LangSmith tracing
load_dotenv(override=True)


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/datapilot"
    GEMINI_API_KEY: str = "placeholder_gemini_key"
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    GROQ_API_KEY: str = "placeholder_groq_key"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()