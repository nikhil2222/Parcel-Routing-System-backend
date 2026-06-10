import os
from typing import List
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_allowed_origins() -> List[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:5174,https://parcel-routing-system.netlify.app/")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_trusted_hosts() -> List[str]:
    raw = os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver,parcel-routing-system-backend.onrender.com")
    return [host.strip() for host in raw.split(",") if host.strip()]


def get_api_key(api_key: str = Security(api_key_header)) -> str:
    expected_key = os.getenv("API_KEY", "dev-secret-key-change-in-production")
    environment = os.getenv("APP_ENV", "development").lower()

    if environment == "production" and expected_key == "dev-secret-key-change-in-production":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key is not configured for production.",
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key. Include 'X-API-Key' header.",
        )
    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key.",
        )
    return api_key