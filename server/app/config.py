"""
Server Configuration
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    
    # SIP
    SIP_USER: str = ""
    SIP_PASSWORD: str = ""
    SIP_SERVER: str = "sipconnect.sipgate.de"
    SIP_PORT: int = 5060
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080
    
    # Audio
    SAMPLE_RATE_SIP: int = 8000  # G.711
    SAMPLE_RATE_AI: int = 24000  # OpenAI output
    SAMPLE_RATE_AI_INPUT: int = 16000  # OpenAI input
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
