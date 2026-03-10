# Multi-stage build for smaller final image
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml README.md uv.lock LICENSE ./
COPY src/ src/

# Copy query examples data (if it exists)
COPY logs_searches.json.gz ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Final stage
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy uv from builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the entire application from builder
COPY --from=builder /app /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Expose MCP server port if using stdio (not needed for stdio mode)
# The server uses stdio by default, no port exposure needed

# Health check (optional - only useful if running in server mode)
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#   CMD python -c "import sys; sys.exit(0)"

# Run the MCP server
CMD ["uv", "run", "sumologic-poweruser-mcp"]
