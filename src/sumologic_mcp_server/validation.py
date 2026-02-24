"""Input validation for Sumo Logic MCP Server."""

import re
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from .exceptions import ValidationError


class QueryValidation(BaseModel):
    """Validation model for search queries."""

    query: str = Field(..., min_length=1, max_length=10000, description="Search query")

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query content."""
        if not v or not v.strip():
            raise ValidationError("Query cannot be empty")

        # Check for excessively long queries
        if len(v) > 10000:
            raise ValidationError("Query exceeds maximum length of 10,000 characters")

        # Basic sanitization - no null bytes
        if '\x00' in v:
            raise ValidationError("Query contains invalid null bytes")

        return v.strip()


class TimeRangeValidation(BaseModel):
    """Validation model for time ranges."""

    hours_back: int = Field(default=1, ge=0, le=8760, description="Hours to look back")

    @field_validator('hours_back')
    @classmethod
    def validate_hours_back(cls, v: int) -> int:
        """Validate hours_back parameter."""
        if v < 0:
            raise ValidationError("hours_back cannot be negative")

        # Warn for very large time ranges (more than 30 days)
        if v > 720:  # 30 days
            # Allow but could log a warning
            pass

        # Hard limit of 1 year
        if v > 8760:  # 365 days
            raise ValidationError("hours_back cannot exceed 8760 hours (1 year)")

        return v


class PaginationValidation(BaseModel):
    """Validation model for pagination parameters."""

    limit: int = Field(default=100, ge=1, le=1000, description="Maximum results to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """Validate limit parameter."""
        if v < 1:
            raise ValidationError("limit must be at least 1")
        if v > 1000:
            raise ValidationError("limit cannot exceed 1000")
        return v

    @field_validator('offset')
    @classmethod
    def validate_offset(cls, v: int) -> int:
        """Validate offset parameter."""
        if v < 0:
            raise ValidationError("offset cannot be negative")
        if v > 100000:
            raise ValidationError("offset cannot exceed 100,000 (use pagination)")
        return v


class CollectorValidation(BaseModel):
    """Validation model for collector operations."""

    collector_id: int = Field(..., ge=1, description="Collector ID")

    @field_validator('collector_id')
    @classmethod
    def validate_collector_id(cls, v: int) -> int:
        """Validate collector ID."""
        if v < 1:
            raise ValidationError("collector_id must be a positive integer")
        return v


class InstanceValidation(BaseModel):
    """Validation model for instance selection."""

    instance: str = Field(default='default', min_length=1, max_length=50, description="Instance name")

    @field_validator('instance')
    @classmethod
    def validate_instance(cls, v: str) -> str:
        """Validate instance name."""
        if not v or not v.strip():
            raise ValidationError("instance name cannot be empty")

        # Only allow alphanumeric, underscore, and hyphen
        if not re.match(r'^[a-z0-9_-]+$', v, re.IGNORECASE):
            raise ValidationError(
                "instance name can only contain letters, numbers, underscores, and hyphens"
            )

        return v.strip().lower()


class ContentTypeValidation(BaseModel):
    """Validation model for content types."""

    content_type: str = Field(default="Dashboard", description="Content type")

    @field_validator('content_type')
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        """Validate content type."""
        valid_types = [
            "Dashboard", "Search", "Folder", "Report", "ScheduledSearch",
            "MetricsSearch", "LogsSearch", "TracesSearch"
        ]

        if v not in valid_types:
            raise ValidationError(
                f"Invalid content_type. Must be one of: {', '.join(valid_types)}"
            )

        return v


class MonitorSearchValidation(BaseModel):
    """Validation model for monitor search queries."""

    query: str = Field(..., min_length=1, max_length=1000, description="Monitor search query")

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate monitor search query."""
        if not v or not v.strip():
            raise ValidationError("Monitor search query cannot be empty")

        if len(v) > 1000:
            raise ValidationError("Monitor search query exceeds maximum length of 1,000 characters")

        return v.strip()


def validate_query_input(query: str, max_length: int = 10000) -> str:
    """Validate and sanitize query input."""
    try:
        validation = QueryValidation(query=query)
        return validation.query
    except Exception as e:
        raise ValidationError(f"Query validation failed: {str(e)}")


def validate_time_range(hours_back: int) -> int:
    """Validate time range input."""
    try:
        validation = TimeRangeValidation(hours_back=hours_back)
        return validation.hours_back
    except Exception as e:
        raise ValidationError(f"Time range validation failed: {str(e)}")


def validate_pagination(limit: int, offset: int = 0) -> tuple[int, int]:
    """Validate pagination parameters."""
    try:
        validation = PaginationValidation(limit=limit, offset=offset)
        return validation.limit, validation.offset
    except Exception as e:
        raise ValidationError(f"Pagination validation failed: {str(e)}")


def validate_instance_name(instance: str) -> str:
    """Validate instance name."""
    try:
        validation = InstanceValidation(instance=instance)
        return validation.instance
    except Exception as e:
        raise ValidationError(f"Instance validation failed: {str(e)}")
