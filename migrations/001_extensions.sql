-- Run with a database role that is allowed to install extensions.
-- pgvector extension name is `vector`.
CREATE EXTENSION IF NOT EXISTS vector;

-- Apache AGE must already be installed on the PostgreSQL server image/host.
CREATE EXTENSION IF NOT EXISTS age;

LOAD 'age';
SET search_path = ag_catalog, "$user", public;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'ai_knowledge_graph'
    ) THEN
        PERFORM ag_catalog.create_graph('ai_knowledge_graph');
    END IF;
END
$$;
