FROM python:3.12-slim

# Install minimal tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22 (Claude Code CLI dependency)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

# Copy source
COPY . .

# Install package with dev dependencies
RUN pip install --no-cache-dir .[dev]

# Verify installations
RUN claudecode-terminal version && \
    cct version && \
    claude --version

# Run tests
CMD ["pytest", "tests/", "-v"]
