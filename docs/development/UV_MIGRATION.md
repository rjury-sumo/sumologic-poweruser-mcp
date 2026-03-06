# UV Migration Guide

The Sumo Logic MCP Server now uses **uv exclusively** for package management. This provides faster installs, better dependency resolution, and a more streamlined developer experience.

## What Changed

### Before (pip/venv)

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
python -m sumologic_mcp_server.sumologic_mcp_server
```

### After (uv)

```bash
uv sync --all-extras
uv run sumologic-mcp-server
```

## Key Benefits

1. **Faster** - uv is 10-100x faster than pip
2. **Simpler** - No manual virtualenv management
3. **Reproducible** - uv.lock file ensures consistent installs
4. **Modern** - Built in Rust, actively maintained by Astral

## Updated Files

### pyproject.toml

- Changed build backend from setuptools to hatchling
- Moved dev dependencies to `[tool.uv]` section
- Updated entry points for proper package resolution

### GitHub Actions

- All workflows now use `uv sync` instead of `pip install`
- Commands run with `uv run` prefix
- Tools installed with `uv tool install`

### Documentation

- README.md now emphasizes uv as the primary method
- Added QUICKSTART.md with uv-focused setup
- All examples use `uv run` commands

## Migration Steps

If you have an existing installation:

### 1. Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with existing pip
pip install uv
```

### 2. Remove old virtualenv (optional)

```bash
# If you have an old venv, you can remove it
rm -rf venv/
rm -rf sumo-mcp-env/
```

### 3. Install with uv

```bash
# Install all dependencies
uv sync

# Or with dev dependencies
uv sync --all-extras
```

### 4. Update Claude Desktop Config

Change from:

```json
{
  "command": "python",
  "args": ["/path/to/sumologic_mcp_server.py"]
}
```

To:

```json
{
  "command": "uv",
  "args": [
    "--directory",
    "/absolute/path/to/sumologic-python-mcp",
    "run",
    "sumologic-mcp-server"
  ]
}
```

### 5. Test Your Setup

```bash
# Run the setup test
uv run python test_setup.py

# Or start the server manually
uv run sumologic-mcp-server
```

## Common Commands

### Development

```bash
# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src

# Format code
uv run black src/ tests/

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/

# Security scan
uv run bandit -r src/
```

### Running the Server

```bash
# Run via entry point
uv run sumologic-mcp-server

# Or run module directly
uv run python -m sumologic_mcp_server.sumologic_mcp_server
```

### Tools (one-off usage)

```bash
# Run pip-audit without installing
uv tool run pip-audit --desc

# Install a tool globally
uv tool install black
```

## Troubleshooting

### "uv: command not found"

Add uv to your PATH:

```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

Add this to your shell rc file (~/.bashrc, ~/.zshrc, etc.)

### Import errors

Make sure you ran `uv sync`:

```bash
uv sync --all-extras
```

### Virtual environment conflicts

uv manages its own virtualenvs. If you have issues:

```bash
# Remove uv cache
rm -rf .venv/

# Resync
uv sync --all-extras
```

## FAQ

### Where is the virtualenv?

uv creates it in `.venv/` in your project directory. You don't need to activate it manually - `uv run` handles this automatically.

### Can I still use pip?

While uv is recommended, you can still use pip if needed:

```bash
uv pip install <package>
```

But `uv sync` is preferred for consistency.

### What about uv.lock?

The `uv.lock` file is committed to git and ensures everyone gets the same dependency versions. Don't delete it!

### How do I add a new dependency?

```bash
# Add to pyproject.toml [project.dependencies] or [tool.uv.dev-dependencies]
# Then run:
uv sync
```

uv will update uv.lock automatically.

## Resources

- [uv Documentation](https://github.com/astral-sh/uv)
- [Quick Start Guide](QUICKSTART.md)
- [README](README.md)

---

**Migration completed:** 2025-02-25
