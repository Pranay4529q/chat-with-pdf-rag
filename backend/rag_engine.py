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
    
    def __init__(self):
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0,
            api_key=os.getenv("GROQ_API_KEY") 
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,   
            chunk_overlap=200, 
            separators=["\n\n", "\n", ". ", " ", ""] 
        )
        
        self.vectorstore = None  # for now it is none but when we add documents it will be initialized with FAISS vectorstore
        
        #QA CHAIN
        # retrieval + llm
        self.qa_chain = None
        
        # AGENT FOR TOOLS
        # Can use tools like calculator, web search, etc. for now there is only calc tool.
        self.agent = None
    
    
    def add_document(self, pdf_path: str):
        """
      expected  workflow: load PDF -> split into chunks -> create embeddings + store in FAISS 
      -> create QA chain with retriever and LLM
        """
        
        loader = PyPDFLoader(pdf_path)
        documents = loader.load() 
        
        print(f"Loaded {len(documents)} pages from PDF")
        
        chunks = self.text_splitter.split_documents(documents)
        
        print(f" Split into {len(chunks)} chunks")
        
        if self.vectorstore is None:
            self.vectorstore = FAISS.from_documents(chunks, self.embeddings)
            print("🆕 Created new FAISS vectorstore")
        else:
            self.vectorstore.add_documents(chunks)
            print("➕ Added to existing vectorstore")
        
        self._create_qa_chain()
    
    
    def _create_qa_chain(self):
        """
        Creating a RetrievalQA chain
        
    expected workflow:-question comes in -> Retriever finds top K most similar chunks -> 
    LLM receives question + chunks as context
        """
        retriever = self.vectorstore.as_retriever(
            search_type="similarity", 
            search_kwargs={"k": 3}     # Returning only top 3 chunks
        )
        
        # Creating QA chain
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",  # "stuff" = put all docs into prompt simple copy pasting the chunks into the prompt
            retriever=retriever,
            return_source_documents=True  # Including the sources in response
        )
        
        # Creating agent with tools
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
        Answering a question using RAG
       sample template:-
        Args:
            question: User's question
            use_tools: If True, use agent with tools. If False, use simple RAG
        Returns:
            dict with 'answer' and 'sources'
        """
        
        if use_tools and self.agent:
            #we will use the agent which can use tools and also retirve relevant chuks
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
         #simple RAG 
            
            result = self.qa_chain.invoke({"query": question})
            
            # Extracting sources (the chunks which were used)
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