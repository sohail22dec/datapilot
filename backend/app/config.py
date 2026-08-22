from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load and override .env variables into os.environ for LangSmith tracing
load_dotenv(override=True)


class Settings(BaseSettings):
    DATABASE_URL: str
    GEMINI_API_KEY: str
    GEMINI_MODEL: str
    GROQ_API_KEY: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()