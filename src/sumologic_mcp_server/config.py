"""Configuration management for Sumo Logic MCP Server."""

import os
import re
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator


class SumoInstanceConfig(BaseModel):
    """Configuration for a single Sumo Logic instance."""

    access_id: str = Field(..., min_length=1, description="Sumo Logic Access ID")
    access_key: str = Field(..., min_length=1, description="Sumo Logic Access Key")
    endpoint: str = Field(..., description="Sumo Logic API endpoint")
    subdomain: Optional[str] = Field(
        default=None, description="Optional subdomain for custom Sumo Logic URL"
    )

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Validate and normalize endpoint URL."""
        if not v:
            raise ValueError("Endpoint cannot be empty")

        # Ensure it's a valid HTTPS URL
        if not v.startswith(("https://", "http://")):
            raise ValueError("Endpoint must start with https:// or http://")

        # Remove trailing slash
        return v.rstrip("/")

    @field_validator("access_id", "access_key")
    @classmethod
    def validate_credentials(cls, v: str) -> str:
        """Validate credentials are not placeholder values."""
        if v in [
            "your_access_id_here",
            "your_access_key_here",
            "your_id",
            "your_key",
            "PLACEHOLDER",
        ]:
            raise ValueError("Please replace placeholder credentials with actual values")
        return v


class ServerConfig(BaseModel):
    """Server configuration settings."""

    max_query_limit: int = Field(
        default=1000, ge=1, le=10000, description="Maximum results per query"
    )
    max_search_timeout: int = Field(
        default=300, ge=10, le=600, description="Maximum search timeout in seconds"
    )
    rate_limit_per_minute: int = Field(
        default=60, ge=1, le=1000, description="Requests per minute per tool"
    )
    log_level: str = Field(default="INFO", description="Logging level")
    enable_audit_log: bool = Field(default=True, description="Enable audit logging")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v_upper


class Config:
    """Application configuration manager."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        self.instances: Dict[str, SumoInstanceConfig] = {}
        self.server_config = self._load_server_config()
        self._load_instances()

    def _load_server_config(self) -> ServerConfig:
        """Load server configuration from environment."""
        return ServerConfig(
            max_query_limit=int(os.getenv("MAX_QUERY_LIMIT", "1000")),
            max_search_timeout=int(os.getenv("MAX_SEARCH_TIMEOUT", "300")),
            rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            enable_audit_log=os.getenv("ENABLE_AUDIT_LOG", "true").lower() == "true",
        )

    def _load_instances(self) -> None:
        """Load all Sumo Logic instance configurations from environment."""
        # Load default instance
        default_id = os.getenv("SUMO_ACCESS_ID")
        default_key = os.getenv("SUMO_ACCESS_KEY")
        default_endpoint = os.getenv("SUMO_ENDPOINT", "https://api.sumologic.com")

        if default_id and default_key:
            try:
                default_subdomain = os.getenv("SUMO_SUBDOMAIN")
                self.instances["default"] = SumoInstanceConfig(
                    access_id=default_id,
                    access_key=default_key,
                    endpoint=default_endpoint,
                    subdomain=default_subdomain,
                )
            except ValueError as e:
                raise ValueError(f"Default instance configuration invalid: {e}")

        # Load named instances (e.g., SUMO_PROD_ACCESS_ID, SUMO_STAGING_ACCESS_ID)
        pattern = re.compile(r"^SUMO_([A-Z0-9_]+)_ACCESS_ID$")

        for key in os.environ.keys():
            match = pattern.match(key)
            if match:
                instance_name = match.group(1).lower()

                # Skip if this would conflict with default
                if instance_name in ["access", "endpoint"]:
                    continue

                access_id = os.getenv(f"SUMO_{match.group(1)}_ACCESS_ID")
                access_key = os.getenv(f"SUMO_{match.group(1)}_ACCESS_KEY")
                endpoint = os.getenv(f"SUMO_{match.group(1)}_ENDPOINT", "https://api.sumologic.com")
                subdomain = os.getenv(f"SUMO_{match.group(1)}_SUBDOMAIN")

                if access_id and access_key:
                    try:
                        self.instances[instance_name] = SumoInstanceConfig(
                            access_id=access_id,
                            access_key=access_key,
                            endpoint=endpoint,
                            subdomain=subdomain,
                        )
                    except ValueError as e:
                        raise ValueError(f"Instance '{instance_name}' configuration invalid: {e}")

    def get_instance(self, instance_name: str = "default") -> SumoInstanceConfig:
        """Get configuration for a specific instance."""
        if instance_name not in self.instances:
            available = ", ".join(self.instances.keys())
            raise ValueError(
                f"Instance '{instance_name}' not found. Available instances: {available}"
            )
        return self.instances[instance_name]

    def list_instances(self) -> list[str]:
        """List all configured instance names."""
        return list(self.instances.keys())

    def validate(self) -> None:
        """Validate configuration."""
        if not self.instances:
            raise ValueError(
                "No Sumo Logic instances configured. "
                "Please set SUMO_ACCESS_ID and SUMO_ACCESS_KEY environment variables."
            )

        # Validate each instance
        for name, instance in self.instances.items():
            # Try to create a simple validation - credentials exist and are not empty
            if not instance.access_id or not instance.access_key:
                raise ValueError(f"Instance '{name}' has empty credentials")


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
        _config.validate()
    return _config


def reset_config() -> None:
    """Reset configuration (mainly for testing)."""
    global _config
    _config = None
