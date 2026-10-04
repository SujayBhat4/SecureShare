from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# boto3 looks for AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in the process
# environment, not in a .env file. load_dotenv copies .env into the environment
# so boto3 finds the keys by itself. (python-dotenv comes with pydantic-settings.)
load_dotenv()


# All app settings in one place. Values come from the environment or the .env
# file, so no secret ever appears in the code.
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    aws_region: str = "ap-southeast-2"
    s3_bucket_name: str
    jwt_secret: str
    environment: str = "development"

    # Fixed rules of the app (not read from .env)
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    allowed_extensions: tuple = ("pdf", "png", "jpg", "jpeg", "docx", "xlsx", "pptx", "txt", "csv")
    presigned_url_seconds: int = 60
    session_hours: int = 12

    # .env uses "postgresql://", but SQLAlchemy with psycopg 3 needs "postgresql+psycopg://"
    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    # The session cookie is only marked Secure (HTTPS only) in production
    @property
    def cookie_secure(self) -> bool:
        return self.environment == "production"


settings = Settings()
