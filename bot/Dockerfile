FROM python:3.11-slim

WORKDIR /app

# Install system deps + uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

# Install nlm CLI
RUN uv tool install notebooklm-mcp-cli

# Add nlm to PATH
ENV PATH="/root/.local/bin:$PATH"

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV NLM_PATH=/root/.local/bin/nlm
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
