# baseball-crawl FastAPI application image
#
# Build: docker build -t baseball-crawl .
# Run:   docker compose up (preferred -- manages volumes and env)
#
# The image installs Python dependencies, copies the source tree,
# runs apply_migrations.py to initialize the SQLite database, and
# then starts uvicorn. The ./data directory is host-mounted at runtime
# so the database is visible on the host filesystem.

FROM python:3.13-slim

# System dependencies: curl is required for the Docker health check.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cached unless requirements change).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source.
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY pyproject.toml .

# Install the package so console scripts (bb) are available on PATH.
RUN pip install --no-cache-dir --no-deps -e .

# Create the data directory inside the image as a mount point fallback.
# At runtime, docker compose mounts ./data here, shadowing this directory.
RUN mkdir -p ./data/seeds

# Copy seed data so it is available inside the container.
COPY data/seeds/ ./data/seeds/

# Start: run migrations then launch uvicorn.
# apply_migrations.py is idempotent -- safe to run on every container start.
CMD ["sh", "-c", "python migrations/apply_migrations.py && uvicorn src.api.main:app --host 0.0.0.0 --port 8000"]
