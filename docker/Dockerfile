# Base image: the pgvector project's own official prebuilt image — pgvector
# comes pre-compiled and pre-installed, no manual `apt-get`/`make` needed.
# Using pg16 to match what we were already running via Postgres.app.
#
# We use pgvector's image (not plain postgres:16) even though today's
# hierarchy work doesn't touch vectors at all — the architecture doc
# already calls for pgvector in the next phase (embeddings/RAG for menu
# generation), and baking it in now avoids rebuilding this image and
# reloading all local data a second time later.
FROM pgvector/pgvector:pg16

# Runs automatically, exactly once, the first time the container starts
# with an empty data volume (this is how the official postgres image's
# entrypoint script works — anything in /docker-entrypoint-initdb.d runs
# in filename order on first boot only, never again after that).
COPY init/01-enable-pgvector.sql /docker-entrypoint-initdb.d/
