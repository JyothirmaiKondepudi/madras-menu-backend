-- Enables the extension so it's available without a manual step later,
-- once the embeddings/RAG work actually needs it. Harmless today — the
-- hierarchy prototype doesn't use any vector columns yet.
CREATE EXTENSION IF NOT EXISTS vector;
