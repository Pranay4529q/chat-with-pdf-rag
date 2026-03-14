from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
from rag_engine import RAGEngine


app = FastAPI(title="Smart Document Q&A API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag = RAGEngine()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class QuestionRequest(BaseModel):
    """Model for question requests from frontend"""

    question: str
    use_tools: bool = False


class AnswerResponse(BaseModel):
    """Model for answer responses to frontend"""
    answer: str
    sources: list[str]



@app.get("/")
async def root():
    return {"message": "Smart Document Q&A API is running!"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    working :- validate file type -> save to uploads -> process with RAG -> adding to vector db
    """
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        rag.add_document(file_path)
        return {
            "message": f"Successfully uploaded and processed {file.filename}",
            "filename": file.filename
        }
    except Exception as e:
        # Cleaning up file if processing fails
        os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@app.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """
    Workflow: convert question to embedding -> search FAISS for similar chunks -> pass chunks + question to LLM 
    -> LLM generates answer based on context -> optionally use tools if enabled
    
    """
    
    if not rag.has_documents():
        raise HTTPException(
            status_code=400, 
            detail="No documents uploaded yet. Please upload a PDF first."
        )
    
    try:
        result = rag.query(request.question, use_tools=request.use_tools)
        return AnswerResponse(
            answer=result["answer"],
            sources=result["sources"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error answering question: {str(e)}")


@app.get("/documents")
async def list_documents():
    """we will read the uploads folder and return the list of all files to frontend"""
    files = os.listdir(UPLOAD_DIR)
    pdf_files = [f for f in files if f.endswith('.pdf')]
    return {"documents": pdf_files, "count": len(pdf_files)}


@app.delete("/clear")
async def clear_all():
    """Clear all documents and reset vector database"""
    for file in os.listdir(UPLOAD_DIR):
        os.remove(os.path.join(UPLOAD_DIR, file))
    
    # Resetting RAG engine
    rag.reset()
    
    return {"message": "All documents cleared successfully"}
