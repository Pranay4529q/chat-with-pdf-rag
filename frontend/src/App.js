import React, { useState } from "react";
import axios from "axios";
import "./App.css";

const API_URL = "http://localhost:8000";

function App() {
  // ========== STATE MANAGEMENT ==========
  const [file, setFile] = useState(null); // Selected PDF file
  const [uploading, setUploading] = useState(false); // Upload in progress
  const [question, setQuestion] = useState(""); // User's question
  const [answer, setAnswer] = useState(null); // LLM's answer
  const [loading, setLoading] = useState(false); // Query in progress
  const [useTools, setUseTools] = useState(false); // Enable tools
  const [documents, setDocuments] = useState([]); // Uploaded docs

  // ========== FILE UPLOAD HANDLER ==========
  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) {
      alert("Please select a PDF file");
      return;
    }

    // Create FormData to send file
    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);
    try {
      const response = await axios.post(`${API_URL}/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      alert(response.data.message);
      setFile(null);
      fetchDocuments(); // Refresh document list
    } catch (error) {
      alert("Error uploading file: " + error.response?.data?.detail);
    } finally {
      setUploading(false);
    }
  };

  // ========== QUESTION HANDLER ==========
  const handleAsk = async () => {
    if (!question.trim()) {
      alert("Please enter a question");
      return;
    }

    setLoading(true);
    setAnswer(null);

    try {
      const response = await axios.post(`${API_URL}/ask`, {
        question: question,
        use_tools: useTools,
      });

      setAnswer(response.data);
    } catch (error) {
      alert("Error: " + error.response?.data?.detail);
    } finally {
      setLoading(false);
    }
  };

  // ========== FETCH DOCUMENTS ==========
  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API_URL}/documents`);
      setDocuments(response.data.documents);
    } catch (error) {
      console.error("Error fetching documents:", error);
    }
  };

  // ========== CLEAR ALL ==========
  const handleClear = async () => {
    if (window.confirm("Clear all documents?")) {
      try {
        await axios.delete(`${API_URL}/clear`);
        setDocuments([]);
        setAnswer(null);
        alert("All documents cleared");
      } catch (error) {
        alert("Error clearing documents");
      }
    }
  };

  // Load documents on component mount
  React.useEffect(() => {
    fetchDocuments();
  }, []);

  // ========== RENDER UI ==========
  return (
    <div className="App">
      <header>
        <h1>📚 Smart Document Q&A</h1>
        <p>Upload PDFs and ask questions powered by RAG + LangChain</p>
      </header>

      <div className="container">
        {/* ===== UPLOAD SECTION ===== */}
        <div className="section upload-section">
          <h2>1. Upload PDF</h2>
          <input type="file" accept=".pdf" onChange={handleFileChange} />
          <button onClick={handleUpload} disabled={uploading || !file}>
            {uploading ? "Uploading..." : "Upload"}
          </button>

          {documents.length > 0 && (
            <div className="documents">
              <h3>Uploaded Documents ({documents.length})</h3>
              <ul>
                {documents.map((doc, idx) => (
                  <li key={idx}>📄 {doc}</li>
                ))}
              </ul>
              <button onClick={handleClear} className="clear-btn">
                Clear All
              </button>
            </div>
          )}
        </div>

        {/* ===== QUESTION SECTION ===== */}
        <div className="section question-section">
          <h2>2. Ask Questions</h2>
          <textarea
            placeholder="What is this document about?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
          />

          <div className="options">
            <label>
              <input
                type="checkbox"
                checked={useTools}
                onChange={(e) => setUseTools(e.target.checked)}
              />
              Enable Tools (Calculator, etc.)
            </label>
          </div>

          <button
            onClick={handleAsk}
            disabled={loading || documents.length === 0}
          >
            {loading ? "Thinking..." : "Ask Question"}
          </button>
        </div>

        {/* ===== ANSWER SECTION ===== */}
        {answer && (
          <div className="section answer-section">
            <h2>Answer</h2>
            <div className="answer">
              <p>{answer.answer}</p>
            </div>

            <h3>Sources</h3>
            <ul className="sources">
              {answer.sources.map((source, idx) => (
                <li key={idx}>{source}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
