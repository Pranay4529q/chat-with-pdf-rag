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
        conn.execute("CREATE INDEX IF NOT EXISTS chunks_owner_idx ON chunks(owner_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS chunks_search_idx ON chunks USING GIN(search)")

def create_document(owner, filename):
    doc_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute("INSERT INTO documents(id,owner_id,filename) VALUES(%s,%s,%s)", (doc_id, owner, filename))
    return doc_id

def set_status(doc_id, owner, status, error=None):
    with connect() as conn:
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
        return conn.execute("""SELECT id,filename,status,error,created_at FROM documents
            WHERE owner_id=%s ORDER BY created_at DESC""", (owner,)).fetchall()

def delete_documents(owner):
    with connect() as conn:
        conn.execute("DELETE FROM chunks WHERE owner_id=%s", (owner,))
        conn.execute("DELETE FROM documents WHERE owner_id=%s", (owner,))

def search(owner, query, embedding, limit=20):
    vector = "[" + ",".join(map(str, embedding)) + "]"
    with connect() as conn:
        rows = conn.execute("""WITH dense AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank
            FROM chunks WHERE owner_id=%s LIMIT 20
        ), lexical AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(search, plainto_tsquery('english', %s)) DESC) AS rank
            FROM chunks WHERE owner_id=%s AND search @@ plainto_tsquery('english', %s)
            ORDER BY ts_rank_cd(search, plainto_tsquery('english', %s)) DESC LIMIT 20
        )
        SELECT c.id,c.document_id,c.page,c.content,d.filename,
            COALESCE(1.0/(60+dense.rank),0)+COALESCE(1.0/(60+lexical.rank),0) AS score
        FROM chunks c
        JOIN documents d ON d.id=c.document_id AND d.owner_id=%s AND d.status='ready'
        LEFT JOIN dense ON dense.id=c.id LEFT JOIN lexical ON lexical.id=c.id
        WHERE c.owner_id=%s AND (dense.id IS NOT NULL OR lexical.id IS NOT NULL)
        ORDER BY score DESC LIMIT %s""",
            (vector, owner, query, owner, query, query, owner, owner, limit)).fetchall()
    return rows
