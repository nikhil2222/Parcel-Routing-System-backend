import os
from pydantic import BaseModel


class FeatureFlags(BaseModel):
    xml_batch_upload_enabled: bool = True
    ruleset_simulation_enabled: bool = True
    insurance_review_blocking_enabled: bool = False

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def from_env(cls) -> "FeatureFlags":
        return cls(
            xml_batch_upload_enabled=cls._env_bool("XML_BATCH_UPLOAD_ENABLED", True),
            ruleset_simulation_enabled=cls._env_bool("RULESET_SIMULATION_ENABLED", True),
            insurance_review_blocking_enabled=cls._env_bool("INSURANCE_REVIEW_BLOCKING_ENABLED", False),
        )