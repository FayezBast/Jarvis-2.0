# ==============================================================================
# Jarvis Telegram Bot - Secure Container
# ==============================================================================
# Security features:
# - Runs as non-root user (jarvis:1000)
# - Minimal base image (python:3.13-slim)
# - No secrets baked into image
# - Read-only filesystem compatible
# - No extra capabilities needed
# ==============================================================================

FROM python:3.13-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt


# ==============================================================================
# Production image - minimal and secure
# ==============================================================================
FROM python:3.13-slim

# Security: Don't run as root
# Create non-root user with specific UID/GID
RUN groupadd --gid 1000 jarvis && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home jarvis

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Security: Set Python to not write bytecode (read-only fs)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create app directory structure
WORKDIR /app

# Create directories that need to be writable
# These will be mounted as volumes or tmpfs
RUN mkdir -p /app/logs /app/workdir && \
    chown -R jarvis:jarvis /app

# Copy application code (owned by root, read-only)
COPY --chown=root:root core/ /app/core/
COPY --chown=root:root tools/ /app/tools/
COPY --chown=root:root functions/ /app/functions/
COPY --chown=root:root *.py /app/
COPY --chown=root:root prompts.py config.py /app/

# Security: Make app files read-only
RUN chmod -R 555 /app/*.py /app/core /app/tools /app/functions

# Security: Switch to non-root user
USER jarvis

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/app/telegram_bot.py') else 1)"

# Default command
CMD ["python", "telegram_bot.py"]
