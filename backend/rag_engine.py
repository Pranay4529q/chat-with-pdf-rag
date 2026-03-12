from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.agents import initialize_agent, AgentType
from tools import get_tools
import os
from dotenv import load_dotenv

load_dotenv()


class RAGEngine:
    """
    Core RAG (Retrieval Augmented Generation) Engine
    
    This class handles:
    1. Loading PDFs
    2. Splitting text into chunks
    3. Creating embeddings
    4. Storing in FAISS vector database
    5. Retrieving relevant chunks
    6. Generating answers with LLM
    """
    
    def __init__(self):
        """Initialize the RAG engine components"""
        
        # ===== EMBEDDINGS MODEL =====
        # Free embeddings from HuggingFace (runs locally)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # ===== LLM (Language Model) =====
        # Groq LLM (free & fast!)
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0,
            api_key=os.getenv("GROQ_API_KEY")  # Read from .env file
        )
        
        # ===== TEXT SPLITTER =====
        # PDFs are too long for LLMs, so we split into chunks
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,        # Each chunk ~1000 characters
            chunk_overlap=200,      # Overlap to maintain context
            separators=["\n\n", "\n", ". ", " ", ""]  # Split priorities
        )
        
        # ===== VECTOR DATABASE =====
        # Stores document chunks as vectors for fast similarity search
        self.vectorstore = None  # Will be created when first doc is added
        
        # ===== QA CHAIN =====
        # Combines retrieval + question answering
        self.qa_chain = None
        
        # ===== AGENT WITH TOOLS =====
        # Can use tools like calculator, web search, etc.
        self.agent = None
    
    
    def add_document(self, pdf_path: str):
        """
        Add a PDF document to the vector database
        
        Steps:
        1. Load PDF and extract text
        2. Split text into manageable chunks
        3. Create embeddings for each chunk
        4. Store in FAISS vector database
        """
        
        # STEP 1: Load PDF
        # PyPDFLoader reads PDF and extracts text from each page
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()  # Returns list of Document objects
        
        print(f"📄 Loaded {len(documents)} pages from PDF")
        
        # STEP 2: Split into chunks
        # Why? LLMs have token limits, and smaller chunks = better retrieval
        chunks = self.text_splitter.split_documents(documents)
        
        print(f"✂️  Split into {len(chunks)} chunks")
        
        # STEP 3 & 4: Create embeddings and store in FAISS
        if self.vectorstore is None:
            # First document - create new vectorstore
            self.vectorstore = FAISS.from_documents(chunks, self.embeddings)
            print("🆕 Created new FAISS vectorstore")
        else:
            # Add to existing vectorstore
            self.vectorstore.add_documents(chunks)
            print("➕ Added to existing vectorstore")
        
        # STEP 5: Create QA chain
        # This connects the vectorstore (retriever) with the LLM (generator)
        self._create_qa_chain()
    
    
    def _create_qa_chain(self):
        """
        Create a RetrievalQA chain
        
        How it works:
        1. Question comes in
        2. Retriever finds top K most similar chunks
        3. LLM receives question + chunks as context
        4. LLM generates answer based on context
        """
        
        # Create retriever from vectorstore
        retriever = self.vectorstore.as_retriever(
            search_type="similarity",  # Find most similar chunks
            search_kwargs={"k": 3}     # Return top 3 chunks
        )
        
        # Create QA chain
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",  # "stuff" = put all docs into prompt
            retriever=retriever,
            return_source_documents=True  # Include sources in response
        )
        
        # Create agent with tools
        tools = get_tools()
        self.agent = initialize_agent(
            tools=tools,
            llm=self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,  # Reasoning agent
            verbose=True,  # Print reasoning steps
            handle_parsing_errors=True
        )
    
    
    def query(self, question: str, use_tools: bool = False):
        """
        Answer a question using RAG
        
        Args:
            question: User's question
            use_tools: If True, use agent with tools. If False, use simple RAG
        
        Returns:
            dict with 'answer' and 'sources'
        """
        
        if use_tools and self.agent:
            # ===== AGENT MODE (WITH TOOLS) =====
            # Agent can decide to:
            # 1. Search documents (RAG)
            # 2. Use calculator
            # 3. Use web search
            # 4. Combine multiple tools
            
            # Add document context to agent
            docs = self.vectorstore.similarity_search(question, k=3)
            context = "\n\n".join([doc.page_content for doc in docs])
            
            enhanced_question = f"""
            Context from documents:
            {context}
            
            Question: {question}
            
            Use the context if relevant, or use tools if needed.
            """
            
            response = self.agent.run(enhanced_question)
            
            return {
                "answer": response,
                "sources": [doc.metadata.get("source", "Unknown") for doc in docs]
            }
        
        else:
            # ===== SIMPLE RAG MODE =====
            # Just retrieve + generate, no tools
            
            result = self.qa_chain.invoke({"query": question})
            
            # Extract sources (which chunks were used)
            sources = []
            for doc in result["source_documents"]:
                source = doc.metadata.get("source", "Unknown")
                page = doc.metadata.get("page", "Unknown")
                sources.append(f"{source} (page {page})")
            
            return {
                "answer": result["result"],
                "sources": sources
            }
    
    
    def has_documents(self):
        """Check if any documents have been added"""
        return self.vectorstore is not None
    
    
    def reset(self):
        """Clear the vector database"""
        self.vectorstore = None
        self.qa_chain = None
        self.agent = None
        print("🔄 RAG engine reset")