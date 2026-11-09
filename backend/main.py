"""Authenticated document API with background PDF ingestion."""
import os
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from auth import register, login, current_user
from storage import initialize, create_document, list_documents, delete_documents
from rag_engine import RAGEngine

@asynccontextmanager
async def lifespan(app):
    initialize()
    yield

app = FastAPI(title="Smart Document Q&A API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
rag = None

def engine():
    global rag
    if rag is None:
        rag = RAGEngine()
    return rag

class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8)

class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[str] = Field(default_factory=list, max_length=10)
    use_tools: bool = False

@app.get("/")
def root():
    return {"message": "Smart Document Q&A API is running"}

@app.post("/auth/register", status_code=201)
def signup(body: Credentials):
    return {"id": register(body.email, body.password)}

@app.post("/auth/login")
def signin(body: Credentials):
    return {"access_token": login(body.email, body.password), "token_type": "bearer"}

@app.post("/upload", status_code=202)
async def upload_pdf(background: BackgroundTasks, file: UploadFile = File(...),
                     owner: str = Depends(current_user)):
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(400, "Only PDF files allowed")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "PDF exceeds 10 MB")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(400, "Invalid PDF header")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
        temp.write(content)
        path = temp.name
    try:
        doc_id = create_document(owner, Path(file.filename).name)
        background.add_task(engine().ingest, doc_id, owner, path)
    except Exception:
        os.remove(path)
        raise
    return {"id": doc_id, "filename": Path(file.filename).name, "status": "pending"}

@app.get("/documents")
def documents(owner: str = Depends(current_user)):
    rows = list_documents(owner)
    return {"documents": [row["filename"] for row in rows], "items": rows, "count": len(rows)}

@app.post("/ask")
def ask(body: QuestionRequest, owner: str = Depends(current_user)):
    if body.use_tools:
        raise HTTPException(400, "Tool execution is disabled for grounded document answers")
    if not any(row["status"] == "ready" for row in list_documents(owner)):
        raise HTTPException(400, "No processed documents available yet")
    return engine().query(owner, body.question, body.history)

@app.delete("/clear")
def clear(owner: str = Depends(current_user)):
    delete_documents(owner)
    return {"message": "Your documents were cleared"}
