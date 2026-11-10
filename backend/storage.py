"""Postgres persistence, pgvector retrieval, and user-scoped documents."""
import os
import uuid
import psycopg
from psycopg.rows import dict_row

DSN = os.environ.get("DATABASE_URL", "postgresql://rag:rag@localhost:5432/rag")

def connect():
    return psycopg.connect(DSN, row_factory=dict_row)

def initialize():
    with connect() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id),
            filename TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            error TEXT, created_at TIMESTAMPTZ DEFAULT now())""")
        conn.execute("""CREATE TABLE IF NOT EXISTS chunks (
            id UUID PRIMARY KEY, document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            owner_id UUID NOT NULL REFERENCES users(id), page INT NOT NULL,
            content TEXT NOT NULL, embedding vector(384) NOT NULL,
            search TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED)""")
        conn.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS policy_key TEXT")
        conn.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS version_label TEXT")
        conn.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS effective_date DATE")
        conn.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_current BOOLEAN NOT NULL DEFAULT TRUE")
        conn.execute("CREATE INDEX IF NOT EXISTS documents_policy_idx ON documents(owner_id,policy_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS chunks_owner_idx ON chunks(owner_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS chunks_search_idx ON chunks USING GIN(search)")

def create_document(owner, filename, policy_key=None, version_label=None, effective_date=None):
    doc_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute("""INSERT INTO documents(id,owner_id,filename,policy_key,version_label,effective_date)
                        VALUES(%s,%s,%s,%s,%s,%s)""",
                     (doc_id, owner, filename, policy_key, version_label, effective_date))
    return doc_id

def set_status(doc_id, owner, status, error=None):
    with connect() as conn:
        if status == "ready":
            row = conn.execute("SELECT policy_key FROM documents WHERE id=%s AND owner_id=%s",
                               (doc_id, owner)).fetchone()
            if row and row["policy_key"]:
                conn.execute("""UPDATE documents SET is_current=FALSE
                    WHERE owner_id=%s AND policy_key=%s AND id<>%s""",
                    (owner, row["policy_key"], doc_id))
        conn.execute("UPDATE documents SET status=%s,error=%s WHERE id=%s AND owner_id=%s",
                     (status, error, doc_id, owner))

def save_chunks(doc_id, owner, chunks, embeddings):
    with connect() as conn:
        for doc, vector in zip(chunks, embeddings):
            conn.execute("""INSERT INTO chunks(id,document_id,owner_id,page,content,embedding)
                VALUES(%s,%s,%s,%s,%s,%s::vector)""",
                (str(uuid.uuid4()), doc_id, owner, int(doc.metadata.get("page", 0)) + 1,
                 doc.page_content, "[" + ",".join(map(str, vector)) + "]"))

def list_documents(owner):
    with connect() as conn:
        return conn.execute("""SELECT id,filename,status,error,created_at,policy_key,version_label,effective_date,is_current FROM documents
            WHERE owner_id=%s ORDER BY created_at DESC""", (owner,)).fetchall()

def delete_documents(owner):
    with connect() as conn:
        conn.execute("DELETE FROM chunks WHERE owner_id=%s", (owner,))
        conn.execute("DELETE FROM documents WHERE owner_id=%s", (owner,))

def search(owner, query, embedding, limit=20, include_superseded=False):
    """Rank only ready, authorized documents. Superseded versions are opt-in."""
    vector = "[" + ",".join(map(str, embedding)) + "]"
    with connect() as conn:
        return conn.execute("""WITH eligible AS (
            SELECT c.id,c.document_id,c.page,c.content,c.embedding,c.search,
                   d.filename,d.policy_key,d.version_label,d.effective_date,d.is_current
            FROM chunks c JOIN documents d ON d.id=c.document_id
            WHERE c.owner_id=%s AND d.owner_id=%s AND d.status='ready'
              AND (%s OR d.is_current)
        ), dense AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank
            FROM eligible ORDER BY embedding <=> %s::vector LIMIT 20
        ), lexical AS (
            SELECT id, ROW_NUMBER() OVER (
                ORDER BY ts_rank_cd(search, plainto_tsquery('english', %s)) DESC
            ) AS rank
            FROM eligible WHERE search @@ plainto_tsquery('english', %s)
            ORDER BY ts_rank_cd(search, plainto_tsquery('english', %s)) DESC LIMIT 20
        )
        SELECT e.id,e.document_id,e.page,e.content,e.filename,e.policy_key,
               e.version_label,e.effective_date,e.is_current,
               COALESCE(1.0/(60+dense.rank),0)+COALESCE(1.0/(60+lexical.rank),0) AS score
        FROM eligible e LEFT JOIN dense ON dense.id=e.id LEFT JOIN lexical ON lexical.id=e.id
        WHERE dense.id IS NOT NULL OR lexical.id IS NOT NULL
        ORDER BY score DESC LIMIT %s""",
        (owner, owner, include_superseded, vector, vector, query, query, query, limit)).fetchall()
