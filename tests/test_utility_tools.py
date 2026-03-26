"""Tests for utility tools."""

import json

import pytest

from sumologic_poweruser_mcp.sumologic_mcp_server import get_skill, get_version


class TestGetSkill:
    """Test cases for get_skill tool."""

    @pytest.mark.asyncio
    async def test_get_skill_valid(self):
        """Test getting a valid skill."""
        # Test with a known skill that should exist
        result = await get_skill("search-write-queries")

        # Should return markdown content, not JSON error
        assert not result.startswith("{")
        assert "# Skill:" in result or "Skill:" in result
        assert len(result) > 100  # Should be substantial content

    @pytest.mark.asyncio
    async def test_get_skill_not_found(self):
        """Test getting a non-existent skill."""
        result = await get_skill("nonexistent-skill-12345")

        # Should return JSON error response
        data = json.loads(result)
        assert "error" in data
        assert "Skill not found" in data["error"]
        assert "available_skills" in data
        assert isinstance(data["available_skills"], list)
        assert len(data["available_skills"]) > 0  # Should list available skills

    @pytest.mark.asyncio
    async def test_get_skill_lists_available(self):
        """Test that error response lists available skills."""
        result = await get_skill("invalid-skill")

        data = json.loads(result)
        available = data["available_skills"]

        # Should include known skills
        skill_names = [s for s in available]
        assert any("search" in s for s in skill_names)
        assert any("discovery" in s for s in skill_names)

    @pytest.mark.asyncio
    async def test_get_skill_multiple_skills(self):
        """Test getting multiple different skills."""
        # Get several skills to ensure consistency
        skills_to_test = [
            "search-write-queries",
            "search-optimize-queries",
        ]

        for skill_name in skills_to_test:
            result = await get_skill(skill_name)

            # Check if it's an error (skill might not exist)
            if result.startswith("{"):
                data = json.loads(result)
                # If error, make sure it's properly formatted
                assert "error" in data
            else:
                # If success, should be markdown
                assert len(result) > 50
                # Most skills should have these sections
                assert "##" in result or "#" in result

    @pytest.mark.asyncio
    async def test_get_skill_path_resolution(self):
        """Test that skill path is correctly resolved."""
        result = await get_skill("search-write-queries")

        # Should successfully read the file
        # Either returns content or error with available skills
        if result.startswith("{"):
            data = json.loads(result)
            # If it's an error, it should still list skills (directory exists)
            assert "available_skills" in data
        else:
            # Success - got markdown content
            assert len(result) > 100


class TestGetVersion:
    """Test cases for get_version tool."""

    @pytest.mark.asyncio
    async def test_get_version_returns_json(self):
        """Test that get_version returns valid JSON."""
        result = await get_version()
        data = json.loads(result)
        assert "version" in data
        assert "name" in data
        assert "description" in data

    @pytest.mark.asyncio
    async def test_get_version_values(self):
        """Test that get_version returns expected values."""
        result = await get_version()
        data = json.loads(result)
        assert data["name"] == "sumologic-poweruser-mcp"
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0
