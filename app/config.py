from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Salestroopz"
    admin_email: str = "admin@salestroopz.com"
    environment: str = "development"

    class Config:
        env_file = ".env"
