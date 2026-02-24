"""Custom exceptions for Sumo Logic MCP Server."""


class SumoMCPError(Exception):
    """Base exception for all Sumo Logic MCP errors."""

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for structured responses."""
        result = {"error": self.message}
        if self.details:
            result["details"] = self.details
        return result


class ConfigurationError(SumoMCPError):
    """Configuration-related errors."""
    pass


class ValidationError(SumoMCPError):
    """Input validation errors."""
    pass


class AuthenticationError(SumoMCPError):
    """Authentication/authorization errors."""
    pass


class RateLimitError(SumoMCPError):
    """Rate limit exceeded errors."""
    pass


class APIError(SumoMCPError):
    """Sumo Logic API errors."""

    def __init__(self, message: str, status_code: int | None = None, details: str | None = None):
        super().__init__(message, details)
        self.status_code = status_code

    def to_dict(self) -> dict:
        """Convert exception to dictionary with status code."""
        result = super().to_dict()
        if self.status_code:
            result["status_code"] = self.status_code
        return result


class TimeoutError(SumoMCPError):
    """Search or request timeout errors."""
    pass


class InstanceNotFoundError(SumoMCPError):
    """Requested Sumo Logic instance not configured."""
    pass
