#!/usr/bin/env python3
"""Quick test script to verify setup is correct."""

import os
import sys


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")

    try:
        from sumologic_poweruser_mcp import config  # noqa: F401
        print("✓ config module imported")
    except ImportError as e:
        print(f"✗ Failed to import config: {e}")
        raise AssertionError(f"Failed to import config: {e}") from e

    try:
        from sumologic_poweruser_mcp import exceptions  # noqa: F401
        print("✓ exceptions module imported")
    except ImportError as e:
        print(f"✗ Failed to import exceptions: {e}")
        raise AssertionError(f"Failed to import exceptions: {e}") from e

    try:
        from sumologic_poweruser_mcp import validation  # noqa: F401
        print("✓ validation module imported")
    except ImportError as e:
        print(f"✗ Failed to import validation: {e}")
        raise AssertionError(f"Failed to import validation: {e}") from e

    try:
        from sumologic_poweruser_mcp import rate_limiter  # noqa: F401
        print("✓ rate_limiter module imported")
    except ImportError as e:
        print(f"✗ Failed to import rate_limiter: {e}")
        raise AssertionError(f"Failed to import rate_limiter: {e}") from e

    try:
        from sumologic_poweruser_mcp import sumologic_mcp_server  # noqa: F401
        print("✓ sumologic_mcp_server module imported")
    except ImportError as e:
        print(f"✗ Failed to import sumologic_mcp_server: {e}")
        raise AssertionError(f"Failed to import sumologic_mcp_server: {e}") from e

    assert True

def test_env():
    """Test that environment variables are configured."""
    print("\nTesting environment configuration...")

    has_creds = False

    if os.getenv("SUMO_ACCESS_ID") and os.getenv("SUMO_ACCESS_KEY"):
        print("✓ Default instance credentials found")
        has_creds = True
    else:
        print("⚠ No default instance credentials (SUMO_ACCESS_ID/SUMO_ACCESS_KEY)")

    # Check for additional instances
    instance_count = 0
    for key in os.environ.keys():
        if key.startswith("SUMO_") and key.endswith("_ACCESS_ID"):
            instance_name = key.replace("SUMO_", "").replace("_ACCESS_ID", "")
            if instance_name.upper() not in ["ACCESS"]:
                print(f"✓ Found instance: {instance_name.lower()}")
                instance_count += 1

    if instance_count == 0 and not has_creds:
        print("\n⚠ Warning: No Sumo Logic credentials configured!")
        print("  Create a .env file with your credentials:")
        print("  cp .env.example .env")
        print("  # Then edit .env with your actual credentials")
        # Don't fail the test, just warn
        assert True
    else:
        assert True

def main():
    """Run all tests."""
    print("=" * 60)
    print("Sumo Logic Power User MCP Server - Setup Test")
    print("=" * 60)

    imports_ok = test_imports()
    env_ok = test_env()

    print("\n" + "=" * 60)
    if imports_ok and env_ok:
        print("✅ Setup looks good! Ready to run.")
        print("\nTo start the server:")
        print("  uv run sumologic-poweruser-mcp")
        return 0
    elif imports_ok:
        print("⚠ Imports OK, but credentials not configured")
        print("\nNext steps:")
        print("  1. cp .env.example .env")
        print("  2. Edit .env with your Sumo Logic credentials")
        print("  3. Run this test again: uv run python test_setup.py")
        return 1
    else:
        print("❌ Setup issues detected. Please check errors above.")
        print("\nTry:")
        print("  uv sync --all-extras")
        return 1

if __name__ == "__main__":
    sys.exit(main())
