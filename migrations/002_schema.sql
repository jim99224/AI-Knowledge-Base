CREATE TABLE IF NOT EXISTS repositories (
    id uuid PRIMARY KEY,
    owner varchar(255) NOT NULL,
    name varchar(255) NOT NULL,
    default_branch varchar(255) NOT NULL DEFAULT 'main',
    last_indexed_commit varchar(64),
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_repository_owner_name UNIQUE (owner, name)
);

CREATE TABLE IF NOT EXISTS documents (
    id uuid PRIMARY KEY,
    repository_id uuid NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    path text NOT NULL,
    title text,
    document_type varchar(64) NOT NULL,
    branch varchar(255) NOT NULL,
    commit_sha varchar(64) NOT NULL,
    content_hash varchar(128) NOT NULL,
    raw_text text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    index_status varchar(32) NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    CONSTRAINT uq_document_source UNIQUE (repository_id, branch, path)
);

CREATE TABLE IF NOT EXISTS chunks (
    id uuid PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    repository_id uuid NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    heading_path text,
    content text NOT NULL,
    token_count integer,
    content_hash varchar(128) NOT NULL,
    commit_sha varchar(64) NOT NULL,
    embedding vector(1024),
    embedding_model varchar(255),
    embedding_index_version varchar(128),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_chunk_document_index UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS index_jobs (
    id uuid PRIMARY KEY,
    repository_id uuid NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_sha varchar(64) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'pending',
    files_scanned integer NOT NULL DEFAULT 0,
    documents_updated integer NOT NULL DEFAULT 0,
    chunks_created integer NOT NULL DEFAULT 0,
    error text,
    started_at timestamptz,
    finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_documents_repository ON documents(repository_id);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_chunks_repository ON chunks(repository_id);
CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON chunks USING gin(metadata);

-- HNSW is the initial ANN index. Recreate this index when embedding dimension/model changes.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
ON chunks USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;
