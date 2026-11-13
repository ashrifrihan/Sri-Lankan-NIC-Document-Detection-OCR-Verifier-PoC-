from pydantic_settings import BaseSettings
from pydantic import ConfigDict, SecretStr, field_validator
from typing import List, Literal

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Sri Lankan NIC Verifier PoC"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    BOOKINGPARTNER_API_KEY: SecretStr | None = None
    BOOKINGPARTNER_PREVIOUS_API_KEY: SecretStr | None = None
    BOOKINGPARTNER_REQUESTS_PER_MINUTE: int = 20

    @field_validator("BOOKINGPARTNER_API_KEY", "BOOKINGPARTNER_PREVIOUS_API_KEY")
    @classmethod
    def validate_bookingpartner_key(cls, value):
        if value is not None:
            key = value.get_secret_value()
            if len(key) < 32 or not key.isascii() or not key.isalnum():
                raise ValueError("Set a random alphanumeric BookingPartner key of at least 32 characters.")
        return value

    # CORS configuration - strictly restricted to localhost
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # File limits
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_MIME_TYPES: List[str] = [
        "image/jpeg",
        "image/png",
        "image/webp"
    ]
    MIN_IMAGE_WIDTH: int = 400
    MIN_IMAGE_HEIGHT: int = 250

    # Image Quality Thresholds
    BLUR_LAPLACIAN_THRESHOLD: float = 85.0
    DARKNESS_THRESHOLD_MEAN: float = 45.0
    GLARE_THRESHOLD_PERCENT: float = 0.12  # If >12% pixels are near saturated (>245)
    STANDARD_ID_ASPECT_RATIO: float = 1.586  # ID-1 standard (85.6mm x 53.98mm)
    ASPECT_RATIO_TOLERANCE: float = 0.35

    # OCR Settings
    OCR_BACKEND: Literal["auto", "paddle", "tesseract", "windows"] = "auto"
    TESSDATA_PREFIX: str | None = None
    OCR_REVIEW_CONFIDENCE: float = 0.65

settings = Settings()
