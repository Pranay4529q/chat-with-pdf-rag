from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
from rag_engine import RAGEngine

# Initialize FastAPI app
app = FastAPI(title="Smart Document Q&A API")

# Enable CORS so React frontend can connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG engine (we'll create this next)
rag = RAGEngine()

# Directory to store uploaded PDFs
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ========== REQUEST/RESPONSE MODELS ==========
class QuestionRequest(BaseModel):
    """Model for question requests from frontend"""
    question: str
    use_tools: bool = False  # Whether to enable tool calling


class AnswerResponse(BaseModel):
    """Model for answer responses to frontend"""
    answer: str
    sources: list[str]  # Which PDF chunks were used


# ========== API ENDPOINTS ==========

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Smart Document Q&A API is running!"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF file and process it for RAG
    
    How it works:
    1. Save the uploaded PDF to disk
    2. Extract text and split into chunks
    3. Create embeddings and store in FAISS vector DB
    4. Return success message
    """
    
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    
    # Save file to uploads directory
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # Process the PDF and add to vector database
        rag.add_document(file_path)
        return {
            "message": f"Successfully uploaded and processed {file.filename}",
            "filename": file.filename
        }
    except Exception as e:
        # Clean up file if processing fails
        os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@app.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """
    Answer a question using RAG
    
    How it works:
    1. Convert question to embedding
    2. Search FAISS for similar document chunks
    3. Pass chunks + question to LLM
    4. LLM generates answer based on context
    5. Optionally use tools if enabled
    """
    
    if not rag.has_documents():
        raise HTTPException(
            status_code=400, 
            detail="No documents uploaded yet. Please upload a PDF first."
        )
    
    try:
        # Get answer from RAG engine
        result = rag.query(request.question, use_tools=request.use_tools)
        return AnswerResponse(
            answer=result["answer"],
            sources=result["sources"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error answering question: {str(e)}")


@app.get("/documents")
async def list_documents():
    """List all uploaded documents"""
    files = os.listdir(UPLOAD_DIR)
    pdf_files = [f for f in files if f.endswith('.pdf')]
    return {"documents": pdf_files, "count": len(pdf_files)}


@app.delete("/clear")
async def clear_all():
    """Clear all documents and reset vector database"""
    # Delete all files in upload directory
    for file in os.listdir(UPLOAD_DIR):
        os.remove(os.path.join(UPLOAD_DIR, file))
    
    # Reset RAG engine
    rag.reset()
    
    return {"message": "All documents cleared successfully"}


# Run with: uvicorn main:app --reload