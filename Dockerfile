FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy dependency files
COPY pyproject.toml poetry.lock* README.md ./

# Copy application code
COPY patient_intake/ ./patient_intake/
COPY templates/ ./templates/

# Install dependencies (no dev dependencies, no virtualenv in container)
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Create creds file
RUN mkdir ./.streamlit
COPY .streamlit/secrets.toml.example ./.streamlit/secrets.toml
COPY .env.example ./.env

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "patient_intake/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
